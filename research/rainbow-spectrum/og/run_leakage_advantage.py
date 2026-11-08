"""Measure the pair (advantage a, leakage l) directly, to test  a <= l/2.

LEAKAGE is measured by exhaustive posterior counting, not estimated. Pick one
secret coordinate (a multiplier), enumerate ALL of its odd values, and count how
many remain consistent with a published witness -- i.e. how many theta' still make
that witness a collision, with the public data S, T held fixed.

    l = log2( |family| / #consistent )

ADVANTAGE comes from the already-measured SAT exponents: private 0.500 w,
public 0.700 w (faithful B, no suffix), so a = 0.200 w.

The control that this is measuring something real: a coordinate the relation does
not read must give l = 0 (every candidate consistent). m3-style outer multipliers
that only rescale should leak less than inner ones.
"""
import sys, pathlib, random, math, statistics
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "og"))
sys.path.insert(0, str(ROOT / "attacks"))

import faithful_plant as FP
from models import rainbow as R
from models import wordops as W


def collides(thetas, start, T, pa, pb, mb, w, seed, k):
    h = start
    for i in range(k - 1):
        h = FP.fwd(h, pa[i], thetas[i], i, seed, w)
    fa = FP.fwd(h, (0, 0), thetas[-1], k - 1, seed, w)
    h = T
    for i in range(k - 1):
        h = FP.fwd(h, pb[i], thetas[i], i, seed, w)
    fb = FP.fwd(h, mb, thetas[-1], k - 1, seed, w)
    return fa == fb


def swap_mult(theta, idx, val):
    m = list(theta.multipliers); m[idx] = val
    return R.Theta(w=theta.w, multipliers=tuple(m),
                   mixa_rotations=theta.mixa_rotations,
                   mixb_rotations=theta.mixb_rotations,
                   pairs=theta.pairs, signs=theta.signs,
                   lane_perm=theta.lane_perm, label="alt")


def leakage(w, t, k, seed, trial, which_theta, which_mult):
    rng = random.Random(9000 + 31 * w + trial)
    thetas, start, T = FP.plant(w, t, rng, seed, k)
    # recover the planted witness by replaying plant's own choices
    r2 = random.Random(9000 + 31 * w + trial)
    th2, s2, T2 = FP.plant(w, t, r2, seed, k)
    assert (s2, T2) == (start, T)
    r3 = random.Random(9000 + 31 * w + trial)
    tl = []
    while len(tl) < k:
        from models import spectrum as SP
        th = SP.random_theta(w, r3, pairs=SP.PAIRINGS[0], signs=((-1, 1), (1, -1)))
        if SP.validate_weakness(th, r3, trials=20)["admissible"]:
            tl.append(th)
    _start = tuple(r3.getrandbits(w) for _ in range(4))
    pa = [(r3.getrandbits(t), r3.getrandbits(t)) for _ in range(k - 1)]
    pb = [(r3.getrandbits(t), r3.getrandbits(t)) for _ in range(k - 1)]
    mb = (r3.getrandbits(w), r3.getrandbits(w))
    assert collides(thetas, start, T, pa, pb, mb, w, seed, k), "plant did not verify"

    consistent = 0
    for v in range(1, 1 << w, 2):
        alt = list(thetas)
        alt[which_theta] = swap_mult(thetas[which_theta], which_mult, v)
        if collides(tuple(alt), start, T, pa, pb, mb, w, seed, k):
            consistent += 1
    family = 1 << (w - 1)
    return math.log2(family / consistent), consistent, family


seed = 0xABCD
print("faithful B: leakage per witness, by exhaustive posterior over one multiplier")
print("  w   theta  mult   consistent / family     l (bits)   2a = 0.40w   verdict")
for w, t, k in ((8, 4, 2), (10, 5, 2), (12, 6, 2)):
    for which_theta in (0, 1):
        for which_mult in (0, 1, 2, 3):
            ls = []
            for trial in range(3):
                try:
                    l, c, f = leakage(w, t, k, seed, trial, which_theta, which_mult)
                    ls.append((l, c, f))
                except AssertionError as e:
                    print(f"  w={w}: {e}"); break
            if not ls:
                continue
            l = statistics.median(x[0] for x in ls)
            c, f = ls[0][1], ls[0][2]
            need = 0.40 * w
            print(f" {w:>2}   th{which_theta}    m{which_mult}    {c:>6} / {f:<6}"
                  f"        {l:6.2f}      {need:5.2f}     "
                  f"{'OK' if l >= need else 'VIOLATES a<=l/2'}", flush=True)
