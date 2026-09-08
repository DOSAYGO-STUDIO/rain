#!/usr/bin/env python3
"""Exhaustive toy differential for f(x) = x + (x << shift) modulo 2^w.

The actual multiplication experiment keeps the two addition operands
correlated.  The optional independent comparison enumerates arbitrary x,y with
the same operand differences and demonstrates why a local xdp+ table can give
the wrong full-function probability when operands are related.
"""
import argparse
import collections
import json


def multiplication_histogram(bits=8, shift=2, input_xor=1):
    """Return XOR-output counts for x and x XOR input_xor."""
    mask = (1 << bits) - 1
    multiplier = (1 + (1 << shift)) & mask
    counts = collections.Counter()
    for x in range(1 << bits):
        paired = x ^ input_xor
        out = (multiplier * x) & mask
        paired_out = (multiplier * paired) & mask
        counts[out ^ paired_out] += 1
    return counts


def additive_histogram(bits=8, shift=2, input_add=1):
    """Return additive-output counts for x and x + input_add."""
    mask = (1 << bits) - 1
    multiplier = (1 + (1 << shift)) & mask
    counts = collections.Counter()
    for x in range(1 << bits):
        paired = (x + input_add) & mask
        out = (multiplier * x) & mask
        paired_out = (multiplier * paired) & mask
        counts[(paired_out - out) & mask] += 1
    return counts


def independent_add_histogram(bits=8, shift=2, input_xor=1):
    """Return xdp+ counts when x and y are independent instead of y=x<<shift."""
    mask = (1 << bits) - 1
    left_difference = input_xor & mask
    right_difference = (input_xor << shift) & mask
    counts = collections.Counter()
    for left in range(1 << bits):
        paired_left = left ^ left_difference
        for right in range(1 << bits):
            paired_right = right ^ right_difference
            out = (left + right) & mask
            paired_out = (paired_left + paired_right) & mask
            counts[out ^ paired_out] += 1
    return counts


def rows(counts, total):
    return [
        {
            "output_difference": f"0x{difference:02x}",
            "count": count,
            "probability": count / total,
        }
        for difference, count in sorted(counts.items())
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bits", type=int, default=8)
    parser.add_argument("--shift", type=int, default=2)
    parser.add_argument("--input-difference", type=lambda value: int(value, 0), default=1)
    parser.add_argument("--mode", choices=("xor", "additive"), default="xor")
    parser.add_argument("--compare-independent", action="store_true")
    args = parser.parse_args()
    if not 2 <= args.bits <= 16:
        raise SystemExit("--bits must be in 2..16")
    if not 1 <= args.shift < args.bits:
        raise SystemExit("--shift must be in 1..bits-1")
    if not 0 < args.input_difference < (1 << args.bits):
        raise SystemExit("--input-difference must be a nonzero word")
    if args.compare_independent and args.bits > 12:
        raise SystemExit("--compare-independent is limited to at most 12 bits")

    if args.mode == "xor":
        actual = multiplication_histogram(args.bits, args.shift, args.input_difference)
    else:
        actual = additive_histogram(args.bits, args.shift, args.input_difference)
    total = 1 << args.bits
    result = {
        "function": f"f(x) = x + (x << {args.shift}) mod 2^{args.bits}",
        "multiplier": 1 + (1 << args.shift),
        "difference_type": args.mode,
        "input_difference": f"0x{args.input_difference:x}",
        "actual_correlated_distribution": rows(actual, total),
    }
    if args.compare_independent:
        independent = independent_add_histogram(args.bits, args.shift, args.input_difference)
        independent_total = 1 << (2 * args.bits)
        result["independent_addition_model"] = {
            "left_input_xor": f"0x{args.input_difference:x}",
            "right_input_xor": f"0x{args.input_difference << args.shift:x}",
            "distribution": rows(independent, independent_total),
        }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
