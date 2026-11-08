#!/usr/bin/env python3
"""Exact integer model and trace checkpoints for production Rainstorm v4."""
from dataclasses import dataclass


MASK = (1 << 64) - 1
K = [
    MASK - 58,
    13166748625691186689,
    1573836600196043749,
    1478582680485693857,
    1584163446043636637,
    1358537349836140151,
    2849285319520710901,
    2366157163652459183,
]
Z = [17, 19, 23, 29, 31, 37, 41, 53]
PRIMES = [1, 2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]
CTR_LEFT = 0xEFCDAB8967452301
CTR_RIGHT = 0x1032547698BADCFE


def rotl(value, count):
    return ((value << count) | (value >> (64 - count))) & MASK


def rotr(value, count):
    return ((value >> count) | (value << (64 - count))) & MASK


def words(block):
    if len(block) != 64:
        raise ValueError("a Rainstorm block must contain exactly 64 bytes")
    return [int.from_bytes(block[offset:offset + 8], "little")
            for offset in range(0, 64, 8)]


def initial_state(message_length, seed=0):
    return [(seed + message_length + prime) & MASK for prime in PRIMES]


def program_round_data(state, transformed, left):
    """Recover the unique data words producing chosen active-word outputs."""
    if len(state) != 16 or len(transformed) != 8:
        raise ValueError("round programming requires 16 state and eight output words")
    counter = CTR_LEFT if left else CTR_RIGHT
    active_offset = 0 if left else 8
    data = []
    for lane, output in enumerate(transformed):
        incoming = state[active_offset + lane]
        if lane:
            incoming = (incoming - counter) & MASK
        pre_rotate = (rotl(output, Z[lane]) + K[lane]) & MASK
        data.append(incoming ^ pre_rotate)
        counter = (counter + output) & MASK
    return data


def invert_left_low(output_low, data):
    """Invert the low-half map induced by one fixed-data left weak round."""
    if len(output_low) != 8 or len(data) != 8:
        raise ValueError("left-low inversion requires eight words")
    incoming = []
    counter = CTR_LEFT
    for lane, transformed in enumerate(output_low):
        before = (rotl(transformed, Z[lane]) + K[lane]) & MASK
        before ^= data[lane]
        incoming.append(before if lane == 0 else (before + counter) & MASK)
        counter = (counter + transformed) & MASK
    return incoming


def weakfunc(state, data, left, observe=None, context=None, trace_level="round"):
    """Apply one v4 weak round; optionally emit word/operation checkpoints."""
    if len(state) != 16 or len(data) != 8:
        raise ValueError("Rainstorm weakfunc requires 16 state and eight data words")
    h = list(state)
    counter = CTR_LEFT if left else CTR_RIGHT
    direction = "left" if left else "right"
    base = dict(context or {})
    base["direction"] = direction

    def emit(lane, operation):
        if observe is None:
            return
        if trace_level == "operation" or (
                trace_level == "word" and operation == "target_subtract"):
            observe({
                **base,
                "lane": lane,
                "operation": operation,
                "counter": counter,
                "state": tuple(h),
            })

    for lane in range(8):
        active = lane if left else 8 + lane
        blit = 8 + lane if left else lane
        if left:
            target = lane + 1
        else:
            target = 8 + lane + 1 if lane < 7 else 0

        h[active] ^= data[lane]
        emit(lane, "data_xor")
        h[active] = (h[active] - K[lane]) & MASK
        emit(lane, "constant_subtract")
        h[active] = rotr(h[active], Z[lane])
        emit(lane, "rotate")
        h[blit] ^= h[active]
        emit(lane, "cross_half_xor")
        counter = (counter + h[active]) & MASK
        emit(lane, "counter_add")
        h[target] = (h[target] - counter) & MASK
        emit(lane, "target_subtract")
    return h


def invert_weakfunc(output, data, left):
    """Invert one production-v4 weak round for fixed data words."""
    if len(output) != 16 or len(data) != 8:
        raise ValueError("Rainstorm weakfunc inversion requires 16 state words")
    transformed = list(output[:8] if left else output[8:])
    base_counter = CTR_LEFT if left else CTR_RIGHT
    counters = []
    counter = base_counter
    for value in transformed:
        counters.append(counter)
        counter = (counter + value) & MASK
    incoming_active = []
    for lane, value in enumerate(transformed):
        before = (rotl(value, Z[lane]) + K[lane]) & MASK
        before ^= data[lane]
        if lane:
            before = (before + counters[lane]) & MASK
        incoming_active.append(before)
    if left:
        incoming_low = incoming_active
        incoming_high = [0] * 8
        incoming_high[0] = ((output[8] + counter) & MASK) ^ transformed[0]
        for lane in range(1, 8):
            incoming_high[lane] = output[8 + lane] ^ transformed[lane]
    else:
        incoming_high = incoming_active
        incoming_low = [0] * 8
        incoming_low[0] = ((output[0] + counter) & MASK) ^ transformed[0]
        for lane in range(1, 8):
            incoming_low[lane] = output[lane] ^ transformed[lane]
    return incoming_low + incoming_high


@dataclass
class HashResult:
    digest: bytes
    state: tuple
    folded: tuple
    tail_words: tuple
    trace: list


def hash_message(message, bits=256, seed=0, trace_level="none", rounds=4):
    """Hash one message and optionally return round, word, or operation traces."""
    if bits not in (64, 128, 256, 512):
        raise ValueError("bits must be 64, 128, 256, or 512")
    if trace_level not in ("none", "round", "word", "operation"):
        raise ValueError("trace_level must be none, round, word, or operation")
    if not 1 <= rounds <= 4:
        raise ValueError("rounds must be in 1..4")
    message = bytes(message)
    h = initial_state(len(message), seed)
    trace = []

    def record(event):
        trace.append(event)

    def checkpoint(stage, **metadata):
        if trace_level != "none":
            record({"stage": stage, **metadata, "state": tuple(h)})

    checkpoint("initial", phase="initial")
    full_blocks = len(message) // 64
    for block_index in range(full_blocks):
        block = message[block_index * 64:(block_index + 1) * 64]
        data = words(block)
        for round_index in range(rounds):
            context = {
                "stage": f"message[{block_index}]/round[{round_index}]",
                "phase": "message",
                "block_index": block_index,
                "round_index": round_index,
            }
            h = weakfunc(
                h, data, bool(round_index & 1), record, context, trace_level)
            checkpoint(**context, direction="left" if round_index & 1 else "right")

    remainder = len(message) % 64
    fill = (0x80 + remainder) & 0xFF
    tail = message[full_blocks * 64:] + bytes([fill]) * (64 - remainder)
    tail_data = words(tail)
    for round_index in range(rounds):
        context = {
            "stage": f"tail/round[{round_index}]",
            "phase": "tail",
            "block_index": full_blocks,
            "round_index": round_index,
        }
        h = weakfunc(h, tail_data, bool(round_index & 1), record, context, trace_level)
        checkpoint(**context, direction="left" if round_index & 1 else "right")

    for lane in range(8):
        h[lane] = (h[lane] - h[8 + lane]) & MASK
    folded = tuple(h[:8])
    checkpoint("fold", phase="fold")

    final_rounds = max(bits // 64, 2) if bits > 64 else 0
    for round_index in range(final_rounds):
        context = {
            "stage": f"final/round[{round_index}]",
            "phase": "final",
            "block_index": full_blocks,
            "round_index": round_index,
        }
        h = weakfunc(h, tail_data, True, record, context, trace_level)
        checkpoint(**context, direction="left")

    digest = b"".join(value.to_bytes(8, "little")
                       for value in h[:bits // 64])
    return HashResult(
        digest=digest,
        state=tuple(h),
        folded=folded,
        tail_words=tuple(tail_data),
        trace=trace,
    )


def paired_message(message, relation="xor", difference=1, rotation=1):
    """Construct a same-length paired message under a declared relation."""
    message = bytes(message)
    width = 8 * len(message)
    if width == 0:
        raise ValueError("a paired experiment requires a nonempty message")
    modulus = 1 << width
    if relation == "xor":
        if not 0 < difference < modulus:
            raise ValueError("XOR difference must be nonzero and fit the message")
        return (int.from_bytes(message, "little") ^ difference).to_bytes(len(message), "little")
    if relation == "add":
        if difference % modulus == 0:
            raise ValueError("additive difference must be nonzero modulo the message width")
        value = (int.from_bytes(message, "little") + difference) % modulus
        return value.to_bytes(len(message), "little")
    if relation == "rx":
        if len(message) % 8:
            raise ValueError("wordwise RX pairing requires a multiple-of-eight length")
        if not 1 <= rotation < 64:
            raise ValueError("RX rotation must be in 1..63")
        if not 0 <= difference < modulus:
            raise ValueError("RX difference must fit the message")
        output = bytearray()
        for offset in range(0, len(message), 8):
            word = int.from_bytes(message[offset:offset + 8], "little")
            delta = (difference >> (8 * offset)) & MASK
            output.extend((rotl(word, rotation) ^ delta).to_bytes(8, "little"))
        return bytes(output)
    raise ValueError("relation must be xor, add, or rx")


def relation_word_differences(left, right, relation="xor", rotation=1):
    """Compare paired word vectors in the selected difference representation."""
    if len(left) != len(right):
        raise ValueError("paired word vectors must have equal length")
    if relation == "xor":
        return [a ^ b for a, b in zip(left, right)]
    if relation == "add":
        return [(b - a) & MASK for a, b in zip(left, right)]
    if relation == "rx":
        if not 1 <= rotation < 64:
            raise ValueError("RX rotation must be in 1..63")
        return [b ^ rotl(a, rotation) for a, b in zip(left, right)]
    raise ValueError("relation must be xor, add, or rx")
