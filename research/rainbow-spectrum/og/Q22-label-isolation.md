# Q22 — label isolation: the right criterion, two controls, and Rainbow's seed

## The criterion Q21 got wrong

Q21 proposed testing whether the consistent master-key set `S_L` shrinks across
labels. That is a key-leakage diagnostic, not a definition of label isolation,
and it produces a false negative on the most important case. If the secret is
`(theta_1, theta_2, ...)` and label `L_i` selects an independent component, then
a witness at `L_1` exposes `theta_1` completely and the global posterior shrinks
hard -- yet knowing `theta_1` buys nothing at `L_2`. That construction is a
perfect label and the naive metric calls it a failure.

The operative question is not

    does the witness reveal information about the master secret?

but

    does a witness at L reveal useful collision CAPABILITY at L'?

## The metric

Define the capability class at a fresh label as the number of distinct functions
a candidate set induces there:

    K(X, L') = |{ H(theta, L', .) : theta in X }|

An attacker holding `W_L` can narrow theta only to `S_L`, and their best play at
`L'` is to guess a candidate and run the private algorithm, so their expected
work is proportional to `K(S_L, L')` against `K(Theta, L')` with no witness:

    l_cross = log2 K(Theta, L') - log2 K(S_L, L')

    l_cross = 0   the label ISOLATES -- the witness bought nothing at L'
    l_cross = l   the label is DECORATIVE -- full carry-over

## Both controls pass, which is what licenses the verdict

`og/run_label_isolation.py`, w=8, median of 5 trials, whole key space enumerated:

    family              L    L'   |S_L|  K(all)  K(S_L)      l   l_cross   verdict
    perfect-label       0     1      16      16      16   4.00      0.00   ISOLATES
    perfect-label       0     3      16      16      16   4.00      0.00   ISOLATES
    decorative-label    0     1       1     128       1   7.00      7.00   decorative
    decorative-label    0     3       2     128       2   6.00      6.00   decorative
    rainbow-seed        0     1       1     128       1   7.00      7.00   decorative
    rainbow-seed        0     3       2     128       2   6.00      6.00   decorative

The positive control is the load-bearing row: global leakage `l = 4.00` -- the
master key really does lose entropy -- while `l_cross = 0.00`. The metric
separates entropy loss from capability transfer, which the Q21 criterion could
not.

## Rainbow's seed is a decorative label

Adversarially swept, `L' = 2^j` for every j plus random labels, with direct
transfer (does the witness ITSELF still collide at L'?) measured alongside:

           L'   v2(L'-L)      l   l_cross   direct transfer
            1          0   7.00      7.00     1/200 = 0.005
            2          1   7.00      7.00     0/200 = 0.000
            4          2   7.00      7.00     6/200 = 0.030
            8          3   7.00      7.00     1/200 = 0.005
           16          4   7.00      7.00     0/200 = 0.000
           32          5   7.00      7.00     1/200 = 0.005
           64          6   7.00      7.00     5/200 = 0.025
          128          7   7.00      7.00    25/200 = 0.125
       random          -   7.00      7.00     1-4/200
 
`l_cross = l = 7.00` at every label, near and far. There is no 2-adic structure
in the label direction: nearby seeds are no kinder than random ones.

**Why, exactly.** The secret `m3` is global and enters as `H = A_L + m3 * C_L`.
Distinct `m3` give distinct functions at EVERY label, so narrowing `S_L` narrows
capability at `L'` by precisely the same factor. The seed shifts the IV; it does
not partition the secret. `mixB`'s `b ^= a + iv` makes the seed look like a
per-instance modifier, but it modifies the MIXING, not which part of the key is
in play, and that is the distinction that matters.

The one real signal is direct transfer at `L' = 128 = 2^(w-1)`: 12.5% against a
~0.5-3% baseline, i.e. a top-bit seed difference sometimes preserves the
collision outright. That is the top-bit transport already seen in Q16/Q18, not
label isolation, and it makes the seed slightly WORSE rather than better.

## Where this leaves the search

Rainbow's seed is ruled out as a label. The Q22 apparatus is general -- it takes
any `(family, H, label)` triple and both controls come with it -- so the next
candidate can be tested before it is built. What the positive control shows is
what to aim for: **the label must select which part of the key is in play.** A
label that modifies the computation while every witness remains evidence about
the same key object will read as decorative no matter how elaborate the
modification.

That is a sharper design target than "hide the structure better", and it is the
first criterion in this program that a construction could pass.
