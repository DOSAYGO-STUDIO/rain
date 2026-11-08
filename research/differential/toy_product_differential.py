#!/usr/bin/env python3
"""Differential experiment for the two-input product F(P || Q) = P * Q.

P and Q are unsigned w-bit operands.  A paired input is defined by fixed XOR
or additive differences alpha and beta:

    XOR:       (P', Q') = (P XOR alpha, Q XOR beta)
    additive:  (P', Q') = (P + alpha, Q + beta) mod 2^w

The default reports the full 2w-bit integer product.  ``--product low`` keeps
only the low w bits and therefore studies multiplication modulo 2^w instead.
Outputs can be compared with XOR or modular subtraction.
"""
import argparse
import collections
import json
import math
import random


def product(p, q, operand_bits, product_mode="full"):
    value = p * q
    if product_mode == "low":
        value &= (1 << operand_bits) - 1
    return value


def paired_operand(value, difference, operand_mask, relation):
    if relation == "xor":
        return value ^ difference
    if relation == "add":
        return (value + difference) & operand_mask
    raise ValueError("input_relation must be xor or add")


def output_difference(out, paired_out, output_mask, relation):
    if relation == "xor":
        return out ^ paired_out
    if relation == "subtract":
        return (paired_out - out) & output_mask
    raise ValueError("output_relation must be xor or subtract")


def _hex(value, bits):
    return f"0x{value:0{(bits + 3) // 4}x}"


def analyze(operand_bits=8, delta_p=0, delta_q=1, product_mode="full",
            input_relation="xor", output_relation="xor", mode="exhaustive",
            samples=65536, seed=1, pairwise=None):
    """Measure a product differential distribution for a fixed operand pair."""
    if not 1 <= operand_bits <= 64:
        raise ValueError("operand_bits must be in 1..64")
    if input_relation not in ("xor", "add"):
        raise ValueError("input_relation must be xor or add")
    if output_relation not in ("xor", "subtract"):
        raise ValueError("output_relation must be xor or subtract")
    operand_mask = (1 << operand_bits) - 1
    if input_relation == "xor" and (
            delta_p < 0 or delta_q < 0 or
            delta_p & ~operand_mask or delta_q & ~operand_mask):
        raise ValueError("XOR operand differences must be nonnegative and fit the operand width")
    if input_relation == "xor":
        normalized_delta_p, normalized_delta_q = delta_p, delta_q
    else:
        normalized_delta_p = delta_p & operand_mask
        normalized_delta_q = delta_q & operand_mask
    if normalized_delta_p == 0 and normalized_delta_q == 0:
        raise ValueError("at least one operand difference must be nonzero")
    if product_mode not in ("full", "low"):
        raise ValueError("product_mode must be full or low")
    if mode not in ("exhaustive", "sample"):
        raise ValueError("mode must be exhaustive or sample")
    if mode == "exhaustive" and operand_bits > 10:
        raise ValueError("exhaustive mode is limited to at most 10 operand bits")
    if samples <= 0:
        raise ValueError("samples must be positive")

    output_bits = 2 * operand_bits if product_mode == "full" else operand_bits
    output_mask = (1 << output_bits) - 1
    if pairwise is None:
        pairwise = output_bits <= 32
    if pairwise and output_bits > 32:
        raise ValueError("pairwise collection is limited to at most 32 output bits")

    exact_counts = collections.Counter()
    bit_ones = [0] * output_bits
    hamming_counts = [0] * (output_bits + 1)
    pair_counts = None
    if pairwise:
        pair_counts = {
            (i, j): [0, 0, 0, 0]
            for i in range(output_bits) for j in range(i + 1, output_bits)
        }

    if mode == "exhaustive":
        limit = 1 << operand_bits
        inputs = ((p, q) for p in range(limit) for q in range(limit))
        denominator = limit * limit
        sampling = "complete ordered input domain; paired unordered edges appear twice"
    else:
        rng = random.Random(seed)
        inputs = ((rng.getrandbits(operand_bits), rng.getrandbits(operand_bits))
                  for _ in range(samples))
        denominator = samples
        sampling = "deterministic pseudorandom sampling with replacement"

    bilinear_matches = 0
    for p, q in inputs:
        paired_p = paired_operand(p, normalized_delta_p, operand_mask, input_relation)
        paired_q = paired_operand(q, normalized_delta_q, operand_mask, input_relation)
        out = product(p, q, operand_bits, product_mode)
        paired_out = product(paired_p, paired_q, operand_bits, product_mode)
        difference = output_difference(out, paired_out, output_mask, output_relation)
        if (product_mode == "low" and input_relation == "add" and
                output_relation == "subtract"):
            predicted = (
                p * normalized_delta_q + q * normalized_delta_p +
                normalized_delta_p * normalized_delta_q
            ) & operand_mask
            bilinear_matches += difference == predicted
        exact_counts[difference] += 1
        hamming_counts[difference.bit_count()] += 1
        active = [i for i in range(output_bits) if (difference >> i) & 1]
        for i in active:
            bit_ones[i] += 1
        if pair_counts is not None:
            for i in range(output_bits):
                bi = (difference >> i) & 1
                for j in range(i + 1, output_bits):
                    bj = (difference >> j) & 1
                    pair_counts[i, j][(bi << 1) | bj] += 1

    top = exact_counts.most_common(16)
    bit_rows = [
        {
            "bit": i,
            "ones": count,
            "probability_one": count / denominator,
            "bias_from_half": count / denominator - 0.5,
        }
        for i, count in enumerate(bit_ones)
    ]
    hamming_rows = [
        {
            "weight": weight,
            "count": count,
            "probability": count / denominator,
            "ideal_probability": math.comb(output_bits, weight) / (1 << output_bits),
        }
        for weight, count in enumerate(hamming_counts) if count
    ]

    result = {
        "experiment": "two-operand-integer-product-differential",
        "function": (
            f"F(P || Q) = P*Q as a {output_bits}-bit full product"
            if product_mode == "full"
            else f"F(P || Q) = P*Q mod 2^{operand_bits}"
        ),
        "operand_bits": operand_bits,
        "output_bits": output_bits,
        "pair_definition": {
            "input_relation": input_relation,
            "delta_p_argument": delta_p,
            "delta_q_argument": delta_q,
            "delta_p_word": _hex(normalized_delta_p, operand_bits),
            "delta_q_word": _hex(normalized_delta_q, operand_bits),
            "P_prime": (
                "P XOR delta_p" if input_relation == "xor"
                else f"(P + delta_p) mod 2^{operand_bits}"
            ),
            "Q_prime": (
                "Q XOR delta_q" if input_relation == "xor"
                else f"(Q + delta_q) mod 2^{operand_bits}"
            ),
        },
        "output_difference": (
            "F(P,Q) XOR F(P',Q')" if output_relation == "xor"
            else f"F(P',Q') - F(P,Q) mod 2^{output_bits}"
        ),
        "mode": mode,
        "samples": denominator,
        "sampling": sampling,
        "ideal_random_reference": {
            "each_output_bit_one_probability": 0.5,
            "each_fixed_exact_difference_probability": 2.0 ** (-output_bits),
            "zero_difference_probability": 2.0 ** (-output_bits),
            "hamming_weight_distribution": f"Binomial({output_bits}, 1/2)",
        },
        "observed": {
            "distinct_output_differences": len(exact_counts),
            "zero_difference_count": exact_counts[0],
            "zero_difference_probability": exact_counts[0] / denominator,
            "most_frequent_differences": [
                {
                    "difference": _hex(difference, output_bits),
                    "count": count,
                    "probability": count / denominator,
                }
                for difference, count in top
            ],
            "max_absolute_bit_bias": max(abs(row["bias_from_half"]) for row in bit_rows),
            "constant_zero_bits": [row["bit"] for row in bit_rows if row["ones"] == 0],
            "constant_one_bits": [row["bit"] for row in bit_rows if row["ones"] == denominator],
            "mean_hamming_weight": sum(
                weight * count for weight, count in enumerate(hamming_counts)
            ) / denominator,
            "ideal_mean_hamming_weight": output_bits / 2,
            "output_bits": bit_rows,
            "hamming_weight": hamming_rows,
        },
    }
    if pair_counts is not None:
        pair_rows = []
        for (i, j), cells in pair_counts.items():
            probabilities = [count / denominator for count in cells]
            pair_rows.append({
                "bits": [i, j],
                "probabilities_00_01_10_11": probabilities,
                "max_cell_bias_from_quarter": max(abs(p - 0.25) for p in probabilities),
                "xor_one_probability": probabilities[1] + probabilities[2],
            })
        pair_rows.sort(key=lambda row: row["max_cell_bias_from_quarter"], reverse=True)
        result["observed"]["most_biased_bit_pairs"] = pair_rows[:16]
        result["observed"]["max_pair_cell_bias_from_quarter"] = pair_rows[0]["max_cell_bias_from_quarter"] if pair_rows else 0.0
    if product_mode == "low" and input_relation == "add" and output_relation == "subtract":
        result["algebraic_check"] = {
            "identity": (
                "delta_out = P*delta_q + Q*delta_p + delta_p*delta_q "
                f"mod 2^{operand_bits}"
            ),
            "matching_inputs": bilinear_matches,
            "total_inputs": denominator,
            "verified_for_all_inputs": bilinear_matches == denominator,
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operand-bits", type=int, default=8)
    parser.add_argument("--delta-p", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--delta-q", type=lambda value: int(value, 0), default=1)
    parser.add_argument("--product", choices=("full", "low"), default="full")
    parser.add_argument("--input-relation", choices=("xor", "add"), default="xor")
    parser.add_argument("--output-relation", choices=("xor", "subtract"), default="xor")
    parser.add_argument("--mode", choices=("exhaustive", "sample"), default="exhaustive")
    parser.add_argument("--samples", type=int, default=65536)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--pairwise", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--output", type=argparse.FileType("w"))
    args = parser.parse_args()
    try:
        result = analyze(
            operand_bits=args.operand_bits,
            delta_p=args.delta_p,
            delta_q=args.delta_q,
            product_mode=args.product,
            input_relation=args.input_relation,
            output_relation=args.output_relation,
            mode=args.mode,
            samples=args.samples,
            seed=args.seed,
            pairwise=args.pairwise,
        )
    except ValueError as exc:
        parser.error(str(exc))
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write(rendered)
        args.output.close()
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
