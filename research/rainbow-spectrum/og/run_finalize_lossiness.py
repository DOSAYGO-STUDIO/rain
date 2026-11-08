"""Is Rainbow's finalization lossy at a NON-degenerate width?

Q12 says "the finalization is lossy -- at w=4 it maps 65,536 states onto 4,014
digests" (6.1% of the space; a random 16->16-bit map covers ~63%). But w=4 has
mixA rotations (1,2,2,2) and mixB rotations (1,1): degenerate. The claim is
re-measured here at widths where the rotations are real.

Method. Exact enumeration at w=4. At larger w the state space 2^(4w) is out of
reach, so image size is estimated from the birthday rate: among N random states,
digest collisions ~ N^2 / (2 I) for an image of size I, hence
I ~ N^2 / (2 * collisions). Reported as I / 2^(4w) against the random-function
value 1 - 1/e = 0.632. Collisions are counted through the actual digest, so any
lossiness anywhere in the finalization is captured.
"""
import sys, pathlib, random, math
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from og import stripe as S

SEED = 0x5EED


def exact(w):
    seen = set()
    for st in range(1 << (4 * w)):
        h = tuple((st >> (w * i)) & ((1 << w) - 1) for i in range(4))
        seen.add(S.finalize(h, SEED, w))
    return len(seen) / (1 << (4 * w))


def birthday(w, n):
    rng = random.Random(w * 1000 + 7)
    digests = {}
    coll = 0
    for _ in range(n):
        h = tuple(rng.getrandbits(w) for _ in range(4))
        d = S.finalize(h, SEED, w)
        if d in digests:
            coll += 1
        else:
            digests[d] = 1
    expect_random = n * n / (2 * (1 << (4 * w)) * (1 - 1 / math.e))
    image = n * n / (2 * coll) if coll else float("inf")
    return coll, expect_random, image / (1 << (4 * w))


print("  w   method        samples   collisions  expected-if-random   image/2^4w   (random: 0.632)")
print(f"  4   exact          65536          -           -            {exact(4):.3f}", flush=True)
for w, n in ((6, 1 << 20), (8, 1 << 20), (10, 1 << 21)):
    coll, er, frac = birthday(w, n)
    print(f" {w:>2}   birthday   {n:>9}   {coll:>9}      {er:9.1f}         {frac:8.3f}",
          flush=True)
