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

ONE ESTIMATOR FOR EVERY WIDTH. Medians are recomputed here from the raw draws
rather than read out of whichever summary field each artifact happens to carry.
scaling_clean.py reports a plain median over solved draws and deepen_w24.py
reports a Kaplan-Meier median, and splicing those two into a single fit would
mean the low widths and the high widths were estimated by different rules --
which is the exact shape of silent mismatch that produced the last three
retractions in this project. So the same censoring-aware estimator is applied
uniformly: a plain median where nothing is censored, Kaplan-Meier where
something is, and no value at all where survival never reaches 0.5.

A WIDTH MAY HAVE NO MEDIAN. Where censoring leaves survival above 0.5 there is
nothing to quote, and the width is dropped with that stated rather than filled
in -- the failure mode guarded against is the earlier version of this script,
which silently fell back to the superseded number when the new one was absent.
"""

import json
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from drift_test import analyse                                   # noqa: E402

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"


def censored_median(rows, metric):
    """Median cost, treating timed-out draws as right-censored lower bounds.

    Plain median when nothing is censored, Kaplan-Meier when something is, and
    None where survival never falls to 0.5 -- in which case there is no median
    and saying so is the only honest option. Returns (value, basis).

    The censoring caveat is worth restating where it is used rather than only in
    a paper: the budget is wall-clock, and timeout-validity.json shows wall time
    on this machine tracks load rather than difficulty. The conflict and rlimit
    COUNTS are exactly reproducible; which draws got censored is not.
    """
    key = "conflicts" if metric == "conflicts" else "rlimit_count"
    observations = [(r[key], bool(r.get("event")))
                    for r in rows if r.get(key)]
    if not observations:
        return None, "no data"
    events = sorted(v for v, e in observations if e)
    if not any(not e for _, e in observations):
        return (statistics.median(events) if events else None,
                f"median of {len(events)} solved, none censored")
    observations.sort()
    at_risk, survival = len(observations), 1.0
    for value, event in observations:
        if event:
            survival *= (at_risk - 1) / at_risk
            if survival <= 0.5:
                return value, (f"Kaplan-Meier over {len(observations)} draws, "
                               f"{sum(1 for _, e in observations if not e)} censored")
        at_risk -= 1
    return None, (f"NOT ESTIMABLE: survival never reaches 0.5 "
                  f"({len(events)} solved of {len(observations)})")


def series(clean, w24, label, metric):
    """{width: cost} for one variant under one cost metric, plus provenance.

    Built from the raw draws of both artifacts so that every width is estimated
    by the same rule.
    """
    hardened = (label == "hardened")
    by_width = {}
    for source in (clean, w24):
        for row in source["raw"]:
            if row.get("hardened") == hardened:
                by_width.setdefault(row["w"], []).append(row)

    out, provenance = {}, {}
    for width in sorted(by_width):
        value, basis = censored_median(by_width[width], metric)
        provenance[str(width)] = f"{basis} (n={len(by_width[width])} drawn)"
        if value:
            out[str(width)] = value
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
            for width in sorted(provenance, key=int):
                if width not in costs:
                    print(f"    w={width:>2}  {'-':>14}  {provenance[width]}")
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
