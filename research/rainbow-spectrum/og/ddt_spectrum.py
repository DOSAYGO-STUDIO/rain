"""DDT row energy of Rainbow's message curve, factored into depth and ray effects.

THE OBJECT. Q16's difference-distribution table is not the DDT of H = A + B. It
is the DDT of `G = C o A^-1`, i.e. differences taken in the A coordinate and
measured in the C coordinate:

    N(d, e) = #{ u : G(u) - G(u - d) = e },   u = A(x),  G(u) = C(x)

because that is what governs whether a collision chord can be rebased. A is a
bijection, so indexing by u is exact. (Measuring H instead gives a different and
much flatter picture -- the first version of this file did that and failed to
reproduce Q16, which is how the distinction got pinned down.)

THE DECOMPOSITION. A row d = 2^r u is reported as two independent numbers:

    M_r    = median over odd u of E_r(u)     the 2-adic DEPTH bias
    R_r(u) = E_r(u) / M_r                    the RAY anisotropy

with E_r(u) = sum_e N(2^r u, e)^2 normalised by the shuffle null, so M_r is
already a multiple of chance. One combined number conflated "valuation alone
lifts the whole row family" with "this one direction is special".

THE NULL. Keep the real G, keep its exact value multiset, randomly reassign which
u carries which value. That destroys the arithmetic relation between neighbouring
inputs while preserving the output distribution exactly. It does NOT preserve
tau_d's cycle structure, but for a plain DDT of G in the u coordinate the cycle
structure IS the translation u -> u - d, which the shuffle is meant to break.
"""

import pathlib
import random
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from models import rainbow as R                                  # noqa: E402
from models import wordops as W                                  # noqa: E402

VARIANTS = ("rainbow", "no-rot-a", "no-rot-c", "no-rot", "no-mul-a",
            "no-mul-c", "couple-add", "no-couple")


def g_table(w, theta, s0, s1, variant="rainbow"):
    """G(u) for every u, under one surgical ablation. A stays a bijection."""
    m, r = theta.multipliers, theta.mixa_rotations
    mask = (1 << w) - 1
    rot = lambda v, k: ((v >> k) | (v << (w - k))) & mask if k else v
    g = [0] * (1 << w)
    for x in range(1 << w):
        t = (s0 - x) & mask
        if variant == "no-mul-a":
            a = rot(t, r[0])
        elif variant in ("no-rot-a", "no-rot"):
            a = (t * m[0] * m[1]) & mask
        else:
            a = (rot((t * m[0]) & mask, r[0]) * m[1]) & mask

        v = (s1 + x) & mask
        if variant == "couple-add":
            k = (v + a) & mask
        elif variant == "no-couple":
            k = v
        else:
            k = v ^ a

        if variant == "no-mul-c":
            c = rot(k, r[1])
        elif variant in ("no-rot-c", "no-rot"):
            c = (k * m[2]) & mask
        else:
            c = rot((k * m[2]) & mask, r[1])
        g[a] = c
    return g


def randomised_theta(w, seed, what):
    base = R.default_theta(w)
    rng = random.Random(seed)
    mults, rots = list(base.multipliers), list(base.mixa_rotations)
    if what in ("mults", "both"):
        mults = [W.make_odd(rng.getrandbits(w), w) for _ in mults]
    if what in ("rots", "both"):
        rots = [rng.randrange(1, w) for _ in rots]
    return R.Theta(w=w, multipliers=tuple(mults), mixa_rotations=tuple(rots),
                   mixb_rotations=base.mixb_rotations, label=f"rand-{what}")


def row_energy(tab, d, w):
    mask = (1 << w) - 1
    counts = {}
    for u in range(1 << w):
        e = (tab[u] - tab[(u - d) & mask]) & mask
        counts[e] = counts.get(e, 0) + 1
    return sum(c * c for c in counts.values())


def null_energy(tab, w, rng, rows=16, trials=3):
    vals = []
    for _ in range(trials):
        shuffled = list(tab)
        rng.shuffle(shuffled)
        for _ in range(rows):
            vals.append(row_energy(shuffled, rng.randrange(1, 1 << w), w))
    return statistics.mean(vals)


def spectrum(w, variant="rainbow", theta_what=None, seed=1, rs=None,
             sample=48, instances=1):
    """{r: (M_r, R_r(1), rank of u=1, units sampled, best u, R_r(best))}."""
    per_r = {}
    for inst in range(instances):
        theta = (randomised_theta(w, seed + inst, theta_what) if theta_what
                 else R.default_theta(w))
        rng = random.Random(seed * 7919 + inst)
        tab = g_table(w, theta, rng.getrandbits(w), rng.getrandbits(w), variant)
        null = null_energy(tab, w, random.Random(seed + 999 + inst))
        for r in (rs if rs is not None else range(0, w - 1)):
            odds = [u for u in range(1, 1 << (w - r), 2)]
            if len(odds) > sample:
                pick = random.Random(seed * 31 + r)
                odds = [1] + pick.sample([u for u in odds if u != 1], sample - 1)
            en = {u: row_energy(tab, (u << r) & ((1 << w) - 1), w) / null
                  for u in odds}
            per_r.setdefault(r, []).append(en)

    out = {}
    for r, runs in per_r.items():
        en = {u: statistics.mean(run[u] for run in runs) for u in runs[0]}
        med = statistics.median(en.values())
        order = sorted(en, key=lambda u: -en[u])
        out[r] = (med, en[1] / med, order.index(1) + 1, len(en),
                  order[0], en[order[0]] / med)
    return out


def show(title, spec):
    print(title)
    print("    r    M_r      R_r(1)   rank      best u   R_r(best)")
    for r in sorted(spec):
        M, R1, rank, n, best, Rb = spec[r]
        print(f"   {r:>2}  {M:7.2f}x  {R1:8.2f}   {rank:>3}/{n:<4}  {best:>7}  {Rb:8.2f}")
