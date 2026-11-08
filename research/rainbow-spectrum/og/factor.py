"""One weak Rainbow factor: its public circuit and its private witness.

A factor is Experiment B's relation, used as a building block rather than as the
whole scheme. Experiment B is frozen (FROZEN-B.md), so nothing here modifies it:
round logic is imported read-only, and the private solver is re-implemented only
because B's privileged_solve discards the witness it finds and the OG needs that
witness to stitch.

THE FACTOR RELATION. Inputs y = (prefix_A, prefix_B, merge_B). The residual
r(y) = side_A(y) XOR side_B(y) is 4w bits, and a witness is any y with r(y) = 0.
Written as a residual so that k factors compose into one system "all residuals
vanish", which is the shape every composition family below shares.

PRIVATE COST is exactly 4 * 2^(w/2) round evaluations, measured in
privileged-scaling.json to hold from w=12 to w=32. That is the number the OG is
built to keep: it must not grow with k, only multiply by it.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "attacks"))

from models import rainbow as R                                  # noqa: E402
from models import wordops as W                                  # noqa: E402
from models.aig import FALSE                                     # noqa: E402
from experiment_b import evaluate, inject_weak, plant, round_fwd  # noqa: E402


def input_bits(w, t, npairs=2, k_rounds=2):
    """Width of one factor's witness vector y, and its layout."""
    pa = (k_rounds - 1) * npairs * t
    pb = (k_rounds - 1) * npairs * t
    mb = npairs * w
    return pa + pb + mb, {"pa": pa, "pb": pb, "mb": mb}


def new_factor(w, t, rng):
    """A fresh weak factor. Returns the secret challenge (theta + public states)."""
    return plant(w, 2, t, rng, False)


# --------------------------------------------------------------- private route
def private_witness(challenge, t):
    """Sigma-match, then force the merge. Returns (y_words, evaluations, ok).

    Mirrors experiment_b.privileged_solve step for step, but returns the witness.
    Cost: 2 sides x npairs x 2^t round evaluations = 4 * 2^(w/2).
    """
    thetas = challenge["thetas"]
    w = thetas[0].w
    npairs = len(thetas[0].pairs)
    last = thetas[-1]
    evaluations = 0

    books = {}
    for side, state in (("a", challenge["S"]), ("b", challenge["T"])):
        for pair_index in range(npairs):
            book = {}
            for value in range(1 << t):
                controls = [0] * npairs
                controls[pair_index] = value
                moved = round_fwd(state, tuple(controls), thetas[0], False)
                evaluations += 1
                book.setdefault(R.invariants(moved, last)[pair_index], value)
            books[(side, pair_index)] = book

    chosen_a, chosen_b = [0] * npairs, [0] * npairs
    for pair_index in range(npairs):
        shared = set(books[("a", pair_index)]) & set(books[("b", pair_index)])
        if not shared:
            return None, evaluations, False
        key = min(shared)                    # deterministic, not set-order
        chosen_a[pair_index] = books[("a", pair_index)][key]
        chosen_b[pair_index] = books[("b", pair_index)][key]

    a = round_fwd(challenge["S"], tuple(chosen_a), thetas[0], False)
    b = round_fwd(challenge["T"], tuple(chosen_b), thetas[0], False)
    a = inject_weak(a, challenge["merge_a"], last)
    merge_b = []
    for (i, _j), (si, _sj) in zip(last.pairs, last.signs):
        delta = W.sub(a[i], b[i], w)
        merge_b.append(delta if si == 1 else W.sub(0, delta, w))

    ok = (evaluate(thetas, challenge["T"], (tuple(chosen_b),), tuple(merge_b),
                   False)
          == evaluate(thetas, challenge["S"], (tuple(chosen_a),),
                      challenge["merge_a"], False))
    return {"pa": tuple(chosen_a), "pb": tuple(chosen_b),
            "mb": tuple(merge_b)}, evaluations, ok


def witness_to_bits(witness, w, t):
    """Pack a witness into the factor's y bit-vector, matching circuit layout."""
    bits = []
    for word in witness["pa"]:
        bits += [(word >> b) & 1 for b in range(t)]
    for word in witness["pb"]:
        bits += [(word >> b) & 1 for b in range(t)]
    for word in witness["mb"]:
        bits += [(word >> b) & 1 for b in range(w)]
    return bits


# ---------------------------------------------------------------- public circuit
def residual_circuit(aig, challenge, t, y):
    """Gates for r(y) = side_A XOR side_B, over caller-supplied input literals.

    Same round arithmetic as models/public_artifact.build, but the inputs are
    handed in rather than declared, so a composition can drive y from a mixing
    layer instead of from fresh inputs. theta is read here and compiled away.
    """
    thetas = challenge["thetas"]
    w = thetas[0].w
    npairs = len(thetas[0].pairs)
    k = len(thetas)
    _, layout = input_bits(w, t, npairs, k)

    cursor = 0
    def take(count):
        nonlocal cursor
        out = y[cursor:cursor + count]
        cursor += count
        return out

    pa_bits, pb_bits, mb_bits = take(layout["pa"]), take(layout["pb"]), take(layout["mb"])
    words = lambda bits, width, n: [bits[i * width:(i + 1) * width] for i in range(n)]
    widen = lambda word, width: list(word) + [FALSE] * (w - width)

    def mix(state, theta):
        m, r = theta.multipliers, theta.mixa_rotations
        out = list(state)
        for index, (i, j) in enumerate(theta.pairs):
            m0, m1, m2, m3 = m[4 * index:4 * index + 4]
            r0, r1 = r[2 * index], r[2 * index + 1]
            a = aig.mul_const(aig.rotr(aig.mul_const(state[i], m0, w), r0), m1, w)
            b = aig.mul_const(aig.rotr(aig.mul_const(aig.xor_word(state[j], a),
                                                     m2, w), r1), m3, w)
            out[i], out[j] = a, b
        return out

    def rnd(state, controls, theta):
        out = list(state)
        for (i, j), (si, sj), x in zip(theta.pairs, theta.signs, controls):
            out[i] = aig.add(out[i], x) if si == 1 else aig.sub(out[i], x)
            out[j] = aig.add(out[j], x) if sj == 1 else aig.sub(out[j], x)
        return mix(out, theta)

    const = lambda values: [aig.const_word(v, w) for v in values]

    state_a = const(challenge["S"])
    state_a = rnd(state_a, [widen(x, t) for x in words(pa_bits, t, npairs)], thetas[0])
    state_a = rnd(state_a, [aig.const_word(v, w) for v in challenge["merge_a"]], thetas[-1])

    state_b = const(challenge["T"])
    state_b = rnd(state_b, [widen(x, t) for x in words(pb_bits, t, npairs)], thetas[0])
    state_b = rnd(state_b, words(mb_bits, w, npairs), thetas[-1])

    return [aig.xor(x, y_) for wa, wb in zip(state_a, state_b)
            for x, y_ in zip(wa, wb)]
