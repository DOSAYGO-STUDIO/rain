#!/usr/bin/env python3
"""Q1: the exact condition for the cross-seed bridge, and why the collision differs.

Seeds shift every IV lane by the same amount, so s0' = s0 + delta and
s1' = s1 + delta. The published collision needs two things per stripe, and they
behave completely differently under that shift.

THE BRIDGE (exact, verified). The merge offset is A(x_b) - A(x_a) with
A(x) = Q * rotr(u_x, r) and u_x = (s0 - x) * P. A seed change adds D = delta * P
to every u. Splitting u into the r bits the rotation moves and the rest,

    rotr(u + D) - rotr(u)  ==  rotr(D) + c(u) - e(u) * 2^(w-r)     (mod 2^w)

where c(u) is the carry out of the low r bits and e(u) the carry out of the top.
Q is odd, so the offsets agree across the two seeds exactly when those extra terms
cancel between the two messages -- and since c and e are single bits and
2^(w-r) is never +/-1 for 0 < r < w, that is exactly when

    c(u_a) == c(u_b)   and   e(u_a) == e(u_b).

Two bits. For a uniformly random seed difference each carry matches with
probability E[p^2 + (1-p)^2] = 2/3, giving (2/3)^2 = 4/9. The same algebra with
the difference d = u_b - u_a in place of D says the seed-free formula
Q * rotr((x_a - x_b) * P) is exact when both of ITS carries vanish: (1/2)^2 = 1/4.
Measured earlier: 0.444 and 0.251. This file checks the condition case by case.

THE COLLISION (derived, not verified case by case). H = A + B with
B = S * rotr(((s1 + x) XOR A(x)) * R). Both XOR inputs move additively -- s1 + x
by delta, A by alpha(x), which depends on the two carries above -- but XOR's
interaction with two independent additive shifts depends on the carry pattern at
every bit position. The collision condition is therefore about w-dimensional,
matching the measured cross-seed H transfer of 2^-13.2 at w=16 and none observed
in 200,000 pairs at w=32 or 64. Structured differences such as the top seed bit
start low-entropy and help at small width, then decay as alpha spreads:
2^-3.8, 2^-6.4, 2^-13.1 at w = 16, 32, 64.

THE DESIGN LEVER. A parameter that enters only along additive paths couples
stripes through a handful of carry bits. A parameter that meets another shifted
quantity under XOR costs about w bits. That is the criterion for which parameters
of a weak family can be combined across stripes.
"""

import json
import pathlib
import random
import sys
import time

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1]))

import stripe as ST                                              # noqa: E402
from models import rainbow as R                                  # noqa: E402
from models import wordops as W                                  # noqa: E402

RESULTS = HERE.parents[1] / "results"


def carries(u, D, r, w):
    low = (1 << r) - 1
    c = ((u & low) + (D & low)) >> r
    e = ((u >> r) + (D >> r) + c) >> (w - r)
    return c & 1, e & 1


def main(samples=200000):
    rows = []
    for w in (16, 32, 64):
        theta = R.default_theta(w)
        P, r = theta.multipliers[0], theta.mixa_rotations[0]
        rng = random.Random(77 + w)
        agree = actual_hits = predicted_hits = 0
        for _ in range(samples):
            s, s2 = rng.getrandbits(w), rng.getrandbits(w)
            xa, xb = rng.getrandbits(w), rng.getrandbits(w)

            def offset(seed):
                iv = ST.iv(seed, 2, w)
                return W.sub(ST.half_sum(xb, iv[0], iv[1], theta)[0],
                             ST.half_sum(xa, iv[0], iv[1], theta)[0], w)

            actual = offset(s) == offset(s2)
            s0 = ST.iv(s, 2, w)[0]
            D = W.mul(W.sub(s2, s, w), P, w)
            predicted = (carries(W.mul(W.sub(s0, xa, w), P, w), D, r, w)
                         == carries(W.mul(W.sub(s0, xb, w), P, w), D, r, w))
            agree += actual == predicted
            actual_hits += actual
            predicted_hits += predicted
        rows.append({"w": w, "rotation": r, "samples": samples,
                     "condition_matches_reality": agree,
                     "transfer_rate": round(actual_hits / samples, 5),
                     "predicted_rate": round(predicted_hits / samples, 5)})
        print(f"w={w:>2} r={r:>2}  condition exact on {agree}/{samples}  "
              f"rate {actual_hits/samples:.4f}  predicted {predicted_hits/samples:.4f}")

    report = {
        "question": "Q1: exact condition for the cross-seed bridge",
        "bridge_condition": "c(u_a)==c(u_b) and e(u_a)==e(u_b): the carry out of the "
                            "rotated low r bits and the carry out of the top, when "
                            "D = (s'-s)*P is added",
        "bridge_probability": "4/9 for a uniformly random seed difference",
        "seed_free_formula_probability": "1/4",
        "collision_condition": "about w-dimensional: B XORs two independently shifted "
                               "additive terms; derived, not verified case by case",
        "design_lever": "parameters on additive-only paths couple stripes through a few "
                        "carry bits; parameters meeting another shift under XOR cost ~w bits",
        "rows": rows,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (RESULTS / "og-q1-bridge-condition.json").write_text(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
