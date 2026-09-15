#!/usr/bin/env python3
"""Deepen the thin top end, where all the leverage sits.

The wide run gave beta = 0.828 with bootstrap [0.505, 0.902]. The lower bound
clears 0.5 by 0.005, which is not precision worth resting a claim on, and the
reason is entirely sample size: w=22 rested on 3 draws and w=24 on 2. Those two
points carry most of the leverage on both the fit and the bootstrap.

So this deepens w = 20, 22, 24 to 10 draws each rather than reaching for one or
two heroic w=26 samples. A tighter interval over the range already measured is
worth more than a seventh point with n=1.

Serially that is about three and a half hours. Every draw is independent, so it
parallelises across cores; the wall time is roughly PROCS times better.

Seeds deliberately differ from scaling_wide.py's, so these are INDEPENDENT
draws rather than repeats of the same instances. Raw per-draw conflict counts
are stored this time -- the earlier run kept only medians, which made pooling
impossible after the fact.

No decision rule is restated here. The verdict remains the one frozen in
drift_test.py before any of this data existed; this only sharpens its inputs.
"""

import json
import math
import multiprocessing as mp
import pathlib
import statistics
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "results"

WIDTHS = (20, 22, 24)
DRAWS = 10
TIMEOUT_MS = 900000
PROCS = 6          # z3 is single threaded; leave headroom for memory at w=24


def task(args):
    """One independent instance. Top level so multiprocessing can pickle it."""
    import random
    from experiment_b import plant, public_solve
    from models import solverstats as ST

    w, hardened, draw = args
    rng = random.Random(8800 + 97 * draw + w)
    t = w // 2
    started = time.time()
    challenge = plant(w, 2, t, rng, hardened)
    if not challenge["witness_valid"]:
        return {"w": w, "hardened": hardened, "draw": draw,
                "conflicts": None, "status": "invalid_plant"}
    public = public_solve(challenge, t, hardened, TIMEOUT_MS)
    conflicts = ST.get(public["stats"], "conflict")
    status = ("sat" if public["verdict"] == "sat" else public["verdict"])
    if status != "sat" or conflicts is None or conflicts <= 0:
        conflicts = None
    return {"w": w, "hardened": hardened, "draw": draw, "conflicts": conflicts,
            "status": status, "seconds": round(time.time() - started, 1)}


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    jobs = [(w, hardened, d)
            for w in WIDTHS for hardened in (False, True) for d in range(DRAWS)]
    print(f"{len(jobs)} instances over {PROCS} processes "
          f"(widths {WIDTHS}, {DRAWS} draws, timeout {TIMEOUT_MS//1000}s)",
          flush=True)

    started = time.time()
    done = 0
    rows = []
    with mp.Pool(PROCS) as pool:
        for row in pool.imap_unordered(task, jobs):
            rows.append(row)
            done += 1
            print(f"  [{done}/{len(jobs)}] w={row['w']} "
                  f"{'hardened' if row['hardened'] else 'weak    '} "
                  f"conflicts={row['conflicts']} {row['status']} "
                  f"({row.get('seconds')}s)", flush=True)

    report = {
        "experiment": "deepen_top_widths",
        "purpose": ("tighten the bootstrap interval where n was 2-3, without "
                    "extending the width range"),
        "widths": list(WIDTHS), "draws": DRAWS, "timeout_ms": TIMEOUT_MS,
        "independent_of": "scaling_wide.py (different seed stream)",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "wall_seconds": round(time.time() - started, 1),
        "raw": rows,
        "variants": {},
    }

    for hardened in (False, True):
        label = "hardened" if hardened else "weak"
        per_width = {}
        for w in WIDTHS:
            values = [r["conflicts"] for r in rows
                      if r["w"] == w and r["hardened"] == hardened
                      and r["conflicts"]]
            censored = sum(1 for r in rows if r["w"] == w
                           and r["hardened"] == hardened and not r["conflicts"])
            per_width[str(w)] = {
                "n": len(values),
                "censored": censored,
                "median": statistics.median(values) if values else None,
                "log2_median": (round(math.log2(statistics.median(values)), 3)
                                if values else None),
                "excess": (round(math.log2(statistics.median(values)) - w / 2, 3)
                           if values else None),
                "raw": sorted(values),
            }
        report["variants"][label] = per_width
        print(f"\n{label}:")
        for w in WIDTHS:
            row = per_width[str(w)]
            print(f"  w={w}  n={row['n']}/{DRAWS} censored={row['censored']}  "
                  f"median={row['median']}  excess={row['excess']}")

    path = RESULTS / "deepen.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\nwall {report['wall_seconds']}s -> {path}")
    print("next: rerun drift_test.py against the combined widths")
    return 0


if __name__ == "__main__":
    sys.exit(main())
