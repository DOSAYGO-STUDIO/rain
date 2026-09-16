# Q16 — the message curve is not random, and the excess sits on dA = +/- 2^j

## Rebasing, formulated exactly

A chord `e = (dC, dA)` is rebasable wherever `Gamma(x) - Gamma(y) = e`. Since A is
a bijection, fixing `dA` makes `x -> y = A^-1(A(x) - dA)` a permutation, so

    N(e) = #{ x : C(x) - C(tau_dA(x)) = dC }

and for each `dA` the 2^w values of x distribute over the dC values. Uniform
would give N ~ 1; concentration means structure.

## Measured, against a matched control

The control is a random curve with A still a bijection -- same shape, no algebra.
w=10, all ordered pairs, averaged over three instances:

                        distinct    mean N   max N   energy/pairs
    real Rainbow         497,665     2.105     175      4.152
    random control       662,174     1.582      10      1.999

So the curve carries **2.08x the additive energy** of a random set of the same
shape, and a maximum multiplicity **17.5x** higher.

## Where the excess lives

The top chords by multiplicity all have `dA = +/- 2^j`:

    N=183  dA = +2^5      N=98  dA = +2^3      N=78  dA = +2^2
    N=183  dA = -2^5      N=98  dA = -2^3      ...

and in aggregate, chords with N >= 20 have mean `v2(dA) = 2.05` against `0.80`
for chords with N == 1. The excess additive structure is concentrated on
single-power-of-two A-differences.

That is the same phenomenon as the earlier differential probe, where one output
difference for a single-bit input difference occurred at ~8,300x baseline. Two
independent measurements, one cause: a single-bit additive difference propagates
through `mul, rotr, mul` with far less spreading than a random difference.

## What it means for rebasing

Outcome 2 of the three: **structured multiplicity, concentrated rather than
abundant**. Typical collision chords average only ~2 realizations, so arbitrary
collision chords cannot be freely moved to new endpoints. The groupoid law of
Q15 remains the operational content; rebasing is not a general tool.

Collision-chord multiplicity stratified by depth showed only a weak trend
(mean N 1.89, 2.02, 2.46, 3.07 for v2(dC) = 0..3, falling after), on small
samples. Not enough to claim depth controls rebasability.
