"""Can label-local capability come from a BOUNDED key? The derivation test.

The Q22 positive control isolates perfectly, but it is trivial: label L_i selects
an independent component, so the key grows linearly with the number of labels.
A useful scheme needs many labels under a bounded master key mu, with per-label
subkeys k_L = f(mu, L). The question is whether a witness at L -- which exposes
k_L -- leaves capability at L' intact.

Two regimes are separated here:

  INVERTIBLE derivation (Rainbow's own arithmetic is all invertible: odd
  multiply, rotate, xor, add). Then k_L determines mu determines k_L'. Predicted
  l_cross = l.

  LOSSY derivation, discarding d bits. Then k_L leaves ~2^d candidates for mu, so
  capability at L' is narrowed to ~2^d classes. Predicted l_cross = l - d, i.e.
  isolation is bought one-for-one with entropy thrown away.

If the second prediction holds, label-locality with a bounded key is
information-theoretically capped: n witnesses at distinct labels extract at most
s bits total, so capability collapses after s/k of them. That would say the route
needs COMPUTATIONAL one-wayness, which Rainbow's arithmetic does not supply.
"""
import sys, pathlib, math, random, statistics
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "og"))
from models import rainbow as R
from models import wordops as W
import stripe as ST


class Derived:
    """H(mu, L, x) = A_L(x) + k_L * C_L(x)  with  k_L = derive(mu, L)."""

    def __init__(self, w, loss):
        self.w, self.loss = w, loss
        self.base = R.default_theta(w)
        self.space = list(range(1, 1 << w, 2))          # master keys mu (odd)

    def derive(self, mu, L):
        w = self.w
        v = W.mul(W.add(mu, W.mul(L, 0x9E37, w), w), 0x2545 | 1, w)
        v = W.rotr(v, 3, w)
        if self.loss:                                    # discard `loss` low bits
            v = (v >> self.loss) << self.loss
        return v | 1

    def H(self, mu, L, x):
        th, w = self.base, self.w
        m, r = th.multipliers, th.mixa_rotations
        s = ST.iv(L, 2, w)
        a = W.mul(W.rotr(W.mul(W.sub(s[0], x, w), m[0], w), r[0], w), m[1], w)
        c = W.rotr(W.mul(W.xor(W.add(s[1], x, w), a, w), m[2], w), r[1], w)
        return W.add(a, W.mul(c, self.derive(mu, L), w), w)


def table(fam, mu, L):
    return tuple(fam.H(mu, L, x) for x in range(1 << fam.w))


def witness(fam, mu, L, rng):
    seen = {}
    for _ in range(1 << (fam.w // 2 + 6)):
        x = rng.randrange(1 << fam.w)
        h = fam.H(mu, L, x)
        if h in seen and seen[h] != x:
            return seen[h], x
        seen.setdefault(h, x)
    return None


def run(fam, labels, rng, trials=4):
    """Consume witnesses at labels[:-1]; measure capability at labels[-1]."""
    rows = []
    for _ in range(trials):
        mu = rng.choice(fam.space)
        cand = list(fam.space)
        Lp = labels[-1]
        K_all = len({table(fam, t, Lp) for t in fam.space})
        seq = []
        for L in labels[:-1]:
            wit = witness(fam, mu, L, rng)
            if wit is None:
                break
            xa, xb = wit
            cand = [t for t in cand if fam.H(t, L, xa) == fam.H(t, L, xb)]
            K_c = len({table(fam, t, Lp) for t in cand})
            seq.append((len(cand), K_c,
                        math.log2(len(fam.space) / len(cand)),
                        math.log2(K_all / K_c)))
        if seq:
            rows.append((K_all, seq))
    if not rows:
        return None
    K_all = rows[0][0]
    n = min(len(r[1]) for r in rows)
    out = []
    for i in range(n):
        out.append((statistics.median(r[1][i][0] for r in rows),
                    statistics.median(r[1][i][1] for r in rows),
                    statistics.median(r[1][i][2] for r in rows),
                    statistics.median(r[1][i][3] for r in rows)))
    return K_all, out


w = 8
print(f"w={w}: bounded master key mu ({w-1} bits of freedom), per-label subkey k_L")
print("Capability at a FRESH label after n witnesses at other labels.\n")
for loss in (0, 2, 4, 6):
    fam = Derived(w, loss)
    res = run(fam, [1, 2, 3, 5, 9], random.Random(7))
    if res is None:
        print(f"  loss={loss}: no witness"); continue
    K_all, seq = res
    tag = "invertible" if loss == 0 else f"lossy, discards {loss} bits"
    print(f"  derivation {tag}:  K(all, L')={K_all}")
    for i, (nc, Kc, l, lc) in enumerate(seq, 1):
        print(f"     after {i} witness(es): |cand|={nc:>5.0f}  K(cand,L')={Kc:>5.0f}"
              f"   l={l:5.2f}   l_cross={lc:5.2f}"
              + ("   ISOLATES" if lc < 0.5 else ""), flush=True)
    print()
