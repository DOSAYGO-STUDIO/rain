#!/usr/bin/env python3
"""Independently replay and trace a programmed reduced-round witness."""
import argparse
import json

from rainstorm_model import MASK, initial_state, weakfunc, words
from scan_production import ProductionNative


PADDING = [0x8080808080808080] * 8


def folded(state):
    return [(state[i] - state[8 + i]) & MASK for i in range(8)]


def difference(left, right):
    xor = [a ^ b for a, b in zip(left, right)]
    return {
        "equal_prefix_words": next(
            (i for i, (a, b) in enumerate(zip(left, right)) if a != b),
            len(left)),
        "active_words": sum(value != 0 for value in xor),
        "active_bits": sum(value.bit_count() for value in xor),
        "xor_words": [f"0x{value:016x}" for value in xor],
    }


def replay(message_a, message_b):
    if len(message_a) != 64 or len(message_b) != 64 or message_a == message_b:
        raise ValueError("witnesses must be distinct 64-byte messages")
    data_a = words(message_a)
    data_b = words(message_b)
    state_a = initial_state(64)
    state_b = initial_state(64)
    stages = []

    def record(stage):
        fold_a = folded(state_a)
        fold_b = folded(state_b)
        stages.append({
            "stage": stage,
            "state_difference": difference(state_a, state_b),
            "prospective_fold_difference": difference(fold_a, fold_b),
            "fold_a": [f"0x{value:016x}" for value in fold_a],
            "fold_b": [f"0x{value:016x}" for value in fold_b],
        })

    record("initial")
    for round_index in range(4):
        state_a = weakfunc(state_a, data_a, bool(round_index & 1))
        state_b = weakfunc(state_b, data_b, bool(round_index & 1))
        record(f"message_round_{round_index + 1}")
    for round_index in range(4):
        state_a = weakfunc(state_a, PADDING, bool(round_index & 1))
        state_b = weakfunc(state_b, PADDING, bool(round_index & 1))
        record(f"padding_round_{round_index + 1}")

    # Recompute the actual two-message-round reduced construction.  It omits
    # padding compression, then folds and retains production's two final left
    # rounds for the 128-bit output.
    reduced_a = initial_state(64)
    reduced_b = initial_state(64)
    for round_index in range(2):
        reduced_a = weakfunc(reduced_a, data_a, bool(round_index & 1))
        reduced_b = weakfunc(reduced_b, data_b, bool(round_index & 1))
    reduced_fold_a = folded(reduced_a)
    reduced_fold_b = folded(reduced_b)
    one_padding_a = weakfunc(reduced_a, PADDING, False)
    one_padding_b = weakfunc(reduced_b, PADDING, False)
    one_padding_fold_a = folded(one_padding_a)
    one_padding_fold_b = folded(one_padding_b)
    reduced_digests = {}
    for bits in (64, 128, 256, 512):
        output_a = list(reduced_a)
        output_b = list(reduced_b)
        for lane in range(8):
            output_a[lane] = reduced_fold_a[lane]
            output_b[lane] = reduced_fold_b[lane]
        final_rounds = max(bits // 64, 2) if bits > 64 else 0
        for _ in range(final_rounds):
            output_a = weakfunc(output_a, PADDING, True)
            output_b = weakfunc(output_b, PADDING, True)
        digest_a = b"".join(
            word.to_bytes(8, "little") for word in output_a[:bits // 64])
        digest_b = b"".join(
            word.to_bytes(8, "little") for word in output_b[:bits // 64])
        reduced_digests[str(bits)] = {
            "digest_a_hex": digest_a.hex(),
            "digest_b_hex": digest_b.hex(),
            "collision": digest_a == digest_b,
        }

    native = ProductionNative()
    production_a = native.hashes(1, 128, 0, message_a, 64, 1)
    production_b = native.hashes(1, 128, 0, message_b, 64, 1)
    return {
        "experiment": "independent-programmed-rebound-replay",
        "message_a_hex": message_a.hex(),
        "message_b_hex": message_b.hex(),
        "reduced_variant": {
            "message_rounds": 2,
            "padding_compression_rounds": 0,
            "final_left_rounds": "production count for each output width",
            "fold_a": [f"0x{value:016x}" for value in reduced_fold_a],
            "fold_b": [f"0x{value:016x}" for value in reduced_fold_b],
            "fold_prefix_words_equal": reduced_fold_a[:2] == reduced_fold_b[:2],
            "digests": reduced_digests,
        },
        "one_real_padding_round_extension": {
            "message_rounds": 2,
            "padding_compression_rounds": 1,
            "padding_round_direction": "right",
            "transformed_sum_a": f"0x{sum(one_padding_a[8:]) & MASK:016x}",
            "transformed_sum_b": f"0x{sum(one_padding_b[8:]) & MASK:016x}",
            "fold_a": [f"0x{value:016x}" for value in one_padding_fold_a],
            "fold_b": [f"0x{value:016x}" for value in one_padding_fold_b],
            "fold_words_1_through_5_equal": (
                one_padding_fold_a[1:6] == one_padding_fold_b[1:6]),
            "fold_word_0_equal": one_padding_fold_a[0] == one_padding_fold_b[0],
            "interpretation": (
                "The G collision fixes the full state prefix through lane 5. "
                "The padding right round preserves words 1..5, while its "
                "lane-7 wrap changes word 0 unless the transformed sums match."
            ),
        },
        "production_v4": {
            "message_rounds": 4,
            "padding_compression_rounds": 4,
            "final_left_rounds": 2,
            "native_digest_a_hex": production_a.hex(),
            "native_digest_b_hex": production_b.hex(),
            "rainstorm_128_collision": production_a == production_b,
        },
        "stages": stages,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("message_a_hex")
    parser.add_argument("message_b_hex")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = replay(bytes.fromhex(args.message_a_hex), bytes.fromhex(args.message_b_hex))
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
