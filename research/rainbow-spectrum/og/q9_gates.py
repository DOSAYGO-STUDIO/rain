#!/usr/bin/env python3
"""Q9: the two gates Q8 has to pass. It fails both.

GATE 2 -- does a valid witness require solving every stripe? No, and structurally
so. The stripes read DISJOINT words, so changing any word touches exactly one
stripe and a collision only needs THAT stripe to collide. The cheapest witness
touches one stripe, so k is not amplification. Nor can it be repaired by
demanding the witness differ in every stripe: the public cannot check that
condition without the partition, which is the secret. Requiring all stripes to be
involved means every stripe reads the whole message -- the shared-message regime
already measured to cost both sides the same (results/og-same-message-stripes.json).

GATE 1 -- can the partition survive program access? No. Public verification needs
a runnable program, and running it produces intermediate words. The attacker here
gets the execution trace UNLABELED and in evaluation order, may vary inputs, and
knows no seed, no geometry and no labels. It takes each traced word's input
support, scores each pair of inputs by the smallest observed support containing
both, and single-links. The true partition appears at every k tried:

    w=8  k=2   6/6        w=8  k=4   6/6
    w=8  k=3   6/6        w=10 k=3   6/6

(A first version of this attack scored 0/6 at k=3 -- its "maximal strict support"
rule latched onto combiner intermediates whose support is stripe1 u stripe2, a
strict subset when k >= 3. That was the heuristic failing, not the construction
resisting, and the k=2 control is what exposed it.)

WHY THIS IS NOT FIXABLE BY COMPILING DIFFERENTLY. The partition is not hidden by
the representation; it is exposed by the function. F depends on m_i only through
W_i(m_i), so that digest is a BOTTLENECK, and any evaluator must compute
something equivalent to it. Its input support is exactly the stripe. The
keyholder's cheap route exists precisely because the computation decomposes
through those bottlenecks -- and a bottleneck is a visible support boundary.

That is the day's obstruction in its sharpest form: the private cheap route
requires a bottleneck, and a bottleneck is publicly visible. Hiding it would take
a general-purpose obfuscator, and then the obfuscator, not Rainbow, is the
trapdoor.
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
from models import rainbow as R                                  # noqa: E402

RESULTS = HERE.parents[1] / "results"


def instrumented(w, k, words_per_stripe, trial):
    rng = random.Random(9000 + trial)
    nwords = k * words_per_stripe
    seeds = [rng.getrandbits(w) for _ in range(k)]
    slots = list(range(nwords))
    rng.shuffle(slots)
    partition = [slots[i * words_per_stripe:(i + 1) * words_per_stripe]
                 for i in range(k)]
    combiner_key = rng.getrandbits(w)
    theta = R.default_theta(w)

    def run(words):
        trace, digests = [], []
        for index, idx in enumerate(partition):
            sub = [words[j] for j in idx]
            blocks = [(sub[2 * b], sub[2 * b + 1]) for b in range(len(sub) // 2)]
            h = ST.iv(seeds[index], len(blocks), w)
            for bi, (x, y) in enumerate(blocks):
                h = ST._inject(h, x, y, w)
                h = (R.mix_a(h, theta) if bi % 2 == 0
                     else R.permute(R.mix_b(h, theta, seeds[index]), theta))
                trace += list(h)
            d = ST.finalize(h, seeds[index], w, 4, theta)
            trace += list(d)
            digests.append(d)
        blocks = ([(d[0], d[1]) for d in digests]
                  + [(d[2], d[3]) for d in digests])
        h = ST.iv(combiner_key, len(blocks), w)
        for bi, (x, y) in enumerate(blocks):
            h = ST._inject(h, x, y, w)
            h = (R.mix_a(h, theta) if bi % 2 == 0
                 else R.permute(R.mix_b(h, theta, combiner_key), theta))
            trace += list(h)
        return trace + list(ST.finalize(h, combiner_key, w, 4, theta))

    return run, partition, nwords


def attack(run, nwords, w, rng, probes=4):
    """Program access only: unlabeled trace, input probing, no seeds or geometry."""
    base_words = [rng.getrandbits(w) for _ in range(nwords)]
    base = run(base_words)
    support = [set() for _ in base]
    for j in range(nwords):
        for _ in range(probes):
            m = list(base_words)
            m[j] = rng.getrandbits(w)
            for idx, (a, b) in enumerate(zip(base, run(m))):
                if a != b:
                    support[idx].add(j)

    sups = [s for s in support if s]
    infinity = nwords + 1
    distance = {}
    for u, v in itertools.combinations(range(nwords), 2):
        sizes = [len(s) for s in sups if u in s and v in s]
        distance[(u, v)] = min(sizes) if sizes else infinity

    parent = list(range(nwords))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    snapshots, previous = [], None
    for (u, v), d in sorted(distance.items(), key=lambda kv: kv[1]):
        if previous is not None and d != previous:
            groups = {}
            for i in range(nwords):
                groups.setdefault(find(i), []).append(i)
            snapshots.append(sorted(sorted(g) for g in groups.values()))
        parent[find(u)] = find(v)
        previous = d
    groups = {}
    for i in range(nwords):
        groups.setdefault(find(i), []).append(i)
    snapshots.append(sorted(sorted(g) for g in groups.values()))
    return snapshots


def main():
    rows = []
    for w, k, wps in ((8, 2, 4), (8, 3, 4), (8, 4, 4), (10, 3, 4)):
        hits, trials = 0, 6
        for t in range(trials):
            run, partition, nwords = instrumented(w, k, wps, t)
            truth = sorted(sorted(p) for p in partition)
            hits += any(s == truth for s in attack(run, nwords, w, random.Random(t)))
        rows.append({"w": w, "k": k, "words_per_stripe": wps,
                     "partition_recovered": f"{hits}/{trials}"})
        print(f"w={w} k={k}: partition recovered from the program trace {hits}/{trials}")

    report = {
        "question": "Q9: Q8's two gates",
        "gate_2_all_stripes_required": "FAILS structurally -- disjoint stripes mean the "
                                       "cheapest witness touches one stripe, and the "
                                       "public cannot require otherwise without the secret",
        "gate_1_partition_hiding": "FAILS under program access",
        "rows": rows,
        "why_not_a_compilation_issue": "F depends on m_i only through W_i(m_i), so that "
                                       "digest is a bottleneck any evaluator must compute, "
                                       "and its input support IS the stripe",
        "sharpest_form": "the private cheap route requires a bottleneck; a bottleneck is a "
                         "publicly visible support boundary",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (RESULTS / "og-q9-gates.json").write_text(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
