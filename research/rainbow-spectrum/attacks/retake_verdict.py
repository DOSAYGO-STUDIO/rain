#!/usr/bin/env python3
"""Re-take the drift verdict on the deepened data.

This splices the deepened w=20/22/24 medians into the w=12..18 series from
scaling_wide.py and calls drift_test.analyse() VERBATIM. No rule is restated,
no threshold is touched, nothing is re-derived here. The verdict comes from the
criteria frozen in c3ea7f0 before any of this data existed; the only thing that
changed is how many draws the three leveraged widths rest on. Where
deepen-w24.json is present it supersedes deepen.json for w=24, which decided the
verdict on n=3 with a 5x spread across its raw draws.

The point of doing it this way, rather than editing drift_test.py, is that the
analysis function cannot be quietly tuned to the answer. If the verdict flips,
it flips because the data moved.

Both variants are reported. The hardened control is not decoration: weak and
hardened should behave alike from the public side, and on the thin data they did
not -- the hardened series had cost FALLING threefold between w=22 and w=24,
which is impossible and marked that whole fit as noise-dominated.
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from drift_test import analyse                                   # noqa: E402

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"
DEEPENED = (20, 22, 24)


def merged_medians(wide_variant, deep_variant):
    """w=12..18 from the wide run, w=20..24 replaced by the deepened draws."""
    out, provenance = {}, {}
    for width, median in wide_variant["median_conflicts"].items():
        if int(width) not in DEEPENED and median:
            out[width] = median
            provenance[width] = f"wide n={wide_variant['n'][width]}"
    for width, row in deep_variant.items():
        if row["median"]:
            out[width] = row["median"]
            provenance[width] = f"deepened n={row['n']}"
    return out, provenance


def main():
    wide_path = RESULTS / "scaling-wide.json"
    deep_path = RESULTS / "deepen.json"
    for path in (wide_path, deep_path):
        if not path.exists():
            print(f"missing {path}")
            return 1
    wide = json.loads(wide_path.read_text())
    deep = json.loads(deep_path.read_text())
    # w=24 decided the verdict on n=3; if it has since been sampled properly,
    # that measurement supersedes the thin one. deepen.json is left intact so
    # both sit on disk rather than one silently replacing the other.
    w24_path = RESULTS / "deepen-w24.json"
    w24 = json.loads(w24_path.read_text()) if w24_path.exists() else None

    report = {
        "analysis": "retake_verdict",
        "inputs": {"widths_12_18": "scaling-wide.json",
                   "widths_20_24": "deepen.json (independent seeds)"},
        "rule": "drift_test.analyse(), unmodified, frozen in c3ea7f0",
        "variants": {},
    }

    for label in ("weak", "hardened"):
        medians, provenance = merged_medians(wide["variants"][label],
                                             deep["variants"][label])
        if w24 and w24["variants"][label]["median"]:
            row24 = w24["variants"][label]
            medians["24"] = row24["median"]
            provenance["24"] = f"deepened-w24 n={row24['n']}"
        before = analyse(wide["variants"][label]["median_conflicts"])
        after = analyse(medians)
        report["variants"][label] = {
            "medians": medians, "provenance": provenance,
            "before_deepening": before, "after_deepening": after,
        }

        print(f"\n=== {label} ===")
        for width in sorted(medians, key=int):
            wide_median = wide["variants"][label]["median_conflicts"].get(width)
            moved = ""
            if wide_median and abs(wide_median - medians[width]) > 1:
                moved = f"   (was {wide_median:.0f}, x{medians[width]/wide_median:.2f})"
            print(f"  w={width:>2}  {medians[width]:>12.0f}  "
                  f"{provenance[width]}{moved}")
        print(f"  before: beta {before['beta_global']}  windows "
              f"{before['window_betas']}  trend {before['trend_slope_per_w']}"
              f"  -> {before['verdict']}")
        print(f"  after:  beta {after['beta_global']}  windows "
              f"{after['window_betas']}  trend {after['trend_slope_per_w']}"
              f"  -> {after['verdict']}")
        print(f"  excess curve: {[e for _, e in after['excess_curve']]}")

    weak = report["variants"]["weak"]
    before, after = weak["before_deepening"], weak["after_deepening"]
    flipped = before["verdict"] != after["verdict"]
    report["verdict"] = after["verdict"]
    report["flipped"] = flipped
    report["conclusion"] = (
        f"With the leveraged widths at 10/8/3 draws instead of 5/3/2, the "
        f"pre-registered verdict is '{after['verdict']}'"
        + (f" -- CHANGED from '{before['verdict']}' on the thin data. The earlier "
           f"reading was carried by undersampled points."
           if flipped else
           f", unchanged from the thin data, which is the outcome that would "
           f"make it worth defending.")
        + f" Global beta moved {before['beta_global']} -> {after['beta_global']}; "
          f"windows {before['window_betas']} -> {after['window_betas']}."
    )

    path = RESULTS / "retake-verdict.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\n{report['conclusion']}\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
