#!/usr/bin/env python3
"""The frozen verdict, applied to data that reproduces.

Every drift verdict this project has taken was computed from conflict counts
gathered by solving many draws inside one process. solver-state-contamination
.json shows those counts are properties of (instance, process history) rather
than of the instance: one fixed instance solved sixteen times in a single
process spans 2.32x, while the same instance in a fresh process reproduces
exactly. So the earlier verdicts -- 'declining' on the deepened data, and the
'stable' reading before it -- were computed over a quantity that cannot be
measured twice.

This re-takes the verdict on scaling-clean.json (w=12..22) and deepen-w24.json
(w=24), both measured one solve per process. The rule is drift_test.analyse(),
imported and called verbatim, frozen in c3ea7f0 before any of this data existed.
Nothing about it is restated or re-derived here, for the same reason as before:
so that it cannot be quietly tuned to the answer.

TWO COST METRICS, WHICH IS THE POINT OF DOING IT THIS WAY. Every clean draw
records both the conflict count and z3's rlimit count. They are different
measures of the same solve, so a verdict that holds on one and not the other is
a verdict about the metric rather than about the construction. Both are
reported; agreement is evidence, disagreement is a finding.

W=24 MAY HAVE NO MEDIAN. Where censoring leaves survival above 0.5 there is no
median to quote, and the width is dropped with that stated rather than filled in
-- the failure mode guarded against here is the earlier version of this script,
which silently fell back to the superseded number when the new one was absent.
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from drift_test import analyse                                   # noqa: E402

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"


def series(clean, w24, label, metric):
    """{width: cost} for one variant under one cost metric, plus provenance."""
    key = "median" if metric == "conflicts" else "median_rlimit"
    out, provenance = {}, {}
    for width, row in clean["variants"][label]["per_width"].items():
        if row[key]:
            out[width] = row[key]
            provenance[width] = (f"clean n={row['n']}/{row['attempted']}"
                                 + (f", {row['censored']} censored"
                                    if row["censored"] else ""))
    row24 = w24["variants"][label]
    if metric == "conflicts" and row24.get("median"):
        out["24"] = row24["median"]
        provenance["24"] = (f"clean n={row24['n']}/{row24['attempted']}, "
                            f"{row24['censored']} censored "
                            f"({row24.get('median_basis')})")
    else:
        provenance["24"] = (
            f"EXCLUDED: no median ({row24['solved']}/{row24['attempted']} "
            f"solved, {row24['censored']} censored)" if metric == "conflicts"
            else "EXCLUDED: rlimit not summarised for w=24")
    return out, provenance


def main():
    clean_path, w24_path = RESULTS / "scaling-clean.json", RESULTS / "deepen-w24.json"
    for path in (clean_path, w24_path):
        if not path.exists():
            print(f"missing {path}")
            return 1
    clean = json.loads(clean_path.read_text())
    w24 = json.loads(w24_path.read_text())

    old = None
    old_path = RESULTS / "retake-verdict.json"
    if old_path.exists():
        old = json.loads(old_path.read_text())

    report = {
        "analysis": "clean_verdict",
        "inputs": {"widths_12_22": "scaling-clean.json",
                   "width_24": "deepen-w24.json"},
        "measurement": "one solve per process; see solver-state-contamination.json",
        "rule": "drift_test.analyse(), unmodified, frozen in c3ea7f0",
        "supersedes": "retake-verdict.json (contaminated conflict counts)",
        "variants": {},
    }

    for label in ("weak", "hardened"):
        report["variants"][label] = {}
        print(f"\n=== {label} ===")
        for metric in ("conflicts", "rlimit"):
            costs, provenance = series(clean, w24, label, metric)
            result = analyse(costs)
            report["variants"][label][metric] = {
                "costs": costs, "provenance": provenance, "analysis": result,
            }
            print(f"  -- {metric} --")
            for width in sorted(costs, key=int):
                print(f"    w={width:>2}  {costs[width]:>14.0f}  "
                      f"{provenance[width]}")
            if "24" in provenance and "24" not in costs:
                print(f"    w=24  {provenance['24']}")
            if result.get("error"):
                print(f"    {result['error']}")
                continue
            print(f"    beta {result['beta_global']}  windows "
                  f"{result['window_betas']}  trend "
                  f"{result['trend_slope_per_w']}  -> {result['verdict']}")

    weak = report["variants"]["weak"]
    by_metric = {m: weak[m]["analysis"].get("verdict") for m in ("conflicts", "rlimit")}
    agree = len(set(v for v in by_metric.values() if v)) == 1
    report["verdict"] = by_metric["conflicts"]
    report["verdict_by_metric"] = by_metric
    report["metrics_agree"] = agree

    previous = (old or {}).get("verdict")
    report["previous_verdict"] = previous
    report["conclusion"] = (
        f"On measurements that reproduce, the pre-registered verdict is "
        f"'{by_metric['conflicts']}' by conflicts and '{by_metric['rlimit']}' by "
        f"rlimit count"
        + (" -- the two cost metrics agree, so this is a statement about the "
           "construction rather than about the metric."
           if agree else
           " -- the two cost metrics DISAGREE, which makes this a statement "
           "about the metric and not about the construction.")
        + (f" The superseded contaminated data gave '{previous}'."
           if previous else ""))

    path = RESULTS / "clean-verdict.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\n{report['conclusion']}\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
