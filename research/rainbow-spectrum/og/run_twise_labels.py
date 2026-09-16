"""Q25 -- t-wise independent label capabilities over GF(2^h).

Q24's polynomial derivation leaked l_cross = 1.00 after ONE witness at every
degree, which under genuine pairwise independence is impossible. The derivation
was at fault, not the idea:

  * polynomials were taken over Z/2^w, which has zero divisors, so the Vandermonde
    matrix is not invertible and evaluations at distinct labels are correlated;
  * coefficients were restricted to odd values, biasing the family;
  * `v | 1` is 2-to-1, not a bijection onto the odd multipliers, destroying
    uniformity.

Done properly: coefficients uniform over GF(2^h), labels distinct nonzero field
elements, and theta_L = 2 z_L + 1, which IS a bijection from GF(2^h) (as h-bit
integers, h = w-1) onto the odd residues mod 2^w.

Prediction: l_cross = 0 for the first t witnesses, then collapse at t+1, with
master key (t+1) h bits rather than N h.
"""
import sys, pathlib, math, random, itertools, statistics
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "og"))
from run_label_sharing import ball

W_BITS = 6
H = W_BITS - 1                      # GF(2^5)
POLY = 0b100101                     # x^5 + x^2 + 1, irreducible over GF(2)
FIELD = 1 << H


def gmul(a, b):
    r = 0
    while b:
        if b & 1:
            r ^= a
        b >>= 1
        a <<= 1
        if a & FIELD:
            a ^= POLY
    return r


def evaluate(coeffs, L):
    """Horner in GF(2^h)."""
    v = 0
    for c in reversed(coeffs):
        v = gmul(v, L) ^ c
    return v


def theta_of(coeffs, L):
    """Bijection GF(2^h) -> odd residues mod 2^w."""
    return (evaluate(coeffs, L) << 1) | 1


def run(t, labels, fresh, trials=8, seed=5):
    space = list(itertools.product(range(FIELD), repeat=t + 1))
    rng = random.Random(seed)
    K_all = len({theta_of(K, fresh) for K in space})
    rows = []
    for _ in range(trials):
        true = rng.choice(space)
        cand = space
        seq = []
        for L in labels:
            B = ball(theta_of(true, L), rng)
            if B is None:
                break
            Bs = set(B)
            cand = [K for K in cand if theta_of(K, L) in Bs]
            if not cand:
                break
            KS = len({theta_of(K, fresh) for K in cand})
            seq.append((len(cand), KS, math.log2(K_all / KS)))
        if seq:
            rows.append(seq)
    n = min(len(r) for r in rows)
    keybits = (t + 1) * H
    print(f"  degree t={t}   key = {t+1} x {H} = {keybits} bits   "
          f"K(all, L'={fresh}) = {K_all}")
    for i in range(n):
        nc = statistics.median(r[i][0] for r in rows)
        ks = statistics.median(r[i][1] for r in rows)
        lc = statistics.median(r[i][2] for r in rows)
        tag = ("   ISOLATES" if lc < 0.01 else
               "   COLLAPSED" if ks <= 1.5 else "   partial")
        print(f"     after {i+1} witness(es): |cand|={nc:>8.0f}  "
              f"K(cand,L')={ks:>4.0f}   l_cross={lc:5.2f}{tag}", flush=True)
    print()


print(f"GF(2^{H}), theta_L = 2 z_L + 1, real Rainbow witnesses and incidence balls.")
print(f"Prediction: l_cross = 0 through t witnesses, collapse at t+1.\n")
for t in (1, 2, 3):
    run(t, labels=[1, 2, 3, 4, 5][:t + 3], fresh=9)
