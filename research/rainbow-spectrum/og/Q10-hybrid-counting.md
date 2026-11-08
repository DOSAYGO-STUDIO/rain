# Q10 — B + nonlinear combiner: the counting, before any code

*Analytical pass only, 2026-09-16. Verdict: the natural construction dies on
paper. One gate genuinely passes, which is new, and the failure is narrower than
Q8's.*

## The construction

k factors, each an Experiment-B instance with its own `θ_i`, public states
`S_i ≠ T_i`, and its own controls `c_i = (prefix_A^i, prefix_B^i, merge_B^i)`.
Public relation, with `G` a bijection on the k-tuple:

    G(out_A^1, …, out_A^k)  =  G(out_B^1, …, out_B^k)

Because `G` is a bijection this is equivalent to `out_A^i = out_B^i` for every i.

## 1. Private cost — passes

Factors have disjoint controls, so the keyholder runs the σ-match per factor:

    C_priv(w, k) = O(k · 2^(w/2)),   latency 2^(w/2) with k workers

exactly the layered result already verified 8/8 at k = 2…8. No change.

## 2. All-factors-required — PASSES, and this is new

Q8 failed here: its relation was a collision `m ≠ m'`, so leaving a stripe's
input unchanged satisfied that stripe for free, and the cheapest witness touched
one stripe. **B's relation cannot be satisfied trivially.** It equates outputs
from two *different* starting states, `S_i ≠ T_i`, so there is no "leave it
unchanged" option — every factor needs a genuine solve. So k is a real
multiplier on the public side's work, not a decoration.

This is the first construction today to pass Gate 2. It makes Gate 1 the whole
question.

## 3. Public seam — FAILS

`G` takes `out_A^i` as arguments, so any evaluator materialises each factor's
full output state. `out_A^i` depends only on `c_i`, so its input support is
exactly factor i's controls — a factor-local intermediate, which is a stronger
seam than a σ would be (the full state, not just its invariant).

That is precisely the object `og/q9_gates.py` recovers: take each traced word's
input support, score input pairs by the smallest support containing both,
single-link. Measured there at **6/6 for k = 2, 3, 4**, with no seeds, no
geometry and no labels. Nothing about B changes that mechanism.

**Fatal for the natural construction.**

## 4. Is there a non-natural construction? A dichotomy, not a theorem

The seam comes from the evaluator forming factor-local quantities. Suppose it
never does — it mixes every `c_i` from the first gate. Then the keyholder cannot
read per-factor coordinates off the public computation either, so to run k
independent σ-matches they must project the combined state back onto per-factor
coordinates using the secret. That projection is exactly Q4's step-3 situation: a
secret transform that is public to evaluate and secret to invert, i.e. a trapdoor
function, and then the transform carries all the security while the Rainbow
factors carry none.

So either:

  - the evaluator forms factor-local intermediates → support analysis wins, or
  - it does not → the keyholder needs a secret projection → trapdoor function.

Worth being precise about what this is *not*: it is not the same argument as Q8's
XOR failure. There, cross-stripe second derivatives vanished *exactly* because
the combiner was additive. Here the relation is a **conjunction**, whose
indicator is a product rather than a sum, so the second-derivative test does not
apply and a nonlinear `G` genuinely defeats it — as measured, 0/6. The kill is
support/topology, not derivatives.

## 5. Witness freedom — the combiner adds nothing

With `G` a bijection the solution set is the product `Sol_1 × … × Sol_k`. The
combiner permutes the output but does not make the relation scarcer: per factor
the constraint-to-freedom ratio is unchanged. So an attacker who decomposes pays
`k · 2^(0.76w)` — linear in k, no amplification — and one who cannot decompose
faces a relation whose hardness is entirely a question of whether the seam holds.

That is the same lesson as Q7: a combiner that leaves the solution space equally
abundant gives a solver more to propagate, not more to search.

## Verdict

Do not implement. The natural hybrid inherits Q9's seam, and the only escape
routes to a non-natural one land on a trapdoor function that would make the
Rainbow machinery irrelevant.

Banked: **Gate 2 passes for B-shaped relations.** If a seam-free evaluator is
ever found, B is the right relation to put behind it — unlike a collision
relation, which can always be satisfied one factor at a time.
