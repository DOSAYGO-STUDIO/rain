#!/usr/bin/env python3
"""Two-free-message programmed-round collision search for Rainstorm.

Both 64-byte messages share a fixed prefix of first-right-round transformed
words and independently choose the remaining suffix.  Their message blocks are
recovered exactly, the remaining message and fixed-padding rounds are modeled,
and selected fold words are equated.  In the production 4+4-round case this is
a complete collision for the corresponding output width.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from rainstorm_model import (
    MASK, initial_state, program_round_data, weakfunc, words,
)
from scan_production import ProductionNative
from smt_digest import symbolic_weakfunc
from smt_rebound import LENGTH, PAD_WORD, reduced_pre_fold, symbolic_programmed_first_right
from solver_backends import solve_bitwuzla


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def symbolic_path(prefix, fixed_outputs, free_outputs, message_rounds,
                  padding_rounds):
    import z3
    chosen = list(fixed_outputs)
    chosen.extend(z3.BitVec(f"{prefix}_y_{lane}", 64)
                  for lane in range(len(fixed_outputs), 8))
    if len(chosen) != 8 or free_outputs != 8 - len(fixed_outputs):
        raise AssertionError("invalid programmed output split")
    state, data = symbolic_programmed_first_right(chosen)
    for round_index in range(1, message_rounds):
        state = symbolic_weakfunc(state, data, bool(round_index & 1))
    padding = [z3.BitVecVal(PAD_WORD, 64)] * 8
    for round_index in range(padding_rounds):
        state = symbolic_weakfunc(state, padding, bool(round_index & 1))
    folded = [state[lane] - state[8 + lane] for lane in range(8)]
    return chosen, data, folded


def search(fold_words=2, free_tail_outputs=3, message_rounds=4,
           padding_rounds=4, backend="sat", timeout=60, random_seed=0,
           bitwuzla_bv_solver="bitblast", fixed_prefix_mode="reference"):
    import z3
    if fold_words not in (1, 2, 4, 8):
        raise ValueError("fold_words must be 1, 2, 4, or 8")
    if not 1 <= free_tail_outputs <= 8:
        raise ValueError("free_tail_outputs must be in 1..8")
    if not 1 <= message_rounds <= 4 or not 0 <= padding_rounds <= 4:
        raise ValueError("round counts out of range")

    reference = bytes(LENGTH)
    reference_data = words(reference)
    first_reference = weakfunc(
        initial_state(LENGTH), reference_data, left=False)
    reference_outputs = first_reference[8:]
    fixed_count = 8 - free_tail_outputs
    if fixed_prefix_mode == "reference":
        fixed_values = reference_outputs[:fixed_count]
    elif fixed_prefix_mode == "zero":
        fixed_values = [0] * fixed_count
    else:
        raise ValueError("fixed_prefix_mode must be reference or zero")
    fixed_outputs = [z3.BitVecVal(value, 64) for value in fixed_values]
    outputs_a, data_a, fold_a = symbolic_path(
        "a", fixed_outputs, free_tail_outputs, message_rounds, padding_rounds)
    outputs_b, data_b, fold_b = symbolic_path(
        "b", fixed_outputs, free_tail_outputs, message_rounds, padding_rounds)
    free_a = outputs_a[fixed_count:]
    free_b = outputs_b[fixed_count:]
    packed_a = free_a[0] if len(free_a) == 1 else z3.Concat(*free_a)
    packed_b = free_b[0] if len(free_b) == 1 else z3.Concat(*free_b)
    constraints = [z3.ULT(packed_a, packed_b)]
    constraints.extend(fold_a[lane] == fold_b[lane]
                       for lane in range(fold_words))

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

    model_variables = free_a + free_b
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
        "experiment": "two-free-full-block-programmed-rainstorm-collision",
        "production_version": "4.0.0",
        "production_equivalent": production_equivalent,
        "message_length": LENGTH,
        "target_digest_bits": fold_words * 64,
        "target_fold_words": list(range(fold_words)),
        "fixed_prefix_first_round_outputs": fixed_count,
        "fixed_prefix_mode": fixed_prefix_mode,
        "fixed_prefix_values": [f"0x{value:016x}" for value in fixed_values],
        "free_tail_first_round_outputs_per_message": free_tail_outputs,
        "symbolic_bits_per_message": free_tail_outputs * 64,
        "message_rounds": message_rounds,
        "padding_rounds": padding_rounds,
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
            "Exact two-free-message 64-bit algebra. Production 4+4-round SAT "
            "is a full native-verifiable collision for the selected width."
        ),
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                ROOT / "src/rainstorm.cpp", HERE / "rainstorm_model.py",
                HERE / "smt_digest.py", HERE / "smt_rebound.py",
                HERE / "solver_backends.py", Path(__file__),
            )
        },
    }
    if status_text == "sat":
        if external_model is not None:
            values = {
                value.decl().name(): external_model[value.decl().name()]
                for value in model_variables
            }
            concrete_a = fixed_values + [
                values[value.decl().name()] for value in free_a]
            concrete_b = fixed_values + [
                values[value.decl().name()] for value in free_b]
        else:
            model = solver.model()
            concrete_a = [model.eval(value, model_completion=True).as_long()
                          for value in outputs_a]
            concrete_b = [model.eval(value, model_completion=True).as_long()
                          for value in outputs_b]
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
            native = ProductionNative()
            bits = fold_words * 64
            digest_a = native.hashes(1, bits, 0, message_a, LENGTH, 1)
            digest_b = native.hashes(1, bits, 0, message_b, LENGTH, 1)
            assert digest_a == digest_b
            result["witness"]["digest_hex"] = digest_a.hex()
            result["witness"]["native_cpp_full_digest_collision_verified"] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fold-words", type=int, choices=(1, 2, 4, 8), default=2)
    parser.add_argument("--free-tail-outputs", type=int, choices=range(1, 9), default=3)
    parser.add_argument(
        "--fixed-prefix-mode", choices=("reference", "zero"), default="reference")
    parser.add_argument("--message-rounds", type=int, choices=(1, 2, 3, 4), default=4)
    parser.add_argument("--padding-rounds", type=int, choices=(0, 1, 2, 3, 4), default=4)
    parser.add_argument(
        "--backend", choices=("smt", "sat", "sls", "bitwuzla"), default="sat")
    parser.add_argument(
        "--bitwuzla-bv-solver", choices=("bitblast", "prop", "preprop"),
        default="bitblast")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--random-seed", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = search(
        args.fold_words, args.free_tail_outputs, args.message_rounds,
        args.padding_rounds, args.backend, args.timeout, args.random_seed,
        args.bitwuzla_bv_solver, args.fixed_prefix_mode)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
