# Q23 — can label-local capability work? Yes in principle, no from Rainbow's structure

## Why the Q22 positive control does not answer this

Q22's `perfect-label` isolates exactly (`l_cross = 0` with `l = 4`), but it is
trivial: label `L_i` selects an independent key component, so the key grows
linearly with the number of labels. That is just K independent trapdoors stacked,
and it buys nothing -- you cannot serve more labels than your key has room for.

A useful scheme needs MANY labels under a BOUNDED master key `mu`, with per-label
subkeys `k_L = f(mu, L)`. So the real question is whether a witness at `L`, which
exposes `k_L`, can leave capability at `L'` intact.

## Measured (`og/run_label_derivation.py`), w=8, master key 7 bits

Capability at a fresh label `L'` after n witnesses at other labels:

    derivation            K(all,L')    n=1         n=2         n=3        n=4
    invertible               64      K=3 lc=4.5  K=2 lc=5.0  K=1 lc=6.0  K=1 lc=6.0
    lossy, discards 2        32      K=4 lc=3.0  K=2 lc=4.0  K=2 lc=4.0  K=2 lc=4.0
    lossy, discards 4         8      K=3 lc=1.5  K=2 lc=2.0  K=1 lc=3.0  K=1 lc=3.0
    lossy, discards 6         4      K=2 lc=1.0  K=2 lc=1.5  K=2 lc=1.5  K=2 lc=1.5

**No isolation at any setting.** Capability at an unseen label collapses to one
or two classes within a handful of witnesses in every row.

**And the apparent improvement in `l_cross` is an illusion.** Discarding `d` bits
shrinks `K(all, L')` by the same factor -- 64, 32, 8, 4 down the table. A lossy
derivation does not isolate labels; it shrinks the capability space, which
weakens the private route by exactly as much as it "protects" it. The small
`l_cross` at `loss=6` is small only because there were just 4 capability classes
to begin with.

## The reason, which is information-theoretic and general

Not specific to this `f`. Any deterministic derivation `f: (mu, L) -> k_L` makes
every subkey a function of the same `s`-bit master. Witnesses at distinct labels
therefore accumulate against one budget: an unbounded adversary extracts at most
`s` bits total, and capability everywhere collapses after about `s / k` witnesses.

Label-locality with a bounded key is impossible information-theoretically. It
requires **computational** one-wayness: `k_L` must be determined by `mu` yet
infeasible to invert, so that exposing `k_L` does not yield `mu` and hence
`k_L'`. That is exactly the mechanism of key-exposure-free chameleon hashing,
where the derivation rests on discrete log or factoring.

## Rainbow supplies no one-way step

Every operation in the round is a bijection on `Z/2^w`: odd multiply, rotate-right,
XOR, add, subtract. The composition of bijections is a bijection, so no part of
Rainbow's arithmetic is one-way. The one lossy element anywhere in the design is
the finalization (Q20: the 256-bit digest depends on 192 bits of state), and the
table above shows that lossiness of exactly that kind shrinks the capability
space rather than isolating labels.

## The answer

**Can a label-local trapdoor work? Yes -- chameleon hashes prove the goal is
achievable, and key-exposure-free variants prove the label mechanism is
achievable. But not from Rainbow's structure.** Getting there requires importing
a computational hardness assumption, and once imported it, not the 2-adic
geometry, is where the security lives. Rainbow becomes decoration.

This closes the trapdoor program on its own terms rather than by exhaustion. The
sequence was: hide a global weakness (Q8-Q17, all dead, each for a reason that
turned out to be the same reason), make the weakness label-local instead (Q22:
Rainbow's seed is decorative), derive label-local subkeys from a bounded key
(here: information-theoretically capped). The remaining door leads out of the
family.

## What survives, and is worth more than the trapdoor was

The 2-adic collision geometry is independent mathematics and it is exact:
transport iff, nested ball intersections, reverse incidence, ultrametric
composition, the work/leakage curve, the DDT depth/ray decomposition with its
gauge action. None of that depended on a trapdoor existing.

And two facts about the shipped function: the pair-sum collision break, and Q20's
finding that the 256-bit digest carries at most 192 bits while the 128-bit
variant ignores half the state outright.
