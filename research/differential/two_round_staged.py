#!/usr/bin/env python3
"""Staged exact attack on the two-round Rainstorm-64 late-lane equation.

Lane seven is solved by an exact carry enumeration exploiting ROTL(..., 53),
which couples each output bit to an input bit only 11 positions ahead.  For
each padding-compatible late-y sum, Z3 receives only the residual lane-5/6
one-word equation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import time

from rainstorm_model import (
    CTR_LEFT, CTR_RIGHT, K, MASK, Z, hash_message, initial_state,
    program_round_data, rotl, weakfunc,
)
from smt_programmed import FILL, LENGTH
from solver_backends import solve_bitwuzla


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def _carry(a, b, incoming):
    return (a & b) | (a & incoming) | (b & incoming)


def solve_rotated_xor_add(addend, constant, difference, rotation=53):
    """Solve (u+addend) XOR (ROTL(u,r)+constant) == difference.

    When ROTL by r is ROTR by m=64-r and m is small, enumerate the first m
    bits.  The equation and the two addition carries force every later bit.
    """
    offset = (64 - rotation) % 64
    if not 1 <= offset <= 20:
        raise ValueError("carry enumeration requires a rotation offset in 1..20")
    solutions = []
    for prefix in range(1 << offset):
        bits = [None] * 64
        for bit in range(offset):
            bits[bit] = (prefix >> bit) & 1
        carry_a = 0
        carry_b = 0
        valid = True
        for bit in range(64):
            u_bit = bits[bit]
            a_bit = (addend >> bit) & 1
            k_bit = (constant >> bit) & 1
            d_bit = (difference >> bit) & 1
            sum_a = u_bit ^ a_bit ^ carry_a
            linked = (bit + offset) & 63
            required_linked = sum_a ^ d_bit ^ k_bit ^ carry_b
            if bits[linked] is None:
                bits[linked] = required_linked
            elif bits[linked] != required_linked:
                valid = False
                break
            carry_a = _carry(u_bit, a_bit, carry_a)
            carry_b = _carry(bits[linked], k_bit, carry_b)
        if valid:
            value = sum(bit_value << bit for bit, bit_value in enumerate(bits))
            assert (((value + addend) & MASK) ^
                    ((rotl(value, rotation) + constant) & MASK)) == difference
            solutions.append(value)
    return solutions


def _solve_y5(s_value, t_value, reference_y5, timeout_ms, random_seed,
              backend="z3", bv_solver="bitblast"):
    import z3
    initial = initial_state(LENGTH)
    # y[0..4] and x[0..4] are the all-zero reference path constants.
    reference_data = [0] * 7 + [FILL << 56]
    after_right = weakfunc(initial, reference_data, left=False)
    after_left = weakfunc(after_right, reference_data, left=True)
    prefix_y = after_right[8:13]
    prefix_x = after_left[:5]
    right_before_5 = (CTR_RIGHT + sum(prefix_y)) & MASK
    left_before_5 = (CTR_LEFT + sum(prefix_x)) & MASK

    y5 = z3.BitVec("residual_y5", 64)
    y6 = z3.BitVecVal(s_value, 64) - y5
    data5 = (z3.BitVecVal(initial[13], 64) - right_before_5) ^ (
        z3.RotateLeft(y5, Z[5]) + K[5])
    incoming5 = (z3.BitVecVal(initial[5], 64) ^ y5) - left_before_5
    x5 = z3.RotateRight((incoming5 ^ data5) - K[5], Z[5])
    data6 = (z3.BitVecVal(initial[14], 64) - right_before_5 - y5) ^ (
        z3.RotateLeft(y6, Z[6]) + K[6])
    incoming6 = ((z3.BitVecVal(initial[6], 64) ^ y6) -
                 z3.BitVecVal(left_before_5, 64) - x5)
    x6 = z3.RotateRight((incoming6 ^ data6) - K[6], Z[6])

    constraints = [x5 + x6 == z3.BitVecVal(t_value, 64)]
    if s_value == ((reference_y5 + after_right[14]) & MASK):
        constraints.append(y5 != z3.BitVecVal(reference_y5, 64))
    if backend == "bitwuzla":
        status, model, detail = solve_bitwuzla(
            constraints, (y5,), timeout_ms, random_seed,
            bv_solver=bv_solver)
        if status != "sat":
            return None, status, detail or ("timeout" if status == "unknown" else None)
        return model["residual_y5"], "sat", None
    solver = z3.Then("simplify", "bit-blast", "sat").solver()
    solver.set(timeout=timeout_ms)
    solver.set(random_seed=random_seed)
    solver.add(*constraints)
    status = solver.check()
    if status != z3.sat:
        return None, str(status), solver.reason_unknown() if status == z3.unknown else None
    model = solver.model()
    return model.eval(y5, model_completion=True).as_long(), "sat", None


def search(max_s_candidates=256, per_candidate_timeout_ms=1000, seed=1,
           residual_backend="z3", bitwuzla_bv_solver="bitblast"):
    initial = initial_state(LENGTH)
    reference = bytes(LENGTH)
    reference_data = [0] * 7 + [FILL << 56]
    after_right = weakfunc(initial, reference_data, left=False)
    after_left = weakfunc(after_right, reference_data, left=True)
    reference_y = after_right[8:]
    reference_x = after_left[:8]
    prefix_y_sum = sum(reference_y[:5]) & MASK
    late_y_sum = sum(reference_y[5:]) & MASK
    prefix_x_sum = sum(reference_x[:5]) & MASK
    late_x_sum = sum(reference_x[5:]) & MASK
    right_before_5 = (CTR_RIGHT + prefix_y_sum) & MASK
    left_before_5 = (CTR_LEFT + prefix_x_sum) & MASK

    rng = random.Random(seed)
    padding_trials = 0
    lane7_solution_counts = []
    residual_statuses = {"sat": 0, "unsat": 0, "unknown": 0}
    started = time.monotonic()
    witness = None

    for candidate_index in range(max_s_candidates):
        while True:
            padding_trials += 1
            s_value = rng.getrandbits(64)
            y7 = (late_y_sum - s_value) & MASK
            data7 = (
                (initial[15] - right_before_5 - s_value) & MASK
            ) ^ ((rotl(y7, Z[7]) + K[7]) & MASK)
            if data7 >> 56 == FILL:
                break

        incoming7_base = ((initial[7] ^ y7) - left_before_5 - late_x_sum) & MASK
        # With u=x7 and t=late_x_sum-u, the lane-7 incoming word is u+B.
        u_solutions = solve_rotated_xor_add(
            incoming7_base, K[7], data7, Z[7])
        lane7_solution_counts.append(len(u_solutions))
        for solution_index, x7 in enumerate(u_solutions):
            t_value = (late_x_sum - x7) & MASK
            y5, status, _ = _solve_y5(
                s_value, t_value, reference_y[5],
                per_candidate_timeout_ms,
                seed + candidate_index * 257 + solution_index,
                residual_backend,
                bitwuzla_bv_solver,
            )
            residual_statuses[status] += 1
            if y5 is None:
                continue
            y6 = (s_value - y5) & MASK
            chosen_y = reference_y[:5] + [y5, y6, y7]
            programmed = program_round_data(initial, chosen_y, left=False)
            block = b"".join(value.to_bytes(8, "little") for value in programmed)
            assert block[-1] == FILL
            candidate = block[:-1]
            candidate_digest = hash_message(candidate, 64, 0, "none", 2).digest
            reference_digest = hash_message(reference, 64, 0, "none", 2).digest
            if candidate != reference and candidate_digest == reference_digest:
                witness = {
                    "candidate_message_hex": candidate.hex(),
                    "reference_message_hex": reference.hex(),
                    "digest_hex": candidate_digest.hex(),
                    "late_y_sum": f"0x{s_value:016x}",
                    "late_x56_sum": f"0x{t_value:016x}",
                    "first_round_outputs": [f"0x{value:016x}" for value in chosen_y],
                    "verification": "independent-integer-reduced-round-model",
                }
                break
        if witness is not None:
            break

    elapsed = time.monotonic() - started
    return {
        "experiment": "staged-two-round-rainstorm64-message-modification",
        "production_version": "4.0.0",
        "production_equivalent": False,
        "status": "sat" if witness is not None else "exhausted-without-witness",
        "message_length": LENGTH,
        "digest_bits": 64,
        "weak_rounds": 2,
        "max_padding_compatible_s_candidates": max_s_candidates,
        "tested_padding_compatible_s_candidates": len(lane7_solution_counts),
        "padding_trials": padding_trials,
        "per_residual_solver_timeout_ms": per_candidate_timeout_ms,
        "residual_solver_backend": residual_backend,
        "bitwuzla_bv_solver": (
            bitwuzla_bv_solver if residual_backend == "bitwuzla" else None),
        "elapsed_seconds": elapsed,
        "lane7_carry_solver": "exact 11-bit-prefix enumeration",
        "lane7_solution_count_histogram": {
            str(count): lane7_solution_counts.count(count)
            for count in sorted(set(lane7_solution_counts))
        },
        "residual_solver_statuses": residual_statuses,
        "witness": witness,
        "scope": (
            "Exact reduced two-round attack. No witness is not UNSAT outside "
            "the recorded sampled sums and per-instance solver budgets."
        ),
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                ROOT / "src/rainstorm.cpp", HERE / "rainstorm_model.py", Path(__file__),
            )
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-s-candidates", type=int, default=256)
    parser.add_argument("--per-candidate-timeout-ms", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--residual-backend", choices=("z3", "bitwuzla"), default="z3")
    parser.add_argument(
        "--bitwuzla-bv-solver",
        choices=("bitblast", "prop", "preprop"), default="bitblast")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = search(
        args.max_s_candidates, args.per_candidate_timeout_ms, args.seed,
        args.residual_backend, args.bitwuzla_bv_solver)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
