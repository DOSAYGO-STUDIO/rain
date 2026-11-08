"""Tree derivation, exactly. The Monte Carlo version thinned out and was junk.

theta_L = sum of node secrets on the truncated root->leaf path. Two leaves with
the SAME truncated path get literally the same theta. Otherwise the rows -- the
indicator vectors of the truncated paths -- are linearly independent over Z/2^k,
because each distinct truncated path ends at a node no other path uses. Linear
independence with uniform node secrets means the theta's are jointly uniform and
INDEPENDENT, so cross-class capability leakage is exactly zero.

That predicts a STEP function, not a gradient: full sharing inside a class, none
between classes. Verified here by enumerating the whole key space at depth 2.
"""
import sys, pathlib, math, random, itertools
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "og"))
from run_label_sharing import ball, ODD, MASK

W_BITS = 6
DEPTH, INTERNAL = 2, 1          # 4 leaves, nodes {1,2,3}: leaves 0,1 | 2,3
NODES = [1, 2, 3]


def path(L):
    out, node = [], 1
    for k in range(INTERNAL):
        out.append(node)
        node = 2 * node + ((L >> (DEPTH - 1 - k)) & 1)
    out.append(node)
    return out


print(f"truncated paths: " + ", ".join(f"leaf{L}->{path(L)}" for L in range(4)))
space = list(itertools.product(range(1 << (W_BITS - 1)), repeat=len(NODES)))
idx = {n: i for i, n in enumerate(NODES)}


def theta(K, L):
    v = sum(K[idx[n]] for n in path(L)) % (1 << (W_BITS - 1))
    return (v << 1) | 1


rng = random.Random(3)
print(f"\nkey space {len(space)} enumerated exactly, w={W_BITS}")
print(f"{'witness L':>10}{'fresh L2':>10}{'same class':>12}"
      f"{'K(all,L2)':>11}{'K(cand,L2)':>12}{'l_cross':>9}")
for L, Lp in ((0, 1), (0, 2), (0, 3), (2, 3), (2, 0)):
    K_all = len({theta(K, Lp) for K in space})
    trials = []
    for _ in range(8):
        true = rng.choice(space)
        B = ball(theta(true, L), rng)
        if B is None:
            continue
        Bs = set(B)
        cand = [K for K in space if theta(K, L) in Bs]
        KS = len({theta(K, Lp) for K in cand})
        trials.append(math.log2(K_all / KS))
    lc = sorted(trials)[len(trials) // 2]
    same = path(L) == path(Lp)
    print(f"{L:>10}{Lp:>10}{str(same):>12}{K_all:>11}"
          f"{int(K_all / 2**lc):>12}{lc:>9.2f}"
          + ("   full share" if lc > 4 else "   ISOLATES" if lc < 0.5 else ""))
