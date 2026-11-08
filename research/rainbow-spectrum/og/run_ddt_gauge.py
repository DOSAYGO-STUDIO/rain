"""Is the outer A multiplier m[1] a gauge freedom of the DDT?

Claim under test: with A' = c A (c = m1' m1^-1), G' = C o A'^-1 = G o c^-1,
so every DDT row is relabelled exactly: N_G'(d, e) = N_G(c^-1 d, e).

The thing that could break it: C(x) = rotr(((s1 + x) XOR A(x)) m2, r1) reads
A(x) through the XOR, so C' != C in general and G' is not G o c^-1 on the nose.
Whether the residual is negligible or dominant is what this measures.

Test 1 (exact): for every d, compare the full histogram N_G'(d, .) with
N_G(c^-1 d, .). Report the fraction of rows that match exactly and the row-energy
relative error.

Test 2 (the rand-mults retraction check): with ALL odd u enumerated at every r,
does max_u E_r(u) survive a random m1? Under pure gauge it must be identical.
"""
import sys, pathlib, random, statistics
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from og import ddt_spectrum as D
from models import rainbow as R
from models import wordops as W

w = 12
mask = (1 << w) - 1
base = R.default_theta(w)
rng = random.Random(1)
s0, s1 = rng.getrandbits(w), rng.getrandbits(w)


def theta_with_m1(m1):
    m = list(base.multipliers); m[1] = m1
    return R.Theta(w=w, multipliers=tuple(m), mixa_rotations=base.mixa_rotations,
                   mixb_rotations=base.mixb_rotations, label="m1")


def hist(tab, d):
    counts = {}
    for u in range(1 << w):
        e = (tab[u] - tab[(u - d) & mask]) & mask
        counts[e] = counts.get(e, 0) + 1
    return counts


G = D.g_table(w, base, s0, s1)
m1 = base.multipliers[1]
inv_m1 = pow(m1, -1, 1 << w)

print(f"w={w}  real m1={m1}")
print("TEST 1: exact row relabelling  N_G'(d,.) == N_G(c^-1 d,.)")
print("  m1'            j   c            rows exact   energy rel.err (median, max)")
cases = [("m1+2^%d" % j, (m1 + (1 << j)) & mask, j) for j in (2, 5, 8, 11)]
cases += [("random", W.make_odd(random.Random(k).getrandbits(w), w), "-") for k in (7, 8)]
for name, m1p, j in cases:
    Gp = D.g_table(w, theta_with_m1(m1p), s0, s1)
    c = (m1p * inv_m1) & mask
    cinv = pow(c, -1, 1 << w)
    exact, errs = 0, []
    ds = random.Random(3).sample(range(1, 1 << w), 256)
    for d in ds:
        hp, h = hist(Gp, d), hist(G, (cinv * d) & mask)
        exact += (hp == h)
        ep = sum(v * v for v in hp.values()); e = sum(v * v for v in h.values())
        errs.append(abs(ep - e) / e)
    print(f"  {name:<12} {str(j):>4}   {c:<10}   {exact:>3}/256      "
          f"{statistics.median(errs):8.4f}  {max(errs):8.4f}", flush=True)

print()
print("TEST 2: max over ALL odd u of E_r(u)/null, per r  (pure gauge => identical)")
null = D.null_energy(G, w, random.Random(999))
def full_max(tab):
    out = {}
    for r in range(0, w - 1):
        best = 0
        for u in range(1, 1 << (w - r), 2):
            best = max(best, D.row_energy(tab, (u << r) & mask, w) / null)
        out[r] = best
    return out
real = full_max(G)
print("  r:        " + "".join(f"{r:>8}" for r in range(w - 1)))
print("  real      " + "".join(f"{real[r]:8.1f}" for r in range(w - 1)), flush=True)
for k in (7, 8):
    m1p = W.make_odd(random.Random(k).getrandbits(w), w)
    fm = full_max(D.g_table(w, theta_with_m1(m1p), s0, s1))
    print(f"  rand m1 #{k} " + "".join(f"{fm[r]:8.1f}" for r in range(w - 1)), flush=True)
th = D.randomised_theta(w, 7, "mults")
fm = full_max(D.g_table(w, th, s0, s1))
print(f"  rand ALL  " + "".join(f"{fm[r]:8.1f}" for r in range(w - 1)), flush=True)
