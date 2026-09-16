#!/usr/bin/env python3
"""Q2: the largest family that preserves Rainbow's cheap collision attack.

Derived from the proof in output/pdf/rainbow-pair-sum-cryptanalysis.tex, then
tested in both directions rather than asserted.

WHAT THE ATTACK ACTUALLY USES
  1. Injection moves the state along a FULL coset of a linear invariant. Per pair,
     h_i += a*x, h_j += b*x preserves lambda = b*h_i - a*h_j for any a, b. But the
     merge must solve a*(x' - x) = delta, so a has to be a unit: odd mod 2^w.
     Rainbow's (-1, +1) is one point in this family, not the family.
  2. The mixer at the merge boundary is separable, with the SAME pairing as the
     injection. Otherwise the other pair's lanes pick up the difference and a
     shared word cannot re-merge them. What each pair-map computes is free,
     provided the invariant it produces is not injective in x.
  3. Nothing non-separable sits between divergence and merge. After the merge
     the states are identical and every later operation is irrelevant.

CLAIMED UNCONSTRAINED: the non-merge mixer (mixB) including non-separable and
seeded, every multiplier and rotation, the IV, the use of the seed, finalization.

TESTS. Sufficiency members change what the derivation says is free and must
still collide. Necessity members violate one condition each and must fail. A
generic attack is used for all of them -- it knows only the injection
coefficients and pairing, and treats every mixer as a black box -- so a success
cannot be an artifact of Rainbow-specific algebra.
"""

import json
import pathlib
import random
import statistics
import sys
import time

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1]))

from models import rainbow as R                                  # noqa: E402
from models import wordops as W                                  # noqa: E402

RESULTS = HERE.parents[1] / "results"


def random_function(bits_in, bits_out, rng):
    """A fixed random function, realised lazily and deterministically."""
    key = rng.getrandbits(64)
    cache = {}
    mask = (1 << bits_out) - 1
    def f(v):
        out = cache.get(v)
        if out is None:
            z = (v * 0x9E3779B97F4A7C15 + key) & ((1 << 128) - 1)
            z ^= z >> 31; z = (z * 0xBF58476D1CE4E5B9) & ((1 << 128) - 1)
            z ^= z >> 29; z = (z * 0x94D049BB133111EB) & ((1 << 128) - 1)
            z ^= z >> 32
            out = cache[v] = z & mask
        return out
    return f


class Member:
    """A 4-lane, w-bit function built from the pieces the derivation names."""

    def __init__(self, name, w, *, pairs=((0, 1), (2, 3)), coeffs=((-1, 1), (1, -1)),
                 merge_mixer, other_mixer, iv, finalize, inject=None,
                 merge_pairs=None, expect):
        self.name, self.w, self.pairs, self.coeffs = name, w, pairs, coeffs
        self.merge_mixer, self.other_mixer = merge_mixer, other_mixer
        self.iv, self.finalize = iv, finalize
        self.custom_inject = inject
        self.expect = expect

    def inject(self, h, words):
        if self.custom_inject:
            return self.custom_inject(h, words)
        out = list(h)
        for (i, j), (a, b), x in zip(self.pairs, self.coeffs, words):
            out[i] = W.add(out[i], W.mul(a % (1 << self.w), x, self.w), self.w)
            out[j] = W.add(out[j], W.mul(b % (1 << self.w), x, self.w), self.w)
        return tuple(out)

    def hash(self, blocks, seed):
        h = self.iv(seed, len(blocks))
        for index, words in enumerate(blocks):
            h = self.inject(h, words)
            h = self.merge_mixer(h) if index % 2 == 0 else self.other_mixer(h, seed)
        return self.finalize(h, seed)

    def invariant0(self, h):
        (i, j), (a, b) = self.pairs[0], self.coeffs[0]
        w = self.w
        return W.sub(W.mul(b % (1 << w), h[i], w), W.mul(a % (1 << w), h[j], w), w)


def generic_attack(member, seed, rng, cap):
    """Knows only pairing and injection coefficients. Mixers are black boxes."""
    w = member.w
    iv = member.iv(seed, 2)
    table, evaluations = {}, 0
    while evaluations < cap:
        x = rng.getrandbits(w)
        s1 = member.merge_mixer(member.inject(iv, (x, 0)))
        evaluations += 1
        key = member.invariant0(s1)
        if key in table and table[key][0] != x:
            xa, sa = table[key]
            xb, sb = x, s1
            (i, _j), (a, _b) = member.pairs[0], member.coeffs[0]
            a %= (1 << w)
            if a % 2 == 0:                              # not a unit: no inverse
                delta = W.sub(sa[i], sb[i], w)
                sols = [d for d in range(1 << min(w, 12))
                        if W.mul(a, d, w) == delta]      # search small solutions
                if not sols:
                    return None, evaluations
                step = sols[0]
            else:
                step = W.mul(W.inv_odd(a, w), W.sub(sa[i], sb[i], w), w)
            m_a = [(xa, 0), (0, 0)]
            m_b = [(xb, 0), (step, 0)]
            return (m_a, m_b), evaluations
        table.setdefault(key, (x, s1))
    return None, evaluations


def build_members(w, rng):
    theta = R.default_theta(w)
    rainbow_iv = lambda seed, n: tuple(W.add(W.add(seed, n * 2, w), c, w) for c in (1, 2, 3, 5))
    def rainbow_final(h, seed):
        h = R.mix_b(h, theta, seed); h = R.mix_a(h, theta)
        h = R.mix_b(h, theta, seed); h = R.mix_a(h, theta)
        return h
    mixA = lambda h: R.mix_a(h, theta)
    mixB = lambda h, seed: R.permute(R.mix_b(h, theta, seed), theta)

    f01 = random_function(2 * w, 2 * w, rng)
    f23 = random_function(2 * w, 2 * w, rng)
    def random_separable(h):
        v = f01((h[0] << w) | h[1]); u = f23((h[2] << w) | h[3])
        return (v >> w, v & ((1 << w) - 1), u >> w, u & ((1 << w) - 1))
    fall = random_function(4 * w, 4 * w, rng)
    def random_nonseparable(h, seed=0):
        v = fall((((h[0] << w | h[1]) << w | h[2]) << w | h[3]) ^ seed)
        m = (1 << w) - 1
        return (v >> 3 * w & m, v >> 2 * w & m, v >> w & m, v & m)
    f02 = random_function(2 * w, 2 * w, rng)
    f13 = random_function(2 * w, 2 * w, rng)
    def separable_wrong_pairing(h):
        v = f02((h[0] << w) | h[2]); u = f13((h[1] << w) | h[3])
        m = (1 << w) - 1
        return (v >> w, u >> w, v & m, u & m)
    rnd_iv_f = random_function(2 * w, 4 * w, rng)
    def random_iv(seed, n):
        v = rnd_iv_f(((seed << 8) | n) & ((1 << 2 * w) - 1)); m = (1 << w) - 1
        return (v >> 3 * w & m, v >> 2 * w & m, v >> w & m, v & m)
    rnd_fin = random_function(4 * w, 4 * w, rng)
    def random_final(h, seed):
        return rnd_fin((((h[0] << w | h[1]) << w | h[2]) << w | h[3]) ^ seed)
    def hardened_inject(h, words):
        x, y = words
        return (W.sub(h[0], x, w), W.add(h[1], W.rotr(x, 1, w), w),
                W.add(h[2], y, w), W.sub(h[3], W.rotr(y, 1, w), w))

    base = dict(iv=rainbow_iv, finalize=rainbow_final,
                merge_mixer=mixA, other_mixer=mixB)
    return [
        Member("actual Rainbow (control)", w, expect=True, **base),
        Member("odd coefficients (3,5),(7,9)", w, coeffs=((3, 5), (7, 9)), expect=True, **base),
        Member("random separable merge mixer", w, expect=True,
               **{**base, "merge_mixer": random_separable}),
        Member("random NON-separable seeded mixB", w, expect=True,
               **{**base, "other_mixer": random_nonseparable}),
        Member("random IV + random finalization", w, expect=True,
               **{**base, "iv": random_iv, "finalize": random_final}),
        Member("all of the above at once", w, coeffs=((3, 5), (7, 9)), expect=True,
               merge_mixer=random_separable, other_mixer=random_nonseparable,
               iv=random_iv, finalize=random_final),
        Member("EVEN coefficient (2,1)", w, coeffs=((2, 1), (1, -1)), expect=False, **base),
        Member("NON-separable merge mixer", w, expect=False,
               **{**base, "merge_mixer": lambda h: random_nonseparable(h)}),
        Member("separable, WRONG pairing", w, expect=False,
               **{**base, "merge_mixer": separable_wrong_pairing}),
        Member("hardened injection (no invariant)", w, expect=False,
               **{**base, "inject": hardened_inject}),
    ]


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    report = {"question": "Q2: largest family preserving the cheap collision attack",
              "rows": [], "generated": time.strftime("%Y-%m-%dT%H:%M:%S")}
    all_as_predicted = True
    for w in (8, 12):
        rng = random.Random(2026 + w)
        for member in build_members(w, rng):
            wins, costs, trials = 0, [], 24
            for t in range(trials):
                seed = random.Random(t * 31 + w).getrandbits(w)
                result, ev = generic_attack(member, seed, random.Random(900 + t), cap=1 << (w + 6))
                if result:
                    m_a, m_b = result
                    if m_a != m_b and member.hash(m_a, seed) == member.hash(m_b, seed):
                        wins += 1
                        costs.append(ev)
            works = wins >= trials * 0.9
            as_predicted = works == member.expect
            all_as_predicted &= as_predicted
            med = statistics.median(costs) if costs else None
            row = {"w": w, "member": member.name, "predicted_to_work": member.expect,
                   "verified_collisions": f"{wins}/{trials}",
                   "median_evaluations": med, "as_predicted": as_predicted}
            report["rows"].append(row)
            print(f"w={w:>2} {'OK ' if as_predicted else 'XX '} {member.name:<36} "
                  f"predicted {'works' if member.expect else 'fails':<5}  "
                  f"verified {wins:>2}/{trials}  median evals {med}", flush=True)
    report["all_as_predicted"] = all_as_predicted
    (RESULTS / "og-q2-weak-family.json").write_text(json.dumps(report, indent=2))
    print("\nALL AS PREDICTED" if all_as_predicted else "\nSOME PREDICTIONS FAILED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
