# Q17 — hiding the coordinate system: passes gate 3, fails gate 1

## The idea

Rather than making a parameter secret (dead: Q14 shows one ordinary collision
usually reveals `m3`), make the **coordinate system** secret. Public
`F(x) = H(c x)` for secret odd `c`; the keyholder transforms into `u = c x`
where the collision geometry is known, exploits it, and transforms back. The
public sees a function whose privileged differential directions have moved to
`c^-1 * 2^j`.

The sharp test, given Q16: the preferred DDT rows sit 13x to 136x above the
correct null. Are they beacons a public attacker can home in on?

## Measured

    w    strongest ray   hidden dirs      probes to find   generic collision
    10      13x            19 / 1024            46               32
    12      34x            23 / 4096           272               64
    14     136x            27 / 16384        2,059              128

## Gate 3 passes: the beacons really are hidden

Locating one costs about `2^w / 2w` probes. The strength of a row is irrelevant
to the search cost -- recognising a 136x peak takes a handful of samples once you
are looking at the right `d`, but there are `2^w` values of `d` and only about
`2w` good ones. So a secret linear transform does conceal the privileged
directions despite their enormous statistical signature.

## Gate 1 fails: the hidden thing is not worth finding

Finding the hidden direction costs `2^w / w`, while simply colliding the same
object costs `2^(w/2)`. The beacon route is therefore 1.4x, 4.3x and 16x DEARER
than the attack a public adversary would actually run, and the ratio grows as
`2^(w/2) / w`. The public never needs the privileged coordinate.

**The general lesson.** A hidden capability is only worth hiding if it beats the
adversary's best alternative. Here the weak structure makes collisions cheap for
*everyone* at `2^(w/2)`, which is below the cost of locating what was hidden. The
secret protects something the attacker does not want.

## What this does not settle

The model collapses the target to the w-bit `H`, where generic collision is
`2^(w/2)`. In full Rainbow the digest is 4w bits and generic is `2^(2w)`, so a
secret coordinate could in principle hide the reduction from `2^(2w)` to
`2^(w/2)`. That version is NOT tested here, and it runs into a known obstacle
rather than an open one: Q3 measured that the injection geometry -- which is what
delivers the reduction -- leaks in four evaluations under program access. So the
binding constraint stays where it was, and it is not the coordinate transform.

## Scorecard

    direct secret m3          fails gate 4 (witness safety) -- Q14
    faithful B                passes 1; weak on 3 and 5 -- Q12, Q13
    naive factor composition  fails gate 3 -- Q8, Q9
    bijective wrappers        fails gate 2 -- Q13 (worth ~0.15 exponent, free)
    hidden coordinates        passes 3, FAILS 1 -- this file
