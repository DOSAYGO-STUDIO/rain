#!/usr/bin/env python3
"""Sample w=24 properly, on a machine that cannot hold it comfortably.

WHY w=24 AT ALL. It decided the drift verdict twice while resting on n=3, with
raw draws spanning 694,652 to 3,574,741 -- a 5x spread on three points. That is
the shape of leverage point that has already burned this project three times.

WHAT THE FIRST ATTEMPT AT THIS TAUGHT, which is more than it looks:

  1. Six of ten weak draws hit the 900s timeout. With a MAJORITY censored, the
     median of the survivors is not the median: it is the median of the easy
     tail. The n=3 figure in deepen.json (1,254,257) came from three draws that
     all happened to finish, so it is a survivorship minimum. That matters
     because a LOW w=24 median is exactly what produced the 'declining' verdict.

  2. Those six timeouts were not information-free, and the old code threw the
     information away. public_solve() collects statistics unconditionally, so
     each one reports the conflicts it got through before the clock stopped --
     a right-censored lower bound. deepen.py nulled them out.

  3. The run was killed by the OS for memory at ONE process, after the whole
     weak half had completed, and wrote nothing: the artifact was only produced
     at the end. Seven thousand seconds of measurement was lost to the absence
     of a checkpoint.

So: one draw per child process, conflicts recorded whether or not the solve
finished, and the artifact rewritten after EVERY draw. A kill now costs the
draw in flight and nothing else, and the run resumes from what is on disk
rather than restarting.

MEASURE THE THING YOU ARE AFRAID OF. deepen.py's concurrency plan rested on a
stated belief: "a z3 instance reaching millions of conflicts holds a very large
clause database, so six at once is far past what is available." That belief was
never measured, and it is FALSE. One w=24 instance was sampled at three
horizons:

    60s   216,131 conflicts    92.4 MB peak RSS
   180s   710,662 conflicts    93.0 MB peak RSS

Three times the search for 0.6 MB, because z3 garbage-collects its clause
database. Ten instances of this fit in a gigabyte. So the two OOM kills were
not caused by this workload at all -- they were collateral on an 8 GB desktop
with a 1 GB swap cap and browsers resident, and the second kill happening at
procs=1 was the clue that should have been read that way immediately. The
5,560s draw with 208k pageouts was this job being starved, not this job being
greedy.

The response is therefore the opposite of the last one. Concurrency goes back
up, and the guard moves to where the problem actually is: total system memory.
Children are only launched while the machine has room, so the job yields to the
desktop instead of competing with it. Per-child RSS is still policed, because
three in-process ceilings were MEASURED not to work here -- z3's
memory_max_size bounds z3's allocator rather than RSS, and Darwin refuses to
lower RLIMIT_AS or RLIMIT_DATA from unlimited at any cap from 2.2 to 8 GB.

REPORTING. Three views, because under this much censoring no single number is
honest on its own:

  survivors-only median  what deepen.py would have said. Reported so the bias
                         is visible, NOT used.
  Kaplan-Meier median    the censoring-aware estimate, undefined when survival
                         never reaches 0.5 -- in which case the median is
                         reported as a lower bound and the width is marked
                         not-estimable rather than guessed at.
  solve rate in budget   assumption-free: the fraction finishing inside 900s.
                         It needs no censoring model, and weak-vs-hardened can
                         be compared with it directly.

No decision rule is restated here. The verdict remains drift_test.analyse(),
frozen in c3ea7f0, and retake_verdict.py is what applies it.
"""

import json
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve()
RESULTS = HERE.parents[1] / "results"
CHILD = HERE.parent / "_w24_child.py"

W = 24
DRAWS = 10
TIMEOUT_MS = 900000
RLIMIT_MB = 2200          # attempted in-process; expected to be refused here
RSS_CAP_MB = 800          # 8x the measured peak: catches a runaway, not normal work
PROCS = int(sys.argv[1]) if len(sys.argv) > 1 else 3
SYSTEM_FLOOR_MB = 700     # do not start a new child below this much free memory
ARTIFACT = RESULTS / "deepen-w24.json"


def system_free_mb():
    """Free + inactive + speculative pages, in MB.

    This is the number that matters, not the child's own footprint: the thing
    that killed this job twice was the machine running out, not the solver
    running away. Inactive pages count because they are reclaimable.
    """
    try:
        out = subprocess.run(["vm_stat"], capture_output=True, text=True,
                             timeout=5).stdout
    except subprocess.SubprocessError:
        return None
    page, total = 4096, 0
    for line in out.splitlines():
        if "page size of" in line:
            page = int(line.split("page size of")[1].split()[0])
        for label in ("Pages free:", "Pages inactive:", "Pages speculative:"):
            if line.startswith(label):
                total += int(line.split(":")[1].strip().rstrip("."))
    return total * page / 1048576


def rss_mb(pid):
    """Child RSS in MB, or None once it is gone. ps reports kilobytes."""
    try:
        out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                             capture_output=True, text=True, timeout=5).stdout
        return int(out.strip()) / 1024 if out.strip() else None
    except (ValueError, subprocess.SubprocessError):
        return None


def kaplan_meier_median(rows):
    """KM median of conflicts-to-solve, treating timeouts as right-censored.

    Returns (estimate, kind). kind is 'point' when survival crosses 0.5, and
    'lower_bound' when it does not -- the case this data is expected to be in,
    and the case where quoting a point estimate would be a fabrication.

    The independence assumption is worth stating plainly: censoring is by wall
    clock, and an instance with a big clause database resolves conflicts more
    slowly, so censoring time is NOT fully independent of difficulty. That
    biases KM, and the solve-rate view is reported precisely because it does
    not depend on this.
    """
    observations = [(r["conflicts"], r["event"]) for r in rows
                    if r.get("conflicts")]
    if not observations:
        return None, "no_data"
    observations.sort()
    at_risk = len(observations)
    survival = 1.0
    for index, (value, event) in enumerate(observations):
        if event:
            survival *= (at_risk - 1) / at_risk
            if survival <= 0.5:
                return value, "point"
        at_risk -= 1
    largest = max(v for v, _ in observations)
    return largest, "lower_bound"


def summarise(rows, label):
    mine = [r for r in rows if r["hardened"] == (label == "hardened")]
    solved = [r["conflicts"] for r in mine if r.get("event") and r["conflicts"]]
    censored = [r["conflicts"] for r in mine
                if r.get("event") is False and r["conflicts"]]
    km, kind = kaplan_meier_median(mine)
    solved.sort()
    survivors_median = (solved[len(solved) // 2] if len(solved) % 2
                        else (solved[len(solved) // 2 - 1]
                              + solved[len(solved) // 2]) / 2) if solved else None
    return {
        "attempted": len(mine),
        "solved": len(solved),
        "censored": len(censored),
        "failed": len(mine) - len(solved) - len(censored),
        "solve_rate_in_budget": (round(len(solved) / len(mine), 3)
                                 if mine else None),
        "survivors_median": survivors_median,
        "survivors_median_is_biased": bool(censored) and len(censored) >= len(solved),
        "km_median": km,
        "km_median_kind": kind,
        # The number handed to the frozen drift test, and it has to be
        # COMPARABLE to how w=20 and w=22 were computed in deepen.json, which
        # used statistics.median over solved draws. With nothing censored the
        # two definitions differ -- KM's median is the smallest value whose
        # survival reaches 0.5, i.e. the lower-middle order statistic, not the
        # average of the two middles -- so the plain median is used whenever it
        # is applicable and KM only where it is actually needed. Where survival
        # never reaches 0.5 there is no median to quote and this stays None.
        "median": (survivors_median if not censored
                   else (km if kind == "point" else None)),
        "median_basis": ("statistics.median of solved draws (no censoring)"
                         if not censored else
                         f"Kaplan-Meier ({kind})"),
        "n": len(solved),
        "raw_solved": solved,
        "raw_censored_lower_bounds": sorted(censored),
        "peak_rss_mb": max((r.get("observed_peak_rss_mb")
                            or r.get("peak_rss_mb") or 0)
                           for r in mine) if mine else None,
        "memory_killed": sum(1 for r in mine
                             if r.get("status") == "memory_killed_by_parent"),
    }


def write(rows, started):
    report = {
        "experiment": "deepen_w24_censoring_aware",
        "purpose": "the width that decided the verdict, sampled past n=3",
        "w": W, "draws_planned": DRAWS,
        "timeout_ms": TIMEOUT_MS,
        "rss_cap_mb": RSS_CAP_MB,
        "memory_ceiling": "parent polls child RSS and SIGKILLs at the cap; "
                          "z3 memory_max_size and Darwin RLIMIT_AS/DATA were "
                          "all measured not to work",
        "isolation": "one child process per draw; artifact rewritten per draw",
        "seed_stream": "same as deepen.py (8800 + 97*draw + w) -- draws 0..9 "
                       "at w=24 are the SAME instances, now recorded correctly",
        "censoring": "timeouts kept as right-censored lower bounds on conflicts",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "wall_seconds": round(time.time() - started, 1),
        "raw": rows,
        "variants": {label: summarise(rows, label)
                     for label in ("weak", "hardened")},
    }
    ARTIFACT.write_text(json.dumps(report, indent=2))
    return report


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    started = time.time()
    rows = []
    # Resume: anything already on disk from a killed run is kept, not redone.
    if ARTIFACT.exists():
        try:
            rows = json.loads(ARTIFACT.read_text()).get("raw", [])
            print(f"resuming with {len(rows)} draws already on disk")
        except json.JSONDecodeError:
            rows = []
    done = {(r["hardened"], r["draw"]) for r in rows}

    jobs = [(hardened, draw)
            for hardened in (False, True) for draw in range(DRAWS)
            if (hardened, draw) not in done]
    running, pending = [], list(jobs)

    while pending or running:
        # Launch while there is both a slot and room on the machine. Yielding
        # to the desktop is the whole lesson of the two kills.
        while pending and len(running) < PROCS:
            free = system_free_mb()
            if free is not None and free < SYSTEM_FLOOR_MB and running:
                break
            hardened, draw = pending.pop(0)
            argv = [sys.executable, str(CHILD), str(W),
                    "1" if hardened else "0", str(draw),
                    str(TIMEOUT_MS), str(RLIMIT_MB)]
            proc = subprocess.Popen(argv, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)
            running.append({"proc": proc, "hardened": hardened, "draw": draw,
                            "peak": 0.0, "killed": False})
            print(f"  launched {'hardened' if hardened else 'weak'} draw {draw}"
                  f" (pid {proc.pid}, {len(running)} running, "
                  f"{free:.0f} MB free)", flush=True)

        time.sleep(2.0)

        for job in list(running):
            proc = job["proc"]
            current = rss_mb(proc.pid)
            if current:
                job["peak"] = max(job["peak"], current)
                if current > RSS_CAP_MB:
                    job["killed"] = True
                    proc.kill()
            if proc.poll() is None:
                continue
            running.remove(job)
            stdout, stderr = proc.communicate()
            if proc.returncode != 0 or not stdout.strip():
                row = {"w": W, "hardened": job["hardened"], "draw": job["draw"],
                       "conflicts": None, "event": None,
                       "status": "memory_killed_by_parent" if job["killed"]
                                 else f"child_exit_{proc.returncode}",
                       "stderr": stderr.strip()[-200:]}
            else:
                row = json.loads(stdout.strip().splitlines()[-1])
            row["observed_peak_rss_mb"] = round(job["peak"], 1)
            rows.append(row)
            report = write(rows, started)
            mark = {True: "solved", False: "CENSORED",
                    None: "failed"}[row.get("event")]
            label = "hardened" if row["hardened"] else "weak    "
            print(f"  w={W} {label} draw {row['draw']}: "
                  f"conflicts={row.get('conflicts')} {mark} "
                  f"({row.get('status')}, {row.get('seconds')}s, "
                  f"peak {row['observed_peak_rss_mb']} MB)  "
                  f"[{len(rows)}/{2 * DRAWS}, elapsed "
                  f"{report['wall_seconds']:.0f}s]", flush=True)

    report = write(rows, started)
    for label in ("weak", "hardened"):
        v = report["variants"][label]
        print(f"\n{label}: solved {v['solved']}/{v['attempted']} in budget "
              f"(rate {v['solve_rate_in_budget']}), censored {v['censored']}")
        print(f"  survivors median {v['survivors_median']}"
              + ("  <- BIASED, majority censored"
                 if v["survivors_median_is_biased"] else ""))
        print(f"  KM median {v['km_median']} ({v['km_median_kind']})")
        print(f"  peak RSS {v['peak_rss_mb']} MB")
    print(f"\nwall {report['wall_seconds']}s -> {ARTIFACT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
