#!/usr/bin/env python3
"""Is a wall-clock timeout a valid censoring criterion on this machine? No.

This exists because a single number quietly decided a verdict twice, and the
instrument that produced it turns out to measure the wrong thing.

THE OBSERVATION. Draw 0 at w=24, weak variant, is a fixed instance: the seed
stream is deterministic, so it is the same SMT problem every time, and z3's
search over it is deterministic too. That one instance has now been observed
finishing in three different amounts of wall time:

    deepen.py            solved     127.5s   1,254,257 conflicts
    memory probe         solved     385.1s   1,254,257 conflicts
    deepen_w24.py (v1)   TIMED OUT  >900s    censored

Same problem, same search, same answer where it got there -- and in one run it
was recorded as a right-censored observation. The conflict count is identical
across both runs that reached sat, which is the proof that the search did not
differ; only the machine did. The v1 run was thrashing (208k pageouts, and one
draw took 5,560s against a 900s limit), so its instances ran several times
slower and hit the clock without being any harder.

WHAT THAT INVALIDATES. The "6 of 10 weak draws censored at w=24" figure does not
mean six instances were too hard to solve in budget. It means six instances were
running on a starved machine. Censoring that correlates with machine load rather
than instance difficulty violates the one assumption Kaplan-Meier needs -- that
censoring is independent of the event time -- and it biases in an undetectable
direction, because whichever draws happened to run while a browser was busy get
recorded as expensive.

It cuts the other way too, and this is the uncomfortable part: it means the
original deepen.py w=24 figures are NOT obviously the survivorship artifact they
looked like. Those three draws ran under better conditions and finished
honestly. The earlier diagnosis in deepen.py's correction note -- that the n=3
median was the median of an easy tail -- was reasoning from censoring that was
itself an artifact.

WHAT TO MEASURE INSTEAD. z3 reports "rlimit count", a deterministic internal
work counter that does not move with CPU contention, memory pressure or machine
speed. Conflicts are likewise deterministic per instance. Both are reproducible;
wall time is not. Every draw now records rlimit_count alongside conflicts, so
the cost series can be read without trusting the clock, and any future budget
should be expressed in rlimit units rather than seconds.

Run this to reproduce the table above. It is cheap at the short horizons and
about seven minutes at the long one.
"""

import json
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve()
RESULTS = HERE.parents[1] / "results"
CHILD = HERE.parent / "_w24_child.py"

HORIZONS = (60000, 180000, 420000)
W, DRAW, HARDENED = 24, 0, False


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows = []
    for timeout_ms in HORIZONS:
        argv = [sys.executable, str(CHILD), str(W), "0", str(DRAW),
                str(timeout_ms), "0"]
        started = time.time()
        proc = subprocess.run(argv, capture_output=True, text=True)
        row = (json.loads(proc.stdout.strip().splitlines()[-1])
               if proc.stdout.strip() else {"status": f"exit_{proc.returncode}"})
        row["budget_ms"] = timeout_ms
        row["wall_seconds"] = round(time.time() - started, 1)
        rows.append(row)
        print(f"  budget {timeout_ms/1000:>5.0f}s -> {row.get('status'):<8} "
              f"conflicts={row.get('conflicts')} "
              f"rlimit={row.get('rlimit_count')} "
              f"peak {row.get('peak_rss_mb')} MB", flush=True)

    solved = [r for r in rows if r.get("event")]
    consistent = len({r["conflicts"] for r in solved}) <= 1
    report = {
        "experiment": "timeout_validity",
        "question": "does a wall-clock budget censor on difficulty or on load?",
        "instance": {"w": W, "draw": DRAW, "hardened": HARDENED,
                     "note": "deterministic: same seed, same search, every run"},
        "horizons": rows,
        "conflicts_identical_across_solved_runs": consistent,
        "prior_observations": {
            "deepen.py": {"status": "sat", "seconds": 127.5,
                          "conflicts": 1254257},
            "deepen_w24.py v1": {"status": "unknown", "seconds": 900.2,
                                 "conflicts_discarded": True,
                                 "machine": "thrashing, 208k pageouts"},
        },
        "finding": (
            "One deterministic instance was recorded as solved in 127.5s, "
            "solved in 385.1s, and censored at 900s, with identical conflict "
            "counts wherever it finished. Wall-clock censoring therefore tracks "
            "machine load, not instance difficulty, and cannot support a "
            "survival analysis. Use rlimit count, which is deterministic."),
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    path = RESULTS / "timeout-validity.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"\nconflicts identical across solved runs: {consistent}")
    print(f"{report['finding']}\n-> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
