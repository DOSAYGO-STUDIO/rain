# Q13 — a bijective suffix inflates the measured exponent by ~0.15

## What was asked

Faithful B measured a public exponent of 0.849 against original B's 0.761, which
looked like being *more* faithful to Rainbow buying a bigger gap.

## Why that reading is wrong

`mixB`+rotate sits **after** the merge and is a bijection applied identically to
both sides, so `F(X) = F(Y) ⟺ X = Y`. The witness set is untouched. Original B's
final `mixA` is equally a bijection. So both relations are equivalent to
comparing at the merge injection, and all three encodings have identical solution
sets.

## The control

Same planted instances, same solver, only the suffix differs:

    suffix    w=10    w=12    w=14    w=16   exponent    gap
    none     10.43   11.51   13.15   14.55     0.700   +0.200
    mixA      9.55   12.14   13.11   15.02     0.869   +0.369
    mixB     10.78   12.96   15.12   15.72     0.849   +0.349

Premise verified rather than assumed: the three encodings agree on acceptance
**672/672** over an exhaustive slice, so the witness sets really are identical.

## Result

A bijective suffix adds **~0.15-0.17** to the measured exponent while changing
nothing about the relation. And `mixA` (0.869) is not distinguishable from
`mixB`+rotate (0.849), so faithful B's apparent edge has nothing to do with
`mixB` crossing the pairs -- any bijection does it.

**This is encoding obfuscation, quantified.** It is the cleanest measurement of
that effect in the whole project, and it is worth having as a number: roughly a
sixth of an exponent, for free, from appending an invertible map.

## Correction to B's headline

B's relation carries exactly such a suffix, so part of its measured +0.261 gap is
representational. Within this controlled comparison the relation-intrinsic figure
is **+0.200**, with ~0.15 attributable to the final `mixA`.

Caveat on comparability: the 0.700 row is measured on faithful-B planted
instances at w = 10..16 with CaDiCaL alone, whereas B's 0.761 came from B's own
artifact at w = 10..18 across three solvers. The *controlled* claim -- same
instances, same solver, suffix the only variable -- is the +0.15-0.17, not the
absolute recalibration of B.

## Also recorded: a measurement that was junk

A first faithful-B sweep reported an exponent of 1.167. It was meaningless: 11 of
16 draws were **unsat** because the instances used random S and T with no planted
witness, and the exponent was fitted over the few that happened to be
satisfiable. The relation asks two *different* states to reach the same state,
which generically has no solution. Planting is now a module,
`og/faithful_plant.py`, because the same error had already occurred twice from
re-deriving it inline.
