#!/usr/bin/env bash
# Build isolated public LLVM PR204805. Never install into the host toolchain.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PIN=d575e43643f7c90a1a2728352a24867d7105d9e9
SRC="$ROOT/toolchain/pr204805/llvm-project-$PIN"
BUILD="$ROOT/toolchain/pr204805/build"
test -f "$SRC/lld/MachO/Driver.cpp"
cmake -S "$SRC/llvm" -B "$BUILD" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DLLVM_ENABLE_PROJECTS=lld \
  -DLLVM_APPEND_VC_REV=OFF \
  -DLLVM_TARGETS_TO_BUILD=X86 -DLLVM_ENABLE_ASSERTIONS=ON \
  -DLLVM_INCLUDE_TESTS=ON -DLLVM_INCLUDE_BENCHMARKS=OFF \
  -DLLVM_ENABLE_ZLIB=OFF -DLLVM_ENABLE_ZSTD=OFF \
  -DLLVM_ENABLE_LIBXML2=OFF -DLLVM_ENABLE_TERMINFO=OFF \
  -DLLVM_PARALLEL_LINK_JOBS=1
cmake --build "$BUILD" --parallel "${JOBS:-6}" --target \
  lld llvm-mc llvm-readobj llvm-objdump llvm-nm llvm-objcopy FileCheck split-file llvm-ar yaml2obj not count llvm-config
ln -sfn llvm-objcopy "$BUILD/bin/llvm-strip"
"$BUILD/bin/ld64.lld" --version
