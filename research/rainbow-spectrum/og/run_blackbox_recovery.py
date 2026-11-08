"""Q26 -- black-box recovery of a label key from public evaluation.

THE LAW UNDER TEST. If the public evaluator exposes H_theta(x) = A(x) + theta C(x)
with A, C public, then D(x) = H_theta(x) - A(x) = theta C(x) is a linear equation
in theta. After queries x_1..x_q with r = min_i v2(C(x_i)):

    theta is determined modulo 2^(w-r),  i.e. exactly 2^r candidates remain

and if any queried C(x_i) is odd then r = 0 and theta is fully exposed by ONE
evaluation. This is representation-independent: no circuit flattening or
obfuscation can help, because the input/output relation already contains the key
equation.

THE ESCAPE TESTED. Rainbow's one lossy element is truncation (Q20). If the public
sees only the low k bits of H, each query gives theta only modulo 2^(k-v2(C)), so
recovery is capped. Measured here as residual candidates vs k.
"""
import sys, pathlib, random, statistics
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "og"))
from models import rainbow as R
from models import wordops as W
import stripe as ST


def tables(w):
    th = R.default_theta(w)
    m, r = th.multipliers, th.mixa_rotations
    iv = ST.iv(0, 2, w)
    A, C = [], []
    for x in range(1 << w):
        a = W.mul(W.rotr(W.mul(W.sub(iv[0], x, w), m[0], w), r[0], w), m[1], w)
        c = W.rotr(W.mul(W.xor(W.add(iv[1], x, w), a, w), m[2], w), r[1], w)
        A.append(a); C.append(c)
    return A, C


def v2(x, w):
    return w if x == 0 else ((x & -x).bit_length() - 1)


print("PART 1 -- the law: r = min v2(C(x_i))  =>  exactly 2^r candidates remain")
print("  w   queries   r   predicted 2^r   measured candidates   agree")
for w in (8, 10, 12):
    A, C = tables(w)
    mask = (1 << w) - 1
    rng = random.Random(w)
    ok = True
    for q in (1, 2, 3):
        for _ in range(60):
            theta = rng.randrange(1, 1 << w, 2)
            xs = [rng.randrange(1 << w) for _ in range(q)]
            obs = [((A[x] + theta * C[x]) & mask) for x in xs]
            cand = [t for t in range(1, 1 << w, 2)
                    if all(((A[x] + t * C[x]) & mask) == o for x, o in zip(xs, obs))]
            r = min(v2(C[x], w) for x in xs)
            if len(cand) != (1 << r):
                ok = False
                print(f"  w={w} q={q}: r={r} predicted {1<<r} got {len(cand)}  MISMATCH")
        print(f" {w:>2}   {q:>7}   -   (law holds over 60 random trials)   "
              f"{'yes' if ok else 'NO'}")

print()
print("PART 2 -- how fast does chosen/random access reach full exposure?")
print("  w   P(C(x) odd)   random queries to r=0 (mean)   chosen queries")
for w in (8, 10, 12, 14):
    A, C = tables(w)
    p = sum(1 for c in C if c & 1) / len(C)
    rng = random.Random(w + 1)
    counts = []
    for _ in range(2000):
        n = 1
        while not (C[rng.randrange(1 << w)] & 1):
            n += 1
        counts.append(n)
    chosen = 1 if p > 0 else None
    print(f" {w:>2}   {p:11.4f}   {statistics.mean(counts):>27.2f}   {chosen:>14}")

print()
print("PART 3 -- the escape: public sees only the low k bits of H")
print("  Each query then gives theta mod 2^(k - v2(C)), so recovery is capped.")
w = 12
A, C = tables(w)
mask = (1 << w) - 1
rng = random.Random(99)
print(f"  w={w}: residual candidates for theta after 8 chosen queries, by k")
print("     k   residual   log2   digest bits kept")
for k in range(w, 0, -2):
    km = (1 << k) - 1
    res = []
    for _ in range(40):
        theta = rng.randrange(1, 1 << w, 2)
        xs = [x for x in range(1 << w) if C[x] & 1][:8]
        obs = [((A[x] + theta * C[x]) & mask) & km for x in xs]
        cand = [t for t in range(1, 1 << w, 2)
                if all((((A[x] + t * C[x]) & mask) & km) == o
                       for x, o in zip(xs, obs))]
        res.append(len(cand))
    med = statistics.median(res)
    import math
    print(f"    {k:>2}   {med:>8.0f}   {math.log2(med):5.2f}   {k}/{w}")
