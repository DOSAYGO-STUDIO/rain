#!/usr/bin/env python3
"""Flat algebraic collision model for full-block Rainstorm v4.

Instead of nesting eight weak rounds, introduce every round's eight
transformed active words explicitly.  Each round becomes a shallow state
update plus eight exact data-consistency equations.  The first message round
programs the 64-byte block; the other message rounds require that same block,
and all tail rounds require the fixed 0x80 block.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from rainstorm_model import (
    CTR_LEFT, CTR_RIGHT, K, MASK, Z, initial_state, program_round_data,
)
from scan_production import ProductionNative
from smt_rebound import LENGTH, PAD_WORD, reduced_pre_fold
from solver_backends import solve_bitwuzla


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def symbolic_round_from_outputs(state, data, left, outputs):
    """Apply a round from chosen transformed words and return consistency."""
    import z3
    if len(state) != 16 or len(data) != 8 or len(outputs) != 8:
        raise ValueError("a flat Rainstorm round needs 16 state and 8 data words")
    h = list(state)
    counter = z3.BitVecVal(CTR_LEFT if left else CTR_RIGHT, 64)
    constraints = []
    for lane, transformed in enumerate(outputs):
        active = lane if left else 8 + lane
        blit = 8 + lane if left else lane
        target = lane + 1 if left else (8 + lane + 1 if lane < 7 else 0)
        required_data = h[active] ^ (
            z3.RotateLeft(transformed, Z[lane]) + z3.BitVecVal(K[lane], 64))
        constraints.append(data[lane] == required_data)
        h[active] = transformed
        h[blit] = h[blit] ^ transformed
        counter = counter + transformed
        h[target] = h[target] - counter
    return h, constraints


def symbolic_path(prefix, message_rounds, padding_rounds):
    """Build one algebraically flattened, exactly reachable hash path."""
    import z3
    initial = [z3.BitVecVal(value, 64) for value in initial_state(LENGTH)]
    first = [z3.BitVec(f"{prefix}_message_r0_t{i}", 64) for i in range(8)]

    # The first right round is freely programmable from the length-keyed IV.
    counter = z3.BitVecVal(CTR_RIGHT, 64)
    data = []
    state = list(initial)
    for lane, transformed in enumerate(first):
        required = state[8 + lane] ^ (
            z3.RotateLeft(transformed, Z[lane]) + z3.BitVecVal(K[lane], 64))
        data.append(required)
        state[8 + lane] = transformed
        state[lane] = state[lane] ^ transformed
        counter = counter + transformed
        target = 8 + lane + 1 if lane < 7 else 0
        state[target] = state[target] - counter

    variables = list(first)
    constraints = []
    for round_index in range(1, message_rounds):
        outputs = [z3.BitVec(
            f"{prefix}_message_r{round_index}_t{lane}", 64)
                   for lane in range(8)]
        state, round_constraints = symbolic_round_from_outputs(
            state, data, bool(round_index & 1), outputs)
        variables.extend(outputs)
        constraints.extend(round_constraints)

    padding = [z3.BitVecVal(PAD_WORD, 64)] * 8
    for round_index in range(padding_rounds):
        outputs = [z3.BitVec(
            f"{prefix}_padding_r{round_index}_t{lane}", 64)
                   for lane in range(8)]
        state, round_constraints = symbolic_round_from_outputs(
            state, padding, bool(round_index & 1), outputs)
        variables.extend(outputs)
        constraints.extend(round_constraints)

    fold = [state[lane] - state[8 + lane] for lane in range(8)]
    return first, data, state, fold, variables, constraints


def search(fold_words=2, message_rounds=4, padding_rounds=4,
           backend="sls", timeout=300, random_seed=0,
           bitwuzla_bv_solver="prop"):
    import z3
    if fold_words not in (1, 2, 4, 8):
        raise ValueError("fold_words must be 1, 2, 4, or 8")
    if not 1 <= message_rounds <= 4 or not 0 <= padding_rounds <= 4:
        raise ValueError("round counts out of range")

    first_a, _, _, fold_a, variables_a, constraints_a = symbolic_path(
        "a", message_rounds, padding_rounds)
    first_b, _, _, fold_b, variables_b, constraints_b = symbolic_path(
        "b", message_rounds, padding_rounds)
    constraints = constraints_a + constraints_b
    constraints.append(z3.ULT(z3.Concat(*first_a), z3.Concat(*first_b)))
    constraints.extend(fold_a[lane] == fold_b[lane]
                       for lane in range(fold_words))
    model_variables = variables_a + variables_b

    solver = None
    if backend == "sat":
        solver = z3.Then("simplify", "bit-blast", "sat").solver()
    elif backend == "sls":
        solver = z3.Tactic("qfbv-sls").solver()
    elif backend == "smt":
        solver = z3.Solver()
    if solver is not None:
        solver.set(timeout=timeout * 1000)
        solver.set(random_seed=random_seed)
        solver.add(*constraints)

    started = time.monotonic()
    external_model = None
    if backend == "bitwuzla":
        status_text, external_model, external_detail = solve_bitwuzla(
            constraints, model_variables, timeout * 1000, random_seed,
            bv_solver=bitwuzla_bv_solver)
        unknown_reason = external_detail or (
            "timeout" if status_text == "unknown" else None)
        solver_name = "Bitwuzla 0.9.1"
        solver_statistics = {}
    else:
        status = solver.check()
        status_text = str(status)
        unknown_reason = solver.reason_unknown() if status == z3.unknown else None
        solver_name = f"Z3 {z3.get_version_string()}"
        solver_statistics = {key: value for key, value in solver.statistics()}
    elapsed = time.monotonic() - started

    production_equivalent = message_rounds == 4 and padding_rounds == 4
    result = {
        "experiment": "flat-algebraic-full-block-rainstorm-collision",
        "production_version": "4.0.0",
        "production_equivalent": production_equivalent,
        "message_length": LENGTH,
        "target_digest_bits": fold_words * 64,
        "target_fold_words": list(range(fold_words)),
        "message_rounds": message_rounds,
        "padding_rounds": padding_rounds,
        "symbolic_transformed_words_per_path": len(variables_a),
        "data_consistency_equations_per_path": len(constraints_a),
        "algebraic_form": "explicit transformed words; shallow per-lane data consistency",
        "solver": solver_name,
        "backend": backend,
        "bitwuzla_bv_solver": (
            bitwuzla_bv_solver if backend == "bitwuzla" else None),
        "status": status_text,
        "unknown_reason": unknown_reason,
        "elapsed_seconds": elapsed,
        "timeout_seconds": timeout,
        "random_seed": random_seed,
        "solver_statistics": solver_statistics,
        "scope": (
            "Exact 64-bit production equations. SAT in a 4+4 instance is a "
            "native-verifiable collision; unknown is inconclusive."
        ),
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                ROOT / "src/rainstorm.cpp", HERE / "rainstorm_model.py",
                HERE / "smt_rebound.py", HERE / "solver_backends.py",
                Path(__file__),
            )
        },
    }

    if status_text == "sat":
        if external_model is not None:
            concrete_a = [external_model[value.decl().name()]
                          for value in first_a]
            concrete_b = [external_model[value.decl().name()]
                          for value in first_b]
        else:
            model = solver.model()
            concrete_a = [model.eval(value, model_completion=True).as_long()
                          for value in first_a]
            concrete_b = [model.eval(value, model_completion=True).as_long()
                          for value in first_b]
        words_a = program_round_data(initial_state(LENGTH), concrete_a, False)
        words_b = program_round_data(initial_state(LENGTH), concrete_b, False)
        message_a = b"".join(value.to_bytes(8, "little") for value in words_a)
        message_b = b"".join(value.to_bytes(8, "little") for value in words_b)
        state_a = reduced_pre_fold(message_a, message_rounds, padding_rounds)
        state_b = reduced_pre_fold(message_b, message_rounds, padding_rounds)
        concrete_fold_a = [(state_a[i] - state_a[8 + i]) & MASK for i in range(8)]
        concrete_fold_b = [(state_b[i] - state_b[8 + i]) & MASK for i in range(8)]
        assert message_a != message_b
        assert concrete_fold_a[:fold_words] == concrete_fold_b[:fold_words]
        result["witness"] = {
            "message_a_hex": message_a.hex(),
            "message_b_hex": message_b.hex(),
            "fold_a": [f"0x{value:016x}" for value in concrete_fold_a],
            "fold_b": [f"0x{value:016x}" for value in concrete_fold_b],
            "integer_model_fold_prefix_verified": True,
        }
        if production_equivalent:
            bits = fold_words * 64
            native = ProductionNative()
            digest_a = native.hashes(1, bits, 0, message_a, LENGTH, 1)
            digest_b = native.hashes(1, bits, 0, message_b, LENGTH, 1)
            assert digest_a == digest_b
            result["witness"]["digest_hex"] = digest_a.hex()
            result["witness"]["native_cpp_full_digest_collision_verified"] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fold-words", type=int, choices=(1, 2, 4, 8), default=2)
    parser.add_argument("--message-rounds", type=int, choices=(1, 2, 3, 4), default=4)
    parser.add_argument("--padding-rounds", type=int, choices=(0, 1, 2, 3, 4), default=4)
    parser.add_argument(
        "--backend", choices=("smt", "sat", "sls", "bitwuzla"), default="sls")
    parser.add_argument(
        "--bitwuzla-bv-solver", choices=("bitblast", "prop", "preprop"),
        default="prop")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--random-seed", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = search(
        args.fold_words, args.message_rounds, args.padding_rounds,
        args.backend, args.timeout, args.random_seed, args.bitwuzla_bv_solver)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
