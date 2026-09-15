# Rainbow spectrum: does factored knowledge beat flat knowledge?

Research program investigating whether Rainbow's collision-steering weakness can
become a structural primitive: individually steerable factors composed into a
flat map whose steering is no longer cheaply accessible, while knowledge of the
factorization still permits cheap steering.

**Status: the phenomenon is not disproved at toy scale, and a scaling separation
is measured. That is not the same as a positive result** — the flat side has so
far survived only two attacks. See [Limitations](#limitations).

Prerequisite: the underlying weakness is the pair-sum collapse documented in
[`../rainbow/`](../rainbow/).

## What is being measured

Both solvers get the same task: given states `S` and `T`, find control sequences
with `F(S; x) == F(T; y)`.

- **Factored** knows every θ and may use intermediate states.
- **Flat** gets only the input/output behaviour of `F`.

Costs are in **round-equivalents** so they are comparable: one flat evaluation of
`F` costs `k` rounds, one factored pair-map costs half a round.

## Results

### Phase 1 — the weakness, exhaustively verified

All checks pass (`results/phase1-verification.json`):

- the w=64 model reproduces production Rainbow, anchored to the independently
  verified implementation in `../rainbow/`;
- fixed-control transitions are permutations (exhaustive, w=3..8 per pair; full
  4-lane state at w=3,4 for both mixers);
- injection preserves both pair invariants (exhaustive at w=3,4);
- **merge iff invariants agree**, both directions: at w=4, all 4096 agreeing
  state pairs merged and **0 of 61440** differing pairs did;
- `steer()` merges for every free choice, and one pair has exactly 2^w solutions;
- the birthday construction tracks theory over nine widths:

| w | 8 | 10 | 12 | 14 | 16 | 18 | 20 | 22 | 24 |
|---|---|---|---|---|---|---|---|---|---|
| log2 median evals | 4.39 | 5.32 | 6.19 | 7.63 | 8.43 | 9.18 | 10.45 | 11.35 | 12.18 |
| analytic `w/2+0.235` | 4.24 | 5.24 | 6.24 | 7.24 | 8.24 | 9.24 | 10.24 | 11.24 | 12.24 |

### k=1 — no separation

A flat attacker who can isolate the injection recovers an equivalent steering
capability in **3 evaluations, independent of w**, and agrees with ground-truth
mergeability 500/500 (`results/flat-invariant-probe.json`). Any separation must
therefore come from composition.

Caveat: this gives the attacker `inject` on its own. In a genuinely flattened map
they would have to invert the mixer, so this is a *weaker* threat model than the
program specifies. It is a bound on where not to look, not a proof about k=1.

### Separation under composition

Aligned pairing across factors (`results/milestone-separation.json`):

| w | factored | flat | separation |
|---|---|---|---|
| 3 | 2^2.6 | 2^7.7 | 2^5.1 |
| 4 | 2^3.4 | 2^9.9 | 2^6.4 |
| 5 | 2^3.4 | 2^11.8 | 2^8.3 |
| 6 | 2^4.0 | 2^13.6 | 2^9.6 |
| 7 | 2^4.3 | 2^15.7 | 2^11.5 |
| 8 | 2^4.6 | 2^16.9 | 2^12.3 |

Factored tracks `2^(w/2)`, flat tracks `2^(2w)` (at w=8, k=2 the prediction is
2^17 and the measurement is 2^16.9), and the gap grows as roughly `2^(1.5w)`.
This is a scaling separation, not a constant factor.

> **⚠️ SUPERSEDED — do not cite this separation as evidence.** The `2^(2w)` flat
> figure is the cost of a **random-search** attacker. An equation-solving
> attacker does far better: z3 merges at every width up to w=24 in seconds (see
> [SMT](#smt-the-capability-was-the-wrong-one)), where birthday is 2^48. Worse,
> it merges a *hardened* construction with the weakness removed just as readily,
> so the query was never hard for anyone. The number below measures a smart
> privileged attacker against a needlessly weak public one.

**Composition depth is not a separation axis.** `k` barely moves either side: the
factored attacker merges at round 2 and coasts, and the flat birthday is on the
final state regardless of `k`. Width is the axis that matters.

### Rotating the pairing is a candidate defence

The divide-and-conquer needs consecutive factors to agree on the pairing. If each
factor rotates its pairing, the merge-round invariant mixes lanes from different
round-1 pairs and the two conditions must be matched **jointly**:

| regime | divide-and-conquer available | factored cost |
|---|---|---|
| aligned | 20/20 | ~2^(w/2) |
| rotated | 0/20 | ~2^w (w=7 → 2^7.4, w=8 k=3 → 2^9.2) |

Rows where the rotated regime still shows 20/20 are the ~1/3 of draws where two
random pairings coincide; their costs fall back to the aligned figure, which
confirms the mechanism. This is also a candidate defence for Rainbow itself.

### Phase 7 — attacking the hypothesis

Neither attack breaks the separation, but attack A is **not** uniformly empty
(`results/flat-adversarial.json`). Classes are enumerated exactly, candidates are
validated against 8 held-out classes, and a candidate only counts if it also
*discriminates* between them. Rates over independent θ draws:

| w | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|
| draws with a discriminating label | 8/12 | 8/12 | 4/12 | 1/8 | 0/4 | 0/2 |
| rate | 0.67 | 0.67 | 0.33 | 0.13 | 0 | 0 |
| median output rank (of 4w) | 9/12 | 14/16 | 19/20 | 23/24 | 28/28 | 32/32 |

So **GF(2)-linear leakage is a small-width phenomenon that dies as w grows.** At
w=3 it is common; by w=7 and w=8 there are no candidates at all, because the
class spans the full output width. (Those two rows use only 4 and 2 draws, but
zero *candidates* is stronger evidence than the draw count suggests: nothing
survives the rank test to be validated.) Where a label does exist it is worth
one bit, which does not touch a gap growing as 2^(1.5w).

The warning for this whole program is that toy widths mislead in both
directions: at w=3 the flat attacker sees structure that simply is not there at
w=8.

- **B, class canonicalisation.** Correct but dominated: 2^9.0 vs generic 2^7 at
  w=3, and 2^11.5 vs 2^9 at w=4, because each label costs a full class
  enumeration.

**Positive control:** the same test on the pre-mixer coset consistently finds 5–7
GF(2)-linear invariants — the low bits of the pair sums, which genuinely are
GF(2)-linear. The test detects structure when structure exists, so the negative
on outputs is meaningful rather than a broken measurement.

### Composition branches: A is the best of the three

The program warned against assuming sequential composition is the useful
operator. It is, in fact, the *least bad* of the three tried
(`results/composition-branches.json`, w=6, k=2):

| operator | factored | flat | separation |
|---|---|---|---|
| A sequential | 2^4.0 | 2^13.9 | **2^9.9** |
| B parallel, lane-wise add | 2^4.0 | 2^12.1 | 2^8.2 |
| B parallel, lane-wise xor | 2^3.7 | 2^11.2 | 2^7.5 |
| C cross-parameterized on σ | 2^4.3 | 2^12.9 | 2^8.6 |
| C naive (control) | — | — | rejected |

- **B makes things worse.** Combining mixers drops the flat cost, because a sum
  of permutations is not a permutation, so outputs collide sooner. Algebraic
  combination helps the flat attacker.
- **C is about the same as A** at these widths. Selecting the mixer by σ hides
  nothing measurable, though it costs nothing either.
- **The naive control is rejected at every width**, which is the design lesson:
  a selector must read a quantity injection cannot change. Reading the state
  directly fragments the coset, because different controls land in different
  parameter regions and cheap steering dies. Reading σ keeps the selector
  constant across the whole control range.

Why A wins is structural, and explains why depth buys nothing: **sequential
composition hands the attacker a choice of merge point, and they take the
cheapest.** Every round keeps its own invariant, so more rounds means more
chances, not fewer.

### Why the rare label is real, and how it was nearly missed

A functional constant across eight classes of 256 points is not chance: for a
random functional the probability is about 2^-255. So where it survives, this is
genuine θ-dependent structure, not noise.

An independent sweep (16 draws per width, 8 and 16 held-out classes) reproduces
the same picture: w=4 gives 1/16 and 3/16, w=5 gives 0/16 and 1/16, w=6 gives
0/16 and 0/16.

It was nearly missed in both directions, which is the methodological point. With
3 held-out classes the test manufactured positives that vanished under 8. With a
single θ draw per width it reported SUCCEEDED at w=4 and failed at w=6, from the
same underlying rate. Only rates over independent draws are meaningful here.

### The linear route is closed, in the right algebra

The GF(2) tests above are weak evidence by construction: Rainbow conserves
`h_i + h_j` **modulo 2^w**, and a GF(2) test sees that only through its low bit.
`attacks/zmod_invariant_search.py` searches the correct ring, and at every
modulus `2^r` for `r <= w`, since a relation surviving only mod `2^r` still
exposes the low `r` bits and is still a usable class label
(`results/zmod-invariant-search.json`).

| w | 3 | 4 | 5 | 6 |
|---|---|---|---|---|
| output: draws with a class label | 0/8 | 0/8 | 0/6 | 0/4 |
| positive control (pre-mixer) | 8/8 | 8/8 | 6/6 | 4/4 |
| control's best modulus | r=3 | r=4 | r=5 | r=6 |

A negative here is only worth anything if the solver is **complete**, and over
`Z/2^w` field intuition does not apply — zero divisors and nonunits mean a lift
that prunes too eagerly, or a cap that truncates, would manufacture exactly the
"no invariant found" we want to see. So the solver is gated three ways:

- **63 synthetic ring cases** — nonunits (`2x=0`), zero divisors, dead-end lifts,
  all-even rows, duplicate rows, non-unique primitives, mixed valuations, the
  empty system — each compared against brute force at every modulus;
- **an exhaustive oracle** on real Rainbow class data at w=3 and w=4, comparing
  complete solution *sets*, not "both found something", with caps disabled;
- **every lifting level** validated (mod 2, 4, 8, …, 2^w), which catches a branch
  vanishing halfway up the lift tree.

Coefficients are canonicalised under unit scaling, so `5*(1,1,0,0) = (5,5,0,0)`
mod 8 is recognised as the same relation rather than counted as a new one. With
that in place the control recovers exactly the expected generators, `(1,1,0,0)`
and `(0,0,1,1)`, plus their combinations.

So: the search demonstrably finds the planted invariant where it exists, and
finds nothing on the composed output at any modulus. **The linear route is
closed.** Non-linear routes are untouched.

### Phase 4: exact flattening, and what it leaks

Until now "flat" meant an attacker who could *evaluate* the function. The
hypothesis is stronger: the attacker holds the exact closed form and merely
lacks a useful decomposition. Those are different adversaries.

`models/symbolic.py` builds a hash-consed bit-vector DAG (with SMT-LIB export),
and `attacks/flatten_and_attack.py` computes the **canonical ANF** of every
output bit. ANF is the honest flattening: it is canonical, so two entirely
different programs computing the same Boolean function produce the *same* ANF.
Intermediates are eliminated by construction, not hidden. Any advantage the
factored solver keeps therefore cannot come from a difference in the
mathematical function — only from knowing a decomposition of it.

Flattening is verified exhaustively: **factored == DAG == ANF on every input**
(64 to 4096 inputs per configuration), so the transformation is trusted rather
than being one more source of artifacts.

Flattening growth (`results/flattening-algebraic.json`):

| w | k | ANF degree | mean monomials | density | DAG nodes / depth / muls |
|---|---|---|---|---|---|
| 3 | 2 | 1..2 | 3.0 | 0.047 | 46 / 14 / 16 |
| 4 | 2 | 1..4 | 6.7 | 0.026 | 50 / 14 / 16 |
| 5 | 2 | 1..5 | 11.0 | 0.011 | 54 / 14 / 16 |
| 6 | 2 | 1..6 | 17.2 | 0.004 | 57 / 14 / 16 |
| 3 | 3 | 1..3 | 2.8 | 0.044 | 65 / 19 / 24 |
| 5 | 3 | 1..4 | 10.5 | 0.010 | 74 / 19 / 24 |

**A caveat that matters.** Max ANF degree tracks `w` and monomial counts grow,
while the DAG stays tiny — dozens of nodes at every size. The function is not
complex; the *ANF representation* of modular arithmetic is. So an apparent
factored advantage must not be read as "composition is hard" when it might be
"ANF is a catastrophically inconvenient representation of carries". This is why
the attacker is handed the DAG and an SMT export as well, not ANF alone.

**Result: partial leakage, not a break.** The flattened form does expose a
discriminating GF(2) class label — a combination of output bits constant as the
last round's controls vary, taking different values on different classes. It
appears in most θ draws (7–9 of 12 at w=3–5, at both k=2 and k=3), and **more**
held-out classes found more of them, so it is not a validation artifact. One was
verified directly by brute force: at w=5, k=2 the combination of output bits
`[10, 11, 18]` is constant across *every* control assignment in all 16 classes
and separates them.

But capability is measured in bits, not existence:

| | bits obtained |
|---|---|
| flat attacker, from the exact closed form | **1** |
| factored attacker, from σ | **2w** (10 at w=5) |

One bit halves the attacker's search. It does not replace a `2^(w/2)` birthday
on σ. **Exact flattening reduces the separation without closing it.**

The Z/2^r search missed these entirely, and that is instructive rather than a
failure: those labels are GF(2)-linear in output **bits**, while the modular
search looked for functionals Z/2^r-linear in output **words**. Carries make
those genuinely different function classes, so the two searches are complements,
not a redundant pair.

**Discrepancy: found and fixed.** Two implementations of the same criterion
disagreed — `flat_adversarial.py` reported rates declining as
0.42 / 0.08 / 0.08 / 0 / 0 / 0 while `flatten_and_attack.py` found 7–9 of 12
draws at w=3–5 — so one had to be wrong.

It was `flat_adversarial.gf2_nullspace`. It reduced each row by iterating a dict
in **insertion order** rather than by pivot column, and back-substituted in a
way that could break constraints it had already satisfied. Tested against
brute-force enumeration of all 2^(4w) functionals: at w=3 it agreed with brute
force, which is how it survived, but at w=4 its single basis vector **did not
annihilate the rows at all**. Invalid candidates are then discarded by held-out
validation, so the visible symptom was a silent undercount at w ≥ 4.

Corrected (the table above), w=4 moves from 0.08 to 0.67 and the two searches
now agree. The function carries a post-condition that raises if any returned
vector fails to annihilate its rows, so this cannot regress silently.

Two things survive the correction unchanged: the decline of the rate with w,
and the zeros at w=7 and w=8 — those come from the output rank being *full*
(28/28, 32/32), so the nullspace is trivial before the solver is consulted at
all, and never depended on it.

### How much does it leak? (quantified)

"Does leakage exist" is the wrong instrument once the answer is yes. What
matters is how many **independent** bits of the steering quotient the closed
form exposes — a hundred relations that are all the same bit still leak one bit
— so labels are counted by the affine rank of their signatures across classes,
and by the partition they induce, `l = log2 |{Λ(σ)}|`
(`attacks/leakage_quantified.py`, `results/leakage-quantified.json`).

| w | σ bits (2w) | independent rank | distinct signatures | leaked bits | fraction of σ |
|---|---|---|---|---|---|
| 3 | 6 | 2 | 4 | 2.0 | **0.333** |
| 4 | 8 | 1 | 2 | 1.0 | **0.125** |
| 5 | 10 | 1 | 2 | 1.0 | **0.100** |
| 6 | 12 | 1 | 2 | 1.0 | **0.083** |
| 7 | 14 | 0 | 1 | 0.0 | **0.000** |

**The leaked bits do not grow with w.** They stay at one or two while σ grows as
2w, so the exposed fraction falls monotonically and reaches zero at w=7. The
flat attacker learns a bounded constant; the factored attacker's quotient keeps
getting larger.

An independent cross-check agrees. Measuring the *operational* narrowing —
`P(σ equal | labels equal)` against the unconditional `P(σ equal)`, over 3000
fresh prefixes — gives 3.994× at w=3 and 2.001× at w=4 and w=5, i.e. 2.0 and 1.0
bits. That reproduces the rank column exactly, by a method that never looks at
ANF. The label carries no hidden extra information.

Two honest caveats. The w=7 zero rests on 3 θ draws (the truth tables are
expensive), so it is suggestive rather than settled — though note it used 8
held-out classes rather than 24, which makes the constancy test *more*
permissive, and it still found nothing discriminating. And the narrowing above
bounds an attacker who is trying to match σ; the flat attacker's actual best
route birthdays on final states and never passes through σ at all, so in
practice even this factor of two does not plug into it.

### SMT: the capability was the wrong one

A solver is different in kind from every earlier flat attack. Those sampled the
function or searched a fixed family of invariants; a solver reads the exact
equations and says "I do not care what your hidden structure was, I will solve
the steering constraint directly." So it was the natural next attacker
(`attacks/smt_steering.py`, `results/smt-steering.json`).

It solves. At every width tried, up to w=24 where generic birthday is 2^48,
with every model replayed through the independent Python model.

But solving proves nothing on its own, and the control is the whole point. The
identical query was run against a **hardened** variant whose injection does not
preserve the pair sums (`h_i -= x, h_j += rotr(x,1)`), so the cheap steering
construction does not exist at all. Three θ draws per cell, 60 queries total:

| w | k | weak: solved, median | conflicts | hardened: solved, median | conflicts |
|---|---|---|---|---|---|
| 8 | 2 | 3/3, 0.038s | 0 | 3/3, 0.038s | 0 |
| 12 | 2 | 3/3, 0.059s | 0 | 3/3, 0.120s | 0 |
| 16 | 4 | 3/3, 0.922s | 0 | 3/3, 5.503s | 0 |
| 20 | 2 | 3/3, 15.712s | 0 | 3/3, 1.911s | 0 |
| 24 | 2 | 2/3, 22.519s | 0 | 1/3, 60.018s | 0 |

Overall: weak 0.933 solved, hardened 0.867. **Removing the weakness barely
changes anything**, so the solver is not exploiting it.

Two details confirm the diagnosis. `conflicts = 0` in every single cell — the
solver is not searching, it is propagating. And the timings are not monotonic in
w (weak takes 15.7s at w=20 but 22.5s at w=24; hardened 5.5s at w=16, k=4 but
1.9s at w=20, k=2), which is what a non-search problem looks like.

The cause is structural: the system offers `2·k·npairs·w` bits of control
freedom against only `4w` bits of equality, so roughly `2^(4w)` solutions exist
and propagation walks to one.

**So the task was badly posed, and that is the finding.** A capability worth
separating on must be one that is generically *hard*; this one is
underdetermined by a factor of `2^(4w)`. Measuring how difficult it was could
only ever produce an artifact.

What survives is narrower and should be stated exactly: the **specific
σ-steering route** is cheap only with the decomposition. That is not the same
claim as "steering is hard without it", and only the latter would support the
hypothesis.

The constructive repair is to tighten the control budget until solutions are
rare rather than abundant. The structure then inverts in a useful way: with a
single round of controls the weak construction's reachable set is exactly a
σ-coset, so two states are either σ-equal or have **disjoint** images —
generically UNSAT, and the solver must *prove* unsatisfiability, which is where
SMT becomes expensive. The hardened variant has no coset structure, so its
images behave like random subsets that intersect about once, and stay SAT. That
is a falsifiable structural difference, and it is much closer to real Rainbow,
where message words cannot simply be solved for. Not yet run.

### The counting argument (do this before any further attack)

The SMT result was not a failure of an attack, it was a failure of a *task*: the
query had ~2^(4w) solutions, so propagation reached one and the measurement
could only ever be an artifact. `attacks/counting_model.py` exists so that
cannot recur — it derives and **exhaustively verifies** the solution count
before an experiment is built on it (`results/counting-model.json`).

Let `N = 4w` be the equality-constraint dimension, `Q` the public control bits,
and `S` the freedom the factor-aware route needs. A capability is worth
measuring only when `S ≤ Q ≲ N`.

**Symmetric design (the obvious one): the window is empty.** With prefix words
restricted to `t` bits and the merge round free, the merge injection is solvable
iff `σ(a) = σ(b)`, and then `x, y` are free while `x', y'` are determined:

```
#solutions ≈ [#σ-matching prefix pairs] × 2^(2w) ≈ 2^(4(k−1)t − 2w) × 2^(2w) = 2^(4(k−1)t)
```

The factored route needs at least one σ-match, i.e. `4(k−1)t ≥ 2w`. So **the
moment the privileged route becomes feasible, ≥ 2^(2w) solutions already
exist.** Verified across w=8…64 and k=2,3: the symmetric window is empty every
time.

The cause is worth naming, because it is the real lesson of this whole phase:

> **The freedom the trapdoor needs is the freedom that makes the public problem
> easy.** Even a *unique* σ-match still carries 2^(2w) merge-round solutions,
> because `x` being free is exactly what makes the merge free for the factored
> attacker. Restricting the merge round does not help: `x' = x + δ` must stay
> representable, which generically fails and breaks the privileged route first.

**Asymmetric repair: non-empty but narrow.** Fix one side's merge controls and
leave the other's free. Each σ-match then contributes exactly one solution:

```
#solutions ≈ 2^(4(k−1)t − 2w),   Q = 4(k−1)t + 2w,   N = 4w
```

At `t = w/(2(k−1)) + c` that is `2^(4c)` solutions in a `2^(4w+4c)` space —
density `2^(−4w)` — while the factored side keeps its birthday match.

Verification against exhaustive enumeration (k=2), 8/8 checked cases agree:

| w | t | design | σ-matches | predicted | actual |
|---|---|---|---|---|---|
| 3 | 2 | symmetric | 12 | 768 | 768 |
| 3 | 2 | asymmetric | 12 | 12 | 12 |
| 3 | 3 | asymmetric | 52 | 52 | 52 |
| 4 | 3 | asymmetric | 4 | 4 | 4 |
| 4 | 1,2 | both | 0 | 0 | 0 |

**Caveat on `c = 0`:** "≈1 expected solution" means a constant fraction of random
challenges have *none*. So the honest next experiment is the planted variant —
generate the instance through the factorization so a witness is guaranteed,
erase the witness and the factor boundary, then ask the public solver to recover
any witness. Generating instances with a known witness is what key generation
is, not cheating.

The next experiment must also re-run the **weakness-removed control** in this
regime. If SMT again solves hardened and weak alike, the same verdict applies
and the construction is finished.

## Limitations

The honest verdict is **"not demonstrated"** — which is weaker than "not yet
disproved", and the distinction matters. The hypothesis has not been refuted,
but there is currently **no standing evidence for it either**, because the one
quantitative result that supported it measured a task that was never hard.

1. The **linear** route is closed (GF(2), and Z/2^r for every r ≤ w with a
   solver proven complete against brute force), **exact ANF flattening** is done
   and leaks ~1 bit, and **SMT** has been run — where it showed the chosen
   capability was underdetermined rather than hard, invalidating the separation
   measurement rather than beating it. What genuinely remains untried:
   meet-in-the-middle; amortised precomputation (a one-off 2^(4w) class
   partition makes every later merge free, which is a real threat model); and
   relations of the form `L(F(x)) = L(x) + c`, or `L(F(x,m)) = φ(L(x),m)` for
   low-complexity φ — steering does not require a *conserved* quotient, only a
   predictably *evolving* one.
1b. **The blocking item was a task, not an attack — and it is now resolved.**
   The counting argument above shows the obvious symmetric construction *cannot*
   host the phenomenon at any width (structural impossibility), and identifies
   the one regime that can: asymmetric merge controls at
   `t = w/(2(k−1)) + c`. No further attack should be run outside that regime,
   because outside it the task is underdetermined and any measurement is an
   artifact. What is still unbuilt is the planted sparse-witness experiment in
   that regime, with the weakness-removed control alongside it.
2. The separation is the *same* phenomenon as the Rainbow break itself —
   birthday on a w-bit invariant versus birthday on a 4w-bit state. It has not
   been shown to be a new primitive.
3. Toy widths only. At w≤8 a flat attacker could brute-force structure that would
   be out of reach asymptotically, so these sizes identify scaling laws; they do
   not establish hardness.
4. Phase 4 exact flattening **is** implemented (canonical ANF + hash-consed DAG
   + SMT-LIB export, equivalence verified exhaustively), and it leaks ~1 bit.
   Still missing: CNF/SAT export driven through an actual solver, and attacks
   that read the symbolic form structurally rather than statistically —
   monomial-support overlaps, higher-order derivatives, annihilators, variable
   partitions, and alternative decompositions of the polynomial map.
5. Composition branches B (algebraic) and C (cross-parameterized) are not built.

## Failure taxonomy

Kept deliberately, per the program:

| failure | cause | lesson |
|---|---|---|
| factored solver merged 0/20 | `mix_a` was hardcoded to lanes (0,1),(2,3) while `random_theta` drew other pairings, so injection and the mixer disagreed | separability must be defined against θ's own pairing |
| `validate_weakness` admitted those members | it only tested properties of *injection*, never that the weakness survives the mixer | admissibility must test per-pair independence **through a round** |
| factored matched the wrong functional | invariants computed with round 1's θ, but `steer` tests the merge round's θ | the invariant that matters belongs to the round where the merge happens |
| Attack A "succeeded" at w=3..6 | last-round controls drawn randomly *with replacement*, so ~40 distinct points of 64 faked a rank deficiency | enumerate classes exactly; validate on held-out data |
| flat cost was an artifact | the birthday ran the whole budget on side A before sampling side B | two-sided interleaved search, stop at first cross-match |
| merge-iff row looked catastrophic | duplicate JSON key `of_which_merged` silently overwrote the agreeing count | never reuse a key in a result record |
| Attack A "succeeded" again after being fixed | validation used only 3 held-out classes; a w=6 hit vanished under 8, and 0/12 draws reproduced it | validation depth is a parameter, and too little of it manufactures positives |
| a single θ draw reported SUCCEEDED at w=4 and failed at w=6 | the structure is θ-dependent and rare, so one composition is not a measurement | report rates over independent draws, never a single-draw verdict |
| naive branch C destroyed the weakness | the mixer was selected from the whole state, so injection moved the state into a different parameter region and the coset fragmented | a selector must read an injection-invariant quantity (σ), not the state |
| the flattening positive control failed at w=3,4 but passed at w=5 | it let earlier rounds' controls vary, and σ is only invariant with respect to the **final** injection — round 1's mixer changes it | a control must isolate exactly the invariant it claims to plant, nothing wider |
| the flattening attack declared a break on any discriminating label | success was counted as existence rather than bits; the label was worth 1 bit against σ's 2w | measure capability in bits against what the privileged side actually gets |
| the whole factored-vs-flat separation turned out to measure nothing | the chosen capability was underdetermined by ~2^(4w), so it was never hard for anyone; the flat baseline was a random-search attacker that a solver trivially beats | before measuring how hard a task is, check that it is *generically* hard — and always run the control where the planted weakness is REMOVED |
| two implementations of one criterion disagreed by ~8x | `gf2_nullspace` reduced rows in dict-insertion order, not pivot order, and returned vectors that annihilated nothing; correct at w=3, wrong at w≥4 | when two of your own measurements disagree, one is broken — arbitrate with brute force before believing either, and give linear-algebra helpers a post-condition |
| a first attempt looked for "low-degree relations" with no cross-class check | constancy alone is trivial — low bits of modular addition are GF(2)-linear — so it found relations that were never class labels | reuse the validated criterion (constant within class **and** discriminating across classes), do not invent a weaker one |

## Layout and reproduction

```
models/      wordops.py (exact width-w arithmetic), rainbow.py (Theta, mixers,
             steer), spectrum.py (parameterized family + admissibility),
             symbolic.py (bit-vector AST, hash-consed DAG, SMT-LIB export)
compositions/sequential.py (branch A), branches.py (branch B parallel-algebraic,
             branch C cross-parameterized, plus the naive negative control)
attacks/     phase1_verify.py, flat_invariant_probe.py,
             milestone_separation.py, flat_adversarial.py, branches_compare.py
results/     machine-readable JSON for every run
```

```bash
cd research/rainbow-spectrum
python3 attacks/phase1_verify.py          # ~16 s, exhaustive
python3 attacks/flat_invariant_probe.py   # instant
python3 attacks/milestone_separation.py   # ~45 s
python3 attacks/flat_adversarial.py       # ~30 s, multi-draw GF(2)
python3 attacks/branches_compare.py       # ~5 s, branches A/B/C
python3 attacks/zmod_invariant_search.py  # ~2.5 min, Z/2^r + ring stress tests
python3 attacks/flatten_and_attack.py     # ~1 s, exact ANF/DAG flattening
```

All runs are seeded (`random.Random(20260915)`) and write JSON to `results/`.
Nothing here modifies Rainbow; `models/rainbow.py` carries its own transcription
and is anchored to production at w=64 by `selftest_matches_production`.
