# Q20 — Rainbow's 256-bit digest is a function of 192 bits of state

Loose end from Q12: "the finalization is lossy -- at w=4 it maps 65,536 states
onto 4,014 digests". That rested on a width whose rotations are (1,2,2,2), so it
was re-measured at widths where they are not. It is not only real, it has a
structural cause that is independent of width and visible in the production
source.

## Measured (`og/run_finalize_lossiness.py`)

Image size of the finalization estimated from the birthday rate among random
states, `I ~ N^2 / (2 * collisions)`:

    w   method     samples    collisions   expected if random   image / 2^(4w)
    4   exact       65,536         -              -                 0.061
    6   birthday  1,048,576    800,800         51,838              0.041
    8   birthday  1,048,576     32,306            203              0.004
   10   birthday  2,097,152      2,093            3.2              0.001

A random `4w -> 4w` map covers 0.632. The image fraction is ~`2^-w`: the digest
loses one whole word, at every width.

## Mechanism

Colliding state pairs show NO structure in the input state -- every word-wise
sum, difference and XOR agrees at the chance rate 1/256 -- but after the four
finalization mixers they agree on words 2 and 3 in 99.3% of cases, and given
that agreement collide at exactly the rate `2^-w`. So the digest depends on the
post-mixer state through `(h2, h3)` plus `w` more bits of `(h0, h1)`.

The `w` bits are `h1'' = mixA(mixA(state))[1]`. Exact fibre test
(`og/run_finalize_lossiness.py` companion, in the session log): fix `(h2, h3)`,
enumerate all `2^(2w)` values of `(h0, h1)`, group by `h1''`:

    w=6: 64 fibres,  digest varies within a fibre: 0/3 trials, distinct across: 64/64
    w=8: 256 fibres, digest varies within a fibre: 0/3 trials, distinct across: 256/256

and at production width, with `default_theta(64)` (exactly production, verified
900/900 elsewhere), replacing `h0''` by a random word changed words 2,3 in 0 of
2000 states.

**Why, from `src/rainbow.cpp` (untouched):**

    mixB:   a = s[1]; b = s[2]; ... s[1] = b; s[2] = a;      // s[0], s[3] untouched
                                                             // new s[2] depends on s[1] only
    squeeze (256): word0 = -(h2+h3); mixA; word1; mixA; mixB; mixA; word2; mixA; word3

Words 0 and 1 read the `(h2, h3)` pair only. `mixA` is pair-separable, so after
two of them `(h0, h1)` has become `(h0'', h1'')` without touching the output
pair. The single `mixB` then copies a function of `h1''` ALONE into slot 2 and
leaves `h0''` where it is, and no later operation reads slot 0. So `h0''` never
reaches the digest: it is a function of `(h2, h3, h1'')`, 3 words.

The 128-bit variant is starker: words 0 and 1 are both functions of the
post-mixer `(h2, h3)`, so the 128-bit digest ignores `(h0, h1)` entirely.

## What it means, stated carefully

  * The image of the 256-bit finalization has at most `2^192` elements, so the
    digest carries at most 192 bits. Generic collision on the digest is at most
    `2^96` and generic preimage of the finalization at most `2^192`, independent
    of and in addition to the pair-sum attack (which already gives collisions at
    `2^32`, so this is not the binding weakness for collisions).
  * It is a second, structurally different defect: the pair-sum break is about
    the injection; this is about the squeeze. Both come from the same design
    fact -- the two halves of the state cross only through `mixB`, and `mixB`
    moves one word each way.
  * Rainbow is avowedly non-cryptographic; this is recorded as a property of
    the function, not as a break of a claim it makes.
  * The Q12 sentence stands, and the reason it was true at w=4 is the same reason
    it is true at w=64.
