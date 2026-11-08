#!/usr/bin/env python3
"""Fail if anything calling itself public reads the secret.

This exists because the central result of Experiment B was wrong for months in a
way that no amount of statistical care could have caught: public_solve received
challenge["thetas"] and compiled the secret multipliers into its formula, so
every "public" cost it produced was a cost paid with the trapdoor in hand. The
docstring said the opposite. Nobody re-read the code because the docstring was
reassuring.

So the boundary is now enforced mechanically rather than by intention. Any
function whose name contains public, flat or attack is parsed, and if it touches
secret material it must carry an explicit QUARANTINED marker in its docstring
saying so. A function that reads theta while calling itself public, and does not
admit it, fails this audit.

The marker is deliberately ugly to type and impossible to add by accident.
"""

import ast
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
SECRET = {"thetas", "theta", "multipliers", "mixa_rotations", "pairs", "signs",
          "merge_a", "merge_b", "prefix_a", "prefix_b", "witness", "sigma"}
PUBLIC_HINT = ("public", "flat", "attack")
MARKER = "QUARANTINED: reads secret material by design."


def touched_secrets(node):
    found = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr in SECRET:
            found.add(sub.attr)
        elif isinstance(sub, ast.Name) and sub.id in SECRET:
            found.add(sub.id)
        elif isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                and sub.value in SECRET:
            found.add(sub.value)
    return found


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    violations, quarantined, clean = [], [], 0
    for path in sorted(list((ROOT / "attacks").glob("*.py"))
                       + list((ROOT / "models").glob("*.py"))):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if not any(hint in node.name.lower() for hint in PUBLIC_HINT):
                continue
            secrets = touched_secrets(node)
            if not secrets:
                clean += 1
                continue
            doc = ast.get_docstring(node) or ""
            entry = {"file": str(path.relative_to(ROOT)), "function": node.name,
                     "secrets": sorted(secrets), "line": node.lineno}
            (quarantined if MARKER in doc else violations).append(entry)

    report = {
        "audit": "leakage_audit",
        "rule": "a public/flat/attack-named function touching secret material "
                "must declare it with the quarantine marker",
        "clean_public_functions": clean,
        "quarantined": quarantined,
        "violations": violations,
        "passed": not violations,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    path = RESULTS / "leakage-audit.json"
    path.write_text(json.dumps(report, indent=2))

    for entry in quarantined:
        print(f"  quarantined  {entry['file']}:{entry['line']} "
              f"{entry['function']}  ({', '.join(entry['secrets'])})")
    for entry in violations:
        print(f"  VIOLATION    {entry['file']}:{entry['line']} "
              f"{entry['function']}  reads {', '.join(entry['secrets'])} "
              f"without declaring it")
    print(f"\n{clean} public-named functions touch no secret material; "
          f"{len(quarantined)} declared; {len(violations)} undeclared.")
    print("PASS" if not violations else "FAIL")
    return 0 if not violations else 1


if __name__ == "__main__":
    sys.exit(main())
