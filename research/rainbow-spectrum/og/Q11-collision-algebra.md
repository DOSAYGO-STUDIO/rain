# Q11 — collisions transport across the family, by 2-adic distance

*Derived then measured, 2026-09-16.*

## The relation

With `A(x) = m1·rotr(m0·(s0−x), r0)` and
`B(x) = m3·rotr(m2·((s1+x) ⊕ A(x)), r1)`, the multiplier `m3` is the **outermost**
operation of B. So changing only `m3` scales B exactly and leaves A untouched:

    B' = (m3'/m3)·B ,  A' = A          measured 20000/20000

For a pair (x_a, x_b), write dA, dB for the differences. Then

    collision under θ :   dA + dB = 0
    collision under θ':   dA + c·dB = 0,      c = m3'/m3

Subtracting gives `(1−c)·dB = 0`.

## The mistake worth recording

I concluded `dB = 0`, hence `dA = 0`, hence `x_a = x_b` since A is a bijection —
so "no collision ever transports, and no common collision exists". Exhaustive
search at w=10 found **5** common collisions. The error is field reasoning in a
ring: `m3` and `m3'` are both odd, so `c` is odd and `1−c` is always **even**.
Z/2^w has zero divisors. (`attacks/zmod_invariant_search.py` was written because
of exactly this distinction, and I made the error anyway.)

## The corrected law

`(1−c)·dB ≡ 0 mod 2^w` requires only `dB ≡ 0 mod 2^(w−v)` where `v = v2(1−c)`.
So the transfer rate is `2^(−(w−v))`, governed by the **2-adic distance** between
the two family members. Writing `m3' = m3·(1+2^j)` gives `v = j`:

    j      v2(1−c)   predicted 2^-(w-j)   measured (w=16, 300 collisions)
    15       15           0.5000              0.480
    14       14           0.2500              0.280
    13       13           0.1250              0.133
    12       12           0.0625              0.060
     1        1           0.00003             0.000

So family members chosen **2-adically close** in `m3` share collisions at a rate
the designer controls, up to one half.

## What it does and does not give

It answers "do collisions have an algebra across the family" with a yes, in one
parameter direction, exactly. It is a genuine collision-transport map: a witness
for one member is a witness for a related member with probability `2^(j−w)`.

It does not by itself give amplification. Transport is *symmetric* — it is a
property of the parameters, which are public in the collision setting — so it
helps a keyholder and an attacker equally. Its value is as structure: it shows
the collision sets of the family are not independent objects, and it identifies
the direction (`m3`, the outermost multiply) in which they are related and the
metric (2-adic) that governs it.

The other directions are not similarly clean. `m1` scales A multiplicatively but
A feeds B's XOR, so B has no closed form under an `m1` change; `m0` and `m2` sit
inside the rotation; the rotations have no multiplicative structure at all. The
seed direction is Q1's exact two-carry condition for the bridge, and no closed
form for the collision. So the family has exactly one direction with clean
collision transport, not a general group action.

## Addendum — the law is an exact iff

Verified in both directions, not just as a rate: transfer holds **iff**
`v2(dB) >= w - nu`. At w=16 over 600 constructed collisions, agreement was
600/600 at every nu, and the transferred count equalled the
divisibility-satisfying count exactly:

    nu    predicted    agree(iff)   transferred   satisfying
    15      0.5000      600/600         263           263
    14      0.2500      600/600         139           139
    13      0.1250      600/600          76            76
    12      0.0625      600/600          43            43
    10      0.0156      600/600           9             9
     8      0.0039      600/600           3             3

So `C_theta ∩ C_theta'` is exactly `{ c : v2(dB(c)) >= w - v2(c-1) }`, giving a
filtration `C^(1) ⊂ C^(2) ⊂ … ⊂ C^(w)` selected by 2-adic parameter distance.

# Q12 — B made faithful to production Rainbow

Production schedule (mixA on even block index, mixB + rotate_right on odd),
production-style IV, randomised theta (the parameters that must stay secret).
The relation stays STATE equality rather than digest equality: the finalization
is lossy -- at w=4 it maps 65,536 states onto 4,014 digests -- so a
digest-equality relation would flood the problem with spurious witnesses, which
is the sparse-witness defect B was designed to avoid.

Witness planted by inverting backwards, which needs the inverse of mixB+rotate
as well as mixA.

    w=12  k=2 (mixA in prefix)           sigma route 12/12 at 4*2^(w/2)
    w=12  k=3 (mixB+rotate in prefix)    sigma route  0/12
    w=14  k=2                            12/12 at 4*2^(w/2)
    w=14  k=3                             0/12

So B survives being made faithful -- at k=2, and only at k=2. Once a
pair-crossing mixer sits inside the prefix, per-pair separability is gone and the
privileged route fails outright.

Consequences worth stating:

  * B's k=2 is not a simplification chosen for convenience. Production's own
    alternation forces it.
  * The earlier layering experiments added mixA-only rounds, i.e. they layered a
    construction that had already departed from Rainbow. In a faithful setting
    there are no extra prefix rounds to add, so that lever does not exist.
  * An earlier run of this test gave 3/12 at k=2 and looked like a partial
    failure. That was an experimental error -- random S and T with no planted
    witness, so the sigma match had only birthday luck, ~40% for two pairs, and
    3/12 is exactly that. Planting is what makes the comparison meaningful.
