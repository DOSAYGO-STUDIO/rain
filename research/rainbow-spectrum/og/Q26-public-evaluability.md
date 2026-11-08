# Q26 — public evaluation cannot conceal a label key, and truncation does not save it

## The law, verified

If the public evaluator exposes `H_theta(x) = A(x) + theta C(x)` with `A, C`
public, then `D(x) = H_theta(x) - A(x) = theta C(x)` is a linear equation in
`theta`. After queries `x_1..x_q` with `r = min_i v2(C(x_i))`, exactly

    2^min(r, w-1)   candidates remain

verified exhaustively at w = 8, 10, 12 over 60 random trials at q = 1, 2, 3.

**The cap matters and was not in the original statement.** When every queried
`C(x_i) = 0` the observation is vacuous, `r = w`, and the naive `2^r` would
predict 1024 survivors at w=10 where only 512 odd residues exist. The correct
exponent is `min(r, w-1)`; this showed up as a genuine mismatch before the cap
was added.

This is **representation-independent**. No circuit flattening, gate-level
compilation or obfuscation helps, because the input/output relation already
contains the key equation. That is strictly stronger than Q3's "geometry
recovered in four evaluations", which was a statement about an artifact.

## Exposure is immediate

    w    P(C(x) odd)    random queries to r=0 (mean)    chosen queries
    8       0.5000                  2.04                      1
   10       0.5000                  1.98                      1
   12       0.5000                  2.04                      1
   14       0.5000                  1.98                      1

`C` is a balanced parity map at every width, so one CHOSEN query exposes `theta`
outright and two random ones suffice on average.

## Truncation: the one escape Rainbow has, and it fails

Rainbow's only lossy element is truncation (Q20). If the public sees the low `k`
bits of `H`, each query gives `theta` only modulo `2^(k - v2(C))`, so recovery is
capped. Measured, w=12, 8 chosen queries:

    k       12     10      8      6      4      2
    residual 1      4     16     64    256   1024
    log2  0.00   2.00   4.00   6.00   8.00  10.00

exactly `2^(w-k)`. So truncation does bound key recovery.

**But it bounds the public's alternative harder.** With a `k`-bit public output:

  * key recovery costs `2^(w-k)`;
  * a GENERIC collision on the `k`-bit output costs `2^(k/2)`;
  * and the private route cannot beat the birthday bound on the output it
    actually produces, so `C_private >= 2^(k/2)`.

Therefore `C_public <= 2^(k/2) <= C_private` for **every** `k`. There is no
truncation level at which the keyholder has an advantage. Balancing the two
public routes (`w-k = k/2`, i.e. `k = 2w/3`) gives a public cost of `2^(w/3)`
against a private `2^(w/2)` — the trapdoor would be slower than the attack.

This is Q17's lesson recurring in a third setting: a hidden capability is worth
nothing unless exploiting it beats the best structure-free attack. Truncation
hides the key by making the problem easier for everyone.

## The three gates, stated separately

    1. private collision advantage          Rainbow's pair-sum weakness supplies this
    2. cross-label exposure isolation       Q25 PASSES at key O(t h)
    3. public evaluability without
       label-key recovery                   FAILS for the raw evaluator, by the
                                            law above, independently of encoding

Gate 3 is now the central unsolved problem, and the failure is information-
theoretic rather than a matter of representation. So the interface cannot reveal
`H_theta` itself. What is needed is a publicly computable secret-linear action
with one-way recovery of the coefficient — something that lets anyone compute an
encoding of `A(x) + theta C(x)` without exposing `theta`.

The obvious shape, publishing `g^theta` and evaluating
`g^A(x) (g^theta)^C(x)`, does not work over `Z/2^w`: a cyclic group of order
`2^w` is maximally smooth and hides no discrete logarithm. So the primitive is
missing rather than merely unbuilt, and importing one means the imported problem
supplies the public-key secrecy while Rainbow supplies the collision engine and
Q25 supplies bounded exposure resistance.

That is a legitimate composite design. It is not "Rainbow contains a public-key
trapdoor".
