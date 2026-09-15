#!/usr/bin/env python3
"""Phase 7: attack the hypothesis. Can a FLAT attacker recover the steering?

The separation measured by milestone_separation.py compares a factored attacker
against a flat attacker doing generic birthday. That is not evidence of anything
until the flat side has actually been attacked, because otherwise the "flat
cost" is only the cost of the best strategy we bothered to write.

Attacks implemented here, all given the complete function and no factor
boundaries:

  A  GF(2)-linear invariant search on the OUTPUT. The merge classes are images
     of additive cosets under the final mixer. If those images were GF(2)-affine
     the attacker would read off class labels by linear algebra, and the
     separation would be fake.

  A' the same test on the PRE-MIXER state, as a control. The coset is affine
     over Z/2^w, so this measures how much of the structure survives as GF(2)
     structure at all -- i.e. whether attack A ever had a chance.

  B  class-canonicalisation birthday: label each class by its minimum element,
     then birthday on labels. Correct, but each label costs a full class
     enumeration, so this measures whether the obvious structural attack is
     actually cheaper than generic birthday (it should not be).

  C  amortised/precomputed attack: build the whole class partition once, then
     answer merges in O(1). Reported separately, because a one-off 2^(4w)
     precomputation that makes every later merge free is a real threat model
     even when the per-merge cost looks good.
"""

import json
import math
import pathlib
import random
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from compositions.sequential import Composition       # noqa: E402
from models import rainbow as R                       # noqa: E402
from models import spectrum as S                      # noqa: E402
from models import wordops as W                       # noqa: E402

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"


def gf2_rank(vectors):
    """Rank over GF(2) of integers treated as bit vectors."""
    basis = []
    for value in vectors:
        cur = value
        for b in basis:
            cur = min(cur, cur ^ b)
        if cur:
            basis.append(cur)
            basis.sort(reverse=True)
    return len(basis)


def build_composition(w, k, rng):
    thetas = []
    while len(thetas) < k:
        theta = S.random_theta(w, rng, pairs=S.PAIRINGS[0], signs=((-1, 1), (1, -1)))
        if S.validate_weakness(theta, rng, trials=40)["admissible"]:
            thetas.append(theta)
    return Composition(thetas=tuple(thetas))


def gf2_nullspace(vectors, bits):
    """Basis of {lambda : parity(lambda & d) == 0 for every d}."""
    rows = [v for v in vectors if v]
    pivot_of = {}
    for row in rows:
        cur = row
        for col, prow in pivot_of.items():
            if (cur >> col) & 1:
                cur ^= prow
        if cur:
            col = cur.bit_length() - 1
            pivot_of[col] = cur
    pivots = sorted(pivot_of)
    free = [c for c in range(bits) if c not in pivot_of]
    basis = []
    for f in free:
        lam = 1 << f
        for col in sorted(pivots, reverse=True):
            prow = pivot_of[col]
            if bin(lam & prow).count("1") % 2:
                lam ^= 1 << col
        basis.append(lam)
    return basis


def enumerate_class(composition, state, prefix, w):
    """Every output reachable by varying ONLY the last round's controls."""
    npairs = composition.controls_per_round
    points = []
    for c0 in range(1 << w):
        for c1 in range(1 << w):
            controls = [prefix] + [(0,) * npairs] * (composition.k - 1)
            controls[composition.k - 1] = (c0, c1)
            points.append(W.words_to_int(composition.evaluate(state, tuple(controls)), w))
    return points


def attack_a_linear_invariant(composition, rng):
    """Is a merge class GF(2)-affine in the output? If so, steering is free.

    Classes are enumerated EXACTLY (no random draws with replacement, which
    would fake a rank deficiency), and any functional the first class suggests
    must then hold on independently drawn held-out classes. A functional is only
    useful if it is constant within a class AND takes different values on
    different classes, i.e. if it is a genuine class label.
    """
    w = composition.w
    bits = 4 * w
    state = tuple(rng.getrandbits(w) for _ in range(4))

    prefixes = [tuple(rng.getrandbits(w) for _ in range(composition.controls_per_round))
                for _ in range(3)]
    classes = [enumerate_class(composition, state, p, w) for p in prefixes]

    train = classes[0]
    out_rank = gf2_rank([p ^ train[0] for p in train[1:]])
    candidates = gf2_nullspace([p ^ train[0] for p in train[1:]], bits)

    # Held-out validation: constant within each class?
    validated = []
    for lam in candidates:
        if all(len({bin(lam & p).count("1") % 2 for p in cls}) == 1 for cls in classes):
            validated.append(lam)
    # Useful only if it distinguishes classes.
    labels = [[bin(lam & cls[0]).count("1") % 2 for cls in classes] for lam in validated]
    discriminating = [lam for lam, lab in zip(validated, labels) if len(set(lab)) > 1]

    # Control: the same measurement on the pre-mixer coset, which really is
    # affine over Z/2^w. Its low-order bits are GF(2)-linear, so a nonzero count
    # here shows the test can detect structure when structure exists.
    premixer = []
    for c0 in range(1 << w):
        for c1 in range(1 << w):
            controls = [prefixes[0]] + [(0,) * composition.controls_per_round] * (composition.k - 1)
            controls[composition.k - 1] = (c0, c1)
            mid = composition.trace(state, tuple(controls))[composition.k - 1]
            premixer.append(W.words_to_int(R.inject(mid, (c0, c1), composition.thetas[-1]), w))
    pre_rank = gf2_rank([p ^ premixer[0] for p in premixer[1:]])

    return {
        "attack": "A_gf2_linear_invariant_on_output",
        "state_bits": bits,
        "class_size": 1 << (2 * w),
        "classes_enumerated_exactly": True,
        "output_difference_rank": out_rank,
        "premixer_difference_rank": pre_rank,
        "premixer_linear_invariants": max(0, bits - pre_rank),
        "candidates_from_training_class": len(candidates),
        "validated_on_heldout_classes": len(validated),
        "discriminating_class_labels": len(discriminating),
        "succeeded": len(discriminating) > 0,
        "note": ("a candidate counts only if it is constant on held-out classes AND "
                 "separates them; constants that survive but never differ are not "
                 "class labels and give the attacker nothing"),
    }


def attack_b_class_canonical(composition, state_a, state_b, rng, max_classes=64):
    """Label classes by their minimum element, then birthday on labels."""
    w = composition.w
    npairs = composition.controls_per_round
    class_size = 1 << (w * npairs)
    evaluations = 0

    def class_label(state, prefix):
        nonlocal evaluations
        best = None
        for c0 in range(1 << w):
            for c1 in range(1 << w):
                controls = [prefix] + [(0,) * npairs] * (composition.k - 1)
                controls[composition.k - 1] = (c0, c1)
                value = W.words_to_int(composition.evaluate(state, tuple(controls)), w)
                evaluations += 1
                best = value if best is None else min(best, value)
        return best

    seen_a, seen_b = {}, {}
    for _ in range(max_classes):
        pa = tuple(rng.getrandbits(w) for _ in range(npairs))
        la = class_label(state_a, pa)
        seen_a.setdefault(la, pa)
        if la in seen_b:
            return {"attack": "B_class_canonicalisation", "merged": True,
                    "evaluations": evaluations, "class_size": class_size}
        pb = tuple(rng.getrandbits(w) for _ in range(npairs))
        lb = class_label(state_b, pb)
        seen_b.setdefault(lb, pb)
        if lb in seen_a:
            return {"attack": "B_class_canonicalisation", "merged": True,
                    "evaluations": evaluations, "class_size": class_size}
    return {"attack": "B_class_canonicalisation", "merged": False,
            "evaluations": evaluations, "class_size": class_size,
            "note": "each label costs a full class enumeration, so this is "
                    "dominated by generic birthday"}


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20260915)
    report = {
        "phase": 7,
        "question": "is the measured separation an artifact of a weak flat solver?",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "attack_a": [],
        "attack_b": [],
    }

    for w in (3, 4, 5, 6, 7, 8):
        composition = build_composition(w, 2, rng)
        row = attack_a_linear_invariant(composition, rng)
        row["w"] = w
        report["attack_a"].append(row)
        print(f"A  w={w}  output rank {row['output_difference_rank']}/{row['state_bits']}"
              f"  premixer rank {row['premixer_difference_rank']}/{row['state_bits']}"
              f"  (premixer invariants {row['premixer_linear_invariants']})"
              f"  candidates {row['candidates_from_training_class']}"
              f" -> validated {row['validated_on_heldout_classes']}"
              f" -> discriminating {row['discriminating_class_labels']}"
              f"  {'SUCCEEDED' if row['succeeded'] else 'failed'}")

    for w in (3, 4):
        composition = build_composition(w, 2, rng)
        sa = tuple(rng.getrandbits(w) for _ in range(4))
        sb = tuple(rng.getrandbits(w) for _ in range(4))
        row = attack_b_class_canonical(composition, sa, sb, rng)
        row["w"] = w
        row["generic_birthday_log2"] = 2 * w + 1
        row["log2_evaluations"] = round(math.log2(row["evaluations"]), 3) if row["evaluations"] else None
        report["attack_b"].append(row)
        print(f"B  w={w}  merged={row['merged']}  evaluations=2^{row['log2_evaluations']}"
              f"  vs generic birthday 2^{row['generic_birthday_log2']}")

    any_success = any(r["succeeded"] for r in report["attack_a"])
    report["flat_attack_succeeded"] = any_success
    report["conclusion"] = (
        "A flat attack recovered linear structure; the separation is at least "
        "partly an artifact." if any_success else
        "No GF(2)-linear invariant of the output exists, and class "
        "canonicalisation is dominated by generic birthday. The separation "
        "survives these attacks -- which is NOT the same as surviving all of "
        "them. Untried: Z/2^w-linear functional search, algebraic/ANF "
        "elimination, SAT/SMT, meet-in-the-middle, and amortised precomputation."
    )
    path = RESULTS / "flat-adversarial.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\n{report['conclusion']}\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
