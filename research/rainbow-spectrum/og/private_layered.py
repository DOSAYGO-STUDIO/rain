#!/usr/bin/env python3
"""The layered private route, with its cost model.

Vary round-0 controls only; rounds 1..k-2 carry RERANDOMISED controls; match the
pair invariant at the last round's input; force the merge controls there.

Cost model. One attempt builds 2 sides x npairs books of 2^t entries, and each
entry costs (k-1) round evaluations, so an attempt is 2*npairs*2^t*(k-1). The
books hold 2^t entries against a w-bit invariant, so with t = w/2 a shared value
exists with probability ~1-1/e per pair; both pairs must match, so the expected
number of attempts is a constant INDEPENDENT of k. Hence

    E[C_priv] = O(k * 2^(w/2)),   log2 C_priv = w/2 + log2 k + O(1)

which is linear in k, not exponential. The measured per-layer slope decays
accordingly (1.58, 1.32, 0.09 bits at w=14) -- it is log k, not a constant rate.

Fixing the middle controls to zero instead of rerandomising drops success to
~40%, because plant() draws them at random so the planted witness falls outside
the search space and only birthday luck remains.
"""

import json
import pathlib
import random
import statistics
import sys
import time

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[1] / "attacks"))

from experiment_b import plant, round_fwd, inject_weak, evaluate  # noqa: E402
from models import rainbow as R                                   # noqa: E402
from models import wordops as W                                   # noqa: E402

RESULTS = HERE.parents[1] / "results"


def attempt(challenge, t, w, mid):
    thetas = challenge["thetas"]
    k, last = len(thetas), thetas[-1]
    npairs = len(thetas[0].pairs)
    evaluations = 0
    books = {}
    for side, state in (("a", challenge["S"]), ("b", challenge["T"])):
        for pair in range(npairs):
            book = {}
            for value in range(1 << t):
                controls = [0] * npairs
                controls[pair] = value
                s = round_fwd(state, tuple(controls), thetas[0], False)
                evaluations += 1
                for r in range(1, k - 1):
                    s = round_fwd(s, mid[r - 1], thetas[r], False)
                    evaluations += 1
                book.setdefault(R.invariants(s, last)[pair], value)
            books[(side, pair)] = book

    ca, cb = [0] * npairs, [0] * npairs
    for pair in range(npairs):
        shared = set(books[("a", pair)]) & set(books[("b", pair)])
        if not shared:
            return None, evaluations
        key = min(shared)
        ca[pair] = books[("a", pair)][key]
        cb[pair] = books[("b", pair)][key]

    def forward(state, first):
        s = round_fwd(state, tuple(first), thetas[0], False)
        for r in range(1, k - 1):
            s = round_fwd(s, mid[r - 1], thetas[r], False)
        return s

    a = inject_weak(forward(challenge["S"], ca), challenge["merge_a"], last)
    b = forward(challenge["T"], cb)
    merge_b = []
    for (i, _j), (si, _sj) in zip(last.pairs, last.signs):
        delta = W.sub(a[i], b[i], w)
        merge_b.append(delta if si == 1 else W.sub(0, delta, w))
    prefix_a = tuple([tuple(ca)] + list(mid))
    prefix_b = tuple([tuple(cb)] + list(mid))
    ok = (evaluate(thetas, challenge["T"], prefix_b, tuple(merge_b), False)
          == evaluate(thetas, challenge["S"], prefix_a, challenge["merge_a"], False))
    return ok, evaluations


def solve(challenge, t, w, rng, cap=40):
    npairs = len(challenge["thetas"][0].pairs)
    k = len(challenge["thetas"])
    total = 0
    for n in range(1, cap + 1):
        mid = tuple(tuple(rng.getrandbits(t) for _ in range(npairs))
                    for _ in range(k - 2))
        ok, ev = attempt(challenge, t, w, mid)
        total += ev
        if ok:
            return total, n
    return None, cap


def main():
    rows = []
    for w in (12, 14):
        t = w // 2
        base = 4 * (1 << t)
        for k in (2, 3, 4, 5, 6, 7, 8):
            totals, tries, wins = [], [], 0
            for trial in range(8):
                rng = random.Random(8800 + 97 * trial + w + 7919 * k)
                challenge = plant(w, k, t, rng, False)
                total, n = solve(challenge, t, w, rng)
                if total is not None:
                    wins += 1
                    totals.append(total)
                    tries.append(n)
            med = statistics.median(totals) if totals else None
            rows.append({"w": w, "k": k, "solved": f"{wins}/8",
                         "median_evaluations": med,
                         "median_attempts": statistics.median(tries) if tries else None,
                         "predicted_per_attempt": base * (k - 1)})
            print(f"w={w} k={k}: solved {wins}/8  median evals {med:>7}  "
                  f"attempts {statistics.median(tries) if tries else '-':>4}  "
                  f"per-attempt model {base*(k-1):>6}", flush=True)

    report = {"model": "E[C_priv] = O(k * 2^(w/2)); attempts bounded independently of k",
              "rows": rows, "generated": time.strftime("%Y-%m-%dT%H:%M:%S")}
    (RESULTS / "og-private-layered.json").write_text(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
