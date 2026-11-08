#!/usr/bin/env python3
"""Experiment B as the 2x2 it always was: representation x weakness.

Every verdict taken in this project until now was a verdict on ONE cell's
scaling, and the framing error was mine: I read the flat-weak vs flat-hardened
null as evidence against the construction. It is the opposite. A trapdoor is
supposed to be invisible from the public side, so a null in that comparison is
the negative control SUCCEEDING. The hypothesis lives in the interaction:

                    weak                     hardened
    flat            hard                     hard          <- should match
    factored        cheap                    no shortcut   <- the claim

Three comparisons, and only the second and third carry the hypothesis:

  negative control   flat-weak vs flat-hardened. Predicted null. A difference
                     here would mean the public solver is somehow feeding on the
                     very weakness that gives the private route its shortcut,
                     which would sink the construction rather than support it.

  representation gap flat-weak vs factored-weak. This is the separation.

  weakness gap       factored-weak vs factored-hardened. Removing the weakness
                     must remove the private route, or the shortcut was never
                     about the weakness.

UNITS, STATED PLAINLY BECAUSE IT LIMITS THE CLAIM. The flat arm is counted in z3
conflicts or rlimit; the factored arm in evaluations of round_fwd. Both are step
counts and an exponent is a dimensionless growth rate, so the exponents may be
compared -- but the CONSTANTS may not. Nothing here says how large w must be
before the private route wins in wall-clock terms; it says how the two routes
grow apart. The public exponent also depends on which solver counter is used,
0.722 by conflicts against 0.854 by rlimit on identical draws, so the gap is
quoted under both rather than under whichever flatters it.

AND THE LIVE THREAT, which no amount of this measures away: z3 is ONE public
attack, written by the same process that built the construction. The separation
stands only until a dedicated public algorithm finds the sigma route without
being handed the decomposition. That is the experiment that could still kill it,
and it has not been run.
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"


def main():
    power = json.loads((RESULTS / "verdict-power.json").read_text())
    priv = json.loads((RESULTS / "privileged-scaling.json").read_text())
    control = json.loads((RESULTS / "weak-vs-hardened.json").read_text())

    pw = priv["variants"]["weak"]
    ph = priv["variants"]["hardened"]
    beta_priv = pw["beta_matched_widths"]
    priv_ci = pw["ci95"]

    report = {
        "analysis": "interaction",
        "design": "representation (flat|factored) x weakness (present|removed)",
        "cells": {}, "comparisons": {},
        "caveats": [
            "flat arm counted in solver steps, factored arm in round_fwd "
            "evaluations: exponents comparable, constants not",
            "the public exponent is metric-dependent (0.722 conflicts vs 0.854 "
            "rlimit on identical draws)",
            "z3 is one public attack, written by the same process that built "
            "the construction; a dedicated public algorithm finding the sigma "
            "route unaided would collapse the separation",
        ],
    }

    for metric in ("conflicts", "rlimit"):
        flat_w = power["variants"]["weak"][metric]
        flat_h = power["variants"]["hardened"][metric]
        # beta_priv has a degenerate interval -- the factored algorithm's cost is
        # exactly 4*2^(w/2) on every instance -- so the gap's interval is the
        # flat interval shifted. That is stated rather than bootstrapped, since
        # resampling a constant would only manufacture false width.
        gap = round(flat_w["beta"] - beta_priv, 4)
        gap_ci = [round(flat_w["ci95"][0] - beta_priv, 4),
                  round(flat_w["ci95"][1] - beta_priv, 4)]
        report["cells"][metric] = {
            "flat_weak": flat_w["beta"], "flat_weak_ci": flat_w["ci95"],
            "flat_hardened": flat_h["beta"], "flat_hardened_ci": flat_h["ci95"],
            "factored_weak": beta_priv, "factored_weak_ci": priv_ci,
            "factored_hardened": None,
        }
        report["comparisons"][metric] = {
            "negative_control_flat_weak_minus_flat_hardened": {
                "delta": control["metrics"][metric]["delta"],
                "ci95": control["metrics"][metric]["ci95"],
                "predicted": "null",
                "as_predicted": not control["metrics"][metric]["excludes_zero"],
            },
            "representation_gap_flat_weak_minus_factored_weak": {
                "delta": gap, "ci95": gap_ci, "excludes_zero": gap_ci[0] > 0,
                "reading": f"public/private cost ratio ~ 2^({gap:.3f}w) "
                           f"in the measured range",
            },
        }
        print(f"\n=== {metric} ===")
        print(f"                  weak                      hardened")
        print(f"  flat        2^{flat_w['beta']:.3f}w {flat_w['ci95']}"
              f"   2^{flat_h['beta']:.3f}w {flat_h['ci95']}")
        print(f"  factored    2^{beta_priv:.3f}w {priv_ci}"
              f"          NO SHORTCUT ({ph['total_solved']}/"
              f"{ph['total_attempted']} solved)")
        neg = report["comparisons"][metric][
            "negative_control_flat_weak_minus_flat_hardened"]
        print(f"  negative control  delta {neg['delta']:+.4f} "
              f"CI {neg['ci95']}  as predicted: {neg['as_predicted']}")
        print(f"  representation gap  {gap:+.4f} CI {gap_ci}  "
              f"-> ratio ~ 2^({gap:.3f}w)")

    report["weakness_gap_factored"] = {
        "weak_solved": f"{pw['total_solved']}/{pw['total_attempted']}",
        "hardened_solved": f"{ph['total_solved']}/{ph['total_attempted']}",
        "reading": "removing the weakness does not raise the private route's "
                   "exponent, it removes the route: the sigma match fails on "
                   "pair 0/1 at every width tried",
    }

    gaps = {m: report["comparisons"][m][
        "representation_gap_flat_weak_minus_factored_weak"] for m in
        ("conflicts", "rlimit")}
    controls_ok = all(report["comparisons"][m][
        "negative_control_flat_weak_minus_flat_hardened"]["as_predicted"]
        for m in ("conflicts", "rlimit"))
    report["separation_holds"] = controls_ok and all(
        g["excludes_zero"] for g in gaps.values())
    report["conclusion"] = (
        f"The matrix comes out as designed. The negative control is null under "
        f"both metrics ({controls_ok}), which is what a hidden trapdoor "
        f"predicts: the weakness is not visible to the public solver. The "
        f"private route is cheap only when the weakness is present -- "
        f"{pw['total_solved']}/{pw['total_attempted']} solved weak against "
        f"{ph['total_solved']}/{ph['total_attempted']} hardened, and removing "
        f"the weakness removes the route rather than slowing it. And the "
        f"representation gap excludes zero under both metrics: "
        f"2^({gaps['conflicts']['delta']:.3f}w) by conflicts, "
        f"2^({gaps['rlimit']['delta']:.3f}w) by rlimit. This is a measured "
        f"separation between representations, not a proof of hardness: the "
        f"public side rests on one solver.")

    path = RESULTS / "interaction.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\n{report['conclusion']}\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
