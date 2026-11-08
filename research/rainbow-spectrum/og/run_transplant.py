"""Q27 -- transplant the Rainbow mechanism into a prime-order algebra.

Branch B asks whether the useful part of Rainbow survives a move to a group where
a one-way public action exists. Public evaluation would be
H_L(x) = g^(A(x)) Y_L^(C(x)) with Y_L = g^theta_L, so the collision condition is

    A(x) + theta C(x) = A(x') + theta C(x')   (mod q)

with q PRIME. The pair-sum invariant itself transplants -- (h0-x)+(h1+x) = h0+h1
holds in any abelian group -- so the question is whether the cheap private
STEERING transplants with it.

Three choices of the public maps A, C, all in the same harness:

  rainbow   A, C from Rainbow's mixA half-round at width w, reduced mod q
  random    A, C uniform random functions
  chameleon message is a PAIR (m, r); A = m, C = r -- the textbook shape

If `rainbow` and `random` agree, Rainbow contributes nothing to Branch B beyond
being an arbitrary choice of public map. If `chameleon` beats both, the textbook
construction dominates and the transplant is a step backwards.
"""
import sys, pathlib, random, statistics, math
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "og"))
from models import rainbow as R
from models import wordops as W
import stripe as ST

Q = 65537          # prime


def rainbow_maps(w):
    th = R.default_theta(w)
    m, r = th.multipliers, th.mixa_rotations
    iv = ST.iv(0, 2, w)
    A, C = {}, {}
    for x in range(1 << w):
        a = W.mul(W.rotr(W.mul(W.sub(iv[0], x, w), m[0], w), r[0], w), m[1], w)
        c = W.rotr(W.mul(W.xor(W.add(iv[1], x, w), a, w), m[2], w), r[1], w)
        A[x], C[x] = a % Q, c % Q
    return A, C


def random_maps(w, seed):
    rng = random.Random(seed)
    return ({x: rng.randrange(Q) for x in range(1 << w)},
            {x: rng.randrange(Q) for x in range(1 << w)})


def private_cost_table(A, C, theta, rng, cap=400000):
    """Keyholder knows theta: birthday on f(x) = A(x) + theta C(x) mod q."""
    seen, ev = {}, 0
    xs = list(A)
    while ev < cap:
        x = rng.choice(xs)
        f = (A[x] + theta * C[x]) % Q
        ev += 1
        if f in seen and seen[f] != x:
            return ev
        seen.setdefault(f, x)
    return None


def private_cost_chameleon(theta, rng):
    """Message is (m, r). Collision: pick m' != m, solve r' = r + (m-m')/theta."""
    m, r = rng.randrange(Q), rng.randrange(Q)
    mp = (m + 1 + rng.randrange(Q - 1)) % Q
    inv = pow(theta, -1, Q)
    rp = (r + (m - mp) * inv) % Q
    assert (m + theta * r) % Q == (mp + theta * rp) % Q
    return 1


w = 12
print(f"q = {Q} (prime), message space 2^{w} for the table variants")
print(f"birthday expectation on q: 2^(log2 q / 2) = {math.sqrt(Q)*1.25:.0f} evaluations\n")
print(f"{'variant':<12}{'private collisions':>20}{'median evaluations':>20}   note")

rng = random.Random(3)
for name, maps in (("rainbow", rainbow_maps(w)),
                   ("random", random_maps(w, 7)),
                   ("random#2", random_maps(w, 8))):
    A, C = maps
    costs = []
    for _ in range(25):
        theta = rng.randrange(1, Q)
        c = private_cost_table(A, C, theta, rng)
        if c:
            costs.append(c)
    med = statistics.median(costs) if costs else None
    print(f"{name:<12}{len(costs):>20}{med:>20.0f}   birthday on q")

costs = [private_cost_chameleon(rng.randrange(1, Q), rng) for _ in range(25)]
print(f"{'chameleon':<12}{len(costs):>20}{statistics.median(costs):>20.0f}"
      f"   ALGEBRAIC INVERSION, O(1)")

print()
print("Does the 2-adic structure survive reduction mod an odd prime?")
A, C = rainbow_maps(w)
th = R.default_theta(w)
mask = (1 << w) - 1
iv = ST.iv(0, 2, w)
Craw = {}
for x in range(1 << w):
    m, r = th.multipliers, th.mixa_rotations
    a = W.mul(W.rotr(W.mul(W.sub(iv[0], x, w), m[0], w), r[0], w), m[1], w)
    Craw[x] = W.rotr(W.mul(W.xor(W.add(iv[1], x, w), a, w), m[2], w), r[1], w)
par = sum(1 for x in Craw if Craw[x] & 1) / len(Craw)
parq = sum(1 for x in C if C[x] & 1) / len(C)
print(f"  P(C(x) odd) in Z/2^w : {par:.4f}   <- the 2-adic handle Q26 exploits")
print(f"  P(C(x) odd) after mod q: {parq:.4f}   <- and v2 is no longer meaningful mod an odd prime")
