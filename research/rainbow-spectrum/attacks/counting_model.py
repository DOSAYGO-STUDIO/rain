#!/usr/bin/env python3
"""The counting argument, verified exhaustively, BEFORE any further attack.

The previous experiment measured how hard a task was without first checking the
task was generically hard. It was not: the query had ~2^(4w) solutions, so a
solver reached one by propagation and the measurement was an artifact. This
module exists so that mistake cannot repeat.

QUANTITIES
  N = effective equality-constraint dimension (final states equal): 4w bits.
  Q = total public control bits the attacker may choose.
  S = control freedom the known factor-aware steering route needs.

A capability is only worth measuring when solutions are rare but the privileged
route still succeeds, i.e. when S <= Q <~ N.

DERIVATION (symmetric design, prefix words restricted to t bits, merge round
free). Given prefixes fixing states a and b, the merge injection is solvable iff
sigma(a) == sigma(b); then x, y are free and x', y' are determined. So

    #solutions ~ [#sigma-matching prefix pairs] * 2^(2w)
               ~ 2^(4(k-1)t - 2w) * 2^(2w)  =  2^(4(k-1)t)

The factored route needs at least one sigma-match, i.e. 4(k-1)t >= 2w. Therefore
whenever the privileged route is feasible at all, at least 2^(2w) solutions
already exist: THE WINDOW IS EMPTY. The cause is structural -- even a unique
sigma-match still carries 2^(2w) merge-round solutions, because x being free is
exactly what makes the merge free for the factored attacker.

Restricting the merge round does not rescue it: x' = x + delta must remain
representable, which generically fails and breaks the privileged route first.

ASYMMETRIC REPAIR. Fix one side's merge controls and leave the other's free.
Each sigma-match then contributes exactly one solution:

    #solutions ~ 2^(4(k-1)t - 2w),  Q = 4(k-1)t + 2w,  N = 4w

At t = w/(2(k-1)) + c this is 2^(4c) solutions -- sparse and tunable -- while the
factored side keeps its birthday match. Non-empty, but narrow.

Everything above is a prediction. This script checks it against exhaustive
enumeration, and reports the regime rather than assuming it.
"""

import json
import math
import pathlib
import random
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from compositions.sequential import Composition       # noqa: E402
from models import rainbow as R                       # noqa: E402
from models import spectrum as S                      # noqa: E402

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"
PAIRS = S.PAIRINGS[0]
SIGNS = ((-1, 1), (1, -1))
LANES = 4


def make_thetas(w, count, rng):
    out = []
    while len(out) < count:
        theta = S.random_theta(w, rng, pairs=PAIRS, signs=SIGNS)
        if S.validate_weakness(theta, rng, trials=20)["admissible"]:
            out.append(theta)
    return tuple(out)


def restricted(t):
    """Control words limited to t low bits."""
    return range(1 << t)


def state_after_prefix(composition, state, prefix):
    for index, theta in enumerate(composition.thetas[:-1]):
        state = R.transition(state, prefix[index], theta, inner=False, seed=0)
    return state


def count_sigma_matches(composition, sa, sb, t):
    """Exhaustive over restricted prefixes: how many pairs align sigma?"""
    last = composition.thetas[-1]
    npairs = composition.controls_per_round
    k = len(composition.thetas)

    def sigmas(state):
        table = {}
        for combo in _prefix_space(k - 1, npairs, t):
            after = state_after_prefix(composition, state, combo)
            table.setdefault(R.invariants(after, last), []).append(combo)
        return table

    ta, tb = sigmas(sa), sigmas(sb)
    matches = 0
    for key, rows in ta.items():
        if key in tb:
            matches += len(rows) * len(tb[key])
    return matches, sum(len(v) for v in ta.values())


def _prefix_space(rounds, npairs, t):
    if rounds == 0:
        yield ()
        return
    space = list(restricted(t))
    def walk(depth):
        if depth == rounds:
            yield ()
            return
        for rest in walk(depth + 1):
            for a in space:
                for b in space:
                    yield ((a, b),) + rest
    yield from walk(0)


def brute_force_solutions(composition, sa, sb, t, asymmetric):
    """Directly enumerate every control assignment and count real merges.

    This is the arbiter for the predicted counts. Only tractable at tiny sizes.
    """
    w = composition.w
    npairs = composition.controls_per_round
    k = len(composition.thetas)
    merge_a = [(0,) * npairs] if asymmetric else None
    total = 0
    for pa in _prefix_space(k - 1, npairs, t):
        for pb in _prefix_space(k - 1, npairs, t):
            a = state_after_prefix(composition, sa, pa)
            b = state_after_prefix(composition, sb, pb)
            xs = merge_a if asymmetric else [
                (x, y) for x in range(1 << w) for y in range(1 << w)]
            for ma in xs:
                lhs = R.inject(a, ma, composition.thetas[-1])
                for x in range(1 << w):
                    for y in range(1 << w):
                        if R.inject(b, (x, y), composition.thetas[-1]) == lhs:
                            total += 1
    return total


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20260915)
    report = {
        "model": "solution_counting_before_attack",
        "N_definition": "4w bits of final-state equality",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "verification": [], "regimes": [],
    }

    print("exhaustive check of the predicted solution counts (k=2)")
    print("  w  t  design       sigma-matches  predicted  actual  agree")
    for w in (3, 4):
        for t in range(1, w + 1):
            composition = Composition(thetas=make_thetas(w, 2, rng))
            sa = tuple(rng.getrandbits(w) for _ in range(LANES))
            sb = tuple(rng.getrandbits(w) for _ in range(LANES))
            matches, _ = count_sigma_matches(composition, sa, sb, t)
            for asymmetric in (False, True):
                predicted = matches * (1 if asymmetric else (1 << (2 * w)))
                # Brute force only where it is affordable.
                affordable = (not asymmetric and w <= 3 and t <= 2) or \
                             (asymmetric and w <= 4 and t <= 3)
                actual = (brute_force_solutions(composition, sa, sb, t, asymmetric)
                          if affordable else None)
                agree = (actual == predicted) if actual is not None else None
                label = "asymmetric" if asymmetric else "symmetric "
                row = {"w": w, "t": t, "design": label.strip(),
                       "sigma_matches": matches, "predicted": predicted,
                       "actual": actual, "agree": agree}
                report["verification"].append(row)
                print(f"  {w}  {t}  {label}   {matches:>12}  {predicted:>9}  "
                      f"{'-' if actual is None else actual:>6}  "
                      f"{'' if agree is None else agree}")

    print("\nregime map: is S <= Q <~ N non-empty?")
    print("  w   k  design       t*    solutions at t*   factored feasible")
    for w in (8, 16, 32, 64):
        for k in (2, 3):
            for asymmetric in (False, True):
                # Smallest t making the factored route feasible: 4(k-1)t >= 2w.
                t_star = math.ceil(2 * w / (4 * (k - 1)))
                exponent = (4 * (k - 1) * t_star - 2 * w) if asymmetric \
                    else (4 * (k - 1) * t_star)
                row = {"w": w, "k": k,
                       "design": "asymmetric" if asymmetric else "symmetric",
                       "t_star": t_star, "log2_solutions_at_t_star": exponent,
                       "window_nonempty": exponent <= 8}
                report["regimes"].append(row)
                print(f"  {w:>2}  {k}  {row['design']:<11}  {t_star:>3}   "
                      f"2^{exponent:<14} {'yes' if row['window_nonempty'] else 'NO'}")

    verified = [r for r in report["verification"] if r["agree"] is not None]
    all_agree = all(r["agree"] for r in verified)
    sym_empty = all(not r["window_nonempty"] for r in report["regimes"]
                    if r["design"] == "symmetric")
    asym_ok = any(r["window_nonempty"] for r in report["regimes"]
                  if r["design"] == "asymmetric")
    report["counts_verified"] = all_agree
    report["symmetric_window_empty"] = sym_empty
    report["asymmetric_window_nonempty"] = asym_ok
    report["conclusion"] = (
        ("Predicted counts match exhaustive enumeration in "
         f"{len(verified)} checked cases. " if all_agree else
         "COUNTS DISAGREE with exhaustive enumeration; the model is wrong and "
         "must be fixed before any experiment is built on it. ")
        + ("The SYMMETRIC design has an empty window: whenever the factored "
           "route is feasible (4(k-1)t >= 2w) at least 2^(2w) solutions already "
           "exist, because a unique sigma-match still carries 2^(2w) merge-round "
           "solutions. That is a structural impossibility result for the obvious "
           "construction. " if sym_empty else "")
        + ("The ASYMMETRIC design -- one side's merge controls fixed -- is "
           "non-empty: each sigma-match contributes exactly one solution, giving "
           "2^(4c) solutions at t = w/(2(k-1)) + c while the factored side keeps "
           "its birthday match. That is the only regime worth building an "
           "experiment in." if asym_ok else
           "No asymmetric regime is non-empty either, which would make this "
           "construction unable to host the phenomenon at all."))
    path = RESULTS / "counting-model.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\n{report['conclusion']}\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
