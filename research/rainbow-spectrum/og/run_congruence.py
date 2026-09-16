"""Q28 -- is there a nontrivial one-way quotient of theta stable under the
affine collision action?

REQUIREMENT. A public encoding E must satisfy, for every achievable (a, c):

    E(theta1) = E(theta2)  =>  E(a + c theta1) = E(a + c theta2)

i.e. the fibres of E form a CONGRUENCE for the affine maps tau_{a,c}(theta) =
a + c theta. Then and only then does a well-defined public T_{a,c} exist on the
quotient.

THE ARGUMENT, before enumerating anything. The achievable pairs are
(a, c) = (A(x), C(x)) over all inputs x, since a public evaluator must work at
every x. If two inputs share a c value with different a values, then

    tau_{a,c} o tau_{a',c}^{-1} (theta) = theta + (a - a')

is a pure TRANSLATION. A congruence invariant under all translations is exactly a
union of cosets of a subgroup of Z/2^w, and the subgroups of Z/2^w are precisely
<2^k>. So the fibres must be the congruence classes mod 2^k -- which is the ring
quotient Z/2^w -> Z/2^k, i.e. truncation, already killed in Q26.

This enumerates the achievable translations and then computes, exhaustively, the
smallest congruence identifying each pair, to confirm nothing else survives.
"""
import sys, pathlib, collections
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "og"))
from models import rainbow as R
from models import wordops as W
import stripe as ST


def maps(w):
    th = R.default_theta(w)
    m, r = th.multipliers, th.mixa_rotations
    iv = ST.iv(0, 2, w)
    out = []
    for x in range(1 << w):
        a = W.mul(W.rotr(W.mul(W.sub(iv[0], x, w), m[0], w), r[0], w), m[1], w)
        c = W.rotr(W.mul(W.xor(W.add(iv[1], x, w), a, w), m[2], w), r[1], w)
        out.append((a, c))
    return out


class DSU:
    def __init__(s, n): s.p = list(range(n))
    def find(s, a):
        while s.p[a] != a:
            s.p[a] = s.p[s.p[a]]; a = s.p[a]
        return a
    def union(s, a, b):
        ra, rb = s.find(a), s.find(b)
        if ra != rb: s.p[ra] = rb; return True
        return False


def smallest_congruence(w, d, pairs):
    """Smallest congruence identifying 0 and d, under the achievable maps."""
    mask = (1 << w) - 1
    dsu = DSU(1 << w)
    dsu.union(0, d)
    queue = collections.deque([(0, d)])
    while queue:
        p, q = queue.popleft()
        for a, c in pairs:
            np_, nq = (a + c * p) & mask, (a + c * q) & mask
            if dsu.find(np_) != dsu.find(nq):
                dsu.union(np_, nq)
                queue.append((np_, nq))
    part = collections.defaultdict(list)
    for v in range(1 << w):
        part[dsu.find(v)].append(v)
    return list(part.values())


def classify(w, blocks):
    """Is this partition exactly the congruence classes mod 2^k?"""
    sizes = {len(b) for b in blocks}
    if sizes == {1}:
        return "trivial (E injective -> reveals theta)"
    if len(blocks) == 1:
        return "total (E constant -> no information at all)"
    if len(sizes) != 1:
        return "IRREGULAR -- not a ring quotient!"
    size = sizes.pop()
    if size & (size - 1):
        return "IRREGULAR -- block size not a power of two!"
    k = (1 << w) // size
    for b in blocks:
        if len({v % k for v in b}) != 1:
            return "IRREGULAR -- blocks are not residues mod 2^k!"
    return f"ring quotient: theta mod {k} (= Q26 truncation)"


for w in (5, 6, 7):
    pairs = maps(w)
    cs = collections.defaultdict(set)
    for a, c in pairs:
        cs[c].add(a)
    trans = {(x - y) % (1 << w) for s in cs.values() if len(s) > 1
             for x in s for y in s}
    print(f"w={w}: {len(pairs)} achievable (a,c); {len(cs)} distinct c values; "
          f"{len(trans)} achievable pure translations")
    seen = {}
    for d in range(1, 1 << w):
        blocks = smallest_congruence(w, d, pairs)
        seen.setdefault(classify(w, blocks), []).append(d)
    for verdict, ds in sorted(seen.items()):
        print(f"    {len(ds):>4} of {(1<<w)-1} starting pairs -> {verdict}")
    print()
