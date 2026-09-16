# The next construction: amplify with k, not with w

*Recorded 2026-09-16 as a design target, not a result. Nothing here has been
built or measured.*

## The defect in what we have

Experiment B's security parameter is the wrong one. Raising security means
raising `w`, and `w` is also the private search exponent:

    private   4 * 2^(w/2)          measured exactly, w = 12..32
    public    2^(0.75w)            best public attack so far (SAT, 3 solvers)

Both sides move together. Pushing the public side out of reach pushes the
private side with it, so the bargain never improves — only the constant in front
of the gap does. That is a fundamentally unattractive shape for a PK system: the
keyholder pays an exponential in the same parameter the attacker does.

## The shape we actually want

Security should compound with the NUMBER of factors while the private cost stays
pinned to one factor's width.

    private work        ~ k * 2^(w/2)      k independent weak searches
    private latency     ~ 2^(w/2)          they are embarrassingly parallel
    public work         ~ grows with k     2^(alpha*k*w), or 2^(w/2 + delta*k),
                                           or anything that compounds

At w = 64 each factor's private search is 2^32 — the scale of the original
Rainbow collision break, which is seconds-to-minutes in optimised native code.
With k workers the private latency stays at 2^32 no matter how large k grows.
Meanwhile the attacker faces one composed relation they cannot split.

This is the rainbow/white-light picture the program was named for: each colour
stays individually weak and usable by whoever knows the spectrum, and it is
recombination that creates the public hardness.

## The crucial design property

Two requirements pull against each other, and the whole problem is finding a
composition that satisfies both:

  **private solutions must compose cheaply.** Having solved each factor
  separately for local witnesses x*_1 .. x*_k, assembling them into a witness for
  the composed relation must be deterministic or near-free. If stitching is
  itself a search, the parallelism is lost.

  **public equations must couple the factors.** The flattened form must not let
  an attacker say "this part is factor 1, this part is factor 2" and run the same
  k independent searches. If it does, the attacker simply becomes the keyholder.

## What we already know bears on this

Two findings from the current program constrain the design, and both are
discouraging for the obvious approaches:

  **Naive sequential composition does not amplify.** Prior work in this
  repository (`compositions/sequential.py`, `attacks/branches_compare.py`)
  already found that stacking rounds sequentially fails to give public hardness
  growing with depth.

  **Pair-separability leaks.** `attacks/theta_recovery.py` shows the pairing is
  recoverable in ~15 public evaluations, because `mix_a` acts independently per
  pair and that independence is visible from outside. This is the second
  requirement failing in miniature: wherever the composition keeps factors
  structurally independent, an attacker can detect the seam by differential
  probing and split the problem. Any k-factor composition must expect the same
  attack at the k-factor seams, and must couple factors in a way that survives
  it.

That second point is the sharpest lesson available: **the separability that
makes the private side cheap is the same property that makes the seam visible.**
A composition that gives the keyholder k independent searches has, by
construction, k independent things for an attacker to notice. Resolving that
tension is the actual open problem, not an implementation detail.

## Status

Not started. The current construction stays frozen and under attack; this is the
direction for the next one.
