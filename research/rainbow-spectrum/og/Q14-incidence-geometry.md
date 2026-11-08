# Q14 — the incidence geometry of collisions and family parameters

Writing `H_m(x) = A(x) + m·C(x)` with `m = m3` (so `B = m·C`; m is a unit, hence
`v2(dB) = v2(dC)`). A chord `e = (dA, dC)` is a collision for m iff
`dA + m·dC = 0`.

## Derived

**Multi-member intersection.** The constraints `(m_i − m_1)·dC = 0` generate the
ideal `2^(min_i v2(m_i − m_1))`, so

    v2(dC) >= w − min_i v2(m_i − m_1)

i.e. the single most 2-adically **distant** member decides the radius; the rest
are free. **Measured 2400/2400 exact.**

**Reverse incidence.** With `dC = 2^v·u`, u odd, `m·dC = −dA` is solvable iff
`2^v | dA`, and then m is determined modulo `2^(w−v)` — a coset of exactly `2^v`
parameters. So a chord does not belong to one member; it names a ball.

**Depth programming.** Forcing `v2(dC) >= r` means colliding the pair
`(H, C mod 2^r)`, i.e. w+r bits, so it should cost `2^((w+r)/2)` — r/2 extra
bits, not r.

## Measured

    v2(dC) over 500 natural collisions   0.508 / 0.242 / 0.128 / 0.054
    geometric expectation                0.500 / 0.250 / 0.125 / 0.0625

So the attack is unbiased across the tree; it does not favour any depth.

    forcing v2(dC) >= r     r=0     r=2     r=4     r=6
    log2 evals/collision   8.30    9.43   10.48   11.77
    predicted (w+r)/2      8.00    9.00   10.00   11.00

## Corrections (both verified)

**Parity was never secret.** Multipliers are odd by construction, so the family
has `2^(w-1)` members, not `2^w`. And since `m = m0 mod 2^(w-v)` with `2^(w-v)`
even for `v <= w-1`, every one of the `2^v` solutions shares `m0`'s parity, so
all are odd. Measured: compatible set size `= 2^v` in 300/300, all odd in
300/300. Uncertainty therefore falls from `w-1` bits to `v`, so the leak is

    l = (w - 1) - v2(dC)

one bit less than the `w - v` first written here.

**The no-leak endpoint is r = w-1, not r = w.** At `r = w`, `dC = 0`, which with
the H-collision forces `dA = 0`, and A is bijective, so `x_a = x_b`. Only the
trivial chord survives; measured 0/300 nontrivial chords with `dC = 0`. The
meaningful extreme is `r = w-1`, where the chord reveals only `m mod 2` — already
known — at cost `2^(w-1/2)`.

**Closed form.** Substituting `r = w - 1 - l` into `C(r) ~ 2^((w+r)/2)`:

    l = (w-1) - v2(dC),        log2 C ~ w - 1/2 - l/2

The incidence/leakage half is exact; the cost half carries the birthday
assumption.

**Multiple collisions do not accumulate.** Each chord gives a ball containing the
true m, and in a 2-adic space intersecting balls are nested, so

    l_total = max_i l_i        not the sum

Measured: the intersection of three balls equalled the smallest ball in 200/200.
Consequently n ordinary collisions expose m uniquely with probability ~`1 - 2^-n`
-- measured 0.487 / 0.707 / 0.853 / 0.919 for n = 1..4 against 0.5 / 0.75 /
0.875 / 0.938. But n collisions all generated at depth `>= r` stay inside one
ball and reveal no more than one of them does.

## The leakage, which is severe

Of 200 chords, **104 pinned m uniquely** — matching the 50.8% with `dC` odd. So
publishing one ordinary collision usually reveals `m3` exactly, and in general a
chord leaks `w − v2(dC)` bits of congruence information about it.

Combining with depth programming gives an exact cost/disclosure curve:

    leak only (w − r) bits about m   <->   pay 2^((w+r)/2) instead of 2^(w/2)

and leaking nothing (r = w) costs `2^w`, precisely the generic bound. So secrecy
in this coordinate is bought back at exactly the rate the weakness gave it away.

## Design consequence

`m3` cannot be a secret in any scheme that publishes collisions. This is not a
weakness of a particular construction but of the coordinate: the incidence
relation `R(m, x_a, x_b)` is too informative. Any trapdoor built on this geometry
must either keep collisions private, or hide the parameter somewhere other than
the outer multiplier.
