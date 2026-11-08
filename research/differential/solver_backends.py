"""Small external-solver adapters used by exact differential experiments."""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


MODEL_VALUE = re.compile(
    r"\(define-fun\s+([^\s()]+)\s+\(\)\s+\(_ BitVec \d+\)\s+"
    r"(#b[01]+|#x[0-9a-fA-F]+|\(_ bv\d+ \d+\))\s*\)")


def _parse_value(rendered):
    if rendered.startswith("#b"):
        return int(rendered[2:], 2)
    if rendered.startswith("#x"):
        return int(rendered[2:], 16)
    return int(rendered.split()[1][2:])


def solve_bitwuzla(assertions, variables, timeout_ms, random_seed=0,
                   sat_solver="cadical", threads=1, bv_solver="bitblast"):
    """Solve Z3-built QF_BV assertions through Bitwuzla's standalone CLI."""
    import z3
    executable = shutil.which("bitwuzla")
    if executable is None:
        raise RuntimeError("Bitwuzla is not installed")
    serializer = z3.Solver()
    # Z3 serializes fixed rotations as its nonstandard ext_rotate_* functions.
    # Simplification expands them to standard extract/concat terms accepted by
    # standalone SMT-LIB solvers.
    serializer.add(*[z3.simplify(assertion) for assertion in assertions])
    with tempfile.TemporaryDirectory(prefix="rain-bitwuzla-") as directory:
        source = Path(directory) / "query.smt2"
        source.write_text(serializer.to_smt2())
        completed = subprocess.run([
            executable,
            "--produce-models",
            "--print-model",
            "--check-model",
            "--sat-solver", sat_solver,
            "--nthreads", str(threads),
            "--bv-solver", bv_solver,
            "--time-limit", str(timeout_ms),
            "--seed", str(random_seed),
            str(source),
        ], capture_output=True, text=True, check=False)
    if completed.returncode not in (0, 20):
        raise RuntimeError(
            f"Bitwuzla failed ({completed.returncode}): {completed.stderr.strip()}")
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    status = lines[0] if lines else "unknown"
    parsed = {name: _parse_value(value) for name, value in MODEL_VALUE.findall(
        completed.stdout)}
    model = {variable.decl().name(): parsed[variable.decl().name()]
             for variable in variables if variable.decl().name() in parsed}
    return status, model, completed.stderr.strip()
