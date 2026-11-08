#!/usr/bin/env python3
"""Q8: k stripes over a SECRET partition of the message, combined into one digest.

    F(m) = C(W_1(m_1), ..., W_k(m_k))     partition secret, C the combiner

The keyholder collides ONE stripe and leaves every other word fixed. An identical
stripe output gives an identical combined output through ANY combiner, so
stitching is free and the private cost is 2^(w/2) whatever k is.

THE COMBINER DECIDES WHETHER THE SECRET SURVIVES. With an additive (XOR)
combiner, F is additively separable across stripes, so for u, v feeding different
stripes

    F(m+u+v) ^ F(m+u) ^ F(m+v) ^ F(m) == 0

identically, and the partition falls out of the combined digest alone -- no seeds,
no geometry, nothing but black-box queries. A nonlinear combiner breaks that
identity while leaving stitching untouched.

Measured at w=8, k=2, four words per stripe:

    XOR combiner        partition recovered 6/6   keyholder collision 6/6
    nonlinear combiner  partition recovered 0/6   keyholder collision 6/6

This is the first construction in the program where the decomposition attack
fails and the privileged route survives.

WHAT IT IS NOT. One attack failing is not security. A program that computes each
stripe's digest and then combines them exposes those digests as intermediates,
and which words feed which stripe follows at once -- the leak Q3 measured in four
evaluations and Q4 found as node-disjoint subcircuits. Public verification needs
a runnable program, so that is the attack to beat next. And k is not yet a
security knob: the keyholder needs one stripe, and a generic birthday on the
combined digest does not depend on k either.

CHAINING THE STRIPES BY CHOSEN PREFIX -- feeding each digest in as the next
stripe's prefix -- does not escape this. It is Q4's feedforward regime: a merge
at the first link propagates to the end, so both sides pay exactly one merge and
the later links never have to be attacked. Chosen-prefix power is symmetric; it
lets either side merge differing states later, which neither needs to do.
"""

import itertools
import json
import pathlib
import random
import sys
import time

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1]))

import stripe as ST                                              # noqa: E402

RESULTS = HERE.parents[1] / "results"


def build(w, k, words_per_stripe, trial, nonlinear):
    rng = random.Random(9000 + trial)
    nwords = k * words_per_stripe
    seeds = [rng.getrandbits(w) for _ in range(k)]
    slots = list(range(nwords))
    rng.shuffle(slots)
    partition = [slots[i * words_per_stripe:(i + 1) * words_per_stripe]
                 for i in range(k)]
    combiner_key = rng.getrandbits(w)

    def F(words):
        digests = []
        for index, idx in enumerate(partition):
            sub = [words[j] for j in idx]
            blocks = [(sub[2 * b], sub[2 * b + 1]) for b in range(len(sub) // 2)]
            digests.append(ST.rainbow(blocks, seeds[index], w))
        if not nonlinear:
            out = [0, 0, 0, 0]
            for d in digests:
                out = [a ^ b for a, b in zip(out, d)]
            return tuple(out)
        blocks = [(d[0], d[1]) for d in digests] + [(d[2], d[3]) for d in digests]
        return ST.rainbow(blocks, combiner_key, w)

    return F, partition, seeds, nwords


def recover_partition(F, nwords, w, rng, probes=6):
    """Black-box only: group words whose second derivative does not vanish."""
    def interacts(u, v):
        for _ in range(probes):
            m = [rng.getrandbits(w) for _ in range(nwords)]
            du, dv, duv = list(m), list(m), list(m)
            du[u] ^= 1
            dv[v] ^= 1
            duv[u] ^= 1
            duv[v] ^= 1
            if any(a ^ b ^ c ^ d for a, b, c, d
                   in zip(F(m), F(du), F(dv), F(duv))):
                return True
        return False

    parent = list(range(nwords))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for u, v in itertools.combinations(range(nwords), 2):
        if interacts(u, v):
            parent[find(u)] = find(v)
    groups = {}
    for i in range(nwords):
        groups.setdefault(find(i), []).append(i)
    return sorted(sorted(g) for g in groups.values())


def main():
    w, k, wps, trials = 8, 2, 4, 6
    rows = []
    for nonlinear in (False, True):
        recovered = stitched = 0
        for t in range(trials):
            F, partition, seeds, nwords = build(w, k, wps, t, nonlinear)
            truth = sorted(sorted(p) for p in partition)
            recovered += recover_partition(F, nwords, w, random.Random(t)) == truth
            rng = random.Random(500 + t)
            m_a, m_b, _ = ST.same_seed_collision(seeds[0], w, rng)
            base = [rng.getrandbits(w) for _ in range(nwords)]
            A, B, idx = list(base), list(base), partition[0]
            for slot, (wa, wb) in enumerate(zip(m_a, m_b)):
                A[idx[2 * slot]], A[idx[2 * slot + 1]] = wa
                B[idx[2 * slot]], B[idx[2 * slot + 1]] = wb
            stitched += (A != B) and F(A) == F(B)
        rows.append({"combiner": "nonlinear" if nonlinear else "xor",
                     "partition_recovered": f"{recovered}/{trials}",
                     "keyholder_one_stripe_collision": f"{stitched}/{trials}"})
        print(f"{'nonlinear' if nonlinear else 'xor      '} combiner: "
              f"partition recovered {recovered}/{trials}   "
              f"keyholder collision {stitched}/{trials}")

    report = {"question": "Q8: does a secret partition survive being combined?",
              "w": w, "k": k, "words_per_stripe": wps, "rows": rows,
              "xor_is_dead_because": "additive combining makes the cross-stripe second "
                                     "derivative vanish exactly",
              "nonlinear_survives_this_attack": "but program access still exposes the "
                                                "per-stripe digests as intermediates",
              "chaining_by_chosen_prefix": "does not escape: Q4 feedforward regime, a "
                                           "merge at the first link propagates, so both "
                                           "sides pay one merge",
              "generated": time.strftime("%Y-%m-%dT%H:%M:%S")}
    (RESULTS / "og-q8-secret-partition.json").write_text(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
