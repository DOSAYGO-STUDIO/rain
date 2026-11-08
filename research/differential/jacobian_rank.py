#!/usr/bin/env python3
"""Boolean finite-difference ranks for Rainstorm message and output maps."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import time

from rainstorm_model import MASK, initial_state, weakfunc, words


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PAD = [0x8080808080808080] * 8


def checkpoints(message):
    """Return message boundary, pre-fold state, and first two fold words."""
    if len(message) not in (64, 128):
        raise ValueError("rank experiment supports 64- and 128-byte messages")
    state = initial_state(len(message))
    for offset in range(0, len(message), 64):
        data = words(message[offset:offset + 64])
        for round_index in range(4):
            state = weakfunc(state, data, bool(round_index & 1))
    boundary = tuple(state)
    for round_index in range(4):
        state = weakfunc(state, PAD, bool(round_index & 1))
    pre_fold = tuple(state)
    fold = tuple((state[lane] - state[8 + lane]) & MASK for lane in range(8))
    return boundary, pre_fold, fold[:2]


def pack(values):
    packed = 0
    for index, value in enumerate(values):
        packed |= value << (64 * index)
    return packed


def gf2_rank(columns):
    """Rank a binary matrix represented by arbitrary-width integer columns."""
    basis = {}
    for column in columns:
        value = column
        while value:
            pivot = value.bit_length() - 1
            if pivot not in basis:
                basis[pivot] = value
                break
            value ^= basis[pivot]
    return len(basis)


def analyze(length, seed):
    rng = random.Random(seed)
    message = bytearray(rng.randbytes(length))
    base = checkpoints(message)
    columns = [[], [], []]
    started = time.monotonic()
    for bit in range(length * 8):
        message[bit >> 3] ^= 1 << (bit & 7)
        changed = checkpoints(message)
        message[bit >> 3] ^= 1 << (bit & 7)
        for stage in range(3):
            columns[stage].append(pack(
                left ^ right for left, right in zip(base[stage], changed[stage])))
    elapsed = time.monotonic() - started
    return {
        "experiment": "rainstorm-boolean-jacobian-rank",
        "production_version": "4.0.0",
        "message_length": length,
        "input_bits": length * 8,
        "base_message_hex": bytes(message).hex(),
        "ranks": {
            "after_all_message_blocks_1024_bit_state": gf2_rank(columns[0]),
            "after_fixed_padding_1024_bit_state": gf2_rank(columns[1]),
            "first_two_fold_words_128_bit_output_core": gf2_rank(columns[2]),
        },
        "elapsed_seconds": elapsed,
        "interpretation": (
            "Ranks are first-order Boolean derivatives at one recorded point. "
            "They diagnose local degrees of freedom; full rank is not an "
            "inversion algorithm or a security proof."
        ),
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (ROOT / "src/rainstorm.cpp", HERE / "rainstorm_model.py",
                         Path(__file__))
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--length", type=int, choices=(64, 128), required=True)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("--trials must be positive")
    results = [analyze(args.length, args.seed + trial)
               for trial in range(args.trials)]
    if args.trials == 1:
        result = results[0]
    else:
        stage_names = list(results[0]["ranks"])
        result = {
            "experiment": "rainstorm-boolean-jacobian-rank-campaign",
            "production_version": "4.0.0",
            "message_length": args.length,
            "input_bits": args.length * 8,
            "trials": args.trials,
            "initial_seed": args.seed,
            "rank_histograms": {
                stage: {
                    str(rank): sum(item["ranks"][stage] == rank
                                   for item in results)
                    for rank in sorted({item["ranks"][stage]
                                        for item in results})
                }
                for stage in stage_names
            },
            "records": [{"base_message_hex": item["base_message_hex"],
                         "ranks": item["ranks"]} for item in results],
            "elapsed_seconds": sum(item["elapsed_seconds"] for item in results),
            "interpretation": results[0]["interpretation"],
            "source_sha256": results[0]["source_sha256"],
        }
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
