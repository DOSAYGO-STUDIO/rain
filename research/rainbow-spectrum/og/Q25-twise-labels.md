# Q25 — bounded-exposure label isolation works, with key O(t h) instead of O(N h)

## The correction that opened this

Q24 argued from pairwise isolation to joint independence. That step is invalid:
`K_L = a L + b` over a field is pairwise independent while the master key is `2h`
bits. The correct bound is exposure-parameterized -- isolation against any `t`
exposed labels requires `(t+1)`-wise independence and

    H(K) >= (t + 1) h

The tell was in Q24's own data. Its degree-3 derivation leaked `l_cross = 1.00`
after ONE witness, which under genuine pairwise independence is impossible. So
the derivation was broken, not the idea:

  * polynomials taken over `Z/2^w`, which has zero divisors, so the Vandermonde
    is not invertible and evaluations at distinct labels are correlated;
  * coefficients restricted to odd values, biasing the family;
  * `v | 1` is 2-to-1, not a bijection onto the odd multipliers.

## Done properly

Coefficients uniform over `GF(2^h)` with `h = w-1`, labels distinct nonzero field
elements, `z_L = a_0 + a_1 L + ... + a_t L^t` by Horner in the field, and

    theta_L = 2 z_L + 1

which is a genuine bijection from `GF(2^h)` as `h`-bit integers onto the odd
residues mod `2^w`. Witnesses are real Rainbow collisions of
`H(x) = A(x) + theta_L C(x)`; consistent sets are Q14's exact incidence balls.
Whole key space enumerated. `og/run_twise_labels.py`, w=6, h=5:

    t=1, key 2 x 5 = 10 bits      t=2, key 15 bits        t=3, key 20 bits
    n=1  lc=0.00  ISOLATES        n=1  lc=0.00  ISOLATES  n=1  lc=0.00  ISOLATES
    n=2  lc=3.00  partial         n=2  lc=0.00  ISOLATES  n=2  lc=0.00  ISOLATES
    n=3  lc=5.00  COLLAPSED       n=3  lc=4.00  partial   n=3  lc=0.00  ISOLATES
    n=4  lc=5.00  COLLAPSED       n=4  lc=5.00  COLLAPSED n=4  lc=2.00  partial
                                                          n=5  lc=5.00  COLLAPSED

**Exactly `l_cross = 0` through `t` witnesses, degradation at `t+1`, collapse at
`t+2`.** Cross-label capability is untouched -- `K(cand, L') = 32` out of 32 --
while the master key visibly bleeds: 32768 candidates down to 256 at t=3.

The one-step margin beyond the field-theoretic bound is Rainbow's own doing: a
witness pins `theta_L` to an incidence BALL rather than a point, so `t+1`
witnesses under-determine the polynomial slightly and full collapse needs `t+2`.

## What this establishes

A **bounded-exposure label-isolation construction** with key size `O(t h)` rather
than `O(N h)`, using real Rainbow collision witnesses. This is the first
construction in the program that is neither a global secret (dead since Q21/Q22)
nor one-secret-per-label (works but pays `N h`). The trade is explicit and
tunable: choose the exposure threshold `t`, pay `(t+1) h` bits.

Revised landscape:

    global structural secret                    dead (Q21, Q22)
    info-theoretic isolation, t exposures       WORKS at (t+1)h -- this file
    fixed key, unbounded exposures              needs computational hardness (Q23)
    public-key realization                      STILL OPEN -- see below

## The gate this does NOT pass

Cross-label isolation of the collision engine is not a public-key trapdoor. A
public representation is still needed from which anyone can evaluate and verify
at label `L` without learning `theta_L`, and that is a separate gate this file
says nothing about.

It is also the gate with the most discouraging prior evidence in this repo: Q3
measured that the injection geometry leaks in FOUR evaluations under program
access. If a public artifact for label `L` leaks `theta_L` that cheaply, the
isolation bought here is spent immediately -- not because the labels failed, but
because the public side hands over what the labels were protecting.

So the next question is not another sharing scheme. It is whether a public
evaluator for one label can exist at all, and Q3 is the measurement to beat.
