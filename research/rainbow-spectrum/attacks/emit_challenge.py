#!/usr/bin/env python3
"""Write public challenges to disk, containing nothing but the public artifact.

This is what gets handed to an attacker who did not design the scheme. It writes
the flattened circuit, the challenge metadata and nothing else: no theta, no
factor boundaries, no intermediate states, no planted witness. The secret is
held back in a separate file the attacker never sees, used only to score
submissions.

attacks/public_boundary.py is the guarantee that this is meaningful -- it
verifies the artifact is exact on every enumerated input at toy widths, and
greps the serialised bytes for secret VALUES rather than field names.
"""

import json
import pathlib
import random
import sys
import time

HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parent))

from models import public_artifact as PA                         # noqa: E402
from experiment_b import plant, privileged_solve                 # noqa: E402

OUT = HERE.parents[1] / "challenges"
WIDTHS = (8, 10, 12, 14, 16, 18, 20)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "secret").mkdir(exist_ok=True)
    index = []
    for w in WIDTHS:
        t = w // 2
        for draw in range(3):
            rng = random.Random(555000 + 97 * draw + w)
            challenge = plant(w, 2, t, rng, False)
            artifact = PA.build(challenge["thetas"], challenge["S"],
                                challenge["T"], challenge["merge_a"], t, False)
            name = f"challenge-w{w:02d}-{draw}"
            (OUT / f"{name}.json").write_text(artifact.to_json())
            privileged = privileged_solve(challenge, t, False)
            # Kept OUT of the published directory; scoring only.
            (OUT / "secret" / f"{name}.secret.json").write_text(json.dumps({
                "privileged_evaluations": privileged.get("evaluations"),
                "privileged_solved": bool(privileged.get("solved")),
            }))
            index.append({"name": name, "w": w, "t": t, "draw": draw,
                          "bytes": (OUT / f"{name}.json").stat().st_size,
                          "gates": artifact.aig.stats()["ands"],
                          "target_evaluations_to_beat":
                              privileged.get("evaluations")})
            print(f"  {name}  w={w:>2} gates={artifact.aig.stats()['ands']:>7} "
                  f"bytes={index[-1]['bytes']:>8}  privileged "
                  f"{privileged.get('evaluations')} evals")
    (OUT / "index.json").write_text(json.dumps(
        {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "format": "rainbow-spectrum/public-artifact/1",
         "contains_no_secret": True, "challenges": index}, indent=2))
    print(f"\n-> {OUT}/index.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
