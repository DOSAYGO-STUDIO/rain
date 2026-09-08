#!/usr/bin/env python3
"""Bounded collision search for actual production Rainstorm v4 digests.

The default instance searches two distinct 8-byte messages for a complete
Rainstorm-64 collision.  Such messages pass through one R/L/R/L tail schedule,
the fold, and no post-fold final rounds.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from rainstorm_model import CTR_LEFT, CTR_RIGHT, K, PRIMES, Z


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def symbolic_weakfunc(state, data, left):
    import z3
    h = list(state)
    counter = z3.BitVecVal(CTR_LEFT if left else CTR_RIGHT, 64)
    for lane in range(8):
        active = lane if left else 8 + lane
        blit = 8 + lane if left else lane
        target = lane + 1 if left else (8 + lane + 1 if lane < 7 else 0)
        h[active] = z3.RotateRight((h[active] ^ data[lane]) - K[lane], Z[lane])
        h[blit] = h[blit] ^ h[active]
        counter = counter + h[active]
        h[target] = h[target] - counter
    return h


def symbolic_words(block):
    import z3
    if len(block) != 64:
        raise ValueError("symbolic blocks must be 64 bytes")
    return [z3.Concat(*reversed(block[offset:offset + 8]))
            for offset in range(0, 64, 8)]


def symbolic_digest(message, bits, rounds=4):
    """Return symbolic digest words and folded words for one exact length."""
    import z3
    length = len(message)
    h = [z3.BitVecVal(length + prime, 64) for prime in PRIMES]
    full_blocks = length // 64
    for block_index in range(full_blocks):
        data = symbolic_words(message[block_index * 64:(block_index + 1) * 64])
        for round_index in range(rounds):
            h = symbolic_weakfunc(h, data, bool(round_index & 1))

    remainder = length % 64
    fill = (0x80 + remainder) & 0xFF
    tail = list(message[full_blocks * 64:])
    tail.extend(z3.BitVecVal(fill, 8) for _ in range(64 - remainder))
    tail_data = symbolic_words(tail)
    for round_index in range(rounds):
        h = symbolic_weakfunc(h, tail_data, bool(round_index & 1))
    for lane in range(8):
        h[lane] = h[lane] - h[8 + lane]
    folded = list(h[:8])
    final_rounds = max(bits // 64, 2) if bits > 64 else 0
    for _ in range(final_rounds):
        h = symbolic_weakfunc(h, tail_data, True)
    return list(h[:bits // 64]), folded


def symbolic_message(prefix, length, symbolic_bytes, suffix_byte):
    import z3
    return [
        z3.BitVec(f"{prefix}_{index}", 8)
        if index < symbolic_bytes else z3.BitVecVal(suffix_byte, 8)
        for index in range(length)
    ]


def search(args):
    try:
        import z3
    except ImportError as exc:
        raise SystemExit("z3-solver is required: python3 -m pip install z3-solver") from exc
    symbolic_bytes = args.symbolic_bytes or args.message_length
    if not 1 <= args.message_length <= 128:
        raise SystemExit("--message-length must be in 1..128")
    if not 1 <= symbolic_bytes <= args.message_length:
        raise SystemExit("--symbolic-bytes must be in 1..message-length")
    output_words = args.bits // 64
    target_words = args.words if args.words is not None else list(range(output_words))
    if not target_words or any(word not in range(output_words) for word in target_words):
        raise SystemExit("--words must select output word indexes")
    if not 0 <= args.suffix_byte <= 255:
        raise SystemExit("--suffix-byte must be in 0..255")

    left = symbolic_message("a", args.message_length, symbolic_bytes, args.suffix_byte)
    reference = None
    if args.reference_message_hex is not None:
        try:
            reference = bytes.fromhex(args.reference_message_hex)
        except ValueError as exc:
            raise SystemExit(f"invalid --reference-message-hex: {exc}") from exc
        if len(reference) != args.message_length:
            raise SystemExit(
                "--reference-message-hex must contain exactly --message-length bytes")
        right = [z3.BitVecVal(value, 8) for value in reference]
    else:
        right = symbolic_message("b", args.message_length, symbolic_bytes, args.suffix_byte)
    if args.rounds != 4 and args.bits != 64:
        raise SystemExit("reduced-round experiments currently require --bits 64")
    digest_a, fold_a = symbolic_digest(left, args.bits, args.rounds)
    digest_b, fold_b = symbolic_digest(right, args.bits, args.rounds)

    if args.backend == "sat":
        solver = z3.Then("simplify", "bit-blast", "sat").solver()
    elif args.backend == "sls":
        solver = z3.Tactic("qfbv-sls").solver()
    else:
        solver = z3.Solver()
    solver.set(timeout=args.timeout * 1000)
    if reference is None:
        # Strict ordering removes the a/b symmetry and also enforces distinctness.
        packed_left = left[0] if len(left) == 1 else z3.Concat(*left)
        packed_right = right[0] if len(right) == 1 else z3.Concat(*right)
        solver.add(z3.ULT(packed_left, packed_right))
    else:
        solver.add(z3.Or(*[
            left[index] != reference[index] for index in range(args.message_length)
        ]))
    for word in target_words:
        solver.add(digest_a[word] == digest_b[word])

    started = time.monotonic()
    status = solver.check()
    elapsed = time.monotonic() - started
    result = {
        "experiment": "bounded-production-rainstorm-digest-collision",
        "production_version": "4.0.0",
        "solver": f"Z3 {z3.get_version_string()}",
        "backend": args.backend,
        "status": str(status),
        "unknown_reason": solver.reason_unknown() if status == z3.unknown else None,
        "elapsed_seconds": elapsed,
        "timeout_seconds": args.timeout,
        "message_length": args.message_length,
        "symbolic_prefix_bytes_per_message": symbolic_bytes,
        "fixed_suffix_byte": args.suffix_byte,
        "digest_bits": args.bits,
        "weak_rounds_per_block": args.rounds,
        "production_equivalent": args.rounds == 4,
        "equal_digest_words": target_words,
        "complete_digest_collision_target": target_words == list(range(output_words)),
        "search_kind": "chosen-second-preimage" if reference is not None else "collision",
        "reference_message_hex": reference.hex() if reference is not None else None,
        "scope": (
            "Exact production-v4 arithmetic in a finite symbolic-prefix domain. "
            "SAT is a witness; UNSAT applies only to this domain; unknown is inconclusive."
        ),
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (ROOT / "src/rainstorm.cpp", HERE / "rainstorm_model.py", Path(__file__))
        },
    }
    if status == z3.sat:
        model = solver.model()
        concrete = lambda values: bytes(
            model.eval(value, model_completion=True).as_long() for value in values)
        message_a = concrete(left)
        message_b = reference if reference is not None else concrete(right)
        if args.rounds == 4:
            from scan_production import ProductionNative
            native = ProductionNative()
            native_a = native.hashes(1, args.bits, 0, message_a, len(message_a), 1)
            native_b = native.hashes(1, args.bits, 0, message_b, len(message_b), 1)
            verification = "native-production-cpp"
        else:
            from rainstorm_model import hash_message
            native_a = hash_message(
                message_a, args.bits, 0, "none", args.rounds).digest
            native_b = hash_message(
                message_b, args.bits, 0, "none", args.rounds).digest
            verification = "independent-integer-reduced-round-model"
        word_bytes = 8
        assert message_a != message_b
        assert all(
            native_a[word * word_bytes:(word + 1) * word_bytes] ==
            native_b[word * word_bytes:(word + 1) * word_bytes]
            for word in target_words
        )
        result["witness"] = {
            "message_a_hex": message_a.hex(),
            "message_b_hex": message_b.hex(),
            "digest_a_hex": native_a.hex(),
            "digest_b_hex": native_b.hex(),
            "fold_a": [f"0x{model.eval(value, model_completion=True).as_long():016x}"
                       for value in fold_a],
            "fold_b": [f"0x{model.eval(value, model_completion=True).as_long():016x}"
                       for value in fold_b],
            "verification": verification,
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--message-length", type=int, default=8)
    parser.add_argument("--symbolic-bytes", type=int)
    parser.add_argument("--suffix-byte", type=int, default=0)
    parser.add_argument(
        "--reference-message-hex",
        help="fix the second message and search a distinct message with the same digest",
    )
    parser.add_argument("--bits", type=int, choices=(64, 128, 256, 512), default=64)
    parser.add_argument(
        "--rounds", type=int, choices=(1, 2, 3, 4), default=4,
        help="weak rounds per message/tail block; production uses 4",
    )
    parser.add_argument("--words", type=int, nargs="+")
    parser.add_argument("--backend", choices=("smt", "sat", "sls"), default="sat")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = search(args)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
