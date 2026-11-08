#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

echo "RAIN HASHES"
echo "C++ test vectors"
echo "Rainbow test vectors:"
./rainsum --test-vectors -a rainbow -s 256
echo "Rainstorm test vectors:"
./rainsum --test-vectors -a rainstorm -s 256
echo "JavaScript/WASM test vectors"
echo "Rainbow test vectors:"
./js/rainsum.mjs --test-vectors -a rainbow -s 256 | sed 's/[[:blank:]]*$//'
echo "Rainstorm test vectors:"
./js/rainsum.mjs --test-vectors -a rainstorm -s 256 | sed 's/[[:blank:]]*$//'
