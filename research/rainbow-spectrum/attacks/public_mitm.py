#!/usr/bin/env python3
"""The public meet-in-the-middle: can the flat side rediscover the sigma route?

This is the attack the construction most needs to survive, because it is the
public analogue of exactly what the trapdoor does. The privileged algorithm
matches a w-bit invariant between 2^(w/2) candidates on each side and then
FORCES the merge controls, costing 4*2^(w/2). If a public attacker can do the
same thing without theta, the candidate is dead.

WHAT THE ATTACKER IS ALLOWED. PublicArtifact.eval_side, and the pairing, which
attacks/theta_recovery.py shows leaks in fifteen public queries. Nothing else:
no theta, no intermediate states, no invariant, no mixer inverse.

WHY IT SHOULD BE MORE EXPENSIVE, and what would falsify that. Because the
pairing leaks, the pairs separate and a witness can be sought for each pair
independently -- one 4w-bit match becomes two 2w-bit matches. But the attacker
cannot compute sigma: sigma is preserved on the PRE-mixer state, and the final
mixer scrambles it into something the attacker has no inverse for. So instead of
matching a w-bit label between 2^(w/2) and 2^(w/2) candidates, the attacker must
match the full 2w-bit pair output between 2^(w/2) side-A candidates and
2^(w/2) x 2^w side-B candidates, which counts to about 2^(3w/2) per pair.

That is the prediction. It is measured rather than asserted, and the measurement
is what matters: if the observed exponent comes in near 0.5 instead of 1.5, the
sigma route was publicly available all along and the separation is dead.

THE EXISTING EVIDENCE THIS RESTS ON. A cheap class label would collapse the
attack immediately, and results/zmod-invariant-search.json already looked: it
recovers the pair sums on the pre-mixer coset, confirming the search works, and
finds NO Z/2^r-linear class label on the composed output at any modulus. So the
label exists but is not linearly accessible. This attack is what happens when
you cannot find the label and have to pay for the match instead.

COST MODEL. Public artifact evaluations, counted exactly. That is the honest
unit for an attacker holding only the artifact, and it is why the widths here
are small: 2^(3w/2) gate simulations in Python is affordable to w=10 and not
beyond. The exponent is fitted over the widths that are affordable and reported
with its range, rather than extrapolated past what was run.
"""

import itertools
import json
import math
import pathlib
import random
import sys
import time

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parent))

from models import public_artifact as PA                         # noqa: E402
from experiment_b import plant, privileged_solve                 # noqa: E402
from theta_recovery import recover_pairing                       # noqa: E402

RESULTS = HERE.parents[1] / "results"
WIDTHS = (4, 6, 8, 10)   # 2^(3w/2) gate simulations caps this near w=10
DRAWS = 3


def attack(artifact, pairing, cap):
    """Public-only MITM, per pair. Returns (solved, evaluations, witness)."""
    meta = artifact.meta
    npairs, k, w, t = meta["npairs"], meta["k"], meta["w"], meta["t"]
    evaluations = 0

    def side_a(prefix_words):
        nonlocal evaluations
        groups = {f"pa{i}": [(prefix_words[j] >> b) & 1
                             for j in range(npairs) for b in range(t)]
                  for i in range(k - 1)}
        groups.update({f"pb{i}": [0] * (npairs * t) for i in range(k - 1)})
        groups["mb"] = [0] * (npairs * w)
        evaluations += 1
        return artifact.eval_side("a", **groups)

    def side_b(prefix_words, merge_words):
        nonlocal evaluations
        groups = {f"pa{i}": [0] * (npairs * t) for i in range(k - 1)}
        groups.update({f"pb{i}": [(prefix_words[j] >> b) & 1
                                  for j in range(npairs) for b in range(t)]
                       for i in range(k - 1)})
        groups["mb"] = [(merge_words[j] >> b) & 1
                        for j in range(npairs) for b in range(w)]
        evaluations += 1
        return artifact.eval_side("b", **groups)

    # Side A table, keyed by each pair's output lanes. 2^t entries per pair.
    tables = []
    for pair_index, lanes in enumerate(pairing):
        book = {}
        for value in range(1 << t):
            words = [0] * npairs
            words[pair_index] = value
            out = side_a(words)
            book.setdefault(tuple(out[lane] for lane in lanes), value)
        tables.append(book)

    # Side B: enumerate (prefix, merge) for this pair until a table hit.
    found = [None] * npairs
    for pair_index, lanes in enumerate(pairing):
        book = tables[pair_index]
        for prefix_value in range(1 << t):
            for merge_value in range(1 << w):
                if evaluations > cap:
                    return False, evaluations, None
                pw = [0] * npairs
                pw[pair_index] = prefix_value
                mw = [0] * npairs
                mw[pair_index] = merge_value
                out = side_b(pw, mw)
                key = tuple(out[lane] for lane in lanes)
                if key in book:
                    found[pair_index] = (book[key], prefix_value, merge_value)
                    break
            if found[pair_index]:
                break
        if not found[pair_index]:
            return False, evaluations, None
    return True, evaluations, found


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows = []
    for w in WIDTHS:
        t = max(1, w // 2)
        cap = 16 * (1 << int(1.5 * w))
        for draw in range(DRAWS):
            rng = random.Random(8800 + 97 * draw + w)
            challenge = plant(w, 2, t, rng, False)
            artifact = PA.build(challenge["thetas"], challenge["S"],
                                challenge["T"], challenge["merge_a"], t, False)
            pairing, probe_queries = recover_pairing(artifact)
            started = time.time()
            solved, evaluations, _ = attack(artifact, pairing, cap)
            privileged = privileged_solve(challenge, t, False)
            rows.append({
                "w": w, "draw": draw, "solved": solved,
                "public_evaluations": evaluations + probe_queries,
                "privileged_evaluations": privileged.get("evaluations"),
                "privileged_solved": bool(privileged.get("solved")),
                "seconds": round(time.time() - started, 1), "cap": cap,
            })
            print(f"  w={w:>2} draw={draw}  public "
                  f"{'solved' if solved else 'CAPPED':<6} in "
                  f"{rows[-1]['public_evaluations']:>9} evals   privileged "
                  f"{privileged.get('evaluations'):>6}", flush=True)

    points, per_width = [], {}
    for w in WIDTHS:
        good = [r["public_evaluations"] for r in rows
                if r["w"] == w and r["solved"]]
        per_width[str(w)] = {"solved": len(good),
                             "attempted": sum(1 for r in rows if r["w"] == w),
                             "median": sorted(good)[len(good) // 2] if good else None}
        if good:
            points.append((w, math.log2(sorted(good)[len(good) // 2])))

    slope = None
    if len(points) >= 2:
        n = len(points)
        mx = sum(x for x, _ in points) / n
        my = sum(y for _, y in points) / n
        slope = (sum((x - mx) * (y - my) for x, y in points)
                 / sum((x - mx) ** 2 for x, _ in points))

    report = {
        "attack": "public_mitm",
        "access": "PublicArtifact.eval_side plus the publicly leaked pairing",
        "cost_unit": "public artifact evaluations",
        "widths": list(WIDTHS), "draws": DRAWS,
        "per_width": per_width,
        "beta_public_mitm": round(slope, 4) if slope else None,
        "beta_privileged": 0.5,
        "predicted_beta": 1.5,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rows": rows,
    }
    report["conclusion"] = (
        f"Public MITM scales as 2^({slope:.3f}w) against the privileged "
        f"2^(0.500w). The sigma route is NOT publicly available by this attack: "
        f"without the invariant the attacker pays for the full 2w-bit match."
        if slope and slope > 0.75 else
        f"Public MITM scales as 2^({slope:.3f}w) -- at or near the privileged "
        f"0.5, which would mean the sigma route IS publicly reachable and the "
        f"separation is dead." if slope else "insufficient data")
    path = RESULTS / "public-mitm.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\n{report['conclusion']}\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
