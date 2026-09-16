# Q18 — the DDT has two mechanisms with disjoint causes, and both live in the A branch

Q16 measured one number per row and saw "structure". Factoring it into

    M_r    = median over odd u of E_r(u) / shuffle-null       DEPTH bias
    R_r(u) = E_r(u) / M_r                                     RAY anisotropy

separates two effects that turn out to have **different causes and opposite
responses to the same ablation**. Apparatus: `og/ddt_spectrum.py`, runners
`og/run_ddt_ablation2.py` and `og/run_ddt_onset.py`.

## The object (an apparatus correction)

The DDT is of `G = C o A^-1` -- differences taken in the A coordinate, measured
in the C coordinate -- not of `H = A + B`. The first harness measured H, got
`R_6(1) = 3.2` instead of Q16's 133, and that mismatch is what identified the
error. H's DDT is comparatively flat; the structure is in G.

## The ray effect is real but it MOVES

The second apparatus error: the first ablation matrix reported `R_r(1)` at fixed
`r in {0,2,4,6,8}`. Several ablations do not destroy the ray, they **relocate**
it, and a fixed-r reading scores a moved ray as a dead one. Randomising the
rotations at w=16 sends r* to 11, 0, 11 across seeds while leaving peak strength
at 203 against real Rainbow's 397. Every number below is therefore
`max_r R_r(1)` with its argmax, not a fixed-r sample.

## The matrix

Three seeds per row, median reported. max M_r is over the same r range.

                       ------- w=12 -------    ------- w=16 -------
    variant             max M_r   max_r R    max M_r   max_r R    r*
    rainbow                10.9      45.3       53.0     396.9     8
    no-rot-a              587.4       3.5     6694.7       5.8     0
    no-rot-c               21.9      49.2      104.7     349.6     8
    no-rot                601.1       4.9     6538.8       7.9     0
    no-mul-a               60.6      23.9     1262.0     154.4     2
    no-mul-c               18.8      30.6       78.9     280.6     8
    couple-add            810.3       2.7     9750.2       3.0     7
    no-couple             696.7       4.6    11111.5       3.4     7
    rand-mults              6.6       2.7      104.9      11.6   scattered
    rand-rots              10.5      27.4       19.7     203.4   scattered
    rand-both              57.7       8.5      591.6       8.0   scattered

## What causes what

**The multipliers create the ray; the rotations mostly place it.** `rand-mults`
collapses the ray 45.3 -> 2.7 and 396.9 -> 11.6 (a 34x drop at w=16) while
leaving M_r at or below the real value. `rand-rots` PRESERVES a huge ray -- 203
against 397 is a factor-2 reduction, not none -- and scatters r* across 11, 0, 11.
The roles are distinguishable without claiming rotations have zero amplitude
effect: random rotations keep a large ray at a different depth, random
multipliers destroy it. So the anisotropy is a
property of Rainbow's *chosen constants*, not of the mul/rotr/mul shape --
sparsity of `d = 2^r` is necessary but nowhere near sufficient, since the same
sparse d gives R ~ 1 once the multipliers are random.

**A's rotation is what suppresses the depth bias.** Deleting it multiplies
max M_r by 54x at w=12 and 126x at w=16, and kills the ray at the same time. It
is doing exactly a rotation's job -- breaking multiplicative 2-adic structure --
and the ray depends on it being present.

**The XOR coupling is load-bearing for both.** Replacing it with modular addition
or deleting it entirely sends M_r to 810 / 9750 / 11111 and flattens R to ~3.
Without a non-ring operation the map is near-affine over Z/2^w and *every* row
concentrates. This is the separable control, and it places the whole phenomenon
in the ring/XOR mismatch.

**Ray formation is an A-branch phenomenon; the depth bias is not.** `no-rot-c`
and `no-mul-c` leave the ray at 0.88x and 0.71x of real Rainbow, so the C-side
operations are secondary for ray formation. They are NOT inert, though: at w=16
`no-rot-c` moves max M_r from 53.0 to 104.7 (2.0x) and `no-mul-c` to 78.9 (1.5x).
So the C-side operations are secondary for ray formation but measurably affect
the broad depth bias -- which is the more interesting statement, since it means
the two mechanisms have different spatial extents inside the round as well as
different causes.

A side observation worth keeping: at w=16 random multipliers give max M_r = 104.9
against real Rainbow's 53.0. Rainbow's actual constants **suppress** depth bias
relative to random odd words while creating the ray. Whether that trade is
deliberate is not something this measurement can say.

## Width scaling: r/w, not a constant carry window

The argmax is a poor observable -- the peak is a plateau (w=12 reads 41.8, 39.4,
45.3 at r=5,6,7). The turn-OFF is razor sharp and needs no threshold: R falls
from 217 to 1.1 in one step at w=14, 237 to 1.1 at w=16.

    w        10    12    14    16    18
    r_off     5     7     8     9    11
    w-r_off   5     5     6     7     7
    r_off/w  0.50  0.58  0.57  0.56  0.61

Regression gives `r_off ~ 0.70 w - 1.8`, with `r_off / w` stable at 0.56 +/- 0.04
while `w - r_off` grows. So the transition tracks **r/w**: a scale-stable 2-adic
phenomenon, not a finite active-word/carry window. Onsets are identical across
three seeds at every width, so this is a property of theta, not of the state.

(`r_on` is threshold-sensitive and should not be used: at w=10 the values sit at
8.0 and 9.3, just under a cutoff of 10, which pushes its onset late and makes the
series non-monotonic. An earlier by-eye reading of `w - r_on = 7,9,9,9` as a
constant active-bit window was an artifact of that.)

## Why this does not immediately give collisions

Unchanged from Q16: the collision family samples the DDT only along the line
`d + m e = 0`. Rows can carry 400x excess energy without raising collision
multiplicity, because the spikes sit off that line. The separation is what lets
the structure be enormous and operationally quiet at the same time.
