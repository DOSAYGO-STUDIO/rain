#!/usr/bin/env python3
"""A(w,k) = log2 C_pub - log2 C_priv, and whether layering buys anything.

The earlier reading used P(w) - w/2, which is wrong: it compares the public
plateau against the private cost at k=2 while the plateau sits at some larger k
where private has also grown. The quantity that decides whether layering helps is

    A(w, k)    = log2 C_pub(w, k) - log2 C_priv(w, k)
    A_max(w)   = max_k A(w, k)
    k*(w)      = argmax_k A(w, k)

against the baseline A(w, 2), which is plain Experiment B. Three outcomes:

    k*(w) = 2                      layering buys nothing; B at k=2 is the best
    A_max(w) > A(w, 2)             a finite-depth amplifier, worth having even
                                   though k saturates
    A_max(w) - A(w,2) grows with w a scalable amplifier

Both sides are MEASURED here -- public by SAT on the genuine artifact, private by
running the layered privileged route -- so the subtraction is between two
measured quantities, not one measured and one modelled. They are still different
units (solver conflicts vs round evaluations), so only DIFFERENCES ACROSS k at a
fixed width are meaningful; the absolute value of A carries an arbitrary offset.
That is exactly why the comparison is A_max(w) - A(w,2) rather than A itself.
"""

import json
import math
import pathlib
import statistics
import sys
from collections import defaultdict

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"
PUBLIC = ["/tmp/kaxis.jsonl", "/tmp/kaxis12.jsonl", "/tmp/kaxis14.jsonl",
          "/tmp/layer.jsonl", "/tmp/layer2.jsonl"]
PRIVATE = "/tmp/priv_all.jsonl"


def main():
    pub = defaultdict(list)
    for path in PUBLIC:
        try:
            for line in open(path):
                r = json.loads(line)
                if r.get("event") and r.get("conflicts"):
                    pub[(r["w"], r["k"])].append(r["conflicts"])
        except FileNotFoundError:
            continue
    priv = {}
    for line in open(PRIVATE):
        r = json.loads(line)
        priv[(r["w"], r["k"])] = r["median_evals"]

    rows, summary = [], []
    for w in sorted({w for w, _ in pub}):
        series = []
        for k in sorted(k for ww, k in pub if ww == w):
            if (w, k) not in priv:
                continue
            cpub = math.log2(statistics.median(pub[(w, k)]))
            cpriv = math.log2(priv[(w, k)])
            series.append((k, cpub, cpriv, cpub - cpriv, len(pub[(w, k)])))
        if not series:
            continue
        base = next((a for k, _, _, a, _ in series if k == 2), None)
        kstar, amax = max(((k, a) for k, _, _, a, _ in series), key=lambda t: t[1])
        rows.append({"w": w, "series": [{"k": k, "pub": round(p, 2),
                                         "priv": round(v, 2), "A": round(a, 2),
                                         "draws": n}
                                        for k, p, v, a, n in series],
                     "A_at_k2": round(base, 2) if base is not None else None,
                     "A_max": round(amax, 2), "k_star": kstar,
                     "gain_over_k2": round(amax - base, 2) if base is not None else None})
        print(f"w={w:>2}:  " + "  ".join(f"k{k}:A={a:5.2f}" for k, _, _, a, _ in series))
        print(f"       A(k=2)={base:.2f}   A_max={amax:.2f} at k*={kstar}   "
              f"gain over k=2 = {amax - base:+.2f} bits")

    gains = [(r["w"], r["gain_over_k2"]) for r in rows if r["gain_over_k2"] is not None]
    verdict = "layering buys nothing beyond k=2"
    if gains and max(g for _, g in gains) > 0.5:
        verdict = "layering buys extra bits beyond k=2"
        if len(gains) >= 2:
            n = len(gains)
            mx = sum(g[0] for g in gains) / n
            my = sum(g[1] for g in gains) / n
            den = sum((x - mx) ** 2 for x, _ in gains)
            if den:
                slope = sum((x - mx) * (y - my) for x, y in gains) / den
                verdict += f"; gain slope {slope:+.3f} bits per bit of w"
    print(f"\ngains over k=2 by width: {gains}\n{verdict}")
    (RESULTS / "og-advantage.json").write_text(json.dumps(
        {"rows": rows, "gains_over_k2": gains, "verdict": verdict,
         "units_caveat": "public in solver conflicts, private in round evaluations; "
                         "only differences across k at fixed w are meaningful"},
        indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
