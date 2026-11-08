"""Actual-Rainbow stripes sharing one message, each under its own seed.

The composition: D(m) = (Rainbow_s1(m), ..., Rainbow_sk(m)). A collision of D is
one message pair colliding under every seed at once -- the original collision
relation, applied to all stripes simultaneously.

WHY THIS COMPOSITION, and what was measured before building it. The published
attack collides one stripe by colliding H(x) = A(x) + B(x) in block 1, then
merging with a block-2 word. That word is free for message a, and message b must
use it plus an OFFSET, A_b - A_a. When stripes share the message, one word serves
every stripe, so two conditions must hold for each extra stripe:

  the offsets must agree      measured nearly seed-free: they agree across two
                              random seeds with probability 2^-1.2, at w = 16,
                              32 and production's w = 64 alike. The seed adds
                              into s0 and multiplication is linear on
                              differences; only the rotation's borrow
                              reintroduces it.

  H must collide              NOT seed-free: the XOR inside B scrambles it.
                              Cross-seed agreement of H differences is 2^-13.2 at
                              w=16 and was never observed in 200,000 pairs at
                              w = 32 or 64.

So each stripe should cost its own w-bit collision condition plus about a bit
for the bridge, and the predicted attack cost is a JOINT birthday over k*w bits:
about 2^(kw/2). This file measures that rather than asserting it.

WHAT THIS IS NOT. There is no secret. Every seed is part of the hash, so the
keyholder pays exactly what the attacker pays. If this composition scales, it is
a stronger hash; it is not yet a trapdoor. It is measured first because a
composition that does not scale for anyone cannot scale for the public alone.

The Joux multicollision attack is the known ceiling for concatenated iterated
hashes and would take over at larger k; see the note in measure_concat.py.
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1]))

import stripe as ST                                              # noqa: E402
from models import rainbow as R                                  # noqa: E402
from models import wordops as W                                  # noqa: E402


def digest(blocks, seeds, w):
    return tuple(ST.rainbow(blocks, s, w) for s in seeds)


def joint_collision(seeds, w, rng, cap):
    """Joint birthday on (H_s1, ..., H_sk), filtered by bridge-offset agreement.

    Returns (m_a, m_b, h_evaluations, candidate_pairs, rejected_by_bridge) or
    None at the cap. Cost is counted in H evaluations -- k per queried x -- which
    is the fair unit when comparing k.
    """
    theta = R.default_theta(w)
    k = len(seeds)
    ivs = [ST.iv(s, 2, w) for s in seeds]
    mask = (1 << w) - 1
    table = {}
    evaluations = candidates = rejected = 0

    while evaluations < cap:
        x = rng.getrandbits(w) & mask
        parts = [ST.half_sum(x, iv[0], iv[1], theta) for iv in ivs]
        evaluations += k
        key = tuple(p[2] for p in parts)
        previous = table.get(key)
        if previous is None or previous[0] == x:
            table.setdefault(key, (x, parts))
            continue
        candidates += 1
        xa, pa = previous
        offsets = {W.sub(parts[i][0], pa[i][0], w) for i in range(k)}
        if len(offsets) != 1:
            rejected += 1
            table[key] = (x, parts)          # keep searching with the newer point
            continue
        offset = offsets.pop()
        p = 0                                 # message a's bridge word is free
        m_a = [(xa, 0), (p, 0)]
        m_b = [(x, 0), (W.add(p, offset, w), 0)]
        return m_a, m_b, evaluations, candidates, rejected
    return None


# ------------------------------------------------- with enough freedom to exist
PREFIX_BLOCKS = 2        # keeps the gadget on a mixA boundary (block index 2)
TOTAL_BLOCKS = PREFIX_BLOCKS + 2


def state_after_prefix(prefix, seed, w, theta):
    """State at the gadget, for a 4-block message. IV uses the TOTAL length."""
    h = ST.iv(seed, TOTAL_BLOCKS, w)
    for index, (x, y) in enumerate(prefix):
        h = ST._inject(h, x, y, w)
        h = (R.mix_a(h, theta) if index % 2 == 0
             else R.permute(R.mix_b(h, theta, seed), theta))
    return h


def joint_collision_prefixed(seeds, w, rng, cap):
    """Shared random prefix per trial, then every x under that prefix.

    Exhaustive enumeration showed a single free word runs out of room: joint H
    collisions over k stripes need about k*w bits, a w-bit word gives 2^(2w)
    pairs, so k=2 has O(1) solutions and k=3 none. A prefix identical in both
    messages re-randomizes every stripe's state and hands the attacker a fresh
    2^(2w) pairs, without breaking the merge -- shared blocks keep equal states
    equal. Within one prefix a hash table over all 2^w values of x finds every
    joint collision at once.

    Predicted cost: about 2^((k-2)w) prefixes for one solution, times k*2^w H
    evaluations each, so roughly 2^((k-1)w) for k >= 2.
    """
    theta = R.default_theta(w)
    k = len(seeds)
    mask = (1 << w) - 1
    evaluations = prefixes = 0
    while evaluations < cap:
        prefix = [(rng.getrandbits(w), rng.getrandbits(w))
                  for _ in range(PREFIX_BLOCKS)]
        prefixes += 1
        states = [state_after_prefix(prefix, sd, w, theta) for sd in seeds]
        table = {}
        for x in range(1 << w):
            parts = [ST.half_sum(x, st[0], st[1], theta) for st in states]
            evaluations += k
            key = tuple(pt[2] for pt in parts)
            if key in table:
                xa, pa = table[key]
                offsets = {W.sub(parts[i][0], pa[i][0], w) for i in range(k)}
                if len(offsets) == 1:
                    off = offsets.pop()
                    m_a = prefix + [(xa, 0), (0, 0)]
                    m_b = prefix + [(x, 0), (off, 0)]
                    return m_a, m_b, evaluations, prefixes
            else:
                table[key] = (x, parts)
    return None
