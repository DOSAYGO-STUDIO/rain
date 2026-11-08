#!/usr/bin/env python3
"""Trace one paired Rainstorm execution at exact internal checkpoints."""
import argparse
import hashlib
import json
from pathlib import Path
import random

from rainstorm_model import MASK, hash_message, paired_message, relation_word_differences, rotl


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def word_hex(values):
    return [f"0x{value:016x}" for value in values]


def state_difference(a, b, selected_relation="xor", rotation=1):
    xor = [left ^ right for left, right in zip(a, b)]
    additive = [(right - left) & MASK for left, right in zip(a, b)]
    rx = [right ^ rotl(left, rotation) for left, right in zip(a, b)]
    selected = relation_word_differences(a, b, selected_relation, rotation)
    return {
        "xor_words": word_hex(xor),
        "additive_b_minus_a_words": word_hex(additive),
        "rx_b_xor_rotl_a_words": word_hex(rx),
        "active_xor_words": sum(value != 0 for value in xor),
        "active_xor_bits": sum(value.bit_count() for value in xor),
        "selected_relation": selected_relation,
        "selected_difference_words": word_hex(selected),
        "active_selected_words": sum(value != 0 for value in selected),
        "active_selected_bits": sum(value.bit_count() for value in selected),
    }


def paired_trace(message, bits=64, relation="xor", difference=1, rotation=1,
                 seed=0, trace_level="round", include_states=False):
    paired = paired_message(message, relation, difference, rotation)
    left = hash_message(message, bits, seed, trace_level)
    right = hash_message(paired, bits, seed, trace_level)
    if len(left.trace) != len(right.trace):
        raise AssertionError("paired traces have different lengths")
    checkpoints = []
    for event_a, event_b in zip(left.trace, right.trace):
        metadata_a = {key: value for key, value in event_a.items() if key != "state"}
        metadata_b = {key: value for key, value in event_b.items() if key != "state"}
        if metadata_a != metadata_b:
            raise AssertionError("paired trace checkpoints do not align")
        row = {
            **metadata_a,
            **state_difference(event_a["state"], event_b["state"], relation, rotation),
        }
        if include_states:
            row["state_a"] = word_hex(event_a["state"])
            row["state_b"] = word_hex(event_b["state"])
        checkpoints.append(row)
    digest_xor = bytes(a ^ b for a, b in zip(left.digest, right.digest))
    return {
        "experiment": "exact-paired-rainstorm-trace",
        "production_version": "4.0.0",
        "bits": bits,
        "seed": seed,
        "message_length": len(message),
        "pair_relation": relation,
        "input_difference": hex(difference),
        "rx_rotation": rotation if relation == "rx" else None,
        "trace_level": trace_level,
        "message_a_hex": message.hex(),
        "message_b_hex": paired.hex(),
        "digest_a_hex": left.digest.hex(),
        "digest_b_hex": right.digest.hex(),
        "digest_xor_hex": digest_xor.hex(),
        "digest_collision": left.digest == right.digest,
        "fold_difference": state_difference(
            left.folded, right.folded, relation, rotation),
        "checkpoints": checkpoints,
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (ROOT / "src/rainstorm.cpp", HERE / "rainstorm_model.py", Path(__file__))
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--message-hex")
    source.add_argument("--length", type=int, default=8)
    parser.add_argument("--base-seed", type=int, default=1)
    parser.add_argument("--bits", type=int, choices=(64, 128, 256, 512), default=64)
    parser.add_argument("--hash-seed", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--relation", choices=("xor", "add", "rx"), default="xor")
    parser.add_argument("--difference", type=lambda value: int(value, 0), default=1)
    parser.add_argument("--rotation", type=int, default=1)
    parser.add_argument("--trace-level", choices=("round", "word", "operation"), default="round")
    parser.add_argument("--include-states", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.message_hex is not None:
        try:
            message = bytes.fromhex(args.message_hex)
        except ValueError as exc:
            parser.error(str(exc))
    else:
        if args.length is None or args.length <= 0:
            parser.error("--length must be positive")
        message = random.Random(args.base_seed).randbytes(args.length)
    try:
        result = paired_trace(
            message=message,
            bits=args.bits,
            relation=args.relation,
            difference=args.difference,
            rotation=args.rotation,
            seed=args.hash_seed,
            trace_level=args.trace_level,
            include_states=args.include_states,
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
