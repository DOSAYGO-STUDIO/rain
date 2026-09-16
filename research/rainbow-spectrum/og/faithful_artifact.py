#!/usr/bin/env python3
"""Public artifact for FAITHFUL B: production's alternating schedule in gates.

Original B's public circuit is mixA-only, so it is pair-separable end to end --
the 4w-bit equality splits into two independent 2w-bit halves and a solver may
exploit that. Faithful B puts mixB + rotate_right after the merge round, which
crosses the pairs, so the split is no longer available publicly. The privileged
route is unaffected (it merges at the injection, before that mixer), so any rise
in the public exponent is a rise in the gap.

theta is compiled into gates and never appears as a parameter, exactly as in
models/public_artifact.py.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from models.aig import Aig, FALSE                                # noqa: E402


class FaithfulArtifact:
    def __init__(self, aig, groups, out_a, out_b, meta):
        self.aig, self.groups = aig, groups
        self.out_a, self.out_b, self.meta = out_a, out_b, meta

    def _assign(self, values):
        a = {}
        for name, lits in self.groups.items():
            for lit, bit in zip(lits, values[name]):
                a[lit] = bit
        return a

    def eval_side(self, side, **values):
        bits = self.aig.evaluate(self.out_a if side == "a" else self.out_b,
                                 self._assign(values))
        w, lanes = self.meta["w"], 4
        return tuple(sum(bits[l * w + i] << i for i in range(w))
                     for l in range(lanes))


def build(thetas, S, T, t, seed):
    w = thetas[0].w
    aig = Aig()
    groups = {
        "pa": [aig.input(f"pa{i}") for i in range(2 * t)],
        "pb": [aig.input(f"pb{i}") for i in range(2 * t)],
        "mb": [aig.input(f"mb{i}") for i in range(2 * w)],
    }
    words = lambda g, width: [groups[g][i * width:(i + 1) * width] for i in range(2)]
    widen = lambda word: list(word) + [FALSE] * (w - len(word))

    def mix_a(state, theta):
        m, r = theta.multipliers, theta.mixa_rotations
        h0, h1, h2, h3 = state
        a = aig.mul_const(aig.rotr(aig.mul_const(h0, m[0], w), r[0]), m[1], w)
        b = aig.mul_const(aig.rotr(aig.mul_const(aig.xor_word(h1, a), m[2], w), r[1]), m[3], w)
        c = aig.mul_const(aig.rotr(aig.mul_const(h2, m[4], w), r[2]), m[5], w)
        d = aig.mul_const(aig.rotr(aig.mul_const(aig.xor_word(h3, c), m[6], w), r[3]), m[7], w)
        return [a, b, c, d]

    def mix_b_rot(state, theta):
        m, r = theta.multipliers, theta.mixb_rotations
        h0, h1, h2, h3 = state
        a = aig.mul_const(aig.rotr(aig.mul_const(h1, m[6], w), r[0]), m[7], w)
        u = aig.xor_word(h2, aig.add(a, aig.const_word(seed, w)))
        b = aig.mul_const(aig.rotr(aig.mul_const(u, m[2], w), r[1]), m[3], w)
        out = [h0, b, a, h3]
        return [out[i] for i in theta.lane_perm]        # rotate_right

    def inject(state, cx, cy):
        return [aig.sub(state[0], cx), aig.add(state[1], cx),
                aig.add(state[2], cy), aig.sub(state[3], cy)]

    const = lambda v: [aig.const_word(x, w) for x in v]
    zero = aig.const_word(0, w)

    sa = const(S)
    pa = words("pa", t)
    sa = mix_a(inject(sa, widen(pa[0]), widen(pa[1])), thetas[0])
    sa = mix_b_rot(inject(sa, zero, zero), thetas[-1])

    sb = const(T)
    pb = words("pb", t)
    sb = mix_a(inject(sb, widen(pb[0]), widen(pb[1])), thetas[0])
    mb = words("mb", w)
    sb = mix_b_rot(inject(sb, mb[0], mb[1]), thetas[-1])

    out_a = [bit for word in sa for bit in word]
    out_b = [bit for word in sb for bit in word]
    return FaithfulArtifact(aig, groups, out_a, out_b,
                            {"w": w, "t": t, "gates": len(aig.ands)})
