#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
actual=$(mktemp -t rain-vectors.XXXXXXXX)
trap 'rm -f -- "$actual"' EXIT
./scripts/vectors.sh > "$actual"
diff -u verification/vectors.txt "$actual"
echo "The native and JavaScript/WASM vectors match."
