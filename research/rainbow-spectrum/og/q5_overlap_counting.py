#!/usr/bin/env python3
"""Q5: partial overlap -- the counting argument, done before the experiment.

Two abstract weak stripes (Q2: invariant-preserving injection, separable merge
mixer; every other component a black box). Stripe i collides iff H_i(X) = H_i(X')
on w bits, a birthday at 2^(w/2). Stripe 1 is driven by X1, stripe 2 by X2, and
the low r bits are SHARED: low_r(X1) == low_r(X2) is a structural constraint on
valid messages. r sweeps 0 .. w.

THE DECISIVE MOVE, available to both solvers: set the shared bits equal in the
two colliding messages, then steer each stripe independently in its free high
bits. That is a within-coset birthday over 2^(w-r) inputs on a w-bit target,
which exists with probability ~(1 - exp(-2^(2(w-r)-1)/2^w)) per stripe --
essentially 1 for r < w/2, ~0.16 at r = w/2, 0 beyond. Validated exhaustively
below at w = 10, 12.

REGION r <= w/2. Both solvers equalize and separate. C_priv = C_pub = 2^(w/2).
The overlap buys nothing because the shared bits are attacker-controllable.

REGION r > w/2. No within-coset collision, so the shared bits must differ
between the two messages and the stripes are coupled through them. The
keyholder's advantage would be knowing the stripe boundary and injection
geometry. Q3 measured that this leaks in 4 evaluations under program access --
the access a public key requires. So the attacker runs the keyholder's own
algorithm: C_pub <= C_priv.

VERDICT. For every r, C_pub <= C_priv, hence d log C_pub / dr <= d log C_priv / dr
everywhere. The advantageous region is EMPTY. Per the rule, the SAT sweep is
not run.

WHAT WOULD CHANGE IT. Either the shared quantity is not a free message input
(derived from a stripe -- Q4's feedforward regime, which reduces to a trapdoor
function in one transform), or the geometry stops leaking under program access
(Q3 says it does not, for the whole family). Message-level overlap by itself
cannot create asymmetry.
"""

import json
import math
import pathlib
import random
import sys
import time

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"


def make_H(w, key):
    rng = random.Random(key)
    table = [rng.getrandbits(w) for _ in range(1 << w)]
    return lambda x: table[x]


def coset_has_collision(H, w, r, shared):
    seen = set()
    low = (1 << r) - 1
    for x in range(1 << w):
        if (x & low) != shared:
            continue
        h = H(x)
        if h in seen:
            return True
        seen.add(h)
    return False


def main():
    rows = []
    for w in (10, 12):
        H1, H2 = make_H(w, 1), make_H(w, 2)
        for r in sorted({0, w // 4, w // 2, 3 * w // 4, w - 1}):
            both = sum(coset_has_collision(H1, w, r, s) and coset_has_collision(H2, w, r, s)
                       for s in range(1 << r))
            measured = both / (1 << r)
            free = w - r
            p_one = 1 - math.exp(-(2 ** (2 * free - 1)) / (2 ** w))
            rows.append({"w": w, "r": r, "free_bits": free,
                         "cosets_with_independent_collision_both": round(measured, 3),
                         "predicted": round(p_one ** 2, 3),
                         "equalize_and_separate_works": measured > 0.5})
            print(f"w={w} r={r:>2} free={free:>2}  measured {measured:.3f}  "
                  f"predicted {p_one**2:.3f}  separate={'yes' if measured > 0.5 else 'no'}")

    report = {
        "question": "Q5: can partial overlap r open a window where public cost grows "
                    "faster than private?",
        "threshold": "r = w/2: equalize-and-separate exists below, not above",
        "region_r_le_half": "both solvers equalize shared bits and separate; "
                            "C_priv = C_pub = 2^(w/2)",
        "region_r_gt_half": "stripes couple through shared bits; the keyholder's only "
                            "edge is the boundary/geometry, which Q3 shows leaks in 4 "
                            "evaluations under program access; C_pub <= C_priv",
        "verdict": "advantageous region EMPTY for all r; SAT sweep not run",
        "would_change_it": ["shared quantity not a free input (Q4 feedforward regime -> "
                            "trapdoor function in one transform)",
                            "injection geometry not leaking under program access "
                            "(Q3: it leaks for the whole family)"],
        "exhaustive_validation": rows,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (RESULTS / "og-q5-overlap-counting.json").write_text(json.dumps(report, indent=2))
    print("\nVERDICT:", report["verdict"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
