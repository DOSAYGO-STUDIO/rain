#!/usr/bin/env python3
"""The Experiment B matrix, rebuilt across a public/private boundary that exists.

The previous version of this table (results/interaction.json) is void. Its flat
row came from public_solve, which was handed challenge["thetas"] and built its
formula out of the secret multipliers, rotations, pairs and signs. So it
compared generic SMT against a specialised algorithm holding identical
information: an algorithmic gap, not a representation gap, and no amount of
careful statistics on top of it could have made it one.

Everything in this table is measured across the repaired boundary. The flat row
comes from attackers holding PublicArtifact and nothing else -- a bit-level
circuit, Tseitin-encoded, with variable numbering, clause order and literal
order shuffled -- validated by attacks/public_boundary.py, which checks
exactness on every enumerated input at toy widths and greps the serialised bytes
for secret values. The factored row comes from the privileged algorithm, whose
cost is exactly 4*2^(w/2) evaluations on every instance.

THE FLAT CELL TAKES THE BEST PUBLIC ATTACK, not the average and not the most
convenient. Reporting anything else would be grading the construction against a
weak adversary of our own choosing. Three independent SAT solvers and an
explicit meet-in-the-middle all ran; the cell is whichever did best.

WHAT IS ALREADY KNOWN TO LEAK, and it is in the table rather than a footnote:
the pairing. Fifteen public evaluations recover it, because mix_a's
pair-separability is visible from outside. Any exact public artifact leaks it.
"""

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve()
RESULTS = HERE.parents[1] / "results"


def main():
    need = ("public-sat-scaling.json", "public-mitm.json",
            "privileged-scaling.json", "theta-recovery.json")
    for name in need:
        if not (RESULTS / name).exists():
            print(f"missing {name}")
            return 1
    sat = json.loads((RESULTS / "public-sat-scaling.json").read_text())
    mitm = json.loads((RESULTS / "public-mitm.json").read_text())
    priv = json.loads((RESULTS / "privileged-scaling.json").read_text())
    leak = json.loads((RESULTS / "theta-recovery.json").read_text())

    rows = {}
    for label, entry in sat["variants"].items():
        solver, variant = label.split("/")
        if entry["beta"] is not None:
            rows.setdefault(variant, []).append((f"sat/{solver}", entry["beta"]))
    if mitm.get("beta_public_mitm"):
        rows.setdefault("weak", []).append(("mitm", mitm["beta_public_mitm"]))

    report = {
        "analysis": "corrected_interaction",
        "supersedes": "interaction.json, whose flat row used public_solve and "
                      "therefore held the secret",
        "boundary": "flat attackers hold PublicArtifact only "
                    "(attacks/public_boundary.json)",
        "flat_attacks": {k: dict(v) for k, v in rows.items()},
        "known_public_leak": {
            "what": "the pairing",
            "cost": f"{leak['queries_per_recovery']} public evaluations",
            "recovered": leak["recovered"],
            "consequence": leak["consequence"],
        },
        "cells": {}, "comparisons": {},
    }

    for variant in ("weak", "hardened"):
        attacks = rows.get(variant, [])
        best_name, best = min(attacks, key=lambda kv: kv[1]) if attacks else (None, None)
        report["cells"][variant] = {
            "flat_best_beta": best, "flat_best_attack": best_name,
            "flat_all": dict(attacks),
        }

    pw, ph = priv["variants"]["weak"], priv["variants"]["hardened"]
    report["cells"]["weak"]["factored_beta"] = pw["beta_matched_widths"]
    report["cells"]["hardened"]["factored_beta"] = None
    report["cells"]["hardened"]["factored_status"] = (
        f"no shortcut: {ph['total_solved']}/{ph['total_attempted']} solved")

    weak, hard = report["cells"]["weak"], report["cells"]["hardened"]
    gap = (round(weak["flat_best_beta"] - weak["factored_beta"], 4)
           if weak["flat_best_beta"] else None)
    control = (round(weak["flat_best_beta"] - hard["flat_best_beta"], 4)
               if weak["flat_best_beta"] and hard["flat_best_beta"] else None)
    report["comparisons"] = {
        "representation_gap_flat_minus_factored_weak": gap,
        "negative_control_flat_weak_minus_flat_hardened": control,
        "weakness_gap": f"{pw['total_solved']}/{pw['total_attempted']} vs "
                        f"{ph['total_solved']}/{ph['total_attempted']}",
    }

    print("                    weak                      hardened")
    print(f"  flat (best)   2^{weak['flat_best_beta']}w "
          f"({weak['flat_best_attack']})".ljust(42)
          + f"2^{hard['flat_best_beta']}w ({hard['flat_best_attack']})")
    print(f"  factored      2^{weak['factored_beta']}w".ljust(42)
          + f"{hard['factored_status']}")
    print(f"\n  representation gap (flat - factored, weak): {gap:+.4f}")
    print(f"  negative control (flat weak - flat hardened): {control:+.4f}")
    print(f"  all flat attacks: {json.dumps(report['flat_attacks'])}")
    print(f"  known public leak: the pairing, "
          f"{report['known_public_leak']['cost']}")

    report["conclusion"] = (
        f"Across a boundary that now exists, the best public attack scales as "
        f"2^({weak['flat_best_beta']}w) against a privileged route of exactly "
        f"2^(0.5w), a gap of {gap:+.4f} in the exponent. The negative control "
        f"holds: weak and hardened look alike publicly ({control:+.4f}), which "
        f"is what a hidden trapdoor predicts rather than evidence against one. "
        f"Removing the weakness does not slow the private route, it deletes it "
        f"({report['comparisons']['weakness_gap']}). The pairing leaks publicly "
        f"and is not repairable by better compilation. This is a toy candidate "
        f"separation against the strongest attacks run so far, not security: "
        f"the widths are small, the flat row is a best-of-four rather than a "
        f"lower bound, and no attack here rules out a cleverer public "
        f"algorithm.")
    path = RESULTS / "corrected-interaction.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\n{report['conclusion']}\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
