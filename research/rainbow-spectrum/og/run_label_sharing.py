"""Q24 -- how does isolation degrade as per-label secrets are compressed?

Q23 showed a bounded master key cannot give information-theoretic label
isolation. This grades the failure. The capability at label L is the multiplier
theta_L that the private route uses; the label selects WHICH secret is in play
and nothing else (A and C use a fixed IV), so the derivation is the sole
mechanism under test.

A real Rainbow witness at L is a collision of H(x) = A(x) + theta_L C(x). It
constrains theta_L to the exact ball

    B = { m odd : m * (C(xa) - C(xb)) = A(xb) - A(xa) }

which is Q14's incidence ball, not a stand-in. Consistency of a master key K is
then `theta_{L_i}(K) in B_i` for every witness label.

Because capability at L' depends on K only through theta_{L'}(K), the capability
counts are exact without building tables:

    K(X, L') = |{ theta_{L'}(K) : K in X }|     l_cross = log2 K(all,L')/K(S,L')

Derivations, in increasing compression:
    independent   theta_L = K_L              key N words   -- the Q22 shape, made real
    poly degree d theta_L = sum c_i L^i      key d+1 words
    tree          theta_L = sum of node secrets on the root->leaf path
"""
import sys, pathlib, math, random, itertools, statistics
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "og"))
from models import rainbow as R
from models import wordops as W
import stripe as ST

W_BITS = 6
MASK = (1 << W_BITS) - 1
TH = R.default_theta(W_BITS)
IV = ST.iv(0, 2, W_BITS)


def AC(x):
    m, r = TH.multipliers, TH.mixa_rotations
    a = W.mul(W.rotr(W.mul(W.sub(IV[0], x, W_BITS), m[0], W_BITS), r[0], W_BITS), m[1], W_BITS)
    c = W.rotr(W.mul(W.xor(W.add(IV[1], x, W_BITS), a, W_BITS), m[2], W_BITS), r[1], W_BITS)
    return a, c


ATAB = [AC(x)[0] for x in range(1 << W_BITS)]
CTAB = [AC(x)[1] for x in range(1 << W_BITS)]
ODD = list(range(1, 1 << W_BITS, 2))


def ball(theta, rng):
    """A real collision of A + theta*C, and the exact set of m it admits."""
    seen = {}
    for _ in range(1 << (W_BITS + 4)):
        x = rng.randrange(1 << W_BITS)
        h = (ATAB[x] + theta * CTAB[x]) & MASK
        if h in seen and seen[h] != x:
            xa, xb = seen[h], x
            dC = (CTAB[xa] - CTAB[xb]) & MASK
            dA = (ATAB[xb] - ATAB[xa]) & MASK
            return [m for m in ODD if (m * dC) & MASK == dA]
        seen.setdefault(h, x)
    return None


# ------------------------------------------------------------- derivations
def make_independent(n):
    space = list(itertools.product(ODD, repeat=n))
    return space, (lambda K, L: K[L]), f"independent ({n} words)"


def make_poly(d):
    space = list(itertools.product(ODD, repeat=d + 1))
    def theta(K, L):
        v = 0
        for c in reversed(K):
            v = (v * L + c) & MASK
        return v | 1
    return space, theta, f"poly degree {d} ({d+1} words)"


def run(space, theta_of, name, wit_labels, fresh, trials=6, rng=None):
    rng = rng or random.Random(5)
    K_all = len({theta_of(K, fresh) for K in space})
    rows = []
    for _ in range(trials):
        true_K = rng.choice(space)
        cand = space
        seq = []
        for L in wit_labels:
            B = ball(theta_of(true_K, L), rng)
            if B is None:
                break
            Bs = set(B)
            cand = [K for K in cand if theta_of(K, L) in Bs]
            KS = len({theta_of(K, fresh) for K in cand})
            seq.append((len(cand), KS, math.log2(K_all / KS)))
        if seq:
            rows.append(seq)
    if not rows:
        return
    n = min(len(r) for r in rows)
    print(f"  {name:<26} K(all,L'={fresh})={K_all}")
    for i in range(n):
        nc = statistics.median(r[i][0] for r in rows)
        ks = statistics.median(r[i][1] for r in rows)
        lc = statistics.median(r[i][2] for r in rows)
        flag = "   ISOLATES" if lc < 0.5 else ("   COLLAPSED" if ks <= 1.5 else "")
        print(f"     after {i+1} witness(es): |cand|={nc:>8.0f}  K(cand,L')={ks:>5.0f}"
              f"   l_cross={lc:5.2f}{flag}", flush=True)
    print()


print(f"w={W_BITS}. Capability at a FRESH label after n witnesses at other labels.")
print("Prediction: degree d collapses after about d+1 informative witnesses.\n")
run(*make_independent(4), wit_labels=[0, 1, 2], fresh=3)
for d in (0, 1, 2, 3):
    run(*make_poly(d), wit_labels=[1, 2, 3, 4, 5], fresh=7)


# ------------------------------------------------------------------ the tree
def tree_experiment(depth=3, internal_depth=2, samples=200000, trials=6):
    """theta_L = sum of node secrets along the root->leaf path, truncated at
    `internal_depth`, so leaves sharing that prefix share capability exactly.

    The key space is too large to enumerate, but only the joint law of the
    theta's matters, so node secrets are sampled directly.
    """
    nleaves = 1 << depth
    def path_nodes(L):
        out, node = [], 1
        for k in range(internal_depth):
            out.append(node)
            node = 2 * node + ((L >> (depth - 1 - k)) & 1)
        out.append(node)
        return out

    def theta_from(secrets, L):
        v = 0
        for nd in path_nodes(L):
            v = (v + secrets[nd]) & MASK
        return (v << 1 | 1) & MASK or 1

    rng = random.Random(21)
    nodes = 1 << (internal_depth + 1)
    print(f"  tree depth {depth}, secrets on the first {internal_depth+1} path nodes")
    print(f"  {'L':>3}{'L2':>4}{'shared prefix':>15}   l_cross after 1 / 2 / 3 witnesses")
    for Lp in range(1, nleaves):
        shared = 0
        for k in range(depth):
            if ((0 >> (depth - 1 - k)) & 1) == ((Lp >> (depth - 1 - k)) & 1):
                shared += 1
            else:
                break
        results = []
        for _ in range(trials):
            keys = [[rng.randrange(1 << MASK.bit_length()) for _ in range(nodes)]
                    for _ in range(samples)]
            true = keys[0]
            K_all = len({theta_from(k, Lp) for k in keys})
            cand = keys
            row = []
            for L in (1, 2, 4):
                if L == Lp:
                    continue
                B = ball(theta_from(true, L), rng)
                if B is None:
                    break
                Bs = set(B)
                cand = [k for k in cand if theta_from(k, L) in Bs]
                if not cand:
                    break
                KS = len({theta_from(k, Lp) for k in cand})
                row.append(math.log2(K_all / KS))
            if row:
                results.append(row)
            break
        if results:
            r = results[0]
            cells = "  ".join(f"{v:5.2f}" for v in r)
            print(f"  {0:>3}{Lp:>4}{shared:>15}   {cells}", flush=True)


if "--tree" in sys.argv:
    print()
    print("TREE derivation: does capability sharing follow tree distance?")
    tree_experiment()
