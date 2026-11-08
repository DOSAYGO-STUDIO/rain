#!/usr/bin/env python3
"""Compare composition branches A, B and C on the same footing.

For each operator: does cheap steering survive at all, what does the factored
attacker pay, what does a flat birthday pay, and does the flat structure attack
(GF(2)-linear class labels, held-out validated) find anything.

The naive cross-parameterized variant is included as a negative control: it is
expected to destroy the weakness, which is why the selector must read a quantity
injection cannot change.
"""

import json
import math
import pathlib
import random
import statistics
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from compositions.branches import (CrossParameterized, NaiveCrossParameterized,
                                   ParallelAlgebraic, steering_survives)   # noqa: E402
from compositions.sequential import Composition                            # noqa: E402
from models import rainbow as R                                            # noqa: E402
from models import spectrum as S                                           # noqa: E402
from models import wordops as W                                            # noqa: E402
from flat_adversarial import gf2_rank, gf2_nullspace                       # noqa: E402

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"
PAIRS = S.PAIRINGS[0]
SIGNS = ((-1, 1), (1, -1))


def make_thetas(w, count, rng):
    out = []
    while len(out) < count:
        theta = S.random_theta(w, rng, pairs=PAIRS, signs=SIGNS)
        if S.validate_weakness(theta, rng, trials=40)["admissible"]:
            out.append(theta)
    return tuple(out)


def factored_merge(composition, sa, sb, rng, budget):
    """Birthday on each pair's sigma after round 1, then merge at round 2.

    Identical in shape for every branch, because every branch keeps a global
    injection: only the mixer differs.
    """
    w = composition.w
    inj = composition.injection_theta
    npairs = composition.controls_per_round
    evaluations = 0
    chosen_a, chosen_b = [0] * npairs, [0] * npairs

    for pair_index in range(npairs):
        seen_a, seen_b, hit = {}, {}, None
        while evaluations < budget and hit is None:
            for who, seen_self, seen_other, state in (
                    ("a", seen_a, seen_b, sa), ("b", seen_b, seen_a, sb)):
                c = [0] * npairs
                c[pair_index] = rng.getrandbits(w)
                mid = composition.round(state, tuple(c))
                evaluations += 1
                inv = R.invariants(mid, inj)[pair_index]
                seen_self.setdefault(inv, c[pair_index])
                if inv in seen_other:
                    hit = (c[pair_index], seen_other[inv]) if who == "a" \
                        else (seen_other[inv], c[pair_index])
                    break
            if hit:
                break
        if hit is None:
            return {"merged": False, "evaluations": evaluations}
        chosen_a[pair_index], chosen_b[pair_index] = hit

    mid_a = composition.round(sa, tuple(chosen_a))
    mid_b = composition.round(sb, tuple(chosen_b))
    steered = R.steer(inj, mid_a, mid_b,
                      free=tuple(rng.getrandbits(w) for _ in range(npairs)))
    if steered is None:
        return {"merged": False, "evaluations": evaluations}
    ca = (tuple(chosen_a), steered[0])
    cb = (tuple(chosen_b), steered[1])
    merged = composition.evaluate(sa, ca) == composition.evaluate(sb, cb)
    return {"merged": merged, "evaluations": evaluations,
            "round_equivalents": evaluations / 2.0}


def flat_merge(composition, sa, sb, rng, budget, k):
    def sample():
        return tuple(tuple(rng.getrandbits(composition.w)
                           for _ in range(composition.controls_per_round))
                     for _ in range(k))
    seen_a, seen_b, evaluations = {}, {}, 0
    while evaluations < budget:
        for seen_self, seen_other, state in ((seen_a, seen_b, sa), (seen_b, seen_a, sb)):
            c = sample()
            out = composition.evaluate(state, c)
            evaluations += 1
            seen_self.setdefault(out, c)
            if out in seen_other:
                return {"merged": True, "evaluations": evaluations,
                        "round_equivalents": evaluations * k}
    return {"merged": False, "evaluations": evaluations,
            "round_equivalents": evaluations * k}


def structure_attack(composition, rng, k):
    """Attack A, held-out validated, on whichever operator is supplied."""
    w = composition.w
    bits = 4 * w
    state = tuple(rng.getrandbits(w) for _ in range(4))
    npairs = composition.controls_per_round

    def enumerate_class(prefix):
        points = []
        for c0 in range(1 << w):
            for c1 in range(1 << w):
                controls = [prefix] + [(0,) * npairs] * (k - 1)
                controls[k - 1] = (c0, c1)
                points.append(W.words_to_int(composition.evaluate(state, tuple(controls)), w))
        return points

    # Eight held-out classes: three yields false positives (see flat_adversarial).
    classes = [enumerate_class(tuple(rng.getrandbits(w) for _ in range(npairs)))
               for _ in range(8)]
    train = classes[0]
    diffs = [p ^ train[0] for p in train[1:]]
    rank = gf2_rank(diffs)
    candidates = gf2_nullspace(diffs, bits)
    validated = [lam for lam in candidates
                 if all(len({bin(lam & p).count("1") % 2 for p in cls}) == 1
                        for cls in classes)]
    labels = [[bin(lam & cls[0]).count("1") % 2 for cls in classes] for lam in validated]
    discriminating = sum(1 for lab in labels if len(set(lab)) > 1)
    return {"output_rank": rank, "state_bits": bits,
            "candidates": len(candidates), "validated": len(validated),
            "discriminating": discriminating, "succeeded": discriminating > 0}


class SequentialShim:
    """Gives branch A the same round()/injection_theta surface as B and C.

    Valid because every factor is drawn with the same pairs and signs, so sigma
    is one functional across rounds and the shared harness applies.
    """

    def __init__(self, composition):
        self.composition = composition

    @property
    def w(self):
        return self.composition.w

    @property
    def controls_per_round(self):
        return self.composition.controls_per_round

    @property
    def injection_theta(self):
        return self.composition.thetas[0]

    def round(self, state, controls):
        return R.transition(state, controls, self.composition.thetas[0],
                            inner=False, seed=0)

    def evaluate(self, state, controls):
        return self.composition.evaluate(state, controls)


def evaluate_branch(name, composition, k, w, rng, trials=12):
    survives = steering_survives(composition, rng, trials=120)
    row = {"branch": name, "w": w, "k": k, "steering_survives": survives}
    if not survives["survives"]:
        row["verdict"] = "rejected: cheap steering does not survive this operator"
        return row

    budget = min(8 << (2 * w), 200000)
    fac, flat = [], []
    for _ in range(trials):
        sa = tuple(rng.getrandbits(w) for _ in range(4))
        sb = tuple(rng.getrandbits(w) for _ in range(4))
        f = factored_merge(composition, sa, sb, rng, budget)
        if f["merged"]:
            fac.append(f["round_equivalents"])
        g = flat_merge(composition, sa, sb, rng, budget, k)
        if g["merged"]:
            flat.append(g["round_equivalents"])
    row["factored_success"] = f"{len(fac)}/{trials}"
    row["flat_success"] = f"{len(flat)}/{trials}"
    if fac and flat:
        fm, gm = statistics.median(fac), statistics.median(flat)
        row["log2_factored"] = round(math.log2(fm), 3)
        row["log2_flat"] = round(math.log2(gm), 3)
        row["log2_separation"] = round(math.log2(gm / fm), 3)
    row["structure_attack"] = structure_attack(composition, rng, k)
    return row


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20260915)
    report = {"experiment": "composition_branches", "branches": [],
              "generated": time.strftime("%Y-%m-%dT%H:%M:%S")}

    for w in (4, 5, 6):
        k = 2
        seq = Composition(thetas=make_thetas(w, k, rng))
        par = ParallelAlgebraic(thetas=make_thetas(w, 2, rng), k=k, combine="add")
        parx = ParallelAlgebraic(thetas=make_thetas(w, 2, rng), k=k, combine="xor")
        cross = CrossParameterized(palette=make_thetas(w, 4, rng), k=k)
        naive = NaiveCrossParameterized(palette=make_thetas(w, 4, rng), k=k)

        for name, comp in (("A_sequential", SequentialShim(seq)),
                           ("B_parallel_add", par),
                           ("B_parallel_xor", parx),
                           ("C_crossparam_sigma", cross),
                           ("C_crossparam_naive_control", naive)):
            row = evaluate_branch(name, comp, k, w, rng)
            report["branches"].append(row)
            verdict = row.get("verdict")
            if verdict:
                print(f"w={w} {name:<28} {verdict}")
            else:
                sa = row["structure_attack"]
                print(f"w={w} {name:<28} factored 2^{row.get('log2_factored')}  "
                      f"flat 2^{row.get('log2_flat')}  sep 2^{row.get('log2_separation')}  "
                      f"structure: rank {sa['output_rank']}/{sa['state_bits']} "
                      f"disc {sa['discriminating']}")

    path = RESULTS / "composition-branches.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
