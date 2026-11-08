# Q15 — collision chords compose, and composition can climb the parameter tree

## The groupoid is exact

With `Gamma(x) = (C(x), A(x))` and `e_xy = Gamma(x) - Gamma(y)`, chords sharing an
endpoint telescope:

    e_xy + e_yz = e_xz

so the sum is automatically a realisable message chord, and if
`H_m(x) = H_m(y) = H_m(z)` then `e_xz` is a collision too. Messages are objects,
collisions are morphisms, `(x,y) o (y,z) = (x,z)`, with identity `(x,x)` and
inverse `(y,x)`. Verified on 250 three-way multicollisions.

## The ball law is exact in both branches

    B(e_xy) ∩ B(e_yz) ⊆ B(e_xz)                    250/250

and splitting by whether the valuations cancel:

    v2(dC_xz) == min(...)   ->  B(e_xz) == intersection     166/166
    v2(dC_xz)  > min(...)   ->  B(e_xz)  > intersection      84/84

Two further exact checks:

    |B(e)| == 2^v2(dC) for all three chords          250/250
    enlargement factor == 2^(v3 - min(v1,v2))        250/250

and the cancellation-depth distribution:

    depth 0 (none)  0.664      depth 3  0.052
    depth 1         0.168      depth 4  0.032
    depth 2         0.080      depth 5  0.004

**Cancellation occurs exactly when v1 == v2.** If the valuations differ then
`v2(dC_xy + dC_yz) = min` exactly. If they are equal, both terms are `2^j * odd`
so their sum is `2^j * even` and `v3 >= j+1` always. Hence

    P(no cancellation) = 1 - sum_j 2^-2(j+1) = 1 - 1/3 = 2/3

against the measured 0.664. So the whole branch structure is predicted, not just
observed. So composing two collisions
gives a collision whose compatible-parameter ball is exactly the intersection of
the constituents' -- unless the `dC` valuations cancel, in which case the result
sits strictly **higher** in the 2-adic tree and is compatible with MORE family
members.

Combined with Q14's leakage law `l = (w-1) - v2(dC)`, that means composition can
never leak more than the strongest constituent, and under cancellation it leaks
strictly **less**:

    l(e1 o e2) <= min(l(e1), l(e2))

## But cancellation is not a cheap knob

Programming the composed depth would mean forcing `dC_xy = -dC_yz mod 2^r`.
Within an H-bucket that needs roughly `2^r` candidate pairs, hence a
multicollision of size about `2^(r/2)`, which is far more expensive than the
direct route of colliding `(H, C mod 2^r)` at `2^((w+r)/2)` (Q14).

So the composition law is **structural, not operational**: it says exactly how
parameter specificity combines, and it does not give a cheaper way to obtain a
chosen specificity.

## Open

Chords that do NOT share an endpoint need not sum to a realisable chord. Whether
arbitrary collision chords can be cheaply rebased onto a common endpoint -- which
would upgrade this groupoid into a genuine message-level algebra -- is untested.
