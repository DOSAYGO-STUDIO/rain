"""Ablations after quotienting out the coordinate action: max over ALL odd u.

og/run_ddt_gauge.py showed m[1] is NOT an exact gauge (0/256 rows relabel
exactly, because C reads A(x) through the XOR) but IS approximately one: with
every odd u enumerated, a random m[1] keeps the strongest ray at 55-70% of real
strength, merely relocated. Q18's "34x collapse" was measured at u=1 and was
mostly the ray moving off that coordinate.

So the honest ablation reports, per depth r,

    S_r = max over ALL odd u of E_r(u) / null

which is invariant under any exact unit relabelling of the A coordinate. Only
parameters that change S_r are structural. Null is recomputed per table.
"""
import sys, pathlib, random, statistics
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from og import ddt_spectrum as D
from models import rainbow as R
from models import wordops as W

w = 12
mask = (1 << w) - 1
RS = list(range(0, w - 1))


def full_max(tab):
    null = D.null_energy(tab, w, random.Random(999))
    return {r: max(D.row_energy(tab, (u << r) & mask, w) / null
                   for u in range(1, 1 << (w - r), 2)) for r in RS}


def theta_rand_one(which, seed):
    base = R.default_theta(w)
    m = list(base.multipliers)
    m[which] = W.make_odd(random.Random(seed).getrandbits(w), w)
    return R.Theta(w=w, multipliers=tuple(m), mixa_rotations=base.mixa_rotations,
                   mixb_rotations=base.mixb_rotations, label=f"rand-m{which}")


cases = [("rainbow", "rainbow", None)] + \
        [(f"rand-m{i}", "rainbow", ("one", i)) for i in (0, 1, 2)] + \
        [("rand-rots", "rainbow", ("rots", None)),
         ("rand-mults", "rainbow", ("mults", None))] + \
        [(v, v, None) for v in ("no-rot-a", "no-rot-c", "no-mul-a", "no-mul-c",
                                "couple-add", "no-couple")]

print(f"S_r = max over ALL odd u of E_r(u)/null, w={w}, median of 3 seeds")
print(f"{'variant':<12}" + "".join(f"{r:>7}" for r in RS) + "   peak")
for name, variant, what in cases:
    runs = []
    for seed in (1, 2, 3):
        if what is None:
            th = R.default_theta(w)
        elif what[0] == "one":
            th = theta_rand_one(what[1], seed)
        else:
            th = D.randomised_theta(w, seed, what[0])
        rng = random.Random(seed * 7919)
        tab = D.g_table(w, th, rng.getrandbits(w), rng.getrandbits(w), variant)
        runs.append(full_max(tab))
    med = {r: statistics.median(run[r] for run in runs) for r in RS}
    pk = max(med, key=med.get)
    print(f"{name:<12}" + "".join(f"{med[r]:7.1f}" for r in RS)
          + f"   {med[pk]:6.1f}@{pk}", flush=True)
