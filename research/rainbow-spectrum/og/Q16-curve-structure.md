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

## Addendum — the control above was wrong, and the real excess is far larger

`tau_d = A^-1 o T_-d o A` is **conjugate to translation**, so it has exactly `2^r`
cycles of length `2^(w-r)` with `r = v2(d)`, and around each cycle
`sum_j (C(x_j) - C(x_{j+1})) = 0` is forced. Verified exactly at w=12: 1, 2, 4,
16, 64, 2048 cycles of length 4096, 2048, 1024, 256, 64, 2.

The earlier "random control" randomised A as well, destroying that cycle
structure, and pooled all `dA` together, washing out per-direction concentration.
Both faults understate the effect.

**Correct null:** keep the real A and hence the real `tau`, keep the real multiset
of C values, and randomly permute C among the x's. That preserves cycle
structure, C's marginal, and the finite-domain constraints, while destroying
exactly the A-C alignment at issue. Stratified by `v2(dA)`, five shuffles each:

    v2(dA)   cycles x len   real maxN   shuffled maxN   energy ratio
       0       1 x 4096         74           6.4           6.57x
       1       2 x 2048         39           6.2           4.71x
       2       4 x 1024         29           6.2           4.54x
       4      16 x  256        211           5.8          32.86x
       6      64 x   64        537           6.4         133.35x
      11    2048 x    2        163           5.8          28.88x

The excess survives everywhere, including at `r = 0` where the cycle structure is
least degenerate and the null is therefore most honest. So **A and C are
genuinely correlated**: the curve has rebasing structure well beyond what
translation geometry alone accounts for.

## Correction to the reading above

The highest-multiplicity chords have `v2(dC) = 0` but `v2(dA) = 5`, so they are
**not collision chords** -- a collision chord has `dA = -m*dC` with m odd, forcing
`v2(dA) = v2(dC)`. The curve's excess additive structure lives on generic chords;
collision chords still average ~2 realizations. Both statements hold, and they
are about different sets.

On the link to the differential probe: the additive-energy concentration and the
earlier single-bit differential excess fall on the same `dA = +/- 2^j`
directions, which strongly indicates a common differential structure. That is a
coincidence of directions, not yet a demonstrated cause. The ablation that would
settle it -- randomising multipliers, rotation amounts and XOR position one at a
time, and checking whether both effects vanish together -- has not been run.
