#!/usr/bin/env python3
"""Algebraic Rainstorm-64 second-preimage search in first-round coordinates.

For a 63-byte message, choose the eight transformed outputs of the first right
round.  The first-round equations then recover all data words exactly.  Only
the final byte of data word seven is constrained to the prescribed 0xbf pad.
The remaining rounds and fold are solved as exact 64-bit bit-vectors.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from rainstorm_model import (
    CTR_RIGHT, K, MASK, Z, hash_message, initial_state, program_round_data,
    weakfunc,
)
from smt_digest import symbolic_weakfunc


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LENGTH = 63
FILL = (0x80 + LENGTH) & 0xFF


def symbolic_first_right(outputs, message_length=LENGTH):
    """Return exact first-round state and the uniquely programmed data."""
    import z3
    incoming = initial_state(message_length)
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


def search(rounds=4, backend="sat", timeout=60, reference=None,
           free_tail_outputs=8):
    import z3
    if not 1 <= rounds <= 4:
        raise ValueError("rounds must be in 1..4")
    reference = bytes(LENGTH) if reference is None else bytes(reference)
    if len(reference) != LENGTH:
        raise ValueError("the reference must contain exactly 63 bytes")
    if not 1 <= free_tail_outputs <= 8:
        raise ValueError("free_tail_outputs must be in 1..8")

    target = int.from_bytes(
        hash_message(reference, 64, 0, "none", rounds).digest, "little")
    outputs = [z3.BitVec(f"y_{lane}", 64) for lane in range(8)]
    reference_block = reference + bytes([FILL])
    reference_words = [int.from_bytes(reference_block[i:i + 8], "little")
                       for i in range(0, 64, 8)]
    reference_first = weakfunc(
        initial_state(LENGTH), reference_words, left=False)
    reference_outputs = reference_first[8:]
    state, data = symbolic_first_right(outputs)
    for round_index in range(1, rounds):
        state = symbolic_weakfunc(state, data, bool(round_index & 1))
    folded = state[0] - state[8]

    if backend == "sat":
        solver = z3.Then("simplify", "bit-blast", "sat").solver()
    elif backend == "sls":
        solver = z3.Tactic("qfbv-sls").solver()
    else:
        solver = z3.Solver()
    solver.set(timeout=timeout * 1000)
    fixed_outputs = 8 - free_tail_outputs
    for lane in range(fixed_outputs):
        solver.add(outputs[lane] == z3.BitVecVal(reference_outputs[lane], 64))
    solver.add(z3.Extract(63, 56, data[7]) == FILL)
    solver.add(z3.Or(*[
        word != z3.BitVecVal(reference_words[lane], 64)
        for lane, word in enumerate(data)
    ]))
    solver.add(folded == z3.BitVecVal(target, 64))

    started = time.monotonic()
    status = solver.check()
    elapsed = time.monotonic() - started
    result = {
        "experiment": "programmed-first-round-rainstorm64-second-preimage",
        "production_version": "4.0.0",
        "production_equivalent": rounds == 4,
        "message_length": LENGTH,
        "digest_bits": 64,
        "weak_rounds": rounds,
        "parameterization": "eight transformed outputs of first right round",
        "free_tail_first_round_outputs": free_tail_outputs,
        "fixed_prefix_first_round_outputs": fixed_outputs,
        "padding_constraint": f"top byte of data[7] equals 0x{FILL:02x}",
        "reference_message_hex": reference.hex(),
        "target_digest_hex": target.to_bytes(8, "little").hex(),
        "solver": f"Z3 {z3.get_version_string()}",
        "backend": backend,
        "status": str(status),
        "unknown_reason": solver.reason_unknown() if status == z3.unknown else None,
        "elapsed_seconds": elapsed,
        "timeout_seconds": timeout,
        "scope": (
            "Exact first-round algebra and exact 64-bit remaining-round circuit. "
            "SAT is a second preimage; unknown is inconclusive. Reduced-round "
            "results are not production collisions."
        ),
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                ROOT / "src/rainstorm.cpp", HERE / "rainstorm_model.py",
                HERE / "smt_digest.py", Path(__file__),
            )
        },
    }
    if status == z3.sat:
        model = solver.model()
        chosen_outputs = [model.eval(value, model_completion=True).as_long()
                          for value in outputs]
        programmed = program_round_data(
            initial_state(LENGTH), chosen_outputs, left=False)
        block = b"".join(value.to_bytes(8, "little") for value in programmed)
        assert block[-1] == FILL
        candidate = block[:-1]
        candidate_digest = hash_message(
            candidate, 64, 0, "none", rounds).digest
        reference_digest = hash_message(
            reference, 64, 0, "none", rounds).digest
        assert candidate != reference and candidate_digest == reference_digest
        verification = "independent-integer-reduced-round-model"
        if rounds == 4:
            from scan_production import ProductionNative
            native = ProductionNative()
            native_candidate = native.hashes(1, 64, 0, candidate, LENGTH, 1)
            native_reference = native.hashes(1, 64, 0, reference, LENGTH, 1)
            assert native_candidate == native_reference == candidate_digest
            verification = "native-production-cpp"
        result["witness"] = {
            "candidate_message_hex": candidate.hex(),
            "reference_message_hex": reference.hex(),
            "digest_hex": candidate_digest.hex(),
            "first_round_outputs": [f"0x{value:016x}" for value in chosen_outputs],
            "verification": verification,
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, choices=(1, 2, 3, 4), default=4)
    parser.add_argument("--backend", choices=("smt", "sat", "sls"), default="sat")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument(
        "--free-tail-outputs", type=int, choices=range(1, 9), default=8,
        help="leave only this many final first-round output words symbolic",
    )
    parser.add_argument("--reference-message-hex", default="00" * LENGTH)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        reference = bytes.fromhex(args.reference_message_hex)
        result = search(
            args.rounds, args.backend, args.timeout, reference,
            args.free_tail_outputs,
        )
    except ValueError as exc:
        parser.error(str(exc))
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
