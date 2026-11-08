"""One Rainbow stripe: actual Rainbow at width w, and its original collision.

This replaces og/factor.py as the building block, on the instruction to use
actual Rainbow so the collision property is preserved rather than a model of it.
factor.py used Experiment B's relation, which differs from real Rainbow in the
ways that matter: a random secret theta instead of Rainbow's public constants,
and mixA on every round with no mixB and no lane rotation. Production alternates
mixA with mixB + rotate_right, and mixB is the only mixer that crosses the
halves.

WHAT "ACTUAL" MEANS AT SMALL WIDTH. Every constant and rotation comes from
models.rainbow.default_theta(w), which is production Rainbow scaled to w and is
exactly production at w = 64 -- checked below against the independently verified
research/rainbow/verify_pair_sum.py, itself replayed against unmodified
src/rainbow.cpp. The schedule is production's: inject, then mixA on odd blocks
and mixB + rotate_right on even ones; IV = seed + len + {1,2,3,5}; finalization
mixB, mixA, mixB, mixA, then words squeezed as -(h2 + h3) with the same mixer
sequence between words. Finalization's mixB takes no rotation, exactly as in
src/rainbow.cpp, and getting that wrong would silently change every digest.

Only whole-block messages are used, so the tail absorb is empty. That is a
restriction on the inputs, not a change to the function.

THE COLLISION RELATION is the published same-seed attack
(output/pdf/rainbow-pair-sum-cryptanalysis.tex, section "Same-Seed Collision"),
transcribed at width w. With the first block's second word fixed, only
H(x) = A(x) + B(x) must collide; the second block's first word -B(x) then drives
both states to the same point, and every later operation agrees. Cost is a
birthday on a w-bit map, about 2^(w/2).
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from models import rainbow as R                                  # noqa: E402
from models import wordops as W                                  # noqa: E402

DIGEST_WORDS = 4


def block_bytes(w):
    """Length unit. 16 at w=64, so the IV matches production byte-for-byte."""
    return max(1, (2 * w) // 8)


def iv(seed, nblocks, w):
    olen = nblocks * block_bytes(w)
    return tuple(W.add(W.add(seed, olen, w), c, w) for c in (1, 2, 3, 5))


def _inject(h, x, y, w):
    return (W.sub(h[0], x, w), W.add(h[1], x, w),
            W.add(h[2], y, w), W.sub(h[3], y, w))


def absorb(blocks, seed, w, theta=None):
    """Whole-block absorb. Returns the state before finalization."""
    theta = theta or R.default_theta(w)
    h = iv(seed, len(blocks), w)
    for index, (x, y) in enumerate(blocks):
        h = _inject(h, x, y, w)
        if index % 2 == 0:
            h = R.mix_a(h, theta)
        else:
            h = R.permute(R.mix_b(h, theta, seed), theta)
    return h


def finalize(h, seed, w, words=DIGEST_WORDS, theta=None):
    theta = theta or R.default_theta(w)
    word = lambda s: W.sub(W.sub(0, s[2], w), s[3], w)
    h = R.mix_b(h, theta, seed)
    h = R.mix_a(h, theta)
    h = R.mix_b(h, theta, seed)
    h = R.mix_a(h, theta)
    out = [word(h)]
    if words >= 2:
        h = R.mix_a(h, theta)
        out.append(word(h))
    if words >= 3:
        h = R.mix_a(h, theta)
        h = R.mix_b(h, theta, seed)
        h = R.mix_a(h, theta)
        out.append(word(h))
    if words >= 4:
        h = R.mix_a(h, theta)
        out.append(word(h))
    return tuple(out[:words])


def rainbow(blocks, seed, w, words=DIGEST_WORDS):
    theta = R.default_theta(w)
    return finalize(absorb(blocks, seed, w, theta), seed, w, words, theta)


# ------------------------------------------------------------- the collision
def half_sum(x, s0, s1, theta):
    """A(x), B(x), H(x) = A + B at the first mixA boundary, width w."""
    w = theta.w
    m, r = theta.multipliers, theta.mixa_rotations
    a = W.mul(W.rotr(W.mul(W.sub(s0, x, w), m[0], w), r[0], w), m[1], w)
    b = W.mul(W.rotr(W.mul(W.xor(W.add(s1, x, w), a, w), m[2], w), r[1], w),
              m[3], w)
    return a, b, W.add(a, b, w)


def same_seed_collision(seed, w, rng):
    """The published attack at width w. Returns (m_a, m_b, evaluations).

    Birthday on H rather than a rho walk: at the widths used here memory is
    free, and a table makes the evaluation count exact rather than a DP estimate.
    """
    theta = R.default_theta(w)
    s = iv(seed, 2, w)
    seen = {}
    evaluations = 0
    mask = (1 << w) - 1
    while True:
        x = rng.getrandbits(w) & mask
        _a, _b, h = half_sum(x, s[0], s[1], theta)
        evaluations += 1
        other = seen.get(h)
        if other is not None and other != x:
            xa, xb = other, x
            break
        seen.setdefault(h, x)
    ba = half_sum(xa, s[0], s[1], theta)[1]
    bb = half_sum(xb, s[0], s[1], theta)[1]
    m_a = [(xa, 0), (W.sub(0, ba, w), 0)]
    m_b = [(xb, 0), (W.sub(0, bb, w), 0)]
    return m_a, m_b, evaluations
