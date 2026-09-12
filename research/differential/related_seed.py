#!/usr/bin/env python3
"""Reproduce the related-seed initialization results in docs/paper/crypto-note.tex.

The state is initialized as h[i] = seed + len + primes[i], so the whole
1024-bit initial state is one 64-bit value replicated with known additive
offsets.  Adding 2^63 to the seed is exactly XOR with 2^63, which turns that
additive initialization into a uniform top-bit XOR difference across all
sixteen words.  Because the first operation applied to each state word in both
round directions is an XOR with a data word, flipping the top bit of every data
word cancels it, and the two states agree exactly after two rounds.

Three checks are reported:

  collapse   the two-round state collapse, for production v4 and for the frozen
             pre-v4 reference
  digest     that the relation does not survive to a digest
  blind      that Delta = 2^63 is the only seed difference whose data
             correction is independent of the seed

Both Python round functions are validated against the corresponding native C++
full hashes before any experiment runs, reusing the existing bridges
(production_native.cpp and native.cpp).  Requires a C++17 compiler on a
little-endian host; no third-party Python packages.
"""

from __future__ import annotations

import argparse
import ctypes as C
import json
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

import rainstorm_model as RM

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MASK = (1 << 64) - 1
TOP = 1 << 63


# --------------------------------------------------------------------------
# round functions
# --------------------------------------------------------------------------

def weakfunc_v4(state, data, left):
    """Production v4 round; delegates to the repository's exact model.

    RM.weakfunc returns a new state list rather than mutating in place, so the
    result is copied back to keep the in-place convention used here.
    """
    state[:] = RM.weakfunc(state, data, left)


def weakfunc_og(state, data, left):
    """Frozen pre-v4 round.

    Identical to v4 except that the right round's final counter subtraction
    wraps inside the high half (h[(k & 7) + 8]) instead of crossing into h[0].
    """
    if left:
        counter = RM.CTR_LEFT
        for i in range(8):
            state[i] ^= data[i]
            state[i] = (state[i] - RM.K[i]) & MASK
            state[i] = RM.rotr(state[i], RM.Z[i])
            state[i + 8] ^= state[i]
            counter = (counter + state[i]) & MASK
            state[i + 1] = (state[i + 1] - counter) & MASK
    else:
        counter = RM.CTR_RIGHT
        for j in range(8):
            i = 8 + j
            state[i] ^= data[j]
            state[i] = (state[i] - RM.K[j]) & MASK
            state[i] = RM.rotr(state[i], RM.Z[j])
            state[j] ^= state[i]
            counter = (counter + state[i]) & MASK
            target = ((j + 1) & 7) + 8
            state[target] = (state[target] - counter) & MASK


VARIANTS = {"v4": weakfunc_v4, "og": weakfunc_og}


def hash_message(message, bits, seed, weakfunc):
    """Full Rainstorm over an explicit round function, for native validation."""
    length = len(message)
    state = [(seed + length + p) & MASK for p in RM.PRIMES]
    offset, remaining = 0, length
    while remaining >= 64:
        block = RM.words(message[offset:offset + 64])
        for r in range(4):
            weakfunc(state, block, bool(r & 1))
        offset += 64
        remaining -= 64
    pad = (0x80 + remaining) & 0xFF
    tail = message[offset:] + bytes([pad]) * (64 - remaining)
    block = RM.words(tail)
    for r in range(4):
        weakfunc(state, block, bool(r & 1))
    for i in range(8):
        state[i] = (state[i] - state[i + 8]) & MASK
    if bits > 64:
        for _ in range(max(bits // 64, 2)):
            weakfunc(state, block, True)
    return b"".join(state[i].to_bytes(8, "little") for i in range(bits // 64))


def two_round_state(seed, data, weakfunc, length=64):
    state = [(seed + length + p) & MASK for p in RM.PRIMES]
    weakfunc(state, data, False)   # right
    weakfunc(state, data, True)    # left
    return state


# --------------------------------------------------------------------------
# native bridges
# --------------------------------------------------------------------------

class Native:
    """Compiles and calls one of the repository's existing C++ bridges."""

    SPECS = {
        "v4": ("production_native.cpp", "rainstorm_hash_many", False),
        "og": ("native.cpp", "hash_many", True),
    }

    def __init__(self, variant, tmpdir):
        source, symbol, takes_algo = self.SPECS[variant]
        library = Path(tmpdir) / f"related-seed-{variant}.so"
        subprocess.run([
            os.environ.get("CXX", "c++"), "-std=c++17", "-O3", "-shared", "-fPIC",
            str(HERE / source), "-o", str(library),
        ], check=True)
        self._lib = C.CDLL(str(library))
        self._fn = getattr(self._lib, symbol)
        self._takes_algo = takes_algo
        if takes_algo:
            self._fn.argtypes = [C.c_int, C.c_uint, C.c_uint64, C.c_void_p,
                                 C.c_size_t, C.c_size_t, C.c_void_p]
        else:
            self._fn.argtypes = [C.c_uint, C.c_uint64, C.c_void_p,
                                 C.c_size_t, C.c_size_t, C.c_void_p]
        self._fn.restype = C.c_int

    def hash(self, message, bits, seed):
        out = C.create_string_buffer(bits // 8)
        args = ([1, bits, seed, message, len(message), 1, out] if self._takes_algo
                else [bits, seed, message, len(message), 1, out])
        if self._fn(*args):
            raise ValueError("native bridge rejected these parameters")
        return out.raw


def validate_against_native(rng, natives, trials=24):
    """Confirm each Python round function reproduces its native full hash."""
    report = {}
    for name, native in natives.items():
        weakfunc = VARIANTS[name]
        mismatches = []
        for _ in range(trials):
            length = rng.choice([0, 1, 8, 63, 64, 65, 127, 128, 192])
            message = bytes(rng.randrange(256) for _ in range(length))
            seed = rng.getrandbits(64)
            for bits in (64, 128, 256, 512):
                if hash_message(message, bits, seed, weakfunc) != native.hash(message, bits, seed):
                    mismatches.append({"length": length, "bits": bits, "seed": seed})
        report[name] = {"trials": trials, "mismatches": mismatches,
                        "agrees": not mismatches}
    return report


# --------------------------------------------------------------------------
# experiments
# --------------------------------------------------------------------------

def check_collapse(rng, trials):
    """Two-round state collapse under (seed, M) vs (seed + 2^63, M XOR 2^63)."""
    results = {}
    for name, weakfunc in VARIANTS.items():
        identical = 0
        for _ in range(trials):
            seed = rng.getrandbits(64)
            data = [rng.getrandbits(64) for _ in range(8)]
            corrected = [word ^ TOP for word in data]
            a = two_round_state(seed, data, weakfunc)
            b = two_round_state((seed + TOP) & MASK, corrected, weakfunc)
            identical += (a == b)
        results[name] = {"trials": trials, "identical": identical,
                         "probability_one": identical == trials}
    return results


def check_digest(rng, trials, bits=256):
    """The relation must not survive to a digest: the pad block is not chosen."""
    results = {}
    for name, weakfunc in VARIANTS.items():
        equal = 0
        for _ in range(trials):
            seed = rng.getrandbits(64)
            message = bytes(rng.randrange(256) for _ in range(64))
            corrected = b"".join(
                (word ^ TOP).to_bytes(8, "little") for word in RM.words(message))
            if (hash_message(message, bits, seed, weakfunc)
                    == hash_message(corrected, bits, (seed + TOP) & MASK, weakfunc)):
                equal += 1
        results[name] = {"trials": trials, "bits": bits, "equal_digests": equal,
                         "relation_reaches_digest": equal > 0}
    return results


def check_blind(rng, trials, deltas):
    """Count distinct required corrections per seed difference.

    The correction for data word j is IV_a[8+j] XOR IV_b[8+j].  It is usable
    without knowing the seed exactly when that value is seed-independent.
    """
    length = 64
    rows = []
    for label, delta in deltas:
        corrections = set()
        for _ in range(trials):
            seed = rng.getrandbits(64)
            corrections.add(tuple(
                ((seed + length + RM.PRIMES[8 + j]) & MASK)
                ^ ((seed + delta + length + RM.PRIMES[8 + j]) & MASK)
                for j in range(8)))
        rows.append({"delta": label, "trials": trials,
                     "distinct_corrections": len(corrections),
                     "seed_independent": len(corrections) == 1})
    return rows


# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--collapse-trials", type=int, default=300)
    parser.add_argument("--digest-trials", type=int, default=200)
    parser.add_argument("--blind-trials", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260912,
                        help="PRNG seed for deterministic replay")
    parser.add_argument("--skip-native", action="store_true",
                        help="skip native validation (no C++ compiler needed)")
    parser.add_argument("--output", help="write the full JSON report here")
    args = parser.parse_args()

    if sys.byteorder != "little":
        raise SystemExit("This script targets little-endian hosts.")

    rng = random.Random(args.seed)
    report = {"prng_seed": args.seed}

    with tempfile.TemporaryDirectory(prefix="rain-related-seed-") as tmpdir:
        if args.skip_native:
            report["native_validation"] = "skipped"
            print("native validation: SKIPPED (--skip-native)\n")
        else:
            natives = {name: Native(name, tmpdir) for name in VARIANTS}
            validation = validate_against_native(rng, natives)
            report["native_validation"] = validation
            for name, entry in validation.items():
                status = "agrees" if entry["agrees"] else "MISMATCH"
                print(f"native validation {name:<3}: {status} "
                      f"({entry['trials']} messages x 4 output sizes)")
            if not all(e["agrees"] for e in validation.values()):
                raise SystemExit("Python model disagrees with native C++; aborting.")
            print()

    report["collapse"] = check_collapse(rng, args.collapse_trials)
    print("two-round state collapse  (seed, M) vs (seed + 2^63, M XOR 2^63/word)")
    for name, entry in report["collapse"].items():
        print(f"  {name:<3} identical 1024-bit state: "
              f"{entry['identical']}/{entry['trials']}")

    report["digest"] = check_digest(rng, args.digest_trials)
    print("\nrelation reaching a digest (expected: never; pad block is not chosen)")
    for name, entry in report["digest"].items():
        print(f"  {name:<3} equal Rainstorm-{entry['bits']} digests: "
              f"{entry['equal_digests']}/{entry['trials']}")

    deltas = [("1", 1), ("2", 2), ("2^32", 1 << 32), ("2^62", 1 << 62), ("2^63", TOP)]
    report["blind"] = check_blind(rng, args.blind_trials, deltas)
    print("\ndistinct data corrections induced per seed difference")
    for row in report["blind"]:
        mark = "  <- seed-independent" if row["seed_independent"] else ""
        print(f"  delta={row['delta']:<5} {row['distinct_corrections']:>3}{mark}")

    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
        print(f"\nwrote {args.output}")


if __name__ == "__main__":
    main()
