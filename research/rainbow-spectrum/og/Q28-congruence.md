# Q28 — there is no Rainbow-native one-way quotient of theta: the congruence lattice IS the 2-adic filtration

## The requirement

A public encoding `E` supports a public affine action iff its fibres form a
congruence: for every achievable `(a, c)`,

    E(theta1) = E(theta2)  =>  E(a + c theta1) = E(a + c theta2)

Only then is `T_{a,c}` well defined on the quotient. This is much stronger than
"the encoding is lossy".

## The argument, before enumerating

A public evaluator must work at every input `x`, so every pair
`(a, c) = (A(x), C(x))` is achievable. If two inputs share a `c` with different
`a`, then

    tau_{a,c} o tau_{a',c}^{-1} (theta) = theta + (a - a')

is a pure translation. An equivalence relation invariant under all translations
is a union of cosets of a subgroup, and the subgroups of `Z/2^w` are exactly
`<2^k>`. So the fibres can only be the residue classes mod `2^k` — the ring
quotient, i.e. truncation, which Q26 already killed.

Achievable translations, measured: 9 at w=6, 57 at w=7. The hypothesis holds.

## Enumerated exhaustively

For every starting pair `(0, d)`, the smallest congruence identifying them, over
the real Rainbow `A, C` (`og/run_congruence.py`):

    w=7, 128 achievable (a,c), 84 distinct c values
        1 of 127 pairs -> theta mod 64     (= Q26 truncation)
        2 of 127 pairs -> theta mod 32
        4 of 127 pairs -> theta mod 16
        8 of 127 pairs -> theta mod 8
       16 of 127 pairs -> theta mod 4
       32 of 127 pairs -> theta mod 2
       64 of 127 pairs -> total (constant: no information at all)

and the same shape at w=5 and w=6. **Zero irregular partitions at any width.**

Case 1 (injective: reveals theta) and Case 2 (ring quotient: Q26) are the only
outcomes. **Case 3 — a genuinely nonlinear Rainbow fibre stable under the affine
action — does not exist.** Not "was not found": there are provably none, and the
translation argument says why.

## The closing observation

The counts are exactly `2^(w-j-1)` starting pairs mapping to the quotient
`theta mod 2^(w-j)`, indexed by `j = v2(d)`. So the congruence lattice of the
secret coefficient under the collision action is **precisely the 2-adic
filtration** — the same ultrametric structure as the transport law, the incidence
balls, and the chord composition.

That is a satisfying way for the construction program to end. The geometry that
made Rainbow's collisions cheap and the obstruction that stops it becoming a
trapdoor are the same object. The 2-adic structure gives the keyholder a cheap
route, and its own congruence lattice is too coarse to hide the coefficient that
route depends on. There was never room for both.

## What is left outside Rainbow

The commit-and-prove escape stands: publish `D(theta)` as a commitment, and prove
in zero knowledge that a claimed collision is valid under the committed `theta`.
That needs no homomorphic encoding of `theta` and no public evaluation of
`H_theta`. It imports a proof system, so the public-key hardness comes from the
import, and by Q27 the collision layer would be better served by algebraic
inversion than by Rainbow's birthday steering anyway.

## Gate status, final

    1. private collision advantage       Rainbow supplies it, but publicly (to everyone)
    2. cross-label exposure isolation    achievable at (t+1)h -- standard technique (Q25/Q27)
    3. public evaluability without
       label-key recovery                NO NATIVE SOLUTION EXISTS (this file)
