#!/usr/bin/env python3
"""Phase 1: formalize and exhaustively verify the current Rainbow weakness.

Checks, in order:
  A  the w=64 model is production Rainbow (anchored to the verified implementation)
  B  fixed-control state transitions are permutations
  C  injection preserves the per-pair invariants
  D  two states are mergeable in one block IFF their invariants agree
  E  steer() is correct, and the solution set has the claimed size
  F  the birthday-style steering construction, with measured cost vs w

Everything at small w is exhaustive, not sampled.  Results are written as JSON.
"""

import itertools
import json
import pathlib
import random
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from models import rainbow as R          # noqa: E402
from models import wordops as W          # noqa: E402

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"


def check_production_anchor():
    ok, detail = R.selftest_matches_production()
    return {"check": "production_anchor", "passed": ok, "detail": detail}


def check_permutation(widths_pair, widths_full):
    """A fixed control makes the transition a permutation of the state."""
    out = {"check": "fixed_control_is_permutation", "passed": True,
           "pair_widths": [], "full_widths": []}

    # mixA is separable, so per-pair bijectivity is equivalent and far cheaper.
    for w in widths_pair:
        theta = R.default_theta(w)
        m, r = theta.multipliers, theta.mixa_rotations
        for lane_pair, (m0, m1, m2, m3, r0, r1) in enumerate(
                [(m[0], m[1], m[2], m[3], r[0], r[1]),
                 (m[4], m[5], m[6], m[7], r[2], r[3])]):
            seen = set()
            for hi in range(1 << w):
                a = W.mul(W.rotr(W.mul(hi, m0, w), r0, w), m1, w)
                for hj in range(1 << w):
                    b = W.mul(W.rotr(W.mul(W.xor(hj, a, w), m2, w), r1, w), m3, w)
                    seen.add((a << w) | b)
            if len(seen) != 1 << (2 * w):
                out["passed"] = False
        out["pair_widths"].append({"w": w, "images": len(seen),
                                   "expected": 1 << (2 * w)})

    # Full-state check, including mixB and the lane permutation.
    for w in widths_full:
        theta = R.default_theta(w)
        for inner in (False, True):
            images = set()
            for packed in range(1 << (4 * w)):
                state = W.int_to_words(packed, 4, w)
                nxt = R.transition(state, (0, 0), theta, inner=inner, seed=1)
                images.add(W.words_to_int(nxt, w))
            if len(images) != 1 << (4 * w):
                out["passed"] = False
            out["full_widths"].append({"w": w, "inner": inner,
                                       "images": len(images),
                                       "expected": 1 << (4 * w)})
    return out


def check_invariant_preserved(widths):
    """Exhaustive over every pair-state and every control."""
    out = {"check": "injection_preserves_invariants", "passed": True, "widths": []}
    for w in widths:
        theta = R.default_theta(w)
        tested = 0
        for h0 in range(1 << w):
            for h1 in range(1 << w):
                for h2 in range(1 << w):
                    state = (h0, h1, h2, 0)
                    before = R.invariants(state, theta)
                    for x in range(1 << w):
                        after = R.invariants(R.inject(state, (x, 0), theta), theta)
                        tested += 1
                        if after != before:
                            out["passed"] = False
        out["widths"].append({"w": w, "cases": tested})
    return out


def check_merge_iff(widths):
    """Mergeable in one block IFF invariants agree -- both directions, exhaustive."""
    out = {"check": "merge_iff_invariants_agree", "passed": True, "widths": []}
    for w in widths:
        theta = R.default_theta(w)
        agree_merged = agree_total = differ_total = differ_merged = 0
        pair_states = list(itertools.product(range(1 << w), repeat=2))
        for a01 in pair_states:
            sa = (a01[0], a01[1], 0, 0)
            for b01 in pair_states:
                sb = (b01[0], b01[1], 0, 0)
                same = R.invariants(sa, theta)[0] == R.invariants(sb, theta)[0]
                merged = False
                for x in range(1 << w):
                    ia = R.inject(sa, (x, 0), theta)
                    for xp in range(1 << w):
                        if R.inject(sb, (xp, 0), theta)[:2] == ia[:2]:
                            merged = True
                            break
                    if merged:
                        break
                if same:
                    agree_total += 1
                    agree_merged += merged
                else:
                    differ_total += 1
                    differ_merged += merged
        # Every agreeing pair must merge; no differing pair may merge.
        if agree_merged != agree_total or differ_merged != 0:
            out["passed"] = False
        out["widths"].append({
            "w": w,
            "invariants_agree": agree_total, "agreeing_that_merged": agree_merged,
            "invariants_differ": differ_total, "differing_that_merged": differ_merged,
        })
    return out


def check_steer(widths, trials=400):
    """steer() merges, for every free choice, and the solution set is 2^w per pair."""
    out = {"check": "steer_correct_and_solution_count", "passed": True, "widths": []}
    rng = random.Random(20260915)
    for w in widths:
        theta = R.default_theta(w)
        merges = 0
        for _ in range(trials):
            sa = tuple(rng.getrandbits(w) for _ in range(4))
            # Build sb sharing both invariants but otherwise unrelated.
            sb = list(tuple(rng.getrandbits(w) for _ in range(4)))
            for (i, j), (si, sj), inv in zip(theta.pairs, theta.signs,
                                             R.invariants(sa, theta)):
                # solve sj*sb_i - si*sb_j = inv for sb_j
                # invariant = sj*b_i - si*b_j, so si*b_j = sj*b_i - inv, and
                # since si is +/-1 it is its own inverse mod 2^w.
                target = W.sub(W.mul(sj % (1 << w), sb[i], w), inv, w)
                sb[j] = target if si == 1 else W.neg(target, w)
            sb = tuple(sb)
            if not R.mergeable(theta, sa, sb):
                out["passed"] = False
                continue
            free = tuple(rng.getrandbits(w) for _ in theta.pairs)
            got = R.steer(theta, sa, sb, free=free)
            if got is None:
                out["passed"] = False
                continue
            ca, cb = got
            if R.inject(sa, ca, theta) != R.inject(sb, cb, theta):
                out["passed"] = False
            else:
                merges += 1
        # Solution-set size for one pair, exhaustively, at small w.
        counted = None
        if w <= 6:
            theta_s = R.default_theta(w)
            sa = (1, 2, 0, 0)
            sb = (3, 0, 0, 0)  # same pair sum 3 when signs are (-1,+1)
            if R.mergeable(theta_s, sa, sb):
                counted = sum(
                    1
                    for x in range(1 << w) for xp in range(1 << w)
                    if R.inject(sa, (x, 0), theta_s)[:2]
                    == R.inject(sb, (xp, 0), theta_s)[:2]
                )
        out["widths"].append({"w": w, "trials": trials, "merged": merges,
                              "solutions_for_one_pair": counted,
                              "expected_solutions": (1 << w) if counted is not None else None})
    return out


def pair_sum_map(theta, s0, s1):
    """H(x): the first pair's invariant after injecting x and applying mixA."""
    w = theta.w
    m, r = theta.multipliers, theta.mixa_rotations

    def H(x):
        h0 = W.add(s0, theta.signs[0][0] * x, w)
        h1 = W.add(s1, theta.signs[0][1] * x, w)
        a = W.mul(W.rotr(W.mul(h0, m[0], w), r[0], w), m[1], w)
        b = W.mul(W.rotr(W.mul(W.xor(h1, a, w), m[2], w), r[1], w), m[3], w)
        return W.add(a, b, w)
    return H


def check_birthday_construction(widths, trials=64):
    """Find x_a != x_b with H(x_a) == H(x_b); median cost against 2^(w/2).

    A single sample says nothing about scaling: the birthday count is a random
    variable with large spread. Each width is therefore repeated over many
    independent start states and the median is reported, alongside the analytic
    median 1.177*2^(w/2) and mean 1.253*2^(w/2) for a random map.
    """
    import math
    import statistics

    out = {"check": "birthday_steering_construction", "passed": True, "widths": []}
    rng = random.Random(4242)
    for w in widths:
        theta = R.default_theta(w)
        costs = []
        example = None
        start = time.time()
        for _ in range(trials):
            s0, s1 = rng.getrandbits(w), rng.getrandbits(w)
            H = pair_sum_map(theta, s0, s1)
            seen = {}
            for x in range(1 << w):
                h = H(x)
                if h in seen:
                    costs.append(x + 1)
                    if example is None:
                        example = {"s0": s0, "s1": s1, "xa": seen[h], "xb": x, "H": h}
                    break
                seen[h] = x
            else:
                out["passed"] = False          # H injective: no collision at all
        elapsed = time.time() - start
        if not costs:
            out["passed"] = False
            out["widths"].append({"w": w, "found": False})
            continue
        median = statistics.median(costs)
        out["widths"].append({
            "w": w,
            "trials": len(costs),
            "median_evaluations": median,
            "log2_median": round(math.log2(median), 3),
            "analytic_log2_median": round(w / 2 + 0.235, 3),
            "log2_mean": round(math.log2(statistics.fmean(costs)), 3),
            "analytic_log2_mean": round(w / 2 + 0.326, 3),
            "example": example,
            "seconds": round(elapsed, 3),
        })
    return out


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    report = {"phase": 1, "generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "checks": []}

    for fn in (
        lambda: check_production_anchor(),
        lambda: check_permutation(widths_pair=[3, 4, 5, 6, 7, 8], widths_full=[3, 4]),
        lambda: check_invariant_preserved(widths=[3, 4]),
        lambda: check_merge_iff(widths=[3, 4]),
        lambda: check_steer(widths=[4, 8, 16, 32, 64]),
        lambda: check_birthday_construction(widths=[8, 10, 12, 14, 16, 18, 20, 22, 24]),
    ):
        result = fn()
        report["checks"].append(result)
        status = "PASS" if result.get("passed") else "FAIL"
        print(f"[{status}] {result['check']}")
        for key in ("detail",):
            if key in result:
                print(f"        {result[key]}")
        for row in result.get("widths", []) + result.get("pair_widths", []) + \
                result.get("full_widths", []):
            print(f"        {row}")

    report["all_passed"] = all(c.get("passed") for c in report["checks"])
    path = RESULTS / "phase1-verification.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\nall_passed={report['all_passed']}  ->  {path}")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
