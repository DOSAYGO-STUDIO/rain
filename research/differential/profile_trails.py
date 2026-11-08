#!/usr/bin/env python3
"""Sample fixed Rainstorm differences and profile every round checkpoint."""
import argparse
import hashlib
import json
from pathlib import Path
import random

from rainstorm_model import hash_message, paired_message, relation_word_differences


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


class CheckpointStats:
    def __init__(self, words):
        self.samples = 0
        self.zero_states = 0
        self.active_bits = 0
        self.active_words = 0
        self.word_zero = [0] * words
        self.word_active_bits = [0] * words
        self.bit_ones = [[0] * 64 for _ in range(words)]

    def add(self, difference):
        self.samples += 1
        self.zero_states += not any(difference)
        self.active_words += sum(value != 0 for value in difference)
        self.active_bits += sum(value.bit_count() for value in difference)
        for word_index, value in enumerate(difference):
            self.word_zero[word_index] += value == 0
            self.word_active_bits[word_index] += value.bit_count()
            for bit in range(64):
                self.bit_ones[word_index][bit] += (value >> bit) & 1

    def render(self):
        n = self.samples
        bit_probabilities = [
            count / n for word in self.bit_ones for count in word
        ]
        return {
            "samples": n,
            "zero_state_probability": self.zero_states / n,
            "mean_active_words": self.active_words / n,
            "mean_active_bits": self.active_bits / n,
            "minimum_bit_one_probability": min(bit_probabilities),
            "maximum_bit_one_probability": max(bit_probabilities),
            "words": [
                {
                    "word": index,
                    "zero_probability": self.word_zero[index] / n,
                    "mean_active_bits": self.word_active_bits[index] / n,
                    "bit_one_probabilities": [count / n for count in self.bit_ones[index]],
                }
                for index in range(len(self.word_zero))
            ],
        }


def profile(length=8, bits=64, relation="xor", difference=1, rotation=1,
            samples=4096, base_seed=1, hash_seed=0):
    if length <= 0 or samples <= 0:
        raise ValueError("length and samples must be positive")
    rng = random.Random(base_seed)
    checkpoints = {}
    order = []
    digest_stats = CheckpointStats(bits // 64)

    for _ in range(samples):
        message = rng.randbytes(length)
        paired = paired_message(message, relation, difference, rotation)
        left = hash_message(message, bits, hash_seed, "round")
        right = hash_message(paired, bits, hash_seed, "round")
        if len(left.trace) != len(right.trace):
            raise AssertionError("paired trace lengths differ")
        for event_a, event_b in zip(left.trace, right.trace):
            stage = event_a["stage"]
            if stage != event_b["stage"]:
                raise AssertionError("paired checkpoints do not align")
            if stage not in checkpoints:
                checkpoints[stage] = CheckpointStats(len(event_a["state"]))
                order.append(stage)
            values = relation_word_differences(
                event_a["state"], event_b["state"], relation, rotation)
            checkpoints[stage].add(values)
        left_digest = [int.from_bytes(left.digest[offset:offset + 8], "little")
                       for offset in range(0, len(left.digest), 8)]
        right_digest = [int.from_bytes(right.digest[offset:offset + 8], "little")
                        for offset in range(0, len(right.digest), 8)]
        digest_stats.add(relation_word_differences(
            left_digest, right_digest, relation, rotation))

    return {
        "experiment": "rainstorm-internal-difference-profile",
        "production_version": "4.0.0",
        "message_length": length,
        "digest_bits": bits,
        "relation": relation,
        "difference": hex(difference),
        "rx_rotation": rotation if relation == "rx" else None,
        "samples": samples,
        "base_seed": base_seed,
        "hash_seed": hash_seed,
        "interpretation": (
            "Reconnaissance frequencies over uniform sampled bases; no trail "
            "probability or family-wide hypothesis-test claim is made."
        ),
        "checkpoints": [
            {"stage": stage, **checkpoints[stage].render()} for stage in order
        ],
        "digest": digest_stats.render(),
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (ROOT / "src/rainstorm.cpp", HERE / "rainstorm_model.py", Path(__file__))
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--length", type=int, default=8)
    parser.add_argument("--bits", type=int, choices=(64, 128, 256, 512), default=64)
    parser.add_argument("--relation", choices=("xor", "add", "rx"), default="xor")
    parser.add_argument("--difference", type=lambda value: int(value, 0), default=1)
    parser.add_argument("--rotation", type=int, default=1)
    parser.add_argument("--samples", type=int, default=4096)
    parser.add_argument("--base-seed", type=int, default=1)
    parser.add_argument("--hash-seed", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = profile(
            length=args.length,
            bits=args.bits,
            relation=args.relation,
            difference=args.difference,
            rotation=args.rotation,
            samples=args.samples,
            base_seed=args.base_seed,
            hash_seed=args.hash_seed,
        )
    except ValueError as exc:
        parser.error(str(exc))
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
