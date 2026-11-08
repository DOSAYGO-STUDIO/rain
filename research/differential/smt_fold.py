#!/usr/bin/env python3
"""Exact bit-vector search for reachable Rainstorm fold cancellations.

This is deliberately a bounded experiment, not a security claim.  It searches
two 64-byte message blocks followed by the identical, prescribed padding block.
"""
import argparse
import json
import sys
import time
from pathlib import Path

from suite import CTR, K, MASK, Z, Native, ror

CTR_LEFT = 0xefcdab8967452301
PRIMES = [1, 2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]


def _ror(value, count, symbolic):
    if symbolic:
        import z3
        return z3.RotateRight(value, count)
    return ror(value & MASK, count)


def weakfunc(state, data, left, variant="A", symbolic=False):
    """Run the OG or A round over integers or Z3 64-bit bit-vectors."""
    h = list(state)
    ctr = CTR_LEFT if left else CTR
    if left:
        for i in range(8):
            h[i] = _ror((h[i] ^ data[i]) - K[i], Z[i], symbolic)
            h[8 + i] = h[8 + i] ^ h[i]
            ctr = ctr + h[i]
            h[i + 1] = h[i + 1] - ctr
    else:
        for i in range(8):
            h[8 + i] = _ror((h[8 + i] ^ data[i]) - K[i], Z[i], symbolic)
            h[i] = h[i] ^ h[8 + i]
            ctr = ctr + h[8 + i]
            target = 8 + ((i + 1) & 7)
            if variant == "A" and i == 7:
                target = 0
            h[target] = h[target] - ctr
    return h if symbolic else [x & MASK for x in h]


def words(block):
    return [int.from_bytes(block[i:i + 8], "little") for i in range(0, 64, 8)]


def state_before_and_after_fold(message, variant="A", seed=0):
    """Return the states around the fold for an exact 64-byte message."""
    if len(message) != 64:
        raise ValueError("this bounded experiment requires exactly 64 bytes")
    h = [(seed + 64 + p) & MASK for p in PRIMES]
    pad = bytes([0x80]) * 64
    for block in (message, pad):
        data = words(block)
        for round_index in range(4):
            h = weakfunc(h, data, bool(round_index & 1), variant)
    before = h
    after = list(h)
    for i in range(8):
        after[i] = (after[i] - after[8 + i]) & MASK
    return before, after


def symbolic_fold(message_bytes, variant):
    """Symbolic counterpart of state_before_and_after_fold."""
    import z3
    h = [z3.BitVecVal(64 + p, 64) for p in PRIMES]
    data = []
    for offset in range(0, 64, 8):
        data.append(z3.Concat(*reversed(message_bytes[offset:offset + 8])))
    pad = [z3.BitVecVal(0x8080808080808080, 64)] * 8
    for block in (data, pad):
        for round_index in range(4):
            h = weakfunc(h, block, bool(round_index & 1), variant, True)
    return [h[i] - h[8 + i] for i in range(8)]


def search(args):
    try:
        import z3
    except ImportError as exc:
        raise SystemExit("z3-solver is required: python3 -m pip install z3-solver") from exc
    if not 1 <= args.symbolic_bytes <= 64:
        raise SystemExit("--symbolic-bytes must be in 1..64")
    if not args.words or any(i not in range(8) for i in args.words):
        raise SystemExit("--words must contain indexes in 0..7")

    solver = z3.Solver()
    solver.set(timeout=args.timeout * 1000)
    left = [z3.BitVec(f"a_{i}", 8) if i < args.symbolic_bytes else z3.BitVecVal(0, 8)
            for i in range(64)]
    right = [z3.BitVec(f"b_{i}", 8) if i < args.symbolic_bytes else z3.BitVecVal(0, 8)
             for i in range(64)]
    solver.add(z3.Or(*[left[i] != right[i] for i in range(args.symbolic_bytes)]))
    folded_a = symbolic_fold(left, args.variant)
    folded_b = symbolic_fold(right, args.variant)
    for index in args.words:
        solver.add(folded_a[index] == folded_b[index])

    started = time.monotonic()
    status = solver.check()
    elapsed = time.monotonic() - started
    result = {
        "experiment": "reachable-fold-cancellation",
        "variant": args.variant,
        "solver": f"Z3 {z3.get_version_string()}",
        "status": str(status),
        "elapsed_seconds": elapsed,
        "timeout_seconds": args.timeout,
        "message_length": 64,
        "symbolic_prefix_bytes_per_message": args.symbolic_bytes,
        "fixed_suffix_byte": 0,
        "equal_fold_words": args.words,
        "scope": "Exact 64-bit arithmetic; bounded symbolic prefixes; SAT is a witness, unknown is inconclusive.",
    }
    if status == z3.unknown:
        result["unknown_reason"] = solver.reason_unknown()
    if status == z3.sat:
        model = solver.model()
        concrete = lambda values: bytes(model.eval(v, model_completion=True).as_long() for v in values)
        ma, mb = concrete(left), concrete(right)
        _, fa = state_before_and_after_fold(ma, args.variant)
        _, fb = state_before_and_after_fold(mb, args.variant)
        assert ma != mb and all(fa[i] == fb[i] for i in args.words)
        result["witness"] = {
            "message_a_hex": ma.hex(), "message_b_hex": mb.hex(),
            "fold_a": [f"0x{x:016x}" for x in fa],
            "fold_b": [f"0x{x:016x}" for x in fb],
        }
        # A 64-bit digest is exactly fold word zero.  Verify it through native
        # C++ when word zero is among the constraints.
        if 0 in args.words:
            if args.variant == "OG":
                native = Native()
                ha = native.hashes(1, 64, 0, ma, 64, 1)
                hb = native.hashes(1, 64, 0, mb, 64, 1)
            else:
                import ctypes as C
                import subprocess
                import tempfile
                from scan_variants import Adapter
                here = Path(__file__).resolve().parent
                with tempfile.TemporaryDirectory() as td:
                    lib = Path(td) / "variants.so"
                    subprocess.run(["c++", "-std=c++17", "-O2", "-shared", "-fPIC",
                                    str(here / "variants/bridge.cpp"), "-o", str(lib)], check=True)
                    adapter = Adapter(C.CDLL(str(lib)), "a")
                    ha = adapter.hashes(1, 64, 0, ma, 64, 1)
                    hb = adapter.hashes(1, 64, 0, mb, 64, 1)
            assert ha == hb
            result["native_cpp_64_bit_collision_verified"] = True
            result["digest_hex"] = ha.hex()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("OG", "A"), default="A")
    parser.add_argument("--symbolic-bytes", type=int, default=8)
    parser.add_argument("--words", type=int, nargs="+", default=[0])
    parser.add_argument("--timeout", type=int, default=60, help="solver timeout in seconds")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = search(args)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    sys.stdout.write(rendered)


if __name__ == "__main__":
    main()
