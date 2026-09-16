# Q24 — isolation costs one fresh secret per label, and every form of sharing leaks

(Numbering note: this is the work proposed as "Q23"; that number was already
taken by the derivation result committed earlier.)

## 1. The counting bound

Let `K_L` be the secret-dependent capability that makes collisions cheap at label
`L`, and suppose a witness at `L` determines `h` bits of `K_L` while revealing
nothing about any `K_{L'}`. Perfect isolation means `I(K_{L'} ; W_L) = 0` for all
`L' != L`, so the capabilities carry independent entropy and

    H(K_1, ..., K_N) = sum_i H(K_i) ~ N h

Every `K_i` is a function of the master secret `K`, so `H(K) >= H(K_1..K_N)` and

    H(K) >= N h

**Information-theoretic label isolation costs `h` fresh bits of master key per
label.** This is why the Q22 positive control works: it is paying, one
independent subkey at a time. Any construction with a key sublinear in the label
count must therefore be *computationally* hiding the relations between the
`K_L`s -- it cannot be hiding them information-theoretically.

## 2. The independent construction, built for real

Not a synthetic control this time: real Rainbow witnesses, and the capability is
the multiplier the private route uses. A witness is an actual collision of
`H(x) = A(x) + theta_L C(x)`, and the consistent set is Q14's exact incidence
ball `{ m odd : m (C(xa) - C(xb)) = A(xb) - A(xa) }`. w=6, whole key space
enumerated (`og/run_label_sharing.py`):

    independent (4 words)                      K(all, L'=3) = 32
       after 1 witness:  |cand| = 65536   K(cand,L') = 32   l_cross = 0.00
       after 2 witnesses: |cand| =  3072   K(cand,L') = 32   l_cross = 0.00
       after 3 witnesses: |cand| =   256   K(cand,L') = 32   l_cross = 0.00

Perfect isolation with genuine Rainbow collisions. The master key loses entropy
fast -- 65536 -> 256 candidates -- while capability at the fresh label is
completely untouched. This is the shape Q22 says is necessary, and it is real.

## 3. Compression: the graded failure

Same apparatus, `theta_L` a polynomial in the label:

    derivation        n=1        n=2        n=3        n=4        n=5
    degree 0 (1 wd)  lc=5.00    5.00       5.00       5.00       5.00
    degree 1 (2 wd)  lc=1.00    4.50       5.00       5.00       5.00
    degree 2 (3 wd)  lc=1.00    1.00       3.00       3.50       3.50
    degree 3 (4 wd)  lc=1.00    1.00       3.00       5.00       5.00

Collapse arrives after roughly `d+1` informative witnesses, as predicted -- exact
for d=0,1,3; d=2 lags because ball sizes vary, so witnesses differ in how much
they pin down.

**The floor is the important part.** Every compressed derivation reads
`l_cross = 1.00` after a SINGLE witness, at every degree. One witness costs one
bit of cross-label capability no matter how much key is spent. Only the
independent construction reaches 0.00.

## 4. The tree: ultrametric, but a step function, and no compression

`theta_L` = sum of node secrets on the truncated root-to-leaf path. The Monte
Carlo version of this was junk -- the sample thinned after two witnesses, which
biases `K(cand,L')` downward and inflates `l_cross`; it reported a spurious 3.00
for a distant leaf. Replaced by exact enumeration at depth 2
(`og/run_tree_exact.py`, key space 32768 enumerated):

    witness L   fresh L'   same class   K(all,L')   K(cand,L')   l_cross
            0          1         True          32            1      5.00  full share
            0          2        False          32           32      0.00  ISOLATES
            0          3        False          32           32      0.00  ISOLATES
            2          3         True          32            1      5.00  full share
            2          0        False          32           32      0.00  ISOLATES

The reason is exact rather than statistical: distinct truncated paths give
linearly independent indicator rows, because each ends at a node no other path
uses. Independent rows with uniform node secrets make the `theta`s jointly
uniform and independent, so cross-class leakage is exactly zero and within-class
sharing is total.

So the geometry IS ultrametric -- capability sharing is membership in a common
ball -- but it is a **step function, not a gradient**. And it does not compress:
a tree serving `N` labels with `N/c` classes is just `N/c` independent secrets
with the leaves relabelled. Key size stays linear in the number of *distinct
capabilities*, which is the only count the bound in section 1 cares about.

## 5. What this settles

    sharing scheme        key size        isolation
    independent           N words         PERFECT (l_cross = 0)
    polynomial degree d   d+1 words       fails after ~d+1 witnesses; >= 1 bit at n=1
    additive tree         #classes words  perfect between classes, none within;
                                          no compression -- classes ARE the key

Every algebraic sharing scheme tried collapses to one of two regimes: pay `N`
independent secrets and isolate, or share and leak from the first witness. That
is section 1's bound showing up construction by construction, which is what it
should do if the bound is right.

**The remaining door is exactly the one the bound names.** A key sublinear in the
label count with `l_cross ~ 0` must hide the relations between capabilities
computationally. That is a PRF, and then, per Q23, the PRF supplies the
isolation hardness -- Rainbow is the cheap collision engine underneath, not the
source of security.

## 6. The sentence the program was looking for

    Rainbow's collision weakness gives cheap private collision construction only
    by consuming label-local secret entropy; sharing that entropy across labels
    makes witnesses transferable, and the trade is one-for-one.
