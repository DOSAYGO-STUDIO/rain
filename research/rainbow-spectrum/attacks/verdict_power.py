#!/usr/bin/env python3
"""How precisely can this data pin beta down? Asked before believing a verdict.

A pre-registered rule returns a verdict on whatever it is fed. It does not know
whether the data can support one. This project has now twice had a headline
reading reverse when a leverage point was sampled better, so the question worth
asking of the CLEAN series is not only what the verdict is but whether the
measurement is precise enough for any verdict to be meaningful.

The exercise is only possible honestly now. Under one solve per process, cost is
a deterministic function of the instance, so the spread across draws at a width
is pure instance variance and a bootstrap over draws resamples exactly the
thing that varies. On the old contaminated data a bootstrap was also resampling
solver noise that would never repeat, so its intervals described the measurement
process rather than the construction.

WHAT IS AND IS NOT RE-DERIVED HERE. beta is refit on each resample by ordinary
least squares on (w, log2 median), which is what drift_test.fit() does -- the
fit is repeated, the DECISION RULE is not touched, and no threshold appears in
this file. The verdict stays wherever clean_verdict.py puts it. This only says
how wide the error bars around it are.

Censoring is carried through the resample with the same estimator used
everywhere else, so a resample that happens to draw mostly censored points
yields no median for that width and drops it, exactly as the real data would.
"""

import json
import math
import pathlib
import random
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from clean_verdict import censored_median                        # noqa: E402
from drift_test import fit                                       # noqa: E402

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"
RESAMPLES = 2000
SEED = 20260915


def draws_by_width(clean, w24, hardened):
    out = {}
    for source in (clean, w24):
        for row in source["raw"]:
            if row.get("hardened") == hardened:
                out.setdefault(row["w"], []).append(row)
    return out


def beta_of(by_width, metric, rng=None):
    """OLS slope of log2(median cost) against w, over the widths that have one."""
    points = []
    for width, rows in sorted(by_width.items()):
        sample = ([rng.choice(rows) for _ in rows] if rng else rows)
        value, _ = censored_median(sample, metric)
        if value:
            points.append((width, math.log2(value)))
    if len(points) < 3:
        return None
    slope, _ = fit(points)
    return slope


def main():
    clean = json.loads((RESULTS / "scaling-clean.json").read_text())
    w24 = json.loads((RESULTS / "deepen-w24.json").read_text())

    report = {
        "analysis": "verdict_power",
        "question": "is the clean series precise enough to support any verdict?",
        "resamples": RESAMPLES, "seed": SEED,
        "note": "bootstrap over draws; the decision rule is not touched here",
        "variants": {},
    }

    for label in ("weak", "hardened"):
        by_width = draws_by_width(clean, w24, label == "hardened")
        report["variants"][label] = {}
        print(f"\n=== {label} ===")
        for metric in ("conflicts", "rlimit"):
            rng = random.Random(SEED)
            point = beta_of(by_width, metric)
            samples = sorted(b for b in
                             (beta_of(by_width, metric, rng)
                              for _ in range(RESAMPLES)) if b is not None)
            if not samples or point is None:
                print(f"  {metric}: insufficient data")
                continue
            lo = samples[int(0.025 * len(samples))]
            hi = samples[int(0.975 * len(samples)) - 1]
            dispersion = {}
            for width, rows in sorted(by_width.items()):
                solved = [math.log2(r["conflicts" if metric == "conflicts"
                                      else "rlimit_count"])
                          for r in rows
                          if r.get("event") and r.get("conflicts")
                          and r.get("rlimit_count")]
                if len(solved) > 1:
                    dispersion[str(width)] = round(statistics.stdev(solved), 3)
            entry = {
                "beta": round(point, 4),
                "ci95": [round(lo, 4), round(hi, 4)],
                "ci_width": round(hi - lo, 4),
                "excludes_half": lo > 0.5,
                "log2_stdev_per_width": dispersion,
            }
            report["variants"][label][metric] = entry
            print(f"  {metric:<10} beta {entry['beta']}  "
                  f"95% CI [{entry['ci95'][0]}, {entry['ci95'][1]}]  "
                  f"width {entry['ci_width']}  "
                  f"excludes 0.5: {entry['excludes_half']}")
            print(f"    per-width log2 sd: {dispersion}")

    weak = report["variants"]["weak"]
    widths = [weak[m]["ci_width"] for m in weak]
    report["conclusion"] = (
        f"Weak-variant beta is determined to within "
        f"{min(widths):.2f}-{max(widths):.2f} in log2 slope at 95%. "
        + ("Both metrics exclude 0.5, so a gap above square-root scaling is "
           "resolvable with this data."
           if all(weak[m]["excludes_half"] for m in weak) else
           "At least one metric's interval contains 0.5, so this data cannot "
           "separate the construction from square-root scaling, and any verdict "
           "the frozen rule returns is a statement about a point estimate whose "
           "error bars span the hypothesis being tested."))

    path = RESULTS / "verdict-power.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\n{report['conclusion']}\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
