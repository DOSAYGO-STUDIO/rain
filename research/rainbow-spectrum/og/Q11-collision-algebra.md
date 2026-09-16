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
