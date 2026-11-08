#!/usr/bin/env python3
"""Earliest possible disproof attempt: can a FLAT attacker recover the steering?

The research program's attitude is to disprove the hypothesis as cheaply as
possible.  The cheapest place to try is k=1, a single factor.

Rainbow's steering rests on a LINEAR invariant preserved by an AFFINE control
action.  A flat attacker who can evaluate the round -- and who is explicitly
given the complete function, not a black box -- can recover the control
direction by differencing two evaluations, and the invariant follows by linear
algebra.  No knowledge of theta is used or needed.

If this succeeds, then k=1 exhibits NO factored-vs-flat separation, and any
separation the program hopes for must come entirely from composition.  That is a
useful negative result: it tells us where not to look.
"""

import json
import pathlib
import random
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from models import rainbow as R          # noqa: E402
from models import wordops as W          # noqa: E402

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"


def recover_control_directions(evaluate, lanes, w, pairs):
    """Recover each control's direction vector using 2 evaluations per pair.

    `evaluate(state, controls) -> state` is injection only (the attacker can
    isolate it at k=1 because no mixer has been applied yet).  Returns one
    direction vector per control.
    """
    base_state = (0,) * lanes
    zero = (0,) * pairs
    base = evaluate(base_state, zero)
    directions = []
    evaluations = 1
    for index in range(pairs):
        controls = [0] * pairs
        controls[index] = 1
        moved = evaluate(base_state, tuple(controls))
        evaluations += 1
        directions.append(tuple(W.sub(moved[i], base[i], w) for i in range(lanes)))
    return directions, evaluations


def invariant_from_direction(direction, w, lanes):
    """Find a linear functional annihilating the control direction.

    Over Z/2^w, for a direction supported on lanes (i, j) with unit entries,
    lambda = (d_j, -d_i) on those lanes annihilates it:
        d_j*d_i - d_i*d_j = 0.
    """
    support = [i for i in range(lanes) if direction[i] != 0]
    if len(support) != 2:
        return None
    i, j = support
    lam = [0] * lanes
    lam[i] = direction[j]
    lam[j] = W.neg(direction[i], w)
    return tuple(lam)


def apply_functional(lam, state, w):
    total = 0
    for coefficient, word in zip(lam, state):
        total = W.add(total, W.mul(coefficient, word, w), w)
    return total


def probe(w, trials=500, seed=20260915):
    theta = R.default_theta(w)
    rng = random.Random(seed)

    def evaluate(state, controls):
        return R.inject(state, controls, theta)

    directions, evaluations = recover_control_directions(
        evaluate, theta.lanes, w, len(theta.pairs))

    recovered = [invariant_from_direction(d, w, theta.lanes) for d in directions]
    if any(lam is None for lam in recovered):
        return {"w": w, "recovered": False, "reason": "direction not a 2-lane vector"}

    # The recovered functionals must be invariant under every control, and must
    # reproduce the true steering capability.
    invariant_ok = True
    for _ in range(trials):
        state = tuple(rng.getrandbits(w) for _ in range(theta.lanes))
        controls = tuple(rng.getrandbits(w) for _ in theta.pairs)
        moved = R.inject(state, controls, theta)
        for lam in recovered:
            if apply_functional(lam, state, w) != apply_functional(lam, moved, w):
                invariant_ok = False

    # Does the recovered invariant predict mergeability as well as theta does?
    agreements = 0
    for _ in range(trials):
        sa = tuple(rng.getrandbits(w) for _ in range(theta.lanes))
        sb = tuple(rng.getrandbits(w) for _ in range(theta.lanes))
        truth = R.mergeable(theta, sa, sb)
        guess = all(apply_functional(lam, sa, w) == apply_functional(lam, sb, w)
                    for lam in recovered)
        agreements += (truth == guess)

    true_invariants = [
        # Rainbow's own functionals, for comparison.
        tuple(1 if i in pair else 0 for i in range(theta.lanes))
        for pair in theta.pairs
    ]
    return {
        "w": w,
        "recovered": True,
        "evaluations_used": evaluations,
        "recovered_functionals": [list(lam) for lam in recovered],
        "reference_pair_sum_functionals": [list(t) for t in true_invariants],
        "invariant_holds_on_random_states": invariant_ok,
        "mergeability_agreement": f"{agreements}/{trials}",
        "agrees_everywhere": agreements == trials,
    }


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    report = {
        "probe": "flat_invariant_recovery_k1",
        "question": "at k=1, can a flat attacker obtain the steering capability?",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "widths": [],
    }
    for w in (4, 8, 16, 32, 64):
        row = probe(w)
        report["widths"].append(row)
        print(f"w={row['w']:>3}  recovered={row['recovered']}  "
              f"evaluations={row.get('evaluations_used')}  "
              f"invariant_holds={row.get('invariant_holds_on_random_states')}  "
              f"mergeability={row.get('mergeability_agreement')}")
        if row.get("recovered"):
            print(f"        recovered functionals: {row['recovered_functionals']}")

    every = all(r.get("recovered") and r.get("agrees_everywhere")
                for r in report["widths"])
    report["k1_separation_exists"] = not every
    report["conclusion"] = (
        "NO separation at k=1: a flat attacker recovers an equivalent steering "
        "capability in a constant number of evaluations, independent of w. Any "
        "factored-vs-flat separation must therefore come from composition."
        if every else
        "Flat recovery failed somewhere; investigate before proceeding."
    )
    path = RESULTS / "flat-invariant-probe.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\n{report['conclusion']}\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
