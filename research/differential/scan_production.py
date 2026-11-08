#!/usr/bin/env python3
"""Run the endpoint differential scanner on current production Rainstorm."""
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from suite import MASK, scan


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRODUCTION_SOURCE = ROOT / "src/rainstorm.cpp"
COMMON_SOURCE = ROOT / "src/common.h"
BRIDGE_SOURCE = HERE / "production_native.cpp"


class ProductionNative:
    def __init__(self):
        if sys.byteorder != "little":
            raise RuntimeError("This scanner currently targets little-endian output.")
        self._temporary = tempfile.TemporaryDirectory(prefix="rain-production-differential-")
        library = Path(self._temporary.name) / "production-native.so"
        subprocess.run([
            os.environ.get("CXX", "c++"), "-std=c++17", "-O3", "-shared", "-fPIC",
            str(BRIDGE_SOURCE), "-o", str(library),
        ], check=True)
        self._library = C.CDLL(str(library))
        self._library.rainstorm_hash_many.argtypes = [
            C.c_uint, C.c_uint64, C.c_void_p, C.c_size_t, C.c_size_t, C.c_void_p,
        ]
        self._library.rainstorm_hash_many.restype = C.c_int

    def hashes(self, algo, bits, seed, data, length, count):
        if algo != 1:
            raise ValueError("ProductionNative exposes Rainstorm only")
        if len(data) != length * count:
            raise ValueError("input batch length does not match length*count")
        output = C.create_string_buffer(count * (bits // 8))
        if self._library.rainstorm_hash_many(bits, seed, data, length, count, output):
            raise ValueError("unsupported Rainstorm output size")
        return output.raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bits", type=int, choices=(64, 128, 256, 512))
    parser.add_argument("--lengths", type=int, nargs="+", default=[1, 15, 16, 17, 63, 64, 65])
    parser.add_argument("--samples", type=int, default=4096)
    parser.add_argument("--batch", type=int, default=1024)
    parser.add_argument("--all-bits", action="store_true")
    parser.add_argument("--masks", nargs="*", help="additional hexadecimal XOR masks")
    parser.add_argument("--hash-seed", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--replay-seed", type=int)
    parser.add_argument("--alpha", type=float, default=0.01)
    parser.add_argument("--p-min", type=float, default=0.01)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not (args.samples > 0 and args.batch > 0 and 0 < args.alpha < 1 and
            0 < args.p_min < 1 and all(length > 0 for length in args.lengths) and
            0 <= args.hash_seed <= MASK):
        parser.error("invalid sample, probability, length, or hash-seed argument")

    scan_args = argparse.Namespace(
        lengths=args.lengths,
        all_bits=args.all_bits,
        masks=args.masks,
        algorithm="rainstorm",
        bits=args.bits,
        alpha=args.alpha,
        samples=args.samples,
        batch=args.batch,
        replay_seed=args.replay_seed,
        hash_seed=args.hash_seed,
        p_min=args.p_min,
    )
    native = ProductionNative()
    vectors = {
        b"": "bf6aa062a4c6ccf8b69697494100743f24da78e0e0140af278f3156772734b49",
        b"The quick brown fox jumps over the lazy dog":
            "2343e4baabecf8be423ab643fcdfa113e14bf75e7a5f8a6a37f02a260282ac45",
    }
    for message, expected in vectors.items():
        actual = native.hashes(1, 256, 0, message, len(message), 1).hex()
        if actual != expected:
            raise SystemExit("production bridge failed a published Rainstorm-256 vector")
    result = scan(native, scan_args)
    result["implementation"] = "current production Rainstorm"
    result["production_version"] = "4.0.0"
    result["published_vector_checks"] = len(vectors)
    result["source_sha256"] = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (
            PRODUCTION_SOURCE, COMMON_SOURCE, BRIDGE_SOURCE,
            HERE / "suite.py", Path(__file__),
        )
    }
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
