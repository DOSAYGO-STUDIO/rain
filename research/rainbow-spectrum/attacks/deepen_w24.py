#!/usr/bin/env python3
"""Bring w=24 to ~10 draws, the last undersampled width.

w=24 decided the drift verdict while resting on n=3, with raw draws spanning
694,652 to 3,574,741 -- a 5x spread. That is precisely the kind of leverage
point that has reversed this project's conclusions twice already, so it gets
sampled properly before anything is frozen, whichever way it lands.

Runs STRICTLY SERIALLY. Two w=24 instances together is what killed the machine,
and the memory ceiling was measured not to bound process RSS.

A note on timings from the previous run: one hardened draw reported 5560s against
a 900s timeout. z3's timeout is soft -- checked between decisions, not enforced
by a clock -- and the machine was paging heavily at the time. Wall times from
runs under memory pressure are therefore not trustworthy. Conflict counts are
solver-internal and unaffected, and conflicts are what the fit uses.

Writes results/deepen-w24.json. deepen.json is left untouched, so the n=3 data
stays on disk beside the deeper measurement rather than being silently replaced.
"""

import json
import math
import pathlib
import random
import statistics
import sys
import time

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parent))

import z3                                                        # noqa: E402
from experiment_b import plant, public_solve                     # noqa: E402
from models import solverstats as ST                             # noqa: E402

RESULTS = HERE.parents[1] / "results"
WIDTH = 24
DRAWS = 10
TIMEOUT_MS = 900000
MEMORY_CAP_MB = 1500


def main():
    z3.set_param("memory_max_size", MEMORY_CAP_MB)   # best effort, not a bound
    rows = []
    started = time.time()
    # weak first: the verdict is taken on it, so partial data still decides.
    for hardened in (False, True):
        label = "hardened" if hardened else "weak"
        for draw in range(DRAWS):
            rng = random.Random(51000 + 131 * draw + WIDTH)
            t = WIDTH // 2
            t0 = time.time()
            try:
                ch = plant(WIDTH, 2, t, rng, hardened)
                if not ch["witness_valid"]:
                    rows.append({"hardened": hardened, "draw": draw,
                                 "conflicts": None, "status": "invalid_plant"})
                    continue
                pub = public_solve(ch, t, hardened, TIMEOUT_MS)
                c = ST.get(pub["stats"], "conflict")
                status = pub["verdict"]
                if status != "sat" or not c:
                    c = None
            except Exception as e:
                rows.append({"hardened": hardened, "draw": draw, "conflicts": None,
                             "status": f"error: {type(e).__name__}",
                             "seconds": round(time.time() - t0, 1)})
                print(f"  {label} draw {draw}: ERROR {type(e).__name__}", flush=True)
                continue
            rows.append({"hardened": hardened, "draw": draw, "conflicts": c,
                         "status": status, "seconds": round(time.time() - t0, 1)})
            print(f"  {label} draw {draw}: conflicts={c} {status} "
                  f"({round(time.time()-t0,1)}s)  [elapsed {round(time.time()-started)}s]",
                  flush=True)

    report = {"experiment": "deepen_w24", "width": WIDTH, "draws": DRAWS,
              "procs": 1, "timeout_ms": TIMEOUT_MS,
              "timeout_note": "z3 timeout is soft; wall times under paging are unreliable",
              "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "wall_seconds": round(time.time() - started, 1),
              "raw": rows, "variants": {}}

    for hardened in (False, True):
        label = "hardened" if hardened else "weak"
        mine = [r for r in rows if r["hardened"] == hardened]
        vals = sorted(r["conflicts"] for r in mine if r["conflicts"])
        report["variants"][label] = {
            "n": len(vals), "attempted": len(mine),
            "censored": [r["status"] for r in mine if not r["conflicts"]],
            "median": statistics.median(vals) if vals else None,
            "excess": (round(math.log2(statistics.median(vals)) - WIDTH / 2, 3)
                       if vals else None),
            "spread": (round(max(vals) / min(vals), 2) if len(vals) > 1 else None),
            "raw": vals,
        }
        r = report["variants"][label]
        print(f"\n{label}: n={r['n']}/{r['attempted']} median={r['median']} "
              f"excess={r['excess']} spread={r['spread']}x")

    (RESULTS / "deepen-w24.json").write_text(json.dumps(report, indent=2))
    print(f"\nwall {report['wall_seconds']}s -> {RESULTS/'deepen-w24.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
