#!/usr/bin/env python3
"""The whole research question, reduced to one number: beta.

Experiment B established that factor knowledge yields a capability that
vanishes when the weakness is removed (privileged: 10/10 on weak, 0/10 on
hardened). What it did NOT establish is whether that capability is worth more
than a constant factor against a competent public solver.

    C_privileged ~ 2^(0.5 w)              (analytic, and measured)
    C_public     ~ 2^(beta w)             (this experiment)

PRE-REGISTERED DECISION RULE, fixed before looking at the data:

    beta - 0.5 > 0.1 and the bootstrap interval excludes 0.5
        -> genuine growing separation
    the bootstrap interval contains 0.5
        -> constant-factor advantage only; no asymptotic separation shown
    beta < 0.5 robustly
        -> the public solver asymptotically catches up

TIMEOUTS ARE EXCLUDED, NOT COUNTED. A capped solve reports the conflicts it
reached, which is a LOWER BOUND on the work the instance needs. Including those
points pulls the fitted slope down precisely at the largest widths, which is
where the slope is decided. An earlier 4-width run showed per-interval slopes of
0.79, 0.735, 0.61, with the last interval sitting against a 60s cap -- exactly
the shape this bias produces. Excluded draws are reported, and a width that
loses too many is dropped from the fit rather than quietly biasing it.
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

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"


def fit(points):
    """Least squares slope of log2(cost) against w."""
    if len(points) < 2:
        return None, None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    n = len(points)
    mx, my = sum(xs) / n, sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return None, None
    beta = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
    alpha = my - beta * mx
    return beta, alpha


def bootstrap_beta(per_width, rounds=2000, seed=7):
    """Resample draws within each width, refit, and return a 5-95 interval."""
    rng = random.Random(seed)
    betas = []
    widths = sorted(per_width)
    for _ in range(rounds):
        points = []
        for w in widths:
            sample = per_width[w]
            if not sample:
                continue
            drawn = [sample[rng.randrange(len(sample))] for _ in sample]
            points.append((w, math.log2(statistics.median(drawn))))
        beta, _ = fit(points)
        if beta is not None:
            betas.append(beta)
    if not betas:
        return None, None, None
    betas.sort()
    lo = betas[int(0.05 * len(betas))]
    hi = betas[int(0.95 * len(betas)) - 1]
    return statistics.median(betas), lo, hi


def run(widths, draws_for, timeout_ms, hardened):
    per_width, excluded, priv_ok, priv_total = {}, {}, 0, 0
    for w in widths:
        draws = draws_for(w)
        t = w // 2
        costs, skipped = [], 0
        for d in range(draws):
            rng = random.Random(4100 + 37 * d + w)
            challenge = plant(w, 2, t, rng, hardened)
            if not challenge["witness_valid"]:
                skipped += 1
                continue
            priv = privileged_solve(challenge, t, hardened)
            priv_total += 1
            priv_ok += bool(priv.get("solved"))
            public = public_solve(challenge, t, hardened, timeout_ms)
            if public["verdict"] != "sat":
                skipped += 1           # capped: a lower bound, not a cost
                continue
            conflicts = ST.get(public["stats"], "conflict")
            if conflicts is None or conflicts <= 0:
                skipped += 1
                continue
            costs.append(conflicts)
        per_width[w] = costs
        excluded[w] = skipped
        print(f"    w={w:>3}  n={len(costs):>3}/{draws}  excluded={skipped}  "
              f"median conflicts="
              f"{statistics.median(costs) if costs else 'n/a'}")
    return per_width, excluded, priv_ok, priv_total


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    widths = (8, 10, 12, 14, 16, 18)
    timeout_ms = 300000          # generous: exclusions should be rare
    draws_for = lambda w: 12 if w <= 14 else (8 if w == 16 else 5)

    report = {
        "experiment": "slope_estimate",
        "question": "is the privileged advantage an exponent gap or a constant factor?",
        "decision_rule": ("separation iff beta - 0.5 > 0.1 and the bootstrap "
                          "interval excludes 0.5; pre-registered before the run"),
        "timeout_ms": timeout_ms,
        "timeout_policy": "capped solves excluded from the fit, never counted",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "variants": {},
    }

    for hardened in (False, True):
        label = "hardened" if hardened else "weak"
        print(f"\n{label}:")
        per_width, excluded, priv_ok, priv_total = run(
            widths, draws_for, timeout_ms, hardened)
        usable = {w: c for w, c in per_width.items() if len(c) >= 3}
        points = [(w, math.log2(statistics.median(c))) for w, c in sorted(usable.items())]
        beta, alpha = fit(points)
        med, lo, hi = bootstrap_beta(usable)
        report["variants"][label] = {
            "per_width_median": {str(w): (statistics.median(c) if c else None)
                                 for w, c in per_width.items()},
            "per_width_n": {str(w): len(c) for w, c in per_width.items()},
            "excluded": {str(w): n for w, n in excluded.items()},
            "beta": round(beta, 4) if beta is not None else None,
            "bootstrap_beta_median": round(med, 4) if med is not None else None,
            "bootstrap_5": round(lo, 4) if lo is not None else None,
            "bootstrap_95": round(hi, 4) if hi is not None else None,
            "privileged_solved": f"{priv_ok}/{priv_total}",
        }
        print(f"  beta={beta:.3f}  bootstrap 5-95% = [{lo:.3f}, {hi:.3f}]"
              f"   privileged {priv_ok}/{priv_total}")

    weak = report["variants"]["weak"]
    hard = report["variants"]["hardened"]
    beta = weak["bootstrap_beta_median"]
    lo, hi = weak["bootstrap_5"], weak["bootstrap_95"]
    separated = beta is not None and (beta - 0.5) > 0.1 and lo > 0.5
    report["separation_demonstrated"] = bool(separated)
    report["conclusion"] = (
        (f"SEPARATION: public cost grows as 2^({beta:.3f}w) against the "
         f"privileged 2^(0.5w), and the bootstrap interval [{lo:.3f}, {hi:.3f}] "
         f"excludes 0.5. The privileged route is not merely a constant factor "
         f"cheaper."
         if separated else
         f"NO ASYMPTOTIC SEPARATION SHOWN: the public exponent is "
         f"{beta if beta is None else round(beta, 3)} with bootstrap interval "
         f"[{lo}, {hi}], which does not clear the pre-registered bar of "
         f"beta > 0.6 with the interval excluding 0.5. On this evidence the "
         f"privileged advantage is consistent with a constant factor, and this "
         f"construction is not the trapdoor.")
        + f" Hardened public exponent {hard['bootstrap_beta_median']} "
          f"[{hard['bootstrap_5']}, {hard['bootstrap_95']}]; the public solver "
          f"should gain nothing from the weakness, so weak and hardened "
          f"exponents agreeing is the expected control. Privileged: weak "
          f"{weak['privileged_solved']}, hardened {hard['privileged_solved']}.")
    path = RESULTS / "slope-estimate.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\n{report['conclusion']}\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
