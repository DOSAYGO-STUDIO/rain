#!/usr/bin/env python3
"""Planting for faithful B: witness chosen first, T derived by inverting backwards.

Saved as a module because this has now been got wrong twice by being re-derived
inline. Random S and T do NOT give a solvable instance: the relation asks two
DIFFERENT states to reach the same state, which generically has no solution, so
an unplanted instance is unsat and any cost fitted over the few satisfiable ones
is meaningless.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "attacks"))
sys.path.insert(0, str(ROOT / "og"))

import stripe as ST                                              # noqa: E402
from models import rainbow as R                                  # noqa: E402
from models import spectrum as S                                 # noqa: E402
from models import wordops as W                                  # noqa: E402
from experiment_b import mix_inv                                 # noqa: E402


def mixb_inv(state, theta, seed, w):
    m, r = theta.multipliers, theta.mixb_rotations
    h0, b, a, h3 = state
    h1 = W.mul(W.rotl(W.mul(a, W.inv_odd(m[7], w), w), r[0], w), W.inv_odd(m[6], w), w)
    u = W.mul(W.rotl(W.mul(b, W.inv_odd(m[3], w), w), r[1], w), W.inv_odd(m[2], w), w)
    h2 = W.xor(u, W.add(a, seed, w), w)
    return (h0, h1, h2, h3)


def fwd(h, ctrl, theta, idx, seed, w):
    h = ST._inject(h, ctrl[0], ctrl[1], w)
    return (R.mix_a(h, theta) if idx % 2 == 0
            else R.permute(R.mix_b(h, theta, seed), theta))


def inv(h, ctrl, theta, idx, seed, w):
    if idx % 2 == 0:
        h = mix_inv(h, theta)
    else:
        unperm = [0] * 4
        for i, src in enumerate(theta.lane_perm):
            unperm[src] = h[i]
        h = mixb_inv(tuple(unperm), theta, seed, w)
    return (W.add(h[0], ctrl[0], w), W.sub(h[1], ctrl[0], w),
            W.sub(h[2], ctrl[1], w), W.add(h[3], ctrl[1], w))


def plant(w, t, rng, seed, k=2):
    """Returns (thetas, S, T) with a witness guaranteed to exist."""
    thetas = []
    while len(thetas) < k:
        theta = S.random_theta(w, rng, pairs=S.PAIRINGS[0], signs=((-1, 1), (1, -1)))
        if S.validate_weakness(theta, rng, trials=20)["admissible"]:
            thetas.append(theta)
    thetas = tuple(thetas)
    start = tuple(rng.getrandbits(w) for _ in range(4))
    prefix_a = [(rng.getrandbits(t), rng.getrandbits(t)) for _ in range(k - 1)]
    prefix_b = [(rng.getrandbits(t), rng.getrandbits(t)) for _ in range(k - 1)]
    merge_b = (rng.getrandbits(w), rng.getrandbits(w))
    h = start
    for i in range(k - 1):
        h = fwd(h, prefix_a[i], thetas[i], i, seed, w)
    final = fwd(h, (0, 0), thetas[-1], k - 1, seed, w)
    back = inv(final, merge_b, thetas[-1], k - 1, seed, w)
    for i in range(k - 2, -1, -1):
        back = inv(back, prefix_b[i], thetas[i], i, seed, w)
    return thetas, start, back
