# Q19 — the outer A multiplier is (almost) a gauge, and Q18's multiplier claim is retracted

## The argument that forced this

Write `A(x) = m1 Z(x)`. Changing `m1 -> m1'` gives `A' = c A` with
`c = m1' m1^-1`. If `C` did not depend on `m1`, then `G' = C o A'^-1 = G o c^-1`
and every DDT row would be relabelled exactly:

    N_G'(d, e) = N_G(c^-1 d, e)

Then `m1` could not create or destroy anything -- it would only move the ray
among the odd units at the same valuation, and the ray at `d = 2^r` stays on the
`u = 1` coordinate iff `(c - 1) 2^r = 0 mod 2^w`, i.e. `v2(m1' - m1) + r >= w`.
That reproduces the measured recovery thresholds EXACTLY at every width
(`j_rec = w - r_off`: 5,5,6,7 against `r_off` = 5,7,8,9), which was the tell.

## Measured: not exact, but mostly right

The gauge is not exact because `C` reads `A(x)` through the XOR
(`k = (s1 + x) XOR A(x)`), so `C' != C`. `og/run_ddt_gauge.py`, w=12, 256 rows:

    m1'          v2     rows relabelled exactly   row-energy rel. error (median, max)
    m1 + 2^2      2            0 / 256               0.16      1.41
    m1 + 2^5      5            0 / 256               0.14      1.05
    m1 + 2^8      8            0 / 256               0.11      1.24
    m1 + 2^11    11            0 / 256               0.01      0.29
    random        -            0 / 256               0.14      1.33
    random        -            0 / 256               0.13      2.59

Zero rows relabel exactly; typical row energy moves 10-16%. So `m1` is an
approximate gauge broken by the XOR feedback, not a symmetry.

## The quotiented ablation

If the coordinate can move, the honest per-depth observable is the maximum over
ALL odd units, `S_r = max_u E_r(u) / null`, which is invariant under any exact
unit relabelling of the A coordinate. `og/run_ddt_quotient.py`, w=12, every odd
u enumerated, per-table null, median of 3 seeds:

    variant         r=0      2      4      5      6      7      8     10    peak
    rainbow        13.2   23.9   33.1  101.5  134.4  142.7    7.9   10.9   142.7 @7
    rand-m0        13.8   19.3   42.4   93.8  133.2  140.9    6.3    6.1   140.9 @7
    rand-m1        10.7    9.1   19.2   33.6   49.4   45.0    6.9   10.8    49.4 @6
    rand-m2        13.3   19.0   29.0  101.9  141.0  187.9    7.3    9.4   187.9 @7
    rand-rots      14.9   22.0   50.9   56.0   80.5   85.3  105.4   10.4   105.4 @8
    rand-mults     10.1   12.1   24.9   40.2   37.4   34.8    4.6    6.6    40.2 @5
    no-rot-a       17.4   16.0   30.3   57.6   61.4  107.4  150.8  588.2   588.2 @10
    no-rot-c       31.7   39.8   82.1  148.0  208.0  257.7   14.3   21.8   257.7 @7
    no-mul-a       47.0   36.7   50.4   92.9  133.5  146.3   46.3   60.4   146.3 @7
    no-mul-c       37.3   28.6   72.7   77.8  130.5  130.2    9.3   18.7   130.5 @6
    couple-add   1124.7 1155.9  649.6  914.1  742.7  524.1 1563.1  694.6  1563.1 @8
    no-couple     868.5 1259.7 1593.5 1239.1  856.1  571.5  983.6  473.3  1807.7 @3

## What Q18 got wrong, and what survives

**Retracted: "the multipliers create the ray."** With all odd u searched,
random multipliers leave a 40x ray (`rand-mults` 40.2 @5). The ray's EXISTENCE is
a property of the mul / rotr / mul + XOR shape, not of the constants. Q18's "34x
collapse" under `rand-mults`, and the m[1] sweep's "1.8 at j=1", were ~90% the ray
leaving the `u = 1` coordinate and ~10% real.

**Corrected roles of the constants.**

  * `m1` -- approximate gauge. Random `m1` relocates the ray and costs ~3x
    (142.7 -> 49.4); the residual is the XOR feedback. Rainbow's actual `m1` is
    the gauge in which the strongest direction is the single bit `d = 2^r`. A
    neighbour (`m1 XOR 2^9` at w=16) gives a ray 3x stronger, so it is not the
    ray-maximising choice.
  * `m0` -- inert for the ray (140.9 vs 142.7). Not structural.
  * `m2` -- modulates; random `m2` raised the peak to 187.9.
  * `m3` -- exact gauge (unit rescaling of the e-axis; provably preserves
    `sum_e N^2`; measured constant to the digit in 33/33 cells).
  * rotations -- relocate in depth and cost ~0.74x.

**Survives.** The XOR coupling is load-bearing: without it every direction
concentrates at ~10^3 (`couple-add`, `no-couple`). `no-rot-a` still explodes the
depth bias (588 @10). Those were structural in Q18 and remain so.

## The 2-adic law, restated honestly

`v2(m1' - m1) + r >= w` is exactly the annihilator condition for a rescaled
direction to fix itself mod `2^w`, and it holds at every width measured. It is
the same arithmetic as collision transport (`v2(m' - m) + v2(e) >= w`) but it
does NOT show that the transport mechanism causes the DDT resonance. What it
shows is that the ring `Z/2^w` acts on the collision geometry and on the DDT
coordinate system in two different exact ways. That is the claim to keep.

## Apparatus

The `(j, r)` survival map in `og/run_ddt_transport_map.py` shows the preserved
region as a clean triangle `r >= w - j` at w=12 and w=14. It was originally run
as evidence for "the same metric governs both"; it is now evidence for the
coordinate-fixing law above, which predicts the identical triangle.
