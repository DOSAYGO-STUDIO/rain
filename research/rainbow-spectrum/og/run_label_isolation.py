"""Q22 -- does a witness at label L reduce collision CAPABILITY at a fresh label L'?

The wrong question (Q21's proposal) was "does the consistent master-key set shrink
across labels". It does so even for a perfect label: if L_i selects an independent
component theta_i, a witness at L_1 exposes theta_1 completely and the global
posterior shrinks, yet knowing theta_1 buys nothing at L_2. Master-key entropy
loss is not label failure.

The right question is operational. Define the capability class at L':

    K(Theta, L')  = number of DISTINCT functions H(theta, L', .) as theta ranges
                    over a candidate set

An attacker holding a witness W_L can only narrow theta to S_L, and their best
play at a fresh L' is to guess a candidate and run the private algorithm. Their
expected work is proportional to K(S_L, L'), against K(Theta, L') with no witness.
So the transfer advantage is exactly

    l_cross = log2 K(Theta, L') - log2 K(S_L, L')

    l_cross = 0       the label ISOLATES: the witness bought nothing at L'
    l_cross = l       the label is DECORATIVE: full carry-over

Both controls are run, because a metric that cannot separate them is worthless:
  * perfect  -- label selects an independent subkey. MUST give l_cross = 0 while
                global leakage l > 0. This is the case that kills the naive metric.
  * decorative -- label merely shifts the input. MUST give l_cross = l.
"""
import sys, pathlib, math, random, statistics
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "og"))
from models import rainbow as R
from models import wordops as W
import stripe as ST


# --------------------------------------------------------------- the families
class RainbowSeed:
    """theta = the outer multiplier m3 (Q14's coordinate). label = the seed."""
    name = "rainbow-seed"

    def __init__(self, w):
        self.w = w
        self.base = R.default_theta(w)
        self.space = list(range(1, 1 << w, 2))

    def H(self, theta, label, x):
        th = self.base
        m, r = th.multipliers, th.mixa_rotations
        w = self.w
        s = ST.iv(label, 2, w)
        a = W.mul(W.rotr(W.mul(W.sub(s[0], x, w), m[0], w), r[0], w), m[1], w)
        c = W.rotr(W.mul(W.xor(W.add(s[1], x, w), a, w), m[2], w), r[1], w)
        return W.add(a, W.mul(c, theta, w), w)


class PerfectLabel:
    """POSITIVE CONTROL. theta = (t0, t1); an even label uses t0, an odd one t1."""
    name = "perfect-label"

    def __init__(self, w):
        self.w = w
        self.base = R.default_theta(w)
        half = list(range(1, 1 << (w // 2 + 1), 2))
        self.space = [(a, b) for a in half for b in half]

    def H(self, theta, label, x):
        t = theta[label & 1]
        th, w = self.base, self.w
        m, r = th.multipliers, th.mixa_rotations
        s = ST.iv(0, 2, w)
        a = W.mul(W.rotr(W.mul(W.sub(s[0], x, w), m[0], w), r[0], w), m[1], w)
        c = W.rotr(W.mul(W.xor(W.add(s[1], x, w), a, w), m[2], w), r[1], w)
        return W.add(a, W.mul(c, W.make_odd(t, w), w), w)


class DecorativeLabel:
    """NEGATIVE CONTROL. The label only shifts the input."""
    name = "decorative-label"

    def __init__(self, w):
        self.w = w
        self.base = R.default_theta(w)
        self.space = list(range(1, 1 << w, 2))

    def H(self, theta, label, x):
        th, w = self.base, self.w
        m, r = th.multipliers, th.mixa_rotations
        s = ST.iv(0, 2, w)
        x = W.add(x, label, w)
        a = W.mul(W.rotr(W.mul(W.sub(s[0], x, w), m[0], w), r[0], w), m[1], w)
        c = W.rotr(W.mul(W.xor(W.add(s[1], x, w), a, w), m[2], w), r[1], w)
        return W.add(a, W.mul(c, theta, w), w)


# ------------------------------------------------------------- the measurement
def table(fam, theta, label):
    return tuple(fam.H(theta, label, x) for x in range(1 << fam.w))


def witness(fam, theta, label, rng):
    seen = {}
    for _ in range(1 << (fam.w // 2 + 6)):
        x = rng.randrange(1 << fam.w)
        h = fam.H(theta, label, x)
        if h in seen and seen[h] != x:
            return seen[h], x
        seen.setdefault(h, x)
    return None


def measure(fam, L, Lp, rng, trials=5):
    out = []
    for _ in range(trials):
        theta = rng.choice(fam.space)
        wit = witness(fam, theta, L, rng)
        if wit is None:
            continue
        xa, xb = wit
        S_L = [t for t in fam.space if fam.H(t, L, xa) == fam.H(t, L, xb)]
        K_all = len({table(fam, t, Lp) for t in fam.space})
        K_SL = len({table(fam, t, Lp) for t in S_L})
        l = math.log2(len(fam.space) / len(S_L))
        l_cross = math.log2(K_all / K_SL)
        out.append((l, l_cross, len(S_L), K_all, K_SL))
    if not out:
        return None
    return (statistics.median(o[0] for o in out),
            statistics.median(o[1] for o in out),
            statistics.median(o[2] for o in out),
            out[0][3], statistics.median(o[4] for o in out))


w = 8
print(f"w={w}: global leakage l vs cross-label capability leakage l_cross")
print(f"{'family':<18}{'L':>4}{'L2':>6}   {'|S_L|':>7}{'K(all)':>8}{'K(S_L)':>8}"
      f"{'l':>7}{'l_cross':>9}   verdict")
for fam_cls in (PerfectLabel, DecorativeLabel, RainbowSeed):
    fam = fam_cls(w)
    rng = random.Random(4)
    for L, Lp in ((0, 1), (0, 3)):
        res = measure(fam, L, Lp, rng)
        if res is None:
            print(f"{fam.name:<18}{L:>4}{Lp:>6}   no witness"); continue
        l, lc, nS, Kall, KS = res
        verdict = ("ISOLATES" if lc < 0.5 else
                   "decorative" if lc >= l - 0.5 else "partial")
        print(f"{fam.name:<18}{L:>4}{Lp:>6}   {nS:>7.0f}{Kall:>8}{KS:>8.0f}"
              f"{l:>7.2f}{lc:>9.2f}   {verdict}", flush=True)


def direct_transfer(fam, L, Lp, rng, trials=400):
    """Does the witness ITSELF still collide at L'? A different question from
    capability transfer, and the one 2-adically-near labels could plausibly pass."""
    hit = tot = 0
    for _ in range(trials):
        theta = rng.choice(fam.space)
        wit = witness(fam, theta, L, rng)
        if wit is None:
            continue
        xa, xb = wit
        tot += 1
        hit += fam.H(theta, Lp, xa) == fam.H(theta, Lp, xb)
    return hit, tot


def seed_sweep(w=8):
    fam = RainbowSeed(w)
    print()
    print(f"ADVERSARIAL SEED SWEEP, w={w}: L=0, L' = 2^j and random")
    print(f"{'L2':>10}{'v2(L2-L)':>10}   {'l':>6}{'l_cross':>9}"
          f"   {'direct transfer':>16}   verdict")
    labels = [(1 << j, j) for j in range(w)] + \
             [(random.Random(k).randrange(1, 1 << w), None) for k in (1, 2, 3)]
    for Lp, j in labels:
        rng = random.Random(11)
        res = measure(fam, 0, Lp, rng, trials=5)
        rng2 = random.Random(12)
        hit, tot = direct_transfer(fam, 0, Lp, rng2, trials=200)
        if res is None:
            continue
        l, lc, nS, Kall, KS = res
        verdict = "ISOLATES" if lc < 0.5 else ("decorative" if lc >= l - 0.5 else "partial")
        jj = "-" if j is None else str(j)
        print(f"{Lp:>10}{jj:>10}   {l:>6.2f}{lc:>9.2f}   "
              f"{hit:>6}/{tot:<6} = {hit/max(tot,1):5.3f}   {verdict}", flush=True)


if "--sweep" in sys.argv:
    seed_sweep()
