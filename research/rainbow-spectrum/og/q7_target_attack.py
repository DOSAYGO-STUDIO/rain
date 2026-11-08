#!/usr/bin/env python3
"""Q7: attack the tag directly. Does the 2^(2wt) blind penalty survive a real solver?

Q6 measured the blind side by REJECTION SAMPLING -- find collisions, wait for the
tag to come up right. That is the weakest adversary imaginable, and the right
question is the one that tries to destroy the assumption:

    given target y, solve directly for a collision with tau(c) = y, without
    using the known aiming parameterization.

PRE-REGISTERED PREDICTION (written before running): the penalty collapses. Work
backwards from the target -- fix the merged state's tagged lanes to y, leave the
other two free, and for any bridge word p the pre-merge state is determined. The
only genuine condition is that mixA^-1 of it lands in the IV's coset: 2w bits of
condition against 4w bits of freedom, so solutions are abundant. And the tag
constrains p ADDITIVELY, which is what a solver propagates rather than searches.
If that is right, SAT cost should be roughly FLAT in t, not 2^(2wt).

The solver is given the same public structure everyone has -- the relation as
bit-vector constraints -- but never the recipe p = A_a - y_0, q = y_2 - C.
Both routes are compared on scaling in t, which is the claim at issue.
"""

import json
import pathlib
import random
import statistics
import sys
import time

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1]))

import z3                                                        # noqa: E402
import stripe as ST                                              # noqa: E402
from models import rainbow as R                                  # noqa: E402
from models import solverstats as STT                            # noqa: E402
from models import wordops as W                                  # noqa: E402

RESULTS = HERE.parents[1] / "results"


def zmix_a(state, theta, w):
    m, r = theta.multipliers, theta.mixa_rotations
    h0, h1, h2, h3 = state
    a = z3.RotateRight(h0 * z3.BitVecVal(m[0], w), r[0]) * z3.BitVecVal(m[1], w)
    b = z3.RotateRight((h1 ^ a) * z3.BitVecVal(m[2], w), r[1]) * z3.BitVecVal(m[3], w)
    c = z3.RotateRight(h2 * z3.BitVecVal(m[4], w), r[2]) * z3.BitVecVal(m[5], w)
    d = z3.RotateRight((h3 ^ c) * z3.BitVecVal(m[6], w), r[3]) * z3.BitVecVal(m[7], w)
    return (a, b, c, d)


def zmix_b(state, theta, w, seed):
    m, r = theta.multipliers, theta.mixb_rotations
    h0, h1, h2, h3 = state
    a = z3.RotateRight(h1 * z3.BitVecVal(m[6], w), r[0]) * z3.BitVecVal(m[7], w)
    b = (h2 ^ (a + z3.BitVecVal(seed, w)))
    b = z3.RotateRight(b * z3.BitVecVal(m[2], w), r[1]) * z3.BitVecVal(m[3], w)
    return (h0, b, a, h3)


def zinject(state, x, y):
    return (state[0] - x, state[1] + x, state[2] + y, state[3] - y)


def build(seed, w, targets, theta, tagged):
    """Merged-state equality per gadget, plus the tag when `tagged` is set."""
    solver = z3.Solver()
    n = 2 * len(targets)
    iv = tuple(z3.BitVecVal(v, w) for v in ST.iv(seed, n, w))
    sa = sb = iv
    words_a, words_b = [], []
    for g, (t0, t2) in enumerate(targets):
        xa, ya = z3.BitVec(f"xa{g}", w), z3.BitVec(f"ya{g}", w)
        xb, yb = z3.BitVec(f"xb{g}", w), z3.BitVec(f"yb{g}", w)
        pa, qa = z3.BitVec(f"pa{g}", w), z3.BitVec(f"qa{g}", w)
        pb, qb = z3.BitVec(f"pb{g}", w), z3.BitVec(f"qb{g}", w)
        words_a += [xa, ya, pa, qa]
        words_b += [xb, yb, pb, qb]
        ma = zinject(zmix_a(zinject(sa, xa, ya), theta, w), pa, qa)
        mb = zinject(zmix_a(zinject(sb, xb, yb), theta, w), pb, qb)
        solver.add(z3.And([ma[i] == mb[i] for i in range(4)]))
        if tagged:
            solver.add(ma[0] == z3.BitVecVal(t0, w))
            solver.add(ma[2] == z3.BitVecVal(t2, w))
        sa = zmix_b(ma, theta, w, seed)
        sa = (sa[3], sa[0], sa[1], sa[2])              # rotate_right
        sb = sa
    solver.add(z3.Or([a != b for a, b in zip(words_a, words_b)]))
    return solver


def main():
    rows = []
    for w in (8, 10, 12):
        theta = R.default_theta(w)
        for t in (1, 2, 3):
            for tagged in (False, True):
                confs, secs, sats = [], [], 0
                for trial in range(5):
                    rng = random.Random(700 + 13 * trial + w)
                    seed = rng.getrandbits(w)
                    targets = [(rng.getrandbits(w), rng.getrandbits(w)) for _ in range(t)]
                    solver = build(seed, w, targets, theta, tagged)
                    solver.set("timeout", 120000)
                    start = time.time()
                    verdict = solver.check()
                    secs.append(time.time() - start)
                    # collect() first: get() takes the dict, not z3's object
                    c = STT.get(STT.collect(solver.statistics()), "conflict")
                    if verdict == z3.sat:
                        sats += 1
                        confs.append(c if c is not None else 0)
                rows.append({"w": w, "pins": t, "tagged": tagged,
                             "sat": f"{sats}/5",
                             "median_conflicts": statistics.median(confs) if confs else None,
                             "median_seconds": round(statistics.median(secs), 2)})
                print(f"w={w:>2} pins={t} {'tagged  ' if tagged else 'untagged'}  "
                      f"sat {sats}/5  median conflicts "
                      f"{statistics.median(confs) if confs else None}  "
                      f"median {statistics.median(secs):.2f}s", flush=True)

    report = {"question": "Q7: can a solver hit the tag without the aiming recipe?",
              "prediction": "penalty collapses; tag constrains p additively so SAT "
                            "propagates it; cost roughly flat in t",
              "rows": rows, "generated": time.strftime("%Y-%m-%dT%H:%M:%S")}
    (RESULTS / "og-q7-target-attack.json").write_text(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
