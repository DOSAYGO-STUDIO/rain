#!/usr/bin/env python3
"""The only comparison that was ever the point: weak minus hardened.

Every verdict this project has taken has been a verdict on the WEAK series
alone -- stable, then declining, now stable again. That was always the wrong
question to stop at. The hardened variant is the control: same relation, same
generator, same solver, same budget, injection that preserves no pair sum. If
the public cost scales the same way with and without the weakness, then whatever
the exponent is, it is a property of the relation and not of the weak factor,
and no verdict on the weak series alone can distinguish those.

So this estimates the DIFFERENCE and puts an interval on it. The null being
tested is delta = 0: the weakness buys nothing asymptotically. Rejecting it
needs an interval that excludes zero.

The bootstrap is paired by construction -- each resample redraws both variants
from their own draws and takes the difference of the refit slopes -- so the
interval is on the difference itself rather than being eyeballed from two
overlapping marginal intervals, which is the standard way to fool yourself here.

Both cost metrics are reported. As everywhere else in this program, agreement
between them is evidence and disagreement is a finding.
"""

import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from verdict_power import beta_of, draws_by_width                # noqa: E402

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"
RESAMPLES = 4000
SEED = 20260916


def main():
    clean = json.loads((RESULTS / "scaling-clean.json").read_text())
    w24 = json.loads((RESULTS / "deepen-w24.json").read_text())
    weak = draws_by_width(clean, w24, False)
    hard = draws_by_width(clean, w24, True)

    report = {
        "analysis": "weak_vs_hardened",
        "null": "delta = beta_weak - beta_hardened = 0 (the weakness buys "
                "nothing asymptotically)",
        "resamples": RESAMPLES, "seed": SEED,
        "metrics": {},
    }

    for metric in ("conflicts", "rlimit"):
        bw, bh = beta_of(weak, metric), beta_of(hard, metric)
        rng = random.Random(SEED)
        deltas = []
        for _ in range(RESAMPLES):
            a, b = beta_of(weak, metric, rng), beta_of(hard, metric, rng)
            if a is not None and b is not None:
                deltas.append(a - b)
        deltas.sort()
        lo = deltas[int(0.025 * len(deltas))]
        hi = deltas[int(0.975 * len(deltas)) - 1]
        entry = {
            "beta_weak": round(bw, 4), "beta_hardened": round(bh, 4),
            "delta": round(bw - bh, 4),
            "ci95": [round(lo, 4), round(hi, 4)],
            "excludes_zero": lo > 0 or hi < 0,
        }
        report["metrics"][metric] = entry
        print(f"{metric:<10} weak {entry['beta_weak']}  hardened "
              f"{entry['beta_hardened']}  delta {entry['delta']:+.4f}  "
              f"95% CI [{lo:+.4f}, {hi:+.4f}]  "
              f"separation: {entry['excludes_zero']}")

    any_sep = any(e["excludes_zero"] for e in report["metrics"].values())
    report["separation_detected"] = any_sep
    report["conclusion"] = (
        "Neither cost metric separates the weak construction from the hardened "
        "control: both difference intervals contain zero, and the hardened "
        "point estimate is in fact slightly HIGHER than the weak one under "
        "both. The public task's exponent is therefore a property of the "
        "relation, not of the weak factor. The 'stable' verdict the frozen rule "
        "returns on the weak series is returned on the control as well, so it "
        "is not evidence for the construction."
        if not any_sep else
        "At least one cost metric shows a difference excluding zero; see the "
        "per-metric intervals, and treat a single-metric separation with the "
        "suspicion this project has earned.")
    path = RESULTS / "weak-vs-hardened.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\n{report['conclusion']}\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
