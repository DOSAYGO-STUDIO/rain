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
