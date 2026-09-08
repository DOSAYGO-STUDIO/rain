# Rainstorm-64 short-digest and programmed-round campaign

Date: 2026-09-08. These are bounded attack experiments, not a security proof.
Production is Rainstorm v4.0.0 with four weak rounds per block.

## Result

A full production Rainstorm-64 collision was found for two distinct 8-byte
messages:

```
ca145d6ba2b04305  -> e2cf74b77eb19e23
9a377294e2e26a9a  -> e2cf74b77eb19e23
```

This is a **generic birthday-cost control, not a cryptanalytic break**. The
distinguished-point rho search used 7,227,220,749 walk evaluations in 244.03
seconds. Under the ideal 64-bit random-mapping birthday model, the collision
CDF at that work is about 0.7573: the observation is ordinary random-function
behavior. The pair was verified by the rho implementation, a separately
compiled production C++ bridge, and the independent integer model. See
[`generic-rho-8byte-64.json`](generic-rho-8byte-64.json).

No subgeneric production collision or second preimage was found. Every
production algebraic/SMT/SAT/local-search query below ended `unknown` because
its exact timeout was reached. A timeout is not UNSAT and is not a probability
or security bound.

The algebraic first-round parameterization did pass its required control: it
found a reduced one-round, 63-byte Rainstorm-64 second preimage in 0.10 seconds,
and in 0.04 seconds when only the final two first-round output words were free.
Both witnesses were independently replayed through the integer model.

| Parameterization | Free first-round words | Rounds | Budget | Result | Time |
| --- | ---: | ---: | ---: | --- | ---: |
| Programmed first right round | 8 | 1 | 10 s | SAT | 0.10 s |
| Programmed first right round | 8 | 2 | 60 s | unknown | 60.23 s |
| Programmed first right round | 8 | 3 | 60 s | unknown | 60.41 s |
| Programmed first right round | 8 | 4 | 60 s | unknown | 60.48 s |
| Fixed early path, programmed late words | 2 | 1 | 30 s | SAT | 0.04 s |
| Fixed early path, programmed late words | 2 | 2 | 30 s | unknown | 30.10 s |
| Fixed early path, programmed late words | 2 | 3 | 30 s | unknown | 30.17 s |
| Fixed early path, programmed late words | 2 | 4 | 30 s | unknown | 30.03 s |

This identifies round two as the first solver-visible self-consistency barrier.
It does **not** measure separate security gains from rounds three and four: once
round two exhausts the budget, all later measurements are right-censored at the
same ceiling.

## Why the new coordinates matter

For a fixed incoming state and chosen transformed right-round words `y_i`, the
unique message data words are

```
d_i = q_i XOR (ROTL(y_i, Z_i) + K_i)  (mod 2^64),
```

where `q_0 = H_0` and `q_i = H_i - (C_R + sum(y_0,...,y_(i-1)))`.
The attack therefore removes the complete first nonlinear right round from the
solver circuit without approximation. For a 63-byte message, it adds only the
real constraint that the top byte of `d_7` is the padding byte `0xbf`.

Round one is directly programmable. At round two the recovered message must
also make the following left round land on the target fold using those same
data words. That same-data self-consistency equation, rather than diffusion by
itself, is the next algebraic target.

## Other exact solver runs

Two-free-message collision searches for 8, 9, 16, and 32-byte Rainstorm-64
messages all timed out. Chosen second-preimage searches against all-zero 16,
32, and 64-byte references timed out under both complete bit-blasted SAT and
bit-vector stochastic local search. These results show the raw circuit is
solver-hostile; the one-round calibration proves they must not be interpreted
as security evidence by themselves.

## Empirical checkpoint profiles

Each profile contains 4,096 uniformly sampled 8-byte base messages. At the
64-bit digest, no collision was observed and the difference bits were close to
balanced:

| Relation | Input relation | Mean active digest bits | Min/max bit-one frequency |
| --- | --- | ---: | --- |
| XOR | `m' = m XOR 1` | 31.979 | 0.4878 / 0.5142 |
| Additive | `m' = m + 1` | 31.967 | 0.4858 / 0.5164 |
| RX | `m' = ROTL(m,1)` | 32.056 | 0.4836 / 0.5161 |

These are reconnaissance frequencies without family-wide error correction.
They show rapid diffusion but do not test rare, constructed trails.

## Next attack

Derive the two-round same-data equation explicitly in `(y_i, x_i)` coordinates,
eliminate the fold equation by solving one late transformed word, and model only
the residual data-consistency/carry conditions. Validate every reduced witness,
then apply the same message-modification constraints to rounds three and four.
Only a production four-round witness replayed by native C++ is a Rainstorm-64

The campaign now has that native collision control, so subsequent work must
beat roughly `2^32` Rainstorm-64 evaluations in total data/time/memory cost to
count as a collision attack on the design. A chosen second-preimage attack has
the stricter generic reference of `2^64` evaluations.
