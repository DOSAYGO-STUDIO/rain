#!/usr/bin/env python3
"""The public cost surface C_pub(w, k), and what layering actually buys.

Reading one-dimensional slopes through this surface was a mistake. Saturation in
k is EXPECTED -- at fixed w there is only so much constraint entropy, so stacking
rounds cannot add bits forever. Classifying the k-axis as negative because w=10
flattens confuses "the knob has a range" with "the knob does nothing". Likewise
the w-slope at fixed k (0.761 at k=2, 0.604 at k=3) summarises a surface with a
crossover by a straight line, which is not meaningful on its own.

The quantities that decide whether layering is a finite-depth security amplifier:

    k_sat(w)   layers before the plateau
    P(w)       plateau exponent, log2 of public cost there
    A(w)       = P(w) - w/2, the advantage over the private birthday exponent

against the private side, which is settled:

    C_priv(w, k) = O(k * 2^(w/2)),  retries bounded, verified 8/8 to k=8

The outcomes that matter:
    A(w) ~ constant  -> layering buys a constant factor. Boring.
    A(w) ~ c*w       -> a genuine exponent margin, even though k saturates.
    k_sat(w) ~ w     -> total amplification grows with width by itself.

From w=10 the plateau is ~2^15.3 against w/2 = 5, so A(10) ~ 10.3, which if
linear gives c ~ 1.03 and predicts P(14) ~ 21.4. That is a falsifiable
prediction, which is the point of writing it down before the data lands.
"""

import json
import math
import pathlib
import statistics
import sys
from collections import defaultdict

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"
SOURCES = ["/tmp/kaxis.jsonl", "/tmp/kaxis12.jsonl", "/tmp/kaxis14.jsonl",
           "/tmp/layer.jsonl", "/tmp/layer2.jsonl"]


def load():
    cells = defaultdict(list)
    for path in SOURCES:
        try:
            for line in open(path):
                r = json.loads(line)
                if r.get("event") and r.get("conflicts"):
                    cells[(r["w"], r["k"])].append(r)
        except FileNotFoundError:
            continue
    return cells


def main(flat_threshold=0.30):
    cells = load()
    widths = sorted({w for w, _ in cells})
    surface, summary = {}, []
    for w in widths:
        ks = sorted(k for ww, k in cells if ww == w)
        series = []
        for k in ks:
            rows = cells[(w, k)]
            med = statistics.median([r["conflicts"] for r in rows])
            series.append((k, math.log2(med), len(rows),
                           rows[0]["cnf"]["ands"]))
        surface[w] = series
        # saturation: first k where the increment drops below the threshold
        k_sat = None
        for i in range(1, len(series)):
            if series[i][1] - series[i - 1][1] < flat_threshold:
                k_sat = series[i - 1][0]
                break
        plateau = max(l for _, l, _, _ in series)
        summary.append({"w": w, "k_values": [k for k, _, _, _ in series],
                        "k_sat": k_sat, "plateau_log2": round(plateau, 2),
                        "advantage_over_w_over_2": round(plateau - w / 2, 2),
                        "saturated": k_sat is not None})
        print(f"w={w:>2}: " + "  ".join(f"k{k}={l:.2f}" for k, l, _, _ in series))
        print(f"      k_sat={k_sat}  plateau={plateau:.2f}  "
              f"A(w)=P-w/2={plateau - w/2:.2f}"
              + ("" if k_sat else "   (NOT yet saturated -- plateau is a lower bound)"))

    done = [s for s in summary if s["saturated"]]
    if len(done) >= 2:
        pts = [(s["w"], s["advantage_over_w_over_2"]) for s in done]
        n = len(pts)
        mx = sum(p[0] for p in pts) / n
        my = sum(p[1] for p in pts) / n
        denom = sum((x - mx) ** 2 for x, _ in pts)
        slope = sum((x - mx) * (y - my) for x, y in pts) / denom if denom else None
        print(f"\nA(w) across saturated widths {pts}: slope {slope:.3f} bits per bit of w"
              if slope is not None else "")
        print("  constant -> a constant factor; ~c*w -> a genuine exponent margin")

    (RESULTS / "og-surface.json").write_text(json.dumps(
        {"surface": {str(w): surface[w] for w in surface}, "summary": summary,
         "private_model": "O(k * 2^(w/2)), retries bounded, verified to k=8"},
        indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
