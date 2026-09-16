#!/usr/bin/env python3
"""Q6: Rainbow collisions are programmable. The collision IS the witness.

A different question from everything before it. Q3 and Q4 assumed the secret had
to make FINDING collisions hard, and both ran into the same wall. Here finding
stays cheap and public; what the structure buys is the ability to AIM a collision
at a prescribed, publicly recomputable target -- a lock whose pins must line up,
not a lock that is hard to pick at all.

DEGREES OF FREEDOM, counted before measuring. After enforcing H(x_a) = H(x_b),
the published construction still has free: the block-1 pair-1 word y, the bridge
word p (message b's is then forced to p + (A_b - A_a)), and the block-2 pair-1
word q. What those buy, exactly:

    merged lane 0 = A_a - p      set p = A_a - target   -> FREE, w bits
    merged lane 1 = H - lane 0                          -> determined by the collision
    merged lane 2 = C + q        set q = target - C     -> FREE, w bits
    merged lane 3 = K - lane 2                          -> determined

So 2w bits of the merged state are exactly prescribable at zero extra search, and
the other 2w are pinned by the collision's pair sums. The merged state is
publicly recomputable: anyone holding both messages runs the function and reads
it. Measured below: every trial hits both prescribed lanes exactly.

CHAINING. After a merge the two messages share a state, so the next pair of
blocks is another gadget from that state. Each gadget aims another 2w bits and
costs another birthday, giving

    aimed bits   = 2*w*t          linear in the number of pins
    private cost = t * 2^(w/2)    linear
    blind cost   = 2^(2*w*t)      exponential -- a solver that finds collisions
                                  without aiming gets a uniform tag

which is the derivative shape the whole program has been looking for, with t as
the security knob instead of w.

THE OBSTRUCTION, stated plainly because it is not solved. A tag must be publicly
verifiable, so it must be computable from public data. Aiming needs A_a and C --
the state after block 1 -- and verifying needs the merged state. Both are the
same internal quantities. So anyone who can run the construction can aim it too:
this is a structure-aware versus structure-blind gap, not yet a trapdoor. Making
it one still requires hiding the coordinate chart, which is exactly what Q3
showed leaks in four evaluations under program access.

What IS new: the free-to-aim set is exactly the coset coordinates. The pair sums
H and K, and the digest itself, are NOT freely aimable -- aiming H means finding
a collision at a prescribed value, and aiming the digest means inverting the
finalization. So the structure does not make everything programmable, only a
precisely delimited 2w bits per gadget.
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

import stripe as ST                                              # noqa: E402
from models import rainbow as R                                  # noqa: E402
from models import wordops as W                                  # noqa: E402

RESULTS = HERE.parents[1] / "results"
W_BITS = 16


def find_H_collision(S, theta, w, rng, cap=1 << 22):
    seen = {}
    for _ in range(cap):
        x = rng.getrandbits(w)
        h = ST.half_sum(x, S[0], S[1], theta)[2]
        if h in seen and seen[h] != x:
            return seen[h], x, len(seen)
        seen.setdefault(h, x)
    return None


def aimed_collision(seed, targets, w, theta, rng, aim=True):
    """One gadget per target. aim=False uses random p, q -- the blind baseline."""
    S = ST.iv(seed, 2 * len(targets), w)
    A, B, cost, merged = [], [], 0, []
    for (t0, t2) in targets:
        xa, xb, c = find_H_collision(S, theta, w, rng)
        cost += c
        sa = R.mix_a(ST._inject(S, xa, 0, w), theta)
        sb = R.mix_a(ST._inject(S, xb, 0, w), theta)
        if aim:
            p, q = W.sub(sa[0], t0, w), W.sub(t2, sa[2], w)
        else:
            p, q = rng.getrandbits(w), rng.getrandbits(w)
        pb = W.add(p, W.sub(sb[0], sa[0], w), w)
        A += [(xa, 0), (p, q)]
        B += [(xb, 0), (pb, q)]
        M = ST._inject(sa, p, q, w)
        merged.append((M[0], M[2]))
        S = R.permute(R.mix_b(M, theta, seed), theta)
    return A, B, cost, merged


def main():
    w = W_BITS
    theta = R.default_theta(w)
    rows = []
    for gadgets in (1, 2, 3):
        hits = collisions = 0
        costs, blind_hits = [], 0
        trials = 12
        for t in range(trials):
            seed = random.Random(t).getrandbits(w)
            rng = random.Random(5000 + t)
            targets = [(rng.getrandbits(w), rng.getrandbits(w)) for _ in range(gadgets)]
            A, B, cost, merged = aimed_collision(seed, targets, w, theta, rng)
            collisions += (A != B) and ST.rainbow(A, seed, w) == ST.rainbow(B, seed, w)
            hits += merged == targets
            costs.append(cost)
            # blind: same construction, random coset coordinates, same targets
            _, _, _, blind = aimed_collision(seed, targets, w, theta,
                                             random.Random(9000 + t), aim=False)
            blind_hits += blind == targets
        rows.append({"gadgets": gadgets, "aimed_bits": 2 * w * gadgets,
                     "verified_collisions": f"{collisions}/{trials}",
                     "tag_hit_exactly": f"{hits}/{trials}",
                     "blind_tag_hit": f"{blind_hits}/{trials}",
                     "median_search": statistics.median(costs),
                     "one_birthday": 2 ** (w // 2)})
        print(f"gadgets={gadgets}  aimed bits={2*w*gadgets:>3}  "
              f"collisions {collisions}/{trials}  tag hit {hits}/{trials}  "
              f"blind hit {blind_hits}/{trials}  median search "
              f"{statistics.median(costs):.0f}")

    report = {
        "question": "Q6: how programmable are Rainbow collisions?",
        "free_to_aim": "exactly 2w bits per gadget -- merged lanes 0 and 2, via the "
                       "bridge word p and the pair-1 word q",
        "determined": "merged lanes 1 and 3, pinned by the collision's pair sums H and K",
        "not_freely_aimable": ["H and K themselves (a collision at a prescribed value)",
                               "the digest (inverting the finalization)"],
        "scaling": {"aimed_bits": "2*w*t", "private_cost": "t * 2^(w/2)",
                    "blind_cost": "2^(2*w*t)"},
        "derivative_shape": "d log C_pub / dt = 2w  vs  d log C_priv / dt ~ 0",
        "obstruction": "a tag must be publicly verifiable, so it is computable from "
                       "public data; aiming and verifying need the same internal "
                       "quantities, so anyone who can run the construction can aim it. "
                       "This is structure-aware vs structure-blind, not yet a trapdoor.",
        "w": w, "rows": rows, "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (RESULTS / "og-q6-programmable-collisions.json").write_text(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
