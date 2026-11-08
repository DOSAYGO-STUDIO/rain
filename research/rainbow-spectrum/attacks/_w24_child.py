#!/usr/bin/env python3
"""One draw, in its own process, so a memory kill costs one point not the run.

Two things are different from the in-pool version in deepen.py, and both are
corrections rather than tuning:

  * conflicts are read out REGARDLESS of verdict. public_solve() collects
    statistics unconditionally, so a timed-out instance still reports how many
    conflicts it got through. deepen.py discarded that as None, which turned six
    informative right-censored observations at w=24 into six holes. A capped
    solve is a LOWER BOUND on the cost, and a lower bound is data.

  * memory is policed from OUTSIDE, because on this machine NOTHING bounds it
    from inside. Three ceilings were tried and all three were measured to fail:
    z3's memory_max_size bounds its own allocator, not RSS (300 MB configured,
    ~381 MiB actual, still returned sat); and Darwin refuses to lower either
    RLIMIT_AS or RLIMIT_DATA from unlimited -- setrlimit returns EINVAL, which
    Python surfaces as "current limit exceeds maximum limit", at every cap from
    2.2 GB to 8 GB. So the parent samples this child's RSS and kills it. The
    attempt is still made here, and recorded when it fails, so the next person
    does not rediscover this.

Peak RSS is reported so the cost of a width is measured rather than guessed.
macOS reports ru_maxrss in BYTES, Linux in kilobytes; normalised here.
"""

import json
import random
import resource
import sys
import time


def main():
    w, hardened, draw, timeout_ms, cap_mb = (
        int(sys.argv[1]), sys.argv[2] == "1", int(sys.argv[3]),
        int(sys.argv[4]), int(sys.argv[5]))

    rlimit_note = "not attempted"
    if cap_mb:
        soft = cap_mb * 1024 * 1024
        _, hard = resource.getrlimit(resource.RLIMIT_AS)
        try:
            resource.setrlimit(resource.RLIMIT_AS, (soft, hard))
            rlimit_note = f"RLIMIT_AS set to {cap_mb} MB"
        except (ValueError, OSError) as error:
            # Expected on Darwin; the parent is the real ceiling.
            rlimit_note = f"RLIMIT_AS unsupported: {error}"

    import pathlib
    here = pathlib.Path(__file__).resolve()
    sys.path.insert(0, str(here.parents[1]))
    sys.path.insert(0, str(here.parent))

    from experiment_b import plant, public_solve
    from models import solverstats as ST

    rng = random.Random(8800 + 97 * draw + w)      # same stream as deepen_w24
    t = w // 2
    started = time.time()
    out = {"w": w, "hardened": hardened, "draw": draw}
    try:
        challenge = plant(w, 2, t, rng, hardened)
        if not challenge["witness_valid"]:
            out.update(status="invalid_plant", conflicts=None, event=None)
        else:
            public = public_solve(challenge, t, hardened, timeout_ms)
            conflicts = ST.get(public["stats"], "conflict")
            verdict = public["verdict"]
            # rlimit count is z3's own deterministic work counter. Unlike wall
            # time it does not move with CPU contention or memory pressure, so
            # it is the honest cross-check on a conflict series gathered on a
            # busy 8 GB desktop -- and the previous run had a draw take 5,560s
            # against a 900s timeout purely because the machine was paging.
            out["rlimit_count"] = ST.get(public["stats"], "rlimit")
            # sat  -> the search finished: an EVENT, conflicts is the cost.
            # unknown -> the clock ran out: CENSORED, conflicts is a lower bound.
            out.update(status=verdict, conflicts=conflicts,
                       event=(verdict == "sat"),
                       replay_verified=public.get("replay_verified"))
    except MemoryError as error:
        out.update(status="memory", conflicts=None, event=False,
                   detail=type(error).__name__)
    except Exception as error:
        out.update(status=f"error:{type(error).__name__}", conflicts=None,
                   event=None, detail=str(error)[:200])

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    out["peak_rss_mb"] = round(peak / (1048576 if sys.platform == "darwin"
                                       else 1024), 1)
    out["seconds"] = round(time.time() - started, 1)
    out["rlimit"] = rlimit_note
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
