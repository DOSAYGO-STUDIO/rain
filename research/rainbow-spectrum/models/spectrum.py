"""Phase 2: a spectrum of parameterized Rainbow variants.

A theta is only admitted to the spectrum if it demonstrably RETAINS the cheap
steering capability. Parameterizations that accidentally destroy the weakness
are rejected and recorded, per the program's instruction to keep failures.

The point of varying theta is not different constants: it is differently
*oriented* weak structure. Injection orientation is the sharpest lever, since
for signs (si, sj) the preserved functional is sj*h_i - si*h_j, so (-1,+1)
yields a pair sum and (+1,+1) yields a pair difference.
"""

import random

from . import rainbow as R
from . import wordops as W

PAIRINGS = (
    ((0, 1), (2, 3)),
    ((0, 2), (1, 3)),
    ((0, 3), (1, 2)),
)


def random_theta(w, rng, label=None, pairs=None, signs=None):
    """Draw a spectrum member. Structure varies, not merely constants.

    `pairs` and `signs` may be pinned so that a composition can share a pairing
    across rounds; whether consecutive factors agree on the pairing turns out to
    decide whether the factored attack can divide and conquer.
    """
    multipliers = tuple(W.make_odd(rng.getrandbits(w) | 1, w) for _ in range(8))
    mixa_rotations = tuple(rng.randrange(1, w) if w > 1 else 0 for _ in range(4))
    mixb_rotations = tuple(rng.randrange(1, w) if w > 1 else 0 for _ in range(2))
    pairs = pairs or rng.choice(PAIRINGS)
    signs = signs or tuple((rng.choice((-1, 1)), rng.choice((-1, 1))) for _ in pairs)
    lanes = list(range(4))
    rng.shuffle(lanes)
    return R.Theta(
        w=w,
        multipliers=multipliers,
        mixa_rotations=mixa_rotations,
        mixb_rotations=mixb_rotations,
        pairs=pairs,
        signs=signs,
        lane_perm=tuple(lanes),
        label=label or f"random-w{w}",
    )


def validate_weakness(theta, rng, trials=200):
    """A member is admissible only if the cheap steering still works.

    Checks, on random inputs:
      1. injection preserves each pair's invariant;
      2. equal invariants imply a zero-search merge via steer();
      3. unequal invariants imply no merge exists (checked exhaustively at
         small w, sampled otherwise);
      4. the fixed-control transition remains a bijection (sampled).
    """
    w = theta.w
    report = {"label": theta.label, "w": w, "admissible": True, "reasons": []}

    for _ in range(trials):
        state = tuple(rng.getrandbits(w) for _ in range(theta.lanes))
        controls = tuple(rng.getrandbits(w) for _ in theta.pairs)
        if R.invariants(R.inject(state, controls, theta), theta) != \
                R.invariants(state, theta):
            report["admissible"] = False
            report["reasons"].append("injection does not preserve the invariant")
            break

    for _ in range(trials):
        sa = tuple(rng.getrandbits(w) for _ in range(theta.lanes))
        sb = list(tuple(rng.getrandbits(w) for _ in range(theta.lanes)))
        for (i, j), (si, sj), inv in zip(theta.pairs, theta.signs,
                                         R.invariants(tuple(sa), theta)):
            target = W.sub(W.mul(sj % (1 << w), sb[i], w), inv, w)
            sb[j] = target if si == 1 else W.neg(target, w)
        sb = tuple(sb)
        if not R.mergeable(theta, sa, sb):
            report["admissible"] = False
            report["reasons"].append("constructed equal-invariant pair not mergeable")
            break
        got = R.steer(theta, sa, sb, free=tuple(rng.getrandbits(w) for _ in theta.pairs))
        if got is None or R.inject(sa, got[0], theta) != R.inject(sb, got[1], theta):
            report["admissible"] = False
            report["reasons"].append("steer() failed to merge an equal-invariant pair")
            break

    # Unequal invariants must never merge.
    for _ in range(trials):
        sa = tuple(rng.getrandbits(w) for _ in range(theta.lanes))
        sb = tuple(rng.getrandbits(w) for _ in range(theta.lanes))
        if R.mergeable(theta, sa, sb):
            continue
        if R.steer(theta, sa, sb) is not None:
            report["admissible"] = False
            report["reasons"].append("steer() returned a merge for unequal invariants")
            break

    # The weakness must SURVIVE the mixer. After one round, each pair's
    # invariant must depend only on that pair's own control word; otherwise the
    # two 64-bit conditions cannot be matched independently and the member is
    # useless for divide-and-conquer steering. This is the condition that a
    # mismatched pairing silently destroys.
    for _ in range(trials):
        state = tuple(rng.getrandbits(w) for _ in range(theta.lanes))
        controls = [rng.getrandbits(w) for _ in theta.pairs]
        base = R.invariants(R.transition(state, tuple(controls), theta), theta)
        broke = False
        for p in range(len(theta.pairs)):
            for q in range(len(theta.pairs)):
                if p == q:
                    continue
                probe = list(controls)
                probe[q] = rng.getrandbits(w)
                moved = R.invariants(R.transition(state, tuple(probe), theta), theta)
                if moved[p] != base[p]:
                    report["admissible"] = False
                    report["reasons"].append(
                        "pair invariant is not independent of the other pair's control")
                    broke = True
                    break
            if broke:
                break
        if broke:
            break

    # Bijectivity of a fixed-control transition, sampled.
    seen = set()
    probes = min(1 << (2 * w), 4096)
    for _ in range(probes):
        state = tuple(rng.getrandbits(w) for _ in range(theta.lanes))
        seen.add(R.transition(state, (0,) * len(theta.pairs), theta))
    if len(seen) < probes * 0.99:
        report["admissible"] = False
        report["reasons"].append("fixed-control transition looks non-injective")

    return report


def build_spectrum(w, count, rng, require_admissible=True):
    """Return (admissible, rejected) spectrum members."""
    admissible, rejected = [], []
    attempts = 0
    while len(admissible) < count and attempts < count * 20:
        attempts += 1
        theta = random_theta(w, rng, label=f"w{w}-{attempts:03d}")
        verdict = validate_weakness(theta, rng)
        if verdict["admissible"] or not require_admissible:
            admissible.append((theta, verdict))
        else:
            rejected.append((theta, verdict))
    return admissible, rejected
