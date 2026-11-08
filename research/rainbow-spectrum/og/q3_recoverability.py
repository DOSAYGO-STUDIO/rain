#!/usr/bin/env python3
"""Q3: what can the public recover, and does it matter?

Q2 already answers the "does it matter" half, and the answer reshapes the
question. The generic attack that collided every sufficiency member knew ONLY
the pairing and the injection coefficients. Every mixer, multiplier, rotation,
IV, seed and finalization was used as a black box. So recovering those is beside
the point: anyone who can evaluate the public function gets them for free by
calling it. Only the injection geometry has to be extracted.

Whether it can be depends on what the public holds, so both models are measured:

  program access   the public function is something anyone can RUN, as a public
                   key must be. Running it exposes intermediate states. Two
                   evaluations differing in one message word read the injection
                   straight off the post-injection state: which lanes move is the
                   pairing, how far they move is the coefficients.

  digest access    only (message -> digest). Not a public key -- verification
                   needs the function -- but it is the one model in which the
                   geometry might not leak, so it is worth knowing.
"""

import json
import pathlib
import random
import sys
import time

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1]))

from q2_weak_family import build_members                         # noqa: E402
from models import wordops as W                                  # noqa: E402

RESULTS = HERE.parents[1] / "results"


def post_injection_state(member, blocks, seed):
    """What running the public program exposes: the state after the last injection."""
    h = member.iv(seed, len(blocks))
    for index, words in enumerate(blocks):
        h = member.inject(h, words)
        if index < len(blocks) - 1:
            h = member.merge_mixer(h) if index % 2 == 0 else member.other_mixer(h, seed)
    return h


def recover_geometry_program(member, seed, rng):
    """Two evaluations per pair word. Returns (pairing, coefficients, evaluations)."""
    w = member.w
    base_x = rng.getrandbits(w)
    evaluations = 0
    pairing, coeffs = [], []
    for slot in range(2):
        words0 = [0, 0]; words1 = [0, 0]; words1[slot] = 1
        s0 = post_injection_state(member, [(base_x, 0), tuple(words0)], seed)
        s1 = post_injection_state(member, [(base_x, 0), tuple(words1)], seed)
        evaluations += 2
        diff = [W.sub(s1[l], s0[l], w) for l in range(4)]
        lanes = tuple(l for l in range(4) if diff[l])
        pairing.append(lanes)
        coeffs.append(tuple(diff[l] for l in lanes))
    return pairing, coeffs, evaluations


def to_signed(c, w):
    return c - (1 << w) if c >= (1 << (w - 1)) else c


def digest_probe(member, seed, rng, trials=400):
    """Digest-only: does varying pair-0's word vs pair-1's word look different?"""
    w = member.w
    def bits(d):
        # A finalization may return a tuple of words or one packed integer;
        # normalise to 4w bits either way so every member is probed alike.
        if isinstance(d, int):
            return [(d >> b) & 1 for b in range(4 * w)]
        return [(v >> b) & 1 for v in d for b in range(w)]
    flips = {0: [0] * (4 * w), 1: [0] * (4 * w)}
    for _ in range(trials):
        x, p = rng.getrandbits(w), rng.getrandbits(w)
        for slot in (0, 1):
            a = [0, 0]; b = [0, 0]; a[slot] = p; b[slot] = W.add(p, 1, w)
            d0 = bits(member.hash([(x, 0), tuple(a)], seed))
            d1 = bits(member.hash([(x, 0), tuple(b)], seed))
            for i, (u, v) in enumerate(zip(d0, d1)):
                flips[slot][i] += u != v
    rate = {s: [f / trials for f in flips[s]] for s in (0, 1)}
    max_gap = max(abs(a - b) for a, b in zip(rate[0], rate[1]))
    mean = {s: sum(rate[s]) / len(rate[s]) for s in (0, 1)}
    return mean, max_gap


def main():
    rows = []
    for w in (8, 12, 16):
        rng = random.Random(3300 + w)
        members = [m for m in build_members(w, rng) if m.expect]
        for member in members:
            seed = rng.getrandbits(w)
            pairing, coeffs, ev = recover_geometry_program(member, seed, random.Random(w))
            truth_pairs = [tuple(p) for p in member.pairs]
            truth_coeffs = [tuple(c % (1 << w) for c in cc) for cc in member.coeffs]
            ok = pairing == truth_pairs and coeffs == truth_coeffs
            mean, gap = digest_probe(member, seed, random.Random(w + 1))
            rows.append({"w": w, "member": member.name,
                         "program_access": {"recovered": ok, "evaluations": ev,
                                            "pairing": pairing,
                                            "coefficients": [[to_signed(c, w) for c in cc]
                                                             for cc in coeffs]},
                         "digest_access": {"mean_bit_flip_pair0": round(mean[0], 3),
                                           "mean_bit_flip_pair1": round(mean[1], 3),
                                           "max_per_bit_gap": round(gap, 3)}})
            print(f"w={w:>2} {member.name:<34} program: geometry recovered={ok} "
                  f"in {ev} evals  |  digest: flip rates {mean[0]:.3f} vs {mean[1]:.3f}, "
                  f"max per-bit gap {gap:.3f}", flush=True)

    report = {"question": "Q3: public recoverability of each parameter class",
              "what_the_attack_needs": "pairing and injection coefficients only; every "
                                       "mixer, constant, rotation, IV, seed and finalization "
                                       "is consumed as a black box (Q2)",
              "rows": rows, "generated": time.strftime("%Y-%m-%dT%H:%M:%S")}
    (RESULTS / "og-q3-recoverability.json").write_text(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
