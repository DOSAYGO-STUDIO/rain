#!/usr/bin/env python3
"""The decisive flat attack: Z/2^r-linear invariant search, for every r <= w.

Every earlier structure attack looked for GF(2)-linear functionals. That is weak
evidence by construction, because the quantity Rainbow actually conserves --
the pair sum h_i + h_j -- lives in addition modulo 2^w, not in XOR. A GF(2) test
sees it only through its low bit.

This searches the right ring, and at every modulus. For a merge class (all
outputs reachable by varying the last round's controls from a fixed prefix) it
looks for alpha in (Z/2^r)^4 with

    sum_i alpha_i * o_i  ==  constant  (mod 2^r)   for every o in the class.

Searching only r = w would miss PARTIAL invariants -- functionals constant in
their low r bits but not in all w. A partial invariant is still a class label,
so it still breaks the separation. Bit-lifting gives this for free: solutions
modulo 2^(j+1) are exactly the lifted solutions modulo 2^j, so each level is
tested as it is built.

An invariant counts only if it is
  * primitive        -- at least one odd (unit) coefficient, so it is not merely
                        a scaled copy of an invariant of a smaller modulus;
  * validated        -- constant on held-out classes, not only the training one;
  * discriminating   -- takes different values on different classes, i.e. a
                        class label rather than a constant of the whole map.

POSITIVE CONTROL: the same search runs on the pre-mixer coset, where the pair
sums genuinely are Z/2^w-linear invariants. If it fails to recover them there,
the search is broken and its negatives mean nothing.
"""

import json
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


def canonical(alpha, r):
    """Canonical representative under unit scaling.

    Over Z/2^r a primitive vector and any unit multiple of it express the SAME
    relation: 5*(1,1,0,0) = (5,5,0,0) mod 8 is not a second invariant. Scaling
    so the first odd coefficient is 1 collapses those duplicates, so counts
    report relations rather than vectors.
    """
    modulus = 1 << r
    for a in alpha:
        if a % 2:
            inverse = pow(a, -1, modulus)
            return tuple((inverse * x) % modulus for x in alpha)
    return tuple(a % modulus for a in alpha)


def zmod_nullspace_levels(rows, w, ncols=LANES, cap=2048):
    """Solutions of rows . alpha == 0 mod 2^r, for r = 1..w, by bit-lifting.

    Exact over Z/2^w: a solution mod 2^j lifts to mod 2^(j+1) by adding
    2^j * beta with beta in {0,1}^ncols. With four unknowns each lifting step is
    a 16-way enumeration rather than a linear solve, so no Smith normal form is
    needed. Returns a list whose entry r-1 holds the solutions modulo 2^r.
    """
    levels = []
    capped = False
    solutions = [tuple([0] * ncols)]
    for j in range(w):
        modulus = 1 << (j + 1)
        lifted = []
        for alpha in solutions:
            for bits in range(1 << ncols):
                candidate = tuple(alpha[i] + (((bits >> i) & 1) << j)
                                  for i in range(ncols))
                for row in rows:
                    acc = 0
                    for i in range(ncols):
                        acc += row[i] * candidate[i]
                    if acc % modulus:
                        break
                else:
                    lifted.append(candidate)
            if cap is not None and len(lifted) > cap:
                # A truncated search can manufacture exactly the negative we
                # are hoping for, so this is reported, never silently accepted.
                capped = True
                break
        solutions = lifted
        levels.append(list(solutions))
        if not solutions:
            break          # nothing survives here, so nothing survives above
    return levels, capped


def exhaustive_nullspace(rows, r, ncols=LANES):
    """Brute-force oracle: every alpha mod 2^r annihilating rows."""
    out = []
    size = 1 << r
    for packed in range(size ** ncols):
        alpha, value = [], packed
        for _ in range(ncols):
            alpha.append(value % size)
            value //= size
        for row in rows:
            acc = 0
            for i in range(ncols):
                acc += row[i] * alpha[i]
            if acc % size:
                break
        else:
            out.append(tuple(alpha))
    return out


def check_lifting_against_exhaustive(w, rng, k=2, rows_used=24):
    """Z/2^w is a ring, not a field, so confirm the lifting loses no solutions.

    Both solvers are given the IDENTICAL row set, and the comparison runs at
    every modulus, so a lift that silently dropped an odd solution -- or a cap
    that truncated the space -- would show up as a mismatch.
    """
    composition = Composition(thetas=make_thetas(w, k, rng))
    state = tuple(rng.getrandbits(w) for _ in range(LANES))
    prefix = tuple(rng.getrandbits(w)
                   for _ in range(composition.controls_per_round))
    points = class_points(composition, state, prefix, w, k)
    base = points[0]
    diffs = [tuple((p[i] - base[i]) % (1 << w) for i in range(LANES))
             for p in points[1:]][:rows_used]

    # Caps are disabled outright at oracle sizes.
    levels, capped = zmod_nullspace_levels(diffs, w, cap=None)
    rows = []
    for index, solutions in enumerate(levels):
        r = index + 1
        brute = set(exhaustive_nullspace(diffs, r))
        lifted = {tuple(a % (1 << r) for a in alpha) for alpha in solutions}
        rows.append({"r": r, "lifted": len(lifted), "exhaustive": len(brute),
                     "identical": lifted == brute,
                     "relations_lifted": len({canonical(a, r) for a in lifted}),
                     "relations_exhaustive": len({canonical(a, r) for a in brute})})
    return rows, capped


# Deliberately nasty systems, to check the solver understands the RING rather
# than merely happening to work on Rainbow-shaped data: nonunits, zero
# divisors, dead-end lifts, branch explosions and non-unique primitives.
SYNTHETIC_SYSTEMS = {
    "single_nonunit_2x": [(2, 0, 0, 0)],
    "zero_divisors": [(2, 2, 0, 0), (4, 0, 4, 0)],
    "dead_end_lift": [(1, 1, 0, 0), (2, 0, 0, 0)],
    "all_even_row": [(2, 4, 6, 0)],
    "empty_system": [],
    "unit_full_rank": [(1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)],
    "duplicate_rows": [(3, 5, 0, 0), (3, 5, 0, 0)],
    "nonunique_primitives": [(1, 1, 1, 1)],
    "mixed_valuation": [(4, 2, 1, 0), (0, 8, 4, 2)],
}


def stress_test_ring_solver(widths=(3, 4)):
    """Lifting must equal brute force on every synthetic system, every modulus."""
    rows = []
    for w in widths:
        for name, system in SYNTHETIC_SYSTEMS.items():
            levels, capped = zmod_nullspace_levels(system, w, cap=None)
            for index, solutions in enumerate(levels):
                r = index + 1
                brute = set(exhaustive_nullspace(system, r))
                lifted = {tuple(a % (1 << r) for a in alpha) for alpha in solutions}
                rows.append({"w": w, "system": name, "r": r,
                             "lifted": len(lifted), "exhaustive": len(brute),
                             "identical": lifted == brute, "capped": capped})
    return rows


def primitive(alpha):
    return any(a % 2 for a in alpha)


def apply_alpha(alpha, point, r):
    acc = 0
    for coefficient, word in zip(alpha, point):
        acc += coefficient * word
    return acc % (1 << r)


def make_thetas(w, count, rng):
    out = []
    while len(out) < count:
        theta = S.random_theta(w, rng, pairs=PAIRS, signs=SIGNS)
        if S.validate_weakness(theta, rng, trials=30)["admissible"]:
            out.append(theta)
    return tuple(out)


def class_points(composition, state, prefix, w, k, premixer=False):
    npairs = composition.controls_per_round
    points = []
    for c0 in range(1 << w):
        for c1 in range(1 << w):
            controls = [prefix] + [(0,) * npairs] * (k - 1)
            controls[k - 1] = (c0, c1)
            if premixer:
                mid = composition.trace(state, tuple(controls))[k - 1]
                points.append(R.inject(mid, (c0, c1), composition.thetas[-1]))
            else:
                points.append(composition.evaluate(state, tuple(controls)))
    return points


def search_invariants(classes, w, search_rows=48):
    """Primitive, validated, discriminating Z/2^r class labels, best r reported."""
    train = classes[0]
    base = train[0]
    diffs = [tuple((p[i] - base[i]) % (1 << w) for i in range(LANES))
             for p in train[1:]]
    sample = (diffs if len(diffs) <= search_rows
              else random.Random(1).sample(diffs, search_rows))

    levels, capped = zmod_nullspace_levels(sample, w)
    per_r, best_r, best = [], 0, []
    for index, solutions in enumerate(levels):
        r = index + 1
        candidates = [a for a in solutions if primitive(a)]
        # Verify against every difference, not just the sampled rows.
        candidates = [a for a in candidates
                      if all(apply_alpha(a, d, r) == 0 for d in diffs)]
        validated = [a for a in candidates
                     if all(len({apply_alpha(a, p, r) for p in cls}) == 1
                            for cls in classes)]
        labels = [[apply_alpha(a, cls[0], r) for cls in classes] for a in validated]
        discriminating = [a for a, lab in zip(validated, labels) if len(set(lab)) > 1]
        per_r.append({"r": r, "candidates": len(candidates),
                      "validated": len(validated),
                      "discriminating": len(discriminating)})
        if discriminating:
            best_r, best = r, discriminating
    return {"per_r": per_r, "max_r": best_r, "discriminating": len(best),
            "search_was_capped": capped,
            "distinct_relations": len({canonical(a, best_r) for a in best}) if best else 0,
            "examples": sorted({canonical(a, best_r) for a in best})[:4] if best else []}


def run_width(w, rng, draws, k=2, heldout=8):
    rows, control_rows = [], []
    for _ in range(draws):
        composition = Composition(thetas=make_thetas(w, k, rng))
        state = tuple(rng.getrandbits(w) for _ in range(LANES))
        prefixes = [tuple(rng.getrandbits(w)
                          for _ in range(composition.controls_per_round))
                    for _ in range(heldout)]
        rows.append(search_invariants(
            [class_points(composition, state, p, w, k) for p in prefixes], w))
        control_rows.append(search_invariants(
            [class_points(composition, state, p, w, k, premixer=True)
             for p in prefixes], w))

    hits = sum(1 for r in rows if r["discriminating"] > 0)
    control_hits = sum(1 for r in control_rows if r["discriminating"] > 0)
    example = next((r["examples"] for r in control_rows if r["examples"]), [])
    control_r = max((r["max_r"] for r in control_rows), default=0)
    return {
        "w": w, "draws": draws,
        "output_draws_with_label": hits,
        "output_rate": round(hits / draws, 3),
        "output_max_r": max((r["max_r"] for r in rows), default=0),
        "control_draws_with_label": control_hits,
        "control_rate": round(control_hits / draws, 3),
        "control_max_r": control_r,
        "control_example_functionals": example,
        "per_draw_output": rows,
    }


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20260915)
    report = {
        "attack": "zmod_2r_linear_invariant_search",
        "question": "does a Z/2^r-linear class label exist for the composed map, any r <= w?",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "widths": [],
    }

    # Prove the ring solver is complete before trusting anything it fails to find.
    stress = stress_test_ring_solver()
    stress_ok = all(r["identical"] for r in stress)
    report["ring_stress_test"] = {"all_identical": stress_ok, "cases": len(stress),
                                  "rows": stress}
    bad = [r for r in stress if not r["identical"]]
    print(f"ring stress: {len(stress)} synthetic cases (nonunits, zero divisors, "
          f"dead-end lifts, duplicates) match brute force: {stress_ok}"
          + (f"  FAILURES: {bad[:3]}" if bad else ""))

    report["lifting_oracle_check"] = []
    for w in (3, 4):
        rows, capped = check_lifting_against_exhaustive(w, rng)
        ok = all(r["identical"] for r in rows) and not capped
        report["lifting_oracle_check"].append(
            {"w": w, "all_identical": ok, "capped": capped, "per_r": rows})
        print(f"oracle w={w}: lifting matches exhaustive at every modulus: {ok}"
              f"  (vectors {[(r['r'], r['lifted'], r['exhaustive']) for r in rows]},"
              f" relations {[(r['r'], r['relations_lifted']) for r in rows]})")
    if not stress_ok or not all(c["all_identical"] for c in report["lifting_oracle_check"]):
        report["conclusion"] = ("LIFTING SOLVER IS INCOMPLETE: it disagrees with "
                                "exhaustive enumeration, so no negative result "
                                "from it can be trusted.")
        (RESULTS / "zmod-invariant-search.json").write_text(json.dumps(report, indent=2))
        print("\n" + report["conclusion"])
        return 1
    print()

    draws_for = {3: 8, 4: 8, 5: 6, 6: 4}
    for w in (3, 4, 5, 6):
        row = run_width(w, rng, draws_for[w])
        report["widths"].append(row)
        print(f"w={w} draws={row['draws']}  "
              f"OUTPUT {row['output_draws_with_label']}/{row['draws']}"
              f" (rate {row['output_rate']}, best r={row['output_max_r']})   "
              f"CONTROL {row['control_draws_with_label']}/{row['draws']}"
              f" (rate {row['control_rate']}, best r={row['control_max_r']})")
        if row["control_example_functionals"]:
            print(f"        control recovered e.g. {row['control_example_functionals']}")

    control_ok = all(r["control_rate"] > 0 for r in report["widths"])
    broke = any(r["output_rate"] > 0 for r in report["widths"])
    report["positive_control_passed"] = control_ok
    report["flat_attack_breaks_separation"] = broke
    if not control_ok:
        report["conclusion"] = (
            "POSITIVE CONTROL FAILED: the search did not recover the pair sums on "
            "the pre-mixer coset, where they provably exist. Every negative below "
            "is therefore meaningless until the search is fixed.")
    elif broke:
        report["conclusion"] = (
            "A Z/2^r-linear class label was recovered from the flat map. The "
            "attacker obtains steering without knowing the factorization, so the "
            "measured separation was an artifact of having tried only GF(2).")
    else:
        report["conclusion"] = (
            "The search recovers the pair sums on the pre-mixer coset, so it "
            "works, and finds no Z/2^r-linear class label on the composed output "
            "at any modulus r <= w. With the GF(2) results this closes the linear "
            "route specifically. Untried: ANF/algebraic elimination, SAT/SMT, "
            "meet-in-the-middle, and amortised precomputation. Phase 4 exact "
            "flattening is still missing, so the attacker holds I/O access rather "
            "than the closed algebraic form the hypothesis actually assumes.")
    path = RESULTS / "zmod-invariant-search.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\n{report['conclusion']}\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
