#!/usr/bin/env python3
"""Deepen the thin top end, within an 8 GB machine.

The wide run gave beta = 0.828 with bootstrap [0.505, 0.902]. The lower bound
clears 0.5 by 0.005, which is not precision worth resting a claim on, and the
cause is sample size rather than anything structural: w=22 rested on 3 draws and
w=24 on 2. Those points carry most of the leverage on both the fit and the
bootstrap. The hardened control makes the same point more bluntly -- its w=22
median was 2,698,196 conflicts against 883,234 at w=24, so measured cost FELL as
width grew, which cannot be true.

So this deepens w = 20, 22, 24 rather than reaching for a seventh width with
n=1.

MEMORY. A first attempt ran six instances in one pool and was killed by the OS.
That was a straightforward misjudgement: this machine has 8 GB, and a z3
instance reaching millions of conflicts holds a very large clause database, so
six at once is far past what is available. Three corrections:

  * concurrency is now per width, highest at the cheap widths and lowest where
    instances are largest -- at w=24 it is ONE, so the biggest solves never run
    beside each other;
  * widths run one at a time, so peak usage is bounded by the most expensive
    width alone rather than by the whole job list;
  * a z3 memory ceiling is set, but is NOT relied upon.

That last point was tested rather than assumed, and it failed. With
memory_max_size = 300 MB a deliberately heavy instance peaked at ~381 MiB of
RSS and still returned sat: the parameter bounds z3's own allocator, not process
memory. It is kept as best effort, and safety comes from the process counts
above. (The probe also had to be read carefully -- macOS reports ru_maxrss in
BYTES where Linux reports kilobytes, which first made the peak look like 381 GB
on an 8 GB machine.)

Censored instances are reported and excluded, never counted -- a capped solve
reports a lower bound, and counting it drags the slope down exactly where the
slope is decided. Memory censoring is reported separately from timeout
censoring, because they bias in the same direction but for different reasons.

Seeds differ from scaling_wide.py's, so these are INDEPENDENT draws rather than
repeats. Raw per-draw conflict counts are stored this time; the earlier run kept
only medians, which is why the top end cannot simply be augmented in place.

No decision rule is restated. The verdict remains the one frozen in
drift_test.py before any of this data existed.
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

# Draws chosen against measured per-draw cost (36.6s, 159s, 367s); procs chosen
# so that the machine survives, since the memory ceiling proved unenforceable.
# w=24 runs strictly serially: those are the instances that reached millions of
# conflicts, and two of them together is what killed the first attempt.
# Estimated wall time ~60 min, which is the price of not gambling on 8 GB.
PLAN = {
    20: {"draws": 10, "procs": 3},
    22: {"draws": 8, "procs": 2},
    24: {"draws": 3, "procs": 1},
}
TIMEOUT_MS = 900000
MEMORY_CAP_MB = 1500


def task(args):
    """One independent instance. Top level so multiprocessing can pickle it."""
    import random
    import z3
    # Degrade to "unknown" on memory rather than dying and taking the pool with
    # it. A killed worker loses the whole run; a censored point loses one draw.
    z3.set_param("memory_max_size", MEMORY_CAP_MB)

    from experiment_b import plant, public_solve
    from models import solverstats as ST

    w, hardened, draw = args
    rng = random.Random(8800 + 97 * draw + w)
    t = w // 2
    started = time.time()
    try:
        challenge = plant(w, 2, t, rng, hardened)
        if not challenge["witness_valid"]:
            return {"w": w, "hardened": hardened, "draw": draw,
                    "conflicts": None, "status": "invalid_plant"}
        public = public_solve(challenge, t, hardened, TIMEOUT_MS)
        conflicts = ST.get(public["stats"], "conflict")
        status = public["verdict"]
        if status != "sat" or conflicts is None or conflicts <= 0:
            conflicts = None
    except Exception as error:                     # memory, or anything else
        return {"w": w, "hardened": hardened, "draw": draw, "conflicts": None,
                "status": f"error: {type(error).__name__}",
                "seconds": round(time.time() - started, 1)}
    return {"w": w, "hardened": hardened, "draw": draw, "conflicts": conflicts,
            "status": status, "seconds": round(time.time() - started, 1)}


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    started = time.time()
    rows = []

    for w in sorted(PLAN):
        plan = PLAN[w]
        jobs = [(w, hardened, d)
                for hardened in (False, True) for d in range(plan["draws"])]
        print(f"\nw={w}: {len(jobs)} instances, {plan['procs']} processes, "
              f"cap {MEMORY_CAP_MB} MB each "
              f"(peak ~{plan['procs'] * MEMORY_CAP_MB / 1024:.1f} GB)", flush=True)
        with mp.Pool(plan["procs"]) as pool:
            for row in pool.imap_unordered(task, jobs):
                rows.append(row)
                print(f"    w={row['w']} "
                      f"{'hardened' if row['hardened'] else 'weak    '} "
                      f"conflicts={row['conflicts']} {row['status']} "
                      f"({row.get('seconds')}s)", flush=True)

    report = {
        "experiment": "deepen_top_widths",
        "purpose": "tighten the interval where n was 2-3, without extending w",
        "plan": {str(w): p for w, p in PLAN.items()},
        "timeout_ms": TIMEOUT_MS, "memory_cap_mb": MEMORY_CAP_MB,
        "independent_of": "scaling_wide.py (different seed stream)",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "wall_seconds": round(time.time() - started, 1),
        "raw": rows, "variants": {},
    }

    for hardened in (False, True):
        label = "hardened" if hardened else "weak"
        per_width = {}
        for w in sorted(PLAN):
            mine = [r for r in rows if r["w"] == w and r["hardened"] == hardened]
            values = [r["conflicts"] for r in mine if r["conflicts"]]
            per_width[str(w)] = {
                "n": len(values),
                "attempted": len(mine),
                "censored": [r["status"] for r in mine if not r["conflicts"]],
                "median": statistics.median(values) if values else None,
                "excess": (round(math.log2(statistics.median(values)) - w / 2, 3)
                           if values else None),
                "raw": sorted(values),
            }
        report["variants"][label] = per_width
        print(f"\n{label}:")
        for w in sorted(PLAN):
            row = per_width[str(w)]
            print(f"  w={w}  n={row['n']}/{row['attempted']}  "
                  f"median={row['median']}  excess={row['excess']}"
                  + (f"  CENSORED {row['censored']}" if row["censored"] else ""))

    path = RESULTS / "deepen.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\nwall {report['wall_seconds']}s -> {path}")
    print("next: re-take the drift verdict against these widths")
    return 0


if __name__ == "__main__":
    sys.exit(main())
