# Q4 — Composition: an obstruction, precisely located

*Derivation, 2026-09-16. Steps 1 and 3 are argued, not measured; step 2 and the
regime in step 4 are measured elsewhere in `og/`. Labels below say which.*

## The target

A composition `P = C(W_θ1, …, W_θk)` of weak colliding functions with public
evaluation, public verification, cheap collision construction given the secret,
expensive without it, and `∂log C_pub/∂k > ∂log C_priv/∂k`.

## Step 1 — output encodings are irrelevant *(exact, trivial)*

If `P = T ∘ G` with `T` a bijection, then `P(m) = P(m′) ⟺ G(m) = G(m′)`.
A collision relation cannot be hidden by anything applied to the output.
Every output-side mixing, masking or re-encoding is removed from the design
space at once.

## Step 2 — merges propagate *(measured)*

Once two states are identical, every later deterministic layer keeps them
identical. Every Rainbow collision in this repository works this way
(`output/pdf/rainbow-pair-sum-cryptanalysis.tex`, "Why the Digest Width Does Not
Help"; `og/stripe.py`).

## Step 3 — feedforward compositions collapse to one layer *(argued)*

Let the message enter once, at the start:

    G = W_k ∘ S_k ∘ … ∘ W_1 ∘ S_1

The keyholder's cheapest collision:

1. find a pair `u ≠ u′` colliding in `W_1` — only one stripe need differ, so
   ~2^(w/2), independent of `k`;
2. invert `S_1` at `u` and `u′`.

By step 2, `S_2 … W_k` are irrelevant. Consequences:

- **private cost does not grow with k at all** — better than the `k·2^32` target;
- **the asymmetry is exactly the invertibility of `S_1`**: public evaluable,
  secret invertible. That is a trapdoor function in its own right;
- **the weak collider is incidental**: any function with known cheap collisions
  serves, including a trivial one. Rainbow contributes nothing essential;
- **k is not a security knob**: the public route is inverting `S_1`, which does
  not depend on `k`.

So in this regime the problem does not get *solved* by composition, it gets
*moved* into `S_1`, and `S_1` is the classical hard problem.

## Step 4 — the only escape recreates the symmetric regime *(measured)*

Merges stop propagating only if the message is injected again at later layers,
so a later differing block can undo an earlier merge. But then every layer reads
the message difference, which is the same-message regime of
`og/concat.py`: a joint condition of about `w` bits per stripe for **everyone**.
Measured at `w = 6, 8`, `k = 1…4`: ~6.4 bits per added stripe, keyholder and
attacker alike (`results/og-same-message-stripes.json`).

## The proposals, placed

| proposal | message enters | regime | reduces to |
|---|---|---|---|
| secret weak bases `S = T_s(U,V)` | once | step 3 | `T_s` a trapdoor function |
| chained `θ_{i+1} = G(s_{i+1}, q_i)` | once | step 3 | the first secret transform |
| chained, message per stripe | per stripe | step 4 | symmetric joint condition |
| shallow dependency tree | either | 3 or 4 | as above |

## What remains open

The obstruction is a dichotomy, not an impossibility proof, and it has one gap.

**Between the regimes.** Step 3 needs merges to propagate; step 4 needs every
layer to read the whole difference. A construction where later layers read
*part* of the message — enough to undo naive merges, not enough to impose a
joint condition on the keyholder's per-stripe merges — is in neither regime.
That is precisely the problem of stitching independently solved stripes, now
located exactly. Whether such a partial-reading schedule exists without making
its seams publicly visible (the wrapper and pairing leaks) is the real question.

**What step 3 does not rule out.** A genuine trapdoor function built from
Rainbow-like parts would make step 3 work. That is not excluded — but it is the
original hard problem, and composition would add nothing to it.

## Result

Q4's search did not find a composition. It found why the obvious families cannot
work: feedforward compositions reduce the collision trapdoor to a trapdoor
function in a single transform layer, and iterated ones recreate the symmetric
joint condition. The one unexplored region is a partial-reading schedule between
the two.
