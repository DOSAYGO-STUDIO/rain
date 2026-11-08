#!/usr/bin/env bash
set -euo pipefail
WORK_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$WORK_DIR"

if [ ! -d smhasher3 ]; then
  git clone https://gitlab.com/fwojcik/smhasher3.git smhasher3
  git -C smhasher3 checkout 3b619371047761408406991685da1c2b3f751899
fi

rm -rf smhasher3/hashes/rainbow2_source
cp -r rainbow2_source smhasher3/hashes/rainbow2_source
cp rainbow2_core.cpp smhasher3/hashes/rainbow2_core.cpp
cp rainbow2_ladder.cpp smhasher3/hashes/rainbow2_ladder.cpp

grep -q 'hashes/rainbow2_ladder.cpp' smhasher3/hashes/Hashsrc.cmake || \
  printf '\nlist(APPEND HASH_SRC_FILES hashes/rainbow2_ladder.cpp)\n' >> smhasher3/hashes/Hashsrc.cmake

grep -q 'hashes/rainbow2_core.cpp' smhasher3/CMakeLists.txt || \
  printf '\ntarget_sources(SMHasher3Hashlib PRIVATE hashes/rainbow2_core.cpp)\n' >> smhasher3/CMakeLists.txt

NCPU=$(nproc)
cmake -S smhasher3 -B smhasher3/build -DCMAKE_BUILD_TYPE=Release '-DCMAKE_CXX_FLAGS=-include cstdlib'
cmake --build smhasher3/build -j "$NCPU"
echo "Build complete on $NCPU cores."
