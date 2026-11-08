# Q27 — Branch B is dominated: steering loses to inversion, and Rainbow adds nothing over a random map

## Measured (`og/run_transplant.py`), q = 65537 prime

The transplant: public evaluation `g^A(x) Y_L^C(x)` with `Y_L = g^theta_L`, so the
collision condition is `A(x) + theta C(x) = A(x') + theta C(x')` mod a PRIME q.
The pair-sum invariant transplants fine -- `(h0-x)+(h1+x) = h0+h1` holds in any
abelian group -- so the question is whether the cheap private STEERING comes with
it. Private cost, keyholder knowing theta:

    variant      private collisions   median evaluations   mechanism
    rainbow             25/25                298           birthday on q
    random              25/25                249           birthday on q
    random #2           25/25                294           birthday on q
    chameleon           25/25                  1           ALGEBRAIC INVERSION

(birthday expectation on q is ~320.)

**Two results, both negative for Branch B.**

`rainbow` and `random` are indistinguishable. Once the maps are reduced mod an
odd prime, Rainbow-derived `A, C` behave exactly like uniform random functions:
Rainbow contributes nothing beyond being an arbitrary choice of public map. The
reason is structural -- `v2` is meaningless mod an odd prime, so every 2-adic
result in this repo (transport, incidence balls, the DDT rays, the gauge action)
evaporates on transplant. The pair-sum invariant survives; the geometry that made
it *exploitable* does not.

And the textbook chameleon hash beats both by ~300x at this q, with the gap
growing as `sqrt(q)`. That is a mechanism difference, not a tuning difference:

    Rainbow's private route   = birthday steering        O(sqrt(q))
    chameleon's private route = algebraic inversion      O(1)

Inversion beats steering, and Rainbow has no inversion to offer. Its cheapness
came from a low-dimensional *sufficient condition* for a high-dimensional
coincidence (the pair-sum collapse), not from invertibility. Worse, that
sufficient condition is PUBLIC in Rainbow -- it hands `2^(w/2)` to everyone, not
to the keyholder, which is the problem the whole program started with.

So transplanting Rainbow into a prime-order algebra produces a strictly worse
chameleon hash than the one already in the literature.

## An honest placement of Q25

Q25 should not be promoted as a new primitive. Deriving per-period capabilities
as a degree-`t` polynomial over `GF(2^h)`, so that any `t` exposures leave a fresh
period independent, is **standard technique** -- Shamir-style `t`-wise independent
sharing, and the same idea as key-insulated cryptography. Q25 arrived at it
independently and measured it carefully in this setting with real Rainbow
witnesses, and the measurement is sound, but the construction is known
cryptography rather than a discovery.

What Q25 genuinely settles for THIS program is narrower and still worth having:
bounded key-exposure isolation is achievable here, it costs `(t+1)h`, and the
incidence-ball structure buys one extra witness of margin.

## Where the architecture stands

The sketched architecture -- one-way public key, label-local collision capability,
capability burns after use -- is sound. The measurements say Rainbow is the wrong
choice for the middle layer:

    layer                        wants            Rainbow offers
    public interface             one-wayness      none (Q26: linear in theta)
    collision capability         invertibility    birthday steering (this file)
    exposure isolation           t-wise keys      nothing Rainbow-specific (Q25)

Each layer's requirement is met by something other than Rainbow, and in the one
layer where Rainbow has a mechanism at all, that mechanism is dominated.

## What is actually left

The trapdoor line is finished. What the program produced that stands on its own:

  * the 2-adic collision spectrum -- transport iff, nested ball intersections,
    reverse incidence, ultrametric composition, the work/leakage curve, the DDT
    depth/ray decomposition and its gauge action. Exact, and about Rainbow as
    shipped;
  * Q20: the 256-bit digest is a function of 192 bits of state, and the 128-bit
    variant ignores half the state outright;
  * Q26's recovery law, which is a clean statement about any `A + theta C` public
    interface and is not Rainbow-specific;
  * a methodology record of the measurement errors that mattered -- solver-state
    contamination, wrong nulls, fixed-`r` sampling hiding a relocated ray,
    Monte Carlo thinning, and the Z/2^w-vs-field derivation bug that Q25 fixed.

The honest summary is that the cryptanalysis succeeded and the construction
program failed, for a reason that is now precisely stated rather than guessed.
