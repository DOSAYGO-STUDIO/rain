#!/usr/bin/env python3
"""Phases 5 and 6: the factored solver against the flat solver.

Task, identical for both solvers: given two states S and T, find control
sequences merging them, F(S; x) == F(T; y).

  FACTORED  knows every theta and may use intermediate states. It exploits two
            facts: injection preserves each pair's invariant, and mixA never
            mixes the two pairs -- so the two 64-bit-style conditions can be
            matched INDEPENDENTLY, one birthday search per pair.

  FLAT      gets only the input/output behaviour of F. Its generic route is a
            birthday on final states, which live in 4w bits.

Cost is reported in ROUND-EQUIVALENTS so the two are comparable: one flat
evaluation of F costs k rounds; one factored pair-map evaluation costs half a
round, since a round is two independent pair maps.

At the smallest sizes the exhaustive optimum is also computed, which is the only
way to know the true optimal public cost rather than the cost of the best
strategy we happened to implement.
"""

import json
import math
import pathlib
import random
import statistics
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from compositions.sequential import Composition, optimal_merge   # noqa: E402
from models import rainbow as R                                  # noqa: E402
from models import spectrum as S                                 # noqa: E402
from models import wordops as W                                  # noqa: E402

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"


def merge_invariants(composition, state, controls):
    """The invariants round 2's injection will steer on, after round 1.

    Crucially these are computed with the MERGE round's theta, not round 1's.
    Matching round 1's own functional is useless: steer() at round 2 tests
    round 2's pairing and signs, which may be different.
    """
    mid = R.transition(state, tuple(controls), composition.thetas[0],
                       inner=composition.inner_flag(0), seed=composition.seed)
    return R.invariants(mid, composition.thetas[1]), mid


def pairs_are_independent(composition, state, rng, probes=16):
    """Does each merge-invariant depend only on its own control word?

    True exactly when consecutive factors agree on the pairing. When false the
    attacker must birthday on both invariants jointly (2^w) instead of on each
    separately (2 * 2^(w/2)).
    """
    npairs = composition.controls_per_round
    w = composition.w
    for _ in range(probes):
        base = [rng.getrandbits(w) for _ in range(npairs)]
        inv, _ = merge_invariants(composition, state, base)
        for q in range(npairs):
            probe = list(base)
            probe[q] = rng.getrandbits(w)
            moved, _ = merge_invariants(composition, state, probe)
            for p in range(npairs):
                if p != q and moved[p] != inv[p]:
                    return False
    return True


def factored_merge(composition, state_a, state_b, rng, budget=None):
    """Two-sided birthday on the merge-round invariants, then a free merge."""
    if composition.k < 2:
        return {"merged": False, "reason": "k=1 offers no prefix freedom",
                "pair_evaluations": 0}

    w = composition.w
    npairs = composition.controls_per_round
    budget = budget or (1 << (w + 6))
    pair_evaluations = 0
    independent = pairs_are_independent(composition, state_a, rng)

    if independent:
        # One two-sided birthday per pair, each over a w-bit invariant.
        chosen_a, chosen_b = [0] * npairs, [0] * npairs
        for pair_index in range(npairs):
            seen_a, seen_b, hit = {}, {}, None
            while pair_evaluations < budget and hit is None:
                x = rng.getrandbits(w)
                controls = [0] * npairs
                controls[pair_index] = x
                inv_a = merge_invariants(composition, state_a, controls)[0][pair_index]
                pair_evaluations += 1
                seen_a.setdefault(inv_a, x)
                if inv_a in seen_b:
                    hit = (x, seen_b[inv_a])
                    break
                y = rng.getrandbits(w)
                controls = [0] * npairs
                controls[pair_index] = y
                inv_b = merge_invariants(composition, state_b, controls)[0][pair_index]
                pair_evaluations += 1
                seen_b.setdefault(inv_b, y)
                if inv_b in seen_a:
                    hit = (seen_a[inv_b], y)
            if hit is None:
                return {"merged": False, "reason": f"no match on pair {pair_index}",
                        "pair_evaluations": pair_evaluations, "independent": True}
            chosen_a[pair_index], chosen_b[pair_index] = hit
    else:
        # Joint birthday over the full invariant tuple: 2w bits.
        seen_a, seen_b, hit = {}, {}, None
        while pair_evaluations < budget and hit is None:
            x = tuple(rng.getrandbits(w) for _ in range(npairs))
            inv_a = merge_invariants(composition, state_a, x)[0]
            pair_evaluations += npairs
            seen_a.setdefault(inv_a, x)
            if inv_a in seen_b:
                hit = (x, seen_b[inv_a])
                break
            y = tuple(rng.getrandbits(w) for _ in range(npairs))
            inv_b = merge_invariants(composition, state_b, y)[0]
            pair_evaluations += npairs
            seen_b.setdefault(inv_b, y)
            if inv_b in seen_a:
                hit = (seen_a[inv_b], y)
        if hit is None:
            return {"merged": False, "reason": "no joint invariant match",
                    "pair_evaluations": pair_evaluations, "independent": False}
        chosen_a, chosen_b = list(hit[0]), list(hit[1])

    controls_a = [tuple(chosen_a)] + [(0,) * npairs] * (composition.k - 1)
    controls_b = [tuple(chosen_b)] + [(0,) * npairs] * (composition.k - 1)

    # After round 1 the invariants agree, so round 2's injection merges exactly.
    _, mid_a = merge_invariants(composition, state_a, controls_a[0])
    _, mid_b = merge_invariants(composition, state_b, controls_b[0])
    steered = R.steer(composition.thetas[1], mid_a, mid_b,
                      free=tuple(rng.getrandbits(w) for _ in range(npairs)))
    if steered is None:
        return {"merged": False, "reason": "invariants matched but steer failed",
                "pair_evaluations": pair_evaluations, "independent": independent}
    controls_a[1], controls_b[1] = steered[0], steered[1]

    merged = composition.evaluate(state_a, tuple(controls_a)) == \
        composition.evaluate(state_b, tuple(controls_b))
    return {
        "merged": merged,
        "independent": independent,
        "pair_evaluations": pair_evaluations,
        "round_equivalents": pair_evaluations / 2.0,
        "controls_a": [list(c) for c in controls_a],
        "controls_b": [list(c) for c in controls_b],
    }


def flat_birthday_merge(composition, state_a, state_b, rng, budget):
    """Generic flat route: TWO-SIDED birthday on final states.

    Interleaved and stopping at the first cross-match, so the reported cost is
    the birthday cost itself rather than a reflection of the budget. Final
    states live in 4w bits, so the expectation is on the order of 2^(2w).
    """
    def sample():
        return tuple(tuple(rng.getrandbits(composition.w)
                           for _ in range(composition.controls_per_round))
                     for _ in range(composition.k))

    seen_a, seen_b = {}, {}
    evaluations = 0
    while evaluations < budget:
        ca = sample()
        fa = composition.evaluate(state_a, ca)
        evaluations += 1
        seen_a.setdefault(fa, ca)
        if fa in seen_b:
            return {"merged": True, "evaluations": evaluations,
                    "round_equivalents": evaluations * composition.k}
        cb = sample()
        fb = composition.evaluate(state_b, cb)
        evaluations += 1
        seen_b.setdefault(fb, cb)
        if fb in seen_a:
            return {"merged": True, "evaluations": evaluations,
                    "round_equivalents": evaluations * composition.k}
    return {"merged": False, "evaluations": evaluations,
            "round_equivalents": evaluations * composition.k}


def run_case(w, k, trials, rng, exhaustive_limit=4, aligned=True):
    """aligned=True shares one pairing across factors, which is what lets the
    factored attacker divide and conquer. aligned=False rotates the pairing per
    factor and is measured separately as a candidate defence."""
    thetas = []
    rejected = 0
    shared_pairs = S.PAIRINGS[0] if aligned else None
    shared_signs = ((-1, 1), (1, -1)) if aligned else None
    while len(thetas) < k:
        theta = S.random_theta(w, rng, pairs=shared_pairs, signs=shared_signs)
        verdict = S.validate_weakness(theta, rng, trials=60)
        if verdict["admissible"]:
            thetas.append(theta)
        else:
            rejected += 1
    composition = Composition(thetas=tuple(thetas))

    factored_costs, flat_costs, independent_flags = [], [], []
    factored_ok = flat_ok = 0
    budget = min(8 << (2 * w), 400000)

    for _ in range(trials):
        sa = tuple(rng.getrandbits(w) for _ in range(4))
        sb = tuple(rng.getrandbits(w) for _ in range(4))
        fac = factored_merge(composition, sa, sb, rng)
        independent_flags.append(bool(fac.get("independent")))
        if fac.get("merged"):
            factored_ok += 1
            factored_costs.append(fac["round_equivalents"])
        flat = flat_birthday_merge(composition, sa, sb, rng, budget)
        if flat.get("merged"):
            flat_ok += 1
            flat_costs.append(flat["round_equivalents"])

    row = {
        "w": w, "k": k, "trials": trials,
        "spectrum_members_rejected": rejected,
        # With 3 pairings drawn at random, ~1/3 of "rotated" cases are aligned
        # by accident; without this the rotated rows are uninterpretable.
        "divide_and_conquer_available":
            f"{sum(independent_flags)}/{len(independent_flags)}",
        "factored_success": f"{factored_ok}/{trials}",
        "flat_success": f"{flat_ok}/{trials}",
        "factored_median_round_equivalents": statistics.median(factored_costs) if factored_costs else None,
        "flat_median_round_equivalents": statistics.median(flat_costs) if flat_costs else None,
    }
    if factored_costs and flat_costs:
        fm, gm = statistics.median(factored_costs), statistics.median(flat_costs)
        row["log2_factored"] = round(math.log2(fm), 3) if fm > 0 else None
        row["log2_flat"] = round(math.log2(gm), 3) if gm > 0 else None
        row["log2_separation"] = round(math.log2(gm / fm), 3) if fm > 0 else None
        row["predicted_log2_factored"] = round(w / 2 + 1, 3)
        row["predicted_log2_flat"] = round(2 * w, 3)

    # Ground truth at the smallest sizes only.
    if w <= exhaustive_limit and k <= 2:
        sa = tuple(rng.getrandbits(w) for _ in range(4))
        sb = tuple(rng.getrandbits(w) for _ in range(4))
        start = time.time()
        exact = optimal_merge(composition, sa, sb)
        exact["seconds"] = round(time.time() - start, 2)
        exact["control_space"] = composition.control_count()
        exact["note"] = ("existence check only -- the evaluation count is dominated "
                         "by enumerating reach(S) in an arbitrary order, so it is "
                         "NOT a measure of the optimal public cost")
        row["merge_exists"] = exact
    return row


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20260915)
    report = {
        "experiment": "factored_vs_flat_separation",
        "question": "does knowing the factorization beat holding only F?",
        "cost_unit": "round-equivalents (1 flat F eval = k rounds; 1 pair map = 0.5 round)",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rows": [],
    }
    for aligned in (True, False):
        print(f"\n=== pairing {'aligned across factors' if aligned else 'rotated per factor'} ===")
        for w in (3, 4, 5, 6, 7, 8):
            for k in (2, 3):
                trials = 20 if w <= 6 else (10 if w == 7 else 5)
                row = run_case(w, k, trials=trials, rng=rng, aligned=aligned)
                row["pairing_aligned"] = aligned
                report["rows"].append(row)
                print(f"w={row['w']} k={row['k']}  "
                      f"factored={row['factored_success']} @2^{row.get('log2_factored')}  "
                      f"flat={row['flat_success']} @2^{row.get('log2_flat')}  "
                      f"separation=2^{row.get('log2_separation')}")
                if "merge_exists" in row:
                    print(f"        merge exists: {row['merge_exists']['merged']} "
                          f"(control space {row['merge_exists']['control_space']})")

    path = RESULTS / "milestone-separation.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
