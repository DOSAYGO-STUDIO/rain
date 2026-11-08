#!/usr/bin/env python3
"""Is the local slope stable, or falling toward 0.5?

WRITTEN AND COMMITTED BEFORE THE DATA EXISTED. scaling_wide.py was already
running and no number from it had been seen when this file and its decision
rule were fixed. That ordering is the point: a trend rule chosen after seeing
the trend is not a test, it is a description.

A single global fit can hide the thing that matters. These two datasets give
the same headline beta and opposite conclusions:

    stable      0.72, 0.70, 0.71, 0.69      -> structural gap
    declining   0.79, 0.68, 0.58, 0.52      -> pre-asymptotic, dying at 0.5

So the question is not only

    beta > 0.5 ?

but

    d(beta_local)/dw ~ 0 ?

MEASURES
  global        least squares over all uncensored widths
  windows       beta refit on each 4-width window, in order
  endpoints     refits with the lowest and with the highest width dropped
  excess        E(w) = log2 C - w/2, flat iff the advantage is a constant factor
  trend         least squares of the windowed betas against their centre width

PRE-REGISTERED DECISION RULE
  stable        every window beta >= 0.60 and trend slope > -0.01
  declining     trend slope <= -0.01
  caught_up     final window beta within [0.45, 0.55]
  inconclusive  anything else

The window count is small, so the trend slope is descriptive rather than
inferential; it is reported with the raw window values so a reader can disagree
with the summary without having to rerun anything.
"""

import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from slope_estimate import fit                                   # noqa: E402

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"
WINDOW = 4
STABLE_BETA = 0.60
TREND_TOLERANCE = -0.01
CAUGHT_UP = (0.45, 0.55)


def windows(points, size=WINDOW):
    out = []
    for start in range(len(points) - size + 1):
        chunk = points[start:start + size]
        beta, _ = fit(chunk)
        if beta is None:
            continue
        centre = sum(p[0] for p in chunk) / len(chunk)
        out.append({"widths": [p[0] for p in chunk],
                    "centre": centre, "beta": round(beta, 4)})
    return out


def analyse(medians):
    points = sorted((int(w), math.log2(c)) for w, c in medians.items() if c)
    if len(points) < WINDOW:
        return {"error": f"need at least {WINDOW} widths, have {len(points)}"}

    beta_global, _ = fit(points)
    win = windows(points)
    betas = [entry["beta"] for entry in win]
    trend, _ = fit([(entry["centre"], entry["beta"]) for entry in win]) if len(win) >= 2 \
        else (None, None)

    excess = [(w, round(y - w / 2, 3)) for w, y in points]
    excess_slope, _ = fit([(w, e) for w, e in excess])

    verdict = "inconclusive"
    if betas and CAUGHT_UP[0] <= betas[-1] <= CAUGHT_UP[1]:
        verdict = "caught_up"
    elif trend is not None and trend <= TREND_TOLERANCE:
        verdict = "declining"
    elif betas and min(betas) >= STABLE_BETA and (trend is None or trend > TREND_TOLERANCE):
        verdict = "stable"

    return {
        "beta_global": round(beta_global, 4) if beta_global is not None else None,
        "beta_drop_lowest": round(fit(points[1:])[0], 4) if len(points) > WINDOW else None,
        "beta_drop_highest": round(fit(points[:-1])[0], 4) if len(points) > WINDOW else None,
        "windows": win,
        "window_betas": betas,
        "trend_slope_per_w": round(trend, 5) if trend is not None else None,
        "excess_curve": excess,
        "excess_slope": round(excess_slope, 4) if excess_slope is not None else None,
        "verdict": verdict,
    }


def main():
    source = RESULTS / "scaling-wide.json"
    if not source.exists():
        print(f"{source} not found; run attacks/scaling_wide.py first")
        return 1
    data = json.loads(source.read_text())

    report = {"analysis": "drift_test",
              "rule": {"stable_beta": STABLE_BETA,
                       "trend_tolerance": TREND_TOLERANCE,
                       "caught_up_band": list(CAUGHT_UP),
                       "preregistered": "written before scaling_wide.py finished"},
              "variants": {}}

    for label, variant in data["variants"].items():
        result = analyse(variant["median_conflicts"])
        report["variants"][label] = result
        if "error" in result:
            print(f"{label}: {result['error']}")
            continue
        print(f"\n{label}:")
        print(f"  global beta      {result['beta_global']}   "
              f"(drop lowest {result['beta_drop_lowest']}, "
              f"drop highest {result['beta_drop_highest']})")
        for entry in result["windows"]:
            print(f"    window {entry['widths'][0]:>2}-{entry['widths'][-1]:<2} "
                  f"centre {entry['centre']:>4}   beta {entry['beta']}")
        print(f"  trend d(beta)/dw {result['trend_slope_per_w']}"
              f"   excess slope {result['excess_slope']} (flat => constant factor)")
        print(f"  VERDICT: {result['verdict']}")

    weak = report["variants"].get("weak", {})
    verdict = weak.get("verdict", "inconclusive")
    report["verdict"] = verdict
    report["conclusion"] = {
        "stable": ("Local slopes do not decay over the tested range: every window "
                   f"keeps beta >= {STABLE_BETA} and the trend in beta is flat to "
                   "within tolerance. That is what a structural gap looks like, "
                   "and it is the outcome that would justify red-teaming the "
                   "construction rather than redesigning it."),
        "declining": ("Local slopes fall with width. The toy-scale separation is "
                      "pre-asymptotic: the construction buys a finite-width "
                      "advantage, and the headline beta averages a decaying curve "
                      "rather than describing a law."),
        "caught_up": ("The final window sits at the privileged 0.5. The public "
                      "solver catches up at larger widths and there is no "
                      "separation to defend."),
        "inconclusive": ("Neither criterion is met over this range, so the data "
                         "does not settle whether the slope is stable. More widths, "
                         "not more analysis, is what would decide it."),
    }[verdict]

    path = RESULTS / "drift-test.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\n{report['conclusion']}\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
