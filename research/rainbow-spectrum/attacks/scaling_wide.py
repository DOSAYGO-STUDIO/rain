#!/usr/bin/env python3
"""Does beta hold up, or drift toward 0.5?

The toy-width run gave beta_flat ~ 0.70 against the privileged 0.5. The open
question is whether that is a scaling law of the construction or a
pre-asymptotic artifact that decays as w grows. A single fit over a wider range
cannot answer it: a slope decaying from 0.8 to 0.55 still *averages* near 0.7.

So the primary instrument here is DRIFT, not the headline number. beta is refit
on every window of four consecutive widths, and the question is whether those
windowed slopes trend downward toward 0.5.

PRE-REGISTERED, fixed before the run:

  widths      12, 14, 16, 18, 20, 22, 24
  draws       12, 12, 10,  8,  5,  3,  2   (cost grows as ~2^(0.7w))
  timeout     900s, chosen so censoring stays at zero; a width losing >10% of
              its draws to timeout is reported and dropped from the primary fit
  primary     beta from least squares on log2(median conflicts) vs w
  drift       beta refit on each 4-width window, reported in order
  secondary   the excess curve log2(C) - w/2, flat iff the advantage is only a
              constant factor

  DECISION RULE
    windowed betas stay >= 0.6 with the bootstrap lower bound above 0.5
        -> the scaling law holds over the tested range
    windowed betas decline monotonically toward 0.5
        -> pre-asymptotic effect; the construction buys a finite-width
           advantage only, and the toy-scale separation does not extrapolate
    final window within [0.45, 0.55]
        -> the public solver has caught up; no separation

Censoring is excluded rather than counted, for the reason established earlier: a
capped solve reports the conflicts it reached, which is a lower bound, and
including those points drags the slope down exactly at the widths that decide
it.
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

from experiment_b import plant, privileged_solve, public_solve   # noqa: E402
from models import solverstats as ST                             # noqa: E402
from slope_estimate import bootstrap_beta, fit                   # noqa: E402

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"

WIDTHS = (12, 14, 16, 18, 20, 22, 24)
DRAWS = {12: 12, 14: 12, 16: 10, 18: 8, 20: 5, 22: 3, 24: 2}
TIMEOUT_MS = 900000
WINDOW = 4


def gather(hardened):
    per_width, excluded = {}, {}
    for w in WIDTHS:
        draws = DRAWS[w]
        t = w // 2
        costs, skipped = [], 0
        started = time.time()
        for d in range(draws):
            rng = random.Random(7700 + 53 * d + w)
            challenge = plant(w, 2, t, rng, hardened)
            if not challenge["witness_valid"]:
                skipped += 1
                continue
            public = public_solve(challenge, t, hardened, TIMEOUT_MS)
            if public["verdict"] != "sat":
                skipped += 1
                continue
            conflicts = ST.get(public["stats"], "conflict")
            if conflicts is None or conflicts <= 0:
                skipped += 1
                continue
            costs.append(conflicts)
        per_width[w] = costs
        excluded[w] = skipped
        median = statistics.median(costs) if costs else None
        print(f"    w={w:>3}  n={len(costs):>2}/{draws}  excluded={skipped}  "
              f"median={median}  "
              f"excess={round(math.log2(median) - w / 2, 2) if median else 'n/a'}  "
              f"[{round(time.time() - started, 1)}s]", flush=True)
    return per_width, excluded


def windows(points, size=WINDOW):
    out = []
    for start in range(len(points) - size + 1):
        chunk = points[start:start + size]
        beta, _ = fit(chunk)
        out.append({"widths": [p[0] for p in chunk],
                    "beta": round(beta, 4) if beta is not None else None})
    return out


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    report = {
        "experiment": "scaling_wide",
        "question": "does beta hold, or drift toward the privileged 0.5?",
        "preregistered": {
            "widths": list(WIDTHS), "draws": DRAWS, "timeout_ms": TIMEOUT_MS,
            "primary": "beta over all uncensored widths",
            "drift": f"beta refit on each {WINDOW}-width window",
            "rule": ("holds if windowed betas stay >=0.6 with bootstrap lower "
                     "bound >0.5; pre-asymptotic if they decline toward 0.5; "
                     "caught up if the final window is within [0.45,0.55]"),
        },
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "variants": {},
    }

    for hardened in (False, True):
        label = "hardened" if hardened else "weak"
        print(f"\n{label}:", flush=True)
        per_width, excluded = gather(hardened)
        usable = {w: c for w, c in per_width.items()
                  if len(c) >= 2 and excluded[w] <= 0.1 * DRAWS[w]}
        points = [(w, math.log2(statistics.median(c)))
                  for w, c in sorted(usable.items())]
        beta, _ = fit(points)
        med, lo, hi = bootstrap_beta(usable)
        drift = windows(points)
        report["variants"][label] = {
            "median_conflicts": {str(w): (statistics.median(c) if c else None)
                                 for w, c in per_width.items()},
            "n": {str(w): len(c) for w, c in per_width.items()},
            "excluded": {str(w): n for w, n in excluded.items()},
            "excess_curve": {str(w): round(math.log2(statistics.median(c)) - w / 2, 3)
                             for w, c in sorted(usable.items())},
            "beta": round(beta, 4) if beta is not None else None,
            "bootstrap": [round(lo, 4) if lo else None, round(hi, 4) if hi else None],
            "drift_windows": drift,
        }
        print(f"  beta={beta:.3f}  bootstrap [{lo:.3f}, {hi:.3f}]")
        print(f"  drift: {[(d['widths'][0], d['widths'][-1], d['beta']) for d in drift]}")

    weak = report["variants"]["weak"]
    betas = [d["beta"] for d in weak["drift_windows"] if d["beta"] is not None]
    lo = weak["bootstrap"][0]
    declining = len(betas) >= 2 and betas[-1] < betas[0] - 0.05
    final_caught_up = bool(betas) and 0.45 <= betas[-1] <= 0.55
    holds = bool(betas) and min(betas) >= 0.6 and lo is not None and lo > 0.5

    report["verdict"] = ("holds" if holds else
                         "caught_up" if final_caught_up else
                         "pre_asymptotic_drift" if declining else "inconclusive")
    report["conclusion"] = {
        "holds": (f"The scaling law HOLDS over w={WIDTHS[0]}..{WIDTHS[-1]}: every "
                  f"4-width window keeps beta >= 0.6 (windows: {betas}) and the "
                  f"bootstrap lower bound {lo} stays above 0.5. The separation is "
                  f"not a toy-width artifact over this range."),
        "caught_up": (f"The public solver CAUGHT UP: the final window beta is "
                      f"{betas[-1] if betas else None}, inside [0.45,0.55]. On this "
                      f"evidence there is no separation at larger widths."),
        "pre_asymptotic_drift": (f"beta DECLINES with width (windows: {betas}). The "
                                 f"toy-scale separation looks pre-asymptotic, and the "
                                 f"construction buys a finite-width advantage rather "
                                 f"than a scaling one."),
        "inconclusive": (f"No clear verdict: windowed betas {betas}, bootstrap lower "
                         f"bound {lo}. Neither the hold nor the drift criterion is met, "
                         f"so the range tested does not settle it."),
    }[report["verdict"]]

    path = RESULTS / "scaling-wide.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\nVERDICT: {report['verdict']}\n{report['conclusion']}\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
