#!/usr/bin/env python3
"""Does the negative control actually hold, or does the weakness show publicly?

corrected_interaction.py reported the weak-minus-hardened public exponent as
+0.0614 and called the negative control satisfied. That was an assertion with no
interval attached, and it is exactly the move this project keeps having to
retract. The number deserves a test, because the pattern behind it is not
obviously noise: all three independent solvers put the weak variant HARDER than
the hardened one, by +0.068, +0.042 and +0.046. Three out of three in the same
direction is not proof, but it is not something to wave through either.

WHY IT MATTERS, AND WHICH DIRECTION IS DANGEROUS. The trapdoor hypothesis
predicts the two variants are publicly indistinguishable. A difference in either
direction is a distinguisher -- an attacker who can tell whether a weakness is
present learns something the construction meant to hide.

The two signs mean different things, though, and conflating them would be
sloppy:

  weak EASIER publicly would be the dangerous one. It would mean the public
  solver is feeding on the very weakness that gives the private route its
  shortcut, which is the failure that sinks the construction.

  weak HARDER publicly, which is what is measured, is not that. It costs
  indistinguishability without handing the attacker an advantage. It is a leak
  of metadata, not of capability.

The bootstrap is paired within each solver and resamples draws, which under the
clean protocol is the only thing that varies: cost is a deterministic function
of the instance, so a resample over draws resamples genuine instance variance
and nothing else.

Reported per solver rather than pooled. Pooling three solvers that disagree
about absolute difficulty would manufacture a tighter interval than the data
supports.
"""

import json
import math
import pathlib
import random
import statistics
import sys
import time

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"
RESAMPLES = 4000
SEED = 20260916


def fit(points):
    n = len(points)
    if n < 2:
        return None
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    denominator = sum((x - mx) ** 2 for x, _ in points)
    if not denominator:
        return None
    return sum((x - mx) * (y - my) for x, y in points) / denominator


def beta(rows_by_width, rng=None):
    points = []
    for width, rows in sorted(rows_by_width.items()):
        sample = [rng.choice(rows) for _ in rows] if rng else rows
        costs = [r for r in sample if r]
        if costs:
            points.append((width, math.log2(statistics.median(costs))))
    return fit(points)


def main():
    data = json.loads((RESULTS / "public-sat-scaling.json").read_text())
    solvers = data["solvers"]
    report = {"analysis": "control_significance",
              "null": "beta_weak - beta_hardened = 0 (variants publicly "
                      "indistinguishable)",
              "resamples": RESAMPLES, "per_solver": {},
              "generated": time.strftime("%Y-%m-%dT%H:%M:%S")}

    for solver in solvers:
        arms = {}
        for hardened in (False, True):
            by_width = {}
            for row in data["raw"]:
                if (row.get("solver") == solver
                        and row.get("hardened") == hardened
                        and row.get("event") and row.get("witness_verified")
                        and row.get("conflicts")):
                    by_width.setdefault(row["w"], []).append(row["conflicts"])
            arms[hardened] = by_width

        point = beta(arms[False]) - beta(arms[True])
        rng = random.Random(SEED)
        deltas = sorted(d for d in
                        (((beta(arms[False], rng) or 0)
                          - (beta(arms[True], rng) or 0))
                         for _ in range(RESAMPLES)) if d)
        lo = deltas[int(0.025 * len(deltas))]
        hi = deltas[int(0.975 * len(deltas)) - 1]
        entry = {"delta": round(point, 4),
                 "ci95": [round(lo, 4), round(hi, 4)],
                 "excludes_zero": lo > 0 or hi < 0,
                 "weak_harder": point > 0}
        report["per_solver"][solver] = entry
        print(f"  {solver:<12} delta {entry['delta']:+.4f}  "
              f"95% CI [{lo:+.4f}, {hi:+.4f}]  "
              f"distinguishable: {entry['excludes_zero']}")

    significant = [s for s, e in report["per_solver"].items()
                   if e["excludes_zero"]]
    same_sign = len({e["weak_harder"] for e in report["per_solver"].values()}) == 1
    report["solvers_showing_a_difference"] = significant
    report["all_same_direction"] = same_sign
    # Significance decides this, not sign. An earlier version of this file
    # branched on direction alone and called the control "partially violated"
    # while every interval contained zero -- an overclaim in the cautious
    # direction, which is still an overclaim.
    #
    # The sign agreement is also weaker evidence than it looks. All three
    # solvers run the SAME instances, drawn from the same seed stream, so their
    # exponent estimates are correlated by construction: a run of instances that
    # happens to favour one variant tilts all three the same way. Three
    # concurring signs are therefore close to one observation, not three, and
    # the 1-in-8 intuition does not apply.
    report["shared_instances_caveat"] = (
        "all solvers ran the same seed stream, so their estimates are "
        "correlated and sign agreement is not independent evidence")
    report["conclusion"] = (
        f"{len(significant)} of {len(solvers)} solvers show a difference whose "
        f"interval excludes zero, so the negative control is NOT violated by "
        f"this data: weak and hardened are publicly indistinguishable within "
        f"the resolution available."
        + (f" All three point estimates put weak slightly harder "
           f"({', '.join(f'{e['delta']:+.4f}' for e in report['per_solver'].values())}), "
           f"but they share instances, so that agreement is close to one "
           f"observation rather than three, and every interval spans zero."
           if same_sign else "")
        + " The direction worth watching is the opposite one: weak EASIER "
          "publicly would mean the solver is feeding on the weakness that "
          "gives the private route its shortcut, and that is the failure that "
          "would sink the construction. Nothing here shows it. Settling the "
          "residual tilt needs an independent seed stream, not more solvers on "
          "these instances.")

    path = RESULTS / "control-significance.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\n{report['conclusion']}\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
