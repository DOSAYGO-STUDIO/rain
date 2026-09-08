#!/usr/bin/env python3
"""Inside-out rebound search for full-block Rainstorm fold-prefix collisions.

The forward side algebraically programs the first right round of a distinct
64-byte message.  The backward side starts from every pre-fold state matching
the reference fold prefix and exactly inverts the fixed 0x80 padding rounds.
Meeting all 16 state words yields a chosen second preimage for the selected
production output width when both round counts are four.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from rainstorm_model import (
    CTR_LEFT, CTR_RIGHT, K, MASK, Z, initial_state, invert_weakfunc,
    program_round_data, weakfunc, words,
)
from smt_digest import symbolic_weakfunc
from solver_backends import solve_bitwuzla


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LENGTH = 64
PAD_WORD = 0x8080808080808080


def symbolic_invert_weakfunc(output, data, left):
    """Exact Z3 inverse of one fixed-data production weak round."""
    import z3
    transformed = list(output[:8] if left else output[8:])
    counter = z3.BitVecVal(CTR_LEFT if left else CTR_RIGHT, 64)
    counters = []
    for value in transformed:
        counters.append(counter)
        counter = counter + value
    incoming_active = []
    for lane, value in enumerate(transformed):
        before = (z3.RotateLeft(value, Z[lane]) + K[lane]) ^ data[lane]
        if lane:
            before = before + counters[lane]
        incoming_active.append(before)
    if left:
        low = incoming_active
        high = [(output[8] + counter) ^ transformed[0]]
        high.extend(output[8 + lane] ^ transformed[lane]
                    for lane in range(1, 8))
    else:
        high = incoming_active
        low = [(output[0] + counter) ^ transformed[0]]
        low.extend(output[lane] ^ transformed[lane]
                   for lane in range(1, 8))
    return low + high


def symbolic_programmed_first_right(outputs):
    """Return first-round state and unique full message block for chosen y."""
    import z3
    incoming = initial_state(LENGTH)
    counter = z3.BitVecVal(CTR_RIGHT, 64)
    data = []
    for lane, output in enumerate(outputs):
        active = z3.BitVecVal(incoming[8 + lane], 64)
        if lane:
            active = active - counter
        data.append(active ^ (z3.RotateLeft(output, Z[lane]) + K[lane]))
        counter = counter + output
    low = [z3.BitVecVal(incoming[lane], 64) ^ outputs[lane]
           for lane in range(8)]
    low[0] = low[0] - counter
    return low + list(outputs), data


def reduced_pre_fold(message, message_rounds=4, padding_rounds=4):
    """Concrete state immediately before the fold for an exact 64-byte block."""
    if len(message) != LENGTH:
        raise ValueError("rebound messages must contain exactly 64 bytes")
    state = initial_state(LENGTH)
    data = words(message)
    for round_index in range(message_rounds):
        state = weakfunc(state, data, bool(round_index & 1))
    padding = [PAD_WORD] * 8
    for round_index in range(padding_rounds):
        state = weakfunc(state, padding, bool(round_index & 1))
    return state


def search(fold_words=2, message_rounds=4, padding_rounds=4,
           match_state_words=16, backend="sat", timeout=60,
           random_seed=0, reference=None, bitwuzla_bv_solver="bitblast"):
    import z3
    if fold_words not in (1, 2, 4, 8):
        raise ValueError("fold_words must be 1, 2, 4, or 8")
    if not 1 <= message_rounds <= 4 or not 0 <= padding_rounds <= 4:
        raise ValueError("message rounds must be 1..4 and padding rounds 0..4")
    if not 1 <= match_state_words <= 16:
        raise ValueError("match_state_words must be in 1..16")
    reference = bytes(LENGTH) if reference is None else bytes(reference)
    if len(reference) != LENGTH:
        raise ValueError("the reference must contain exactly 64 bytes")

    reference_pre_fold = reduced_pre_fold(
        reference, message_rounds, padding_rounds)
    reference_fold = [
        (reference_pre_fold[lane] - reference_pre_fold[8 + lane]) & MASK
        for lane in range(8)
    ]

    outputs = [z3.BitVec(f"forward_y_{lane}", 64) for lane in range(8)]
    forward, data = symbolic_programmed_first_right(outputs)
    for round_index in range(1, message_rounds):
        forward = symbolic_weakfunc(forward, data, bool(round_index & 1))

    backward_high = [z3.BitVec(f"fold_high_{lane}", 64)
                     for lane in range(8)]
    backward_low = []
    for lane in range(8):
        if lane < fold_words:
            backward_low.append(
                backward_high[lane] + z3.BitVecVal(reference_fold[lane], 64))
        else:
            backward_low.append(z3.BitVec(f"fold_low_{lane}", 64))
    backward = backward_low + backward_high
    padding = [z3.BitVecVal(PAD_WORD, 64)] * 8
    for round_index in reversed(range(padding_rounds)):
        backward = symbolic_invert_weakfunc(
            backward, padding, bool(round_index & 1))

    reference_data = words(reference)
    constraints = [forward[index] == backward[index]
                   for index in range(match_state_words)]
    constraints.append(z3.Or(*[
        data[lane] != z3.BitVecVal(reference_data[lane], 64)
        for lane in range(8)
    ]))

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
            constraints, outputs, timeout * 1000, random_seed,
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

    production_equivalent = (
        message_rounds == 4 and padding_rounds == 4 and match_state_words == 16)
    result = {
        "experiment": "full-block-inside-out-rainstorm-rebound",
        "production_version": "4.0.0",
        "production_equivalent": production_equivalent,
        "search_kind": "chosen-second-preimage",
        "message_length": LENGTH,
        "target_digest_bits": 64 * fold_words,
        "target_fold_words": list(range(fold_words)),
        "message_rounds": message_rounds,
        "padding_rounds": padding_rounds,
        "matched_middle_state_words": match_state_words,
        "reference_message_hex": reference.hex(),
        "reference_fold": [f"0x{value:016x}" for value in reference_fold],
        "forward_parameterization": "eight outputs of first message right round",
        "backward_parameterization": "pre-fold state manifold with fixed fold prefix",
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
            "Exact 64-bit round algebra. SAT with all 16 middle words matched "
            "is a fold-prefix second preimage for the declared round counts. "
            "Only the 4+4-round configuration is production-equivalent."
        ),
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                ROOT / "src/rainstorm.cpp", HERE / "rainstorm_model.py",
                HERE / "smt_digest.py", HERE / "solver_backends.py", Path(__file__),
            )
        },
    }

    if status_text == "sat":
        if external_model is not None:
            chosen_outputs = [external_model[value.decl().name()]
                              for value in outputs]
        else:
            model = solver.model()
            chosen_outputs = [model.eval(value, model_completion=True).as_long()
                              for value in outputs]
        candidate_words = program_round_data(
            initial_state(LENGTH), chosen_outputs, left=False)
        candidate = b"".join(value.to_bytes(8, "little")
                             for value in candidate_words)
        result["candidate_message_hex"] = candidate.hex()
        result["messages_distinct"] = candidate != reference
        if match_state_words == 16:
            candidate_pre_fold = reduced_pre_fold(
                candidate, message_rounds, padding_rounds)
            candidate_fold = [
                (candidate_pre_fold[lane] - candidate_pre_fold[8 + lane]) & MASK
                for lane in range(8)
            ]
            assert candidate != reference
            assert candidate_fold[:fold_words] == reference_fold[:fold_words]
            result["candidate_fold"] = [f"0x{value:016x}"
                                        for value in candidate_fold]
            result["integer_model_fold_prefix_verified"] = True
            if production_equivalent:
                from scan_production import ProductionNative
                native = ProductionNative()
                bits = fold_words * 64
                digest_a = native.hashes(1, bits, 0, reference, LENGTH, 1)
                digest_b = native.hashes(1, bits, 0, candidate, LENGTH, 1)
                assert digest_a == digest_b
                result["native_cpp_full_digest_collision_verified"] = True
                result["digest_hex"] = digest_a.hex()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fold-words", type=int, choices=(1, 2, 4, 8), default=2)
    parser.add_argument("--message-rounds", type=int, choices=(1, 2, 3, 4), default=4)
    parser.add_argument("--padding-rounds", type=int, choices=(0, 1, 2, 3, 4), default=4)
    parser.add_argument("--match-state-words", type=int, default=16)
    parser.add_argument(
        "--backend", choices=("smt", "sat", "sls", "bitwuzla"), default="sat")
    parser.add_argument(
        "--bitwuzla-bv-solver", choices=("bitblast", "prop", "preprop"),
        default="bitblast")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--random-seed", type=int, default=0)
    parser.add_argument("--reference-message-hex", default="00" * LENGTH)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        reference = bytes.fromhex(args.reference_message_hex)
        result = search(
            args.fold_words, args.message_rounds, args.padding_rounds,
            args.match_state_words, args.backend, args.timeout,
            args.random_seed, reference, args.bitwuzla_bv_solver)
    except ValueError as exc:
        parser.error(str(exc))
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
