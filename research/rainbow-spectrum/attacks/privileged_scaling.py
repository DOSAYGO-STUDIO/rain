#!/usr/bin/env python3
"""The factored row of the 2x2, measured rather than assumed.

Experiment B is an interaction, not a contrast: representation (flat vs
factored) crossed with weakness (present vs removed). Three of the four cells
have been treated carelessly at some point in this project, and the worst of it
was mine -- I read the flat-weak vs flat-hardened null as evidence against the
construction, when a null THERE is the negative control succeeding. A trapdoor
is supposed to be invisible from the public side. The prediction is:

                    weak              hardened
    flat            hard              hard        <- these SHOULD match
    factored        cheap             no shortcut <- this is the claim

So the contrast that carries the hypothesis is flat-weak against factored-weak,
and the hardened column is what rules out "this relation is just easy/hard for
everyone".

WHY THIS FILE EXISTS AT ALL, rather than quoting 2^(w/2+1) from the docstring of
privileged_solve(). The flat exponent is a MEASURED z3 search cost; the factored
one has so far been an ANALYTIC operation count. Differencing those is crossing
units, which is exactly the class of mistake this project keeps making. Here the
factored arm is measured the same way as anything else: draws from the same seed
stream, the same widths, a fitted exponent with a bootstrap interval, and a
check that the witness it returns actually verifies.

A UNIT CAVEAT THAT DOES NOT GO AWAY. The public arm's exponent depends on which
solver counter is used -- 0.722 by conflicts, 0.854 by rlimit, on identical
draws. Both are step counts and an exponent is dimensionless, so the comparison
is meaningful, but the gap inherits that spread and is quoted under both rather
than under whichever is more flattering.

The factored arm is cheap, so it is also run past w=24, where the flat arm
cannot go. That is not a like-for-like extension of the comparison; it is there
to show the factored exponent is flat rather than a short-range artifact.
"""

import json
import math
import pathlib
import random
import statistics
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from drift_test import fit                                       # noqa: E402
from experiment_b import plant, privileged_solve                 # noqa: E402

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"
MATCHED = (12, 14, 16, 18, 20, 22, 24)      # the widths the flat arm reaches
EXTENDED = (26, 28, 30, 32)                 # factored only, to show it is flat
DRAWS = 10
RESAMPLES = 4000
SEED = 20260916


def measure(w, hardened, draw):
    """One factored solve. Same seed stream as every other experiment here."""
    rng = random.Random(8800 + 97 * draw + w)
    t = w // 2
    challenge = plant(w, 2, t, rng, hardened)
    if not challenge["witness_valid"]:
        return {"w": w, "hardened": hardened, "draw": draw,
                "solved": False, "status": "invalid_plant"}
    started = time.time()
    result = privileged_solve(challenge, t, hardened)
    return {"w": w, "hardened": hardened, "draw": draw,
            "solved": bool(result.get("solved")),
            "evaluations": result.get("evaluations"),
            "verified": result.get("replay_verified", result.get("solved")),
            "reason": result.get("reason"),
            "seconds": round(time.time() - started, 2)}


def beta_of(by_width, rng=None):
    points = []
    for width, rows in sorted(by_width.items()):
        sample = [rng.choice(rows) for _ in rows] if rng else rows
        costs = [r["evaluations"] for r in sample
                 if r.get("solved") and r.get("evaluations")]
        if costs:
            points.append((width, math.log2(statistics.median(costs))))
    return fit(points)[0] if len(points) >= 3 else None


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows = []
    for w in MATCHED + EXTENDED:
        for hardened in (False, True):
            if hardened and w in EXTENDED:
                continue                      # the extension is about the claim
            for draw in range(DRAWS):
                rows.append(measure(w, hardened, draw))
        weak = [r for r in rows if r["w"] == w and not r["hardened"]]
        solved = [r for r in weak if r["solved"]]
        print(f"  w={w:>2} weak solved {len(solved)}/{len(weak)}"
              + (f"  median evals "
                 f"{statistics.median([r['evaluations'] for r in solved]):.0f}"
                 if solved else ""), flush=True)

    report = {"experiment": "privileged_scaling",
              "purpose": "measure the factored row of the Experiment B matrix",
              "draws": DRAWS, "matched_widths": list(MATCHED),
              "extended_widths": list(EXTENDED),
              "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "raw": rows, "variants": {}}

    for label in ("weak", "hardened"):
        hardened = label == "hardened"
        mine = [r for r in rows if r["hardened"] == hardened]
        by_width, per_width = {}, {}
        for r in mine:
            by_width.setdefault(r["w"], []).append(r)
        for width, group in sorted(by_width.items()):
            solved = [r["evaluations"] for r in group
                      if r.get("solved") and r.get("evaluations")]
            per_width[str(width)] = {
                "solved": len(solved), "attempted": len(group),
                "verified": sum(1 for r in group if r.get("verified")),
                "median_evaluations": (statistics.median(solved)
                                       if solved else None),
                "reasons": sorted({r.get("reason") for r in group
                                   if r.get("reason")}),
            }
        entry = {"per_width": per_width,
                 "total_solved": sum(v["solved"] for v in per_width.values()),
                 "total_attempted": sum(v["attempted"] for v in per_width.values())}

        matched = {w: g for w, g in by_width.items() if w in MATCHED}
        point = beta_of(matched)
        if point is not None:
            rng = random.Random(SEED)
            samples = sorted(b for b in (beta_of(matched, rng)
                                         for _ in range(RESAMPLES))
                             if b is not None)
            entry["beta_matched_widths"] = round(point, 4)
            entry["ci95"] = [round(samples[int(0.025 * len(samples))], 4),
                             round(samples[int(0.975 * len(samples)) - 1], 4)]
            full = beta_of(by_width)
            entry["beta_all_widths"] = round(full, 4) if full else None
        report["variants"][label] = entry

        print(f"\n{label}: solved {entry['total_solved']}/"
              f"{entry['total_attempted']}")
        for width, row in per_width.items():
            print(f"  w={width:>2}  {row['solved']}/{row['attempted']} solved  "
                  f"median evals {row['median_evaluations']}"
                  + (f"  {row['reasons']}" if row["reasons"] else ""))
        if "beta_matched_widths" in entry:
            print(f"  beta (w=12..24) {entry['beta_matched_widths']} "
                  f"CI {entry['ci95']}"
                  + (f"   beta (all widths) {entry['beta_all_widths']}"
                     if entry.get("beta_all_widths") else ""))

    path = RESULTS / "privileged-scaling.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
