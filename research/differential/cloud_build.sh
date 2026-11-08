#!/usr/bin/env bash
# Run from the extracted bundle directory on Linux, after installing dependencies.
set -euo pipefail
ncpu=${1:-32}
[[ "$ncpu" =~ ^[1-9][0-9]*$ ]] || exit 2
python3 - <<'PY'
import hashlib,json
from pathlib import Path
for name, expected in json.loads(Path('source-manifest.json').read_text()).items():
    if hashlib.sha256((Path('smhasher3')/name).read_bytes()).hexdigest() != expected:
        raise SystemExit('Source fingerprint mismatch: '+name)
PY
# Upstream AEStest.cpp uses exit() without including its declaration on GCC.
# Supply the standard header without editing hash or statistical test sources.
cmake -S smhasher3 -B smhasher3/build -DCMAKE_BUILD_TYPE=Release \
  '-DCMAKE_CXX_FLAGS=-include cstdlib'
cmake --build smhasher3/build -j "$ncpu"
python3 cloud_run.py --ncpu "$ncpu"
