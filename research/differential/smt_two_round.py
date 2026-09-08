#!/usr/bin/env python3
"""Exact two-round Rainstorm-64 message-modification second-preimage attack.

The first five right-round transformed words are fixed to a reference path.
Two late words are free and the eighth is derived to preserve their total sum,
which keeps the right-round wrap and early left-round path fixed.  The last
left-round transformed word is derived to preserve the fold.  Z3 solves only
the remaining late-lane data-consistency equation and real padding byte.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from rainstorm_model import (
    CTR_LEFT, K, MASK, Z, hash_message, initial_state, program_round_data,
    weakfunc, words,
)
from smt_programmed import FILL, LENGTH, symbolic_first_right
from solver_backends import solve_bitwuzla


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def search(timeout=60, backend="sat", reference=None, consistency_bits=64,
           threads=1, random_seed=0, bitwuzla_sat_solver="cadical",
           bitwuzla_bv_solver="bitblast", message_length=LENGTH):
    import z3
    if message_length not in (63, 64):
        raise ValueError("message_length must be 63 or 64")
    reference = bytes(message_length) if reference is None else bytes(reference)
    if len(reference) != message_length:
        raise ValueError("the reference length must equal message_length")
    if not 1 <= consistency_bits <= 64:
        raise ValueError("consistency_bits must be in 1..64")
    block = reference + bytes([FILL]) if message_length == 63 else reference
    reference_data = words(block)
    initial = initial_state(message_length)
    after_right = weakfunc(initial, reference_data, left=False)
    after_left = weakfunc(after_right, reference_data, left=True)
    reference_y = after_right[8:]
    reference_x = after_left[:8]
    target = (after_left[0] - after_left[8]) & MASK

    y5 = z3.BitVec("y_5", 64)
    y6 = z3.BitVec("y_6", 64)
    late_y_sum = z3.BitVecVal(sum(reference_y[5:]) & MASK, 64)
    y7 = late_y_sum - y5 - y6
    outputs = [z3.BitVecVal(value, 64) for value in reference_y[:5]]
    outputs.extend((y5, y6, y7))
    state, data = symbolic_first_right(outputs, message_length)

    # Preserving y[0..4] and sum(y) fixes x[0..4] exactly.  Continue only the
    # two variable late lanes, then derive x7 from preservation of sum(x).
    x = [z3.BitVecVal(value, 64) for value in reference_x[:5]]
    counter = z3.BitVecVal(
        (CTR_LEFT + sum(reference_x[:5])) & MASK, 64)
    for lane in (5, 6):
        incoming = state[lane] - counter
        value = z3.RotateRight((incoming ^ data[lane]) - K[lane], Z[lane])
        x.append(value)
        counter = counter + value
    reference_late_x_sum = z3.BitVecVal(sum(reference_x[5:]) & MASK, 64)
    x7 = reference_late_x_sum - x[5] - x[6]
    incoming7 = state[7] - counter
    required_data7 = incoming7 ^ (z3.RotateLeft(x7, Z[7]) + K[7])

    constraints = []
    if consistency_bits == 64:
        constraints.append(data[7] == required_data7)
    else:
        constraints.append(
            z3.Extract(consistency_bits - 1, 0, data[7]) ==
            z3.Extract(consistency_bits - 1, 0, required_data7))
    if message_length == 63:
        constraints.append(z3.Extract(63, 56, data[7]) == FILL)
    constraints.append(z3.Or(y5 != reference_y[5], y6 != reference_y[6]))

    solver = None
    if backend == "sat":
        solver = z3.Then("simplify", "bit-blast", "sat").solver()
    elif backend == "sls":
        solver = z3.Tactic("qfbv-sls").solver()
    elif backend == "smt":
        solver = z3.Solver()
    if solver is not None:
        solver.set(timeout=timeout * 1000)
        solver.set(threads=threads)
        solver.set(random_seed=random_seed)
        solver.add(*constraints)

    started = time.monotonic()
    external_model = None
    if backend == "bitwuzla":
        status_text, external_model, external_detail = solve_bitwuzla(
            constraints, (y5, y6), timeout * 1000, random_seed,
            bitwuzla_sat_solver, threads, bitwuzla_bv_solver)
        status = status_text
        unknown_reason = external_detail or ("timeout" if status == "unknown" else None)
        solver_name = "Bitwuzla 0.9.1"
        solver_statistics = {}
    else:
        status = solver.check()
        status_text = str(status)
        unknown_reason = solver.reason_unknown() if status == z3.unknown else None
        solver_name = f"Z3 {z3.get_version_string()}"
        solver_statistics = {key: value for key, value in solver.statistics()}
    elapsed = time.monotonic() - started
    result = {
        "experiment": "two-round-rainstorm64-message-modification",
        "production_version": "4.0.0",
        "production_equivalent": False,
        "message_length": message_length,
        "digest_bits": 64,
        "weak_rounds": 2,
        "fixed_first_right_outputs": [0, 1, 2, 3, 4],
        "free_first_right_outputs": [5, 6],
        "derived_first_right_output": 7,
        "preserved_conditions": [
            "sum(y[5..7])", "x[0..4]", "sum(x[5..7])", "fold word 0",
        ],
        "remaining_constraints": (
            ["left lane-7 data consistency", "data[7] top padding byte is 0xbf"]
            if message_length == 63 else ["left lane-7 data consistency"]),
        "lane7_consistency_bits": consistency_bits,
        "reference_message_hex": reference.hex(),
        "target_digest_hex": target.to_bytes(8, "little").hex(),
        "solver": solver_name,
        "backend": backend,
        "status": status_text,
        "unknown_reason": unknown_reason,
        "elapsed_seconds": elapsed,
        "timeout_seconds": timeout,
        "threads": threads,
        "random_seed": random_seed,
        "bitwuzla_sat_solver": (
            bitwuzla_sat_solver if backend == "bitwuzla" else None),
        "bitwuzla_bv_solver": (
            bitwuzla_bv_solver if backend == "bitwuzla" else None),
        "scope": (
            "Exact reduced two-round message modification. SAT is a verified "
            "reduced-round second preimage, not a production collision."
        ),
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                ROOT / "src/rainstorm.cpp", HERE / "rainstorm_model.py",
                HERE / "smt_programmed.py", Path(__file__),
            )
        },
        "solver_statistics": solver_statistics,
    }
    if status_text == "sat":
        if external_model is not None:
            y5_value = external_model["y_5"]
            y6_value = external_model["y_6"]
            chosen_y = reference_y[:5] + [
                y5_value, y6_value,
                (sum(reference_y[5:]) - y5_value - y6_value) & MASK,
            ]
        else:
            model = solver.model()
            chosen_y = [model.eval(value, model_completion=True).as_long()
                        for value in outputs]
        programmed = program_round_data(initial, chosen_y, left=False)
        candidate_block = b"".join(
            value.to_bytes(8, "little") for value in programmed)
        if message_length == 63:
            assert candidate_block[-1] == FILL
            candidate = candidate_block[:-1]
        else:
            candidate = candidate_block
        if message_length == 63:
            candidate_digest = hash_message(candidate, 64, 0, "none", 2).digest
            reference_digest = hash_message(reference, 64, 0, "none", 2).digest
        else:
            candidate_state = initial_state(message_length)
            reference_state = initial_state(message_length)
            for round_index in range(2):
                candidate_state = weakfunc(
                    candidate_state, programmed, bool(round_index & 1))
                reference_state = weakfunc(
                    reference_state, reference_data, bool(round_index & 1))
            candidate_digest = ((candidate_state[0] - candidate_state[8]) & MASK).to_bytes(8, "little")
            reference_digest = ((reference_state[0] - reference_state[8]) & MASK).to_bytes(8, "little")
        assert candidate != reference
        if consistency_bits == 64:
            assert candidate_digest == reference_digest
        candidate_right = weakfunc(initial, programmed, left=False)
        candidate_left = weakfunc(candidate_right, programmed, left=True)
        result["witness"] = {
            "candidate_message_hex": candidate.hex(),
            "reference_message_hex": reference.hex(),
            "digest_hex": candidate_digest.hex(),
            "reference_digest_hex": reference_digest.hex(),
            "complete_two_round_second_preimage": consistency_bits == 64,
            "first_round_outputs": [f"0x{value:016x}" for value in chosen_y],
            "second_round_outputs": [f"0x{value:016x}"
                                     for value in candidate_left[:8]],
            "verification": "independent-integer-reduced-round-model",
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend", choices=("smt", "sat", "sls", "bitwuzla"), default="sat")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--message-length", type=int, choices=(63, 64), default=63)
    parser.add_argument("--consistency-bits", type=int, default=64)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--random-seed", type=int, default=0)
    parser.add_argument(
        "--bitwuzla-sat-solver",
        choices=("cadical", "cms", "gimsatul", "kissat"), default="cadical")
    parser.add_argument(
        "--bitwuzla-bv-solver",
        choices=("bitblast", "prop", "preprop"), default="bitblast")
    parser.add_argument("--reference-message-hex")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        reference = (bytes(args.message_length) if args.reference_message_hex is None
                     else bytes.fromhex(args.reference_message_hex))
        result = search(
            args.timeout, args.backend, reference,
            args.consistency_bits, args.threads, args.random_seed,
            args.bitwuzla_sat_solver, args.bitwuzla_bv_solver,
            args.message_length)
    except ValueError as exc:
        parser.error(str(exc))
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
