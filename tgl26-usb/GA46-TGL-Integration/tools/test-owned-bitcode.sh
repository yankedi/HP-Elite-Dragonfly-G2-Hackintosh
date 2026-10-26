#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=${1:?unique output directory required}
mkdir "$OUT"
CLANG=${CLANG:-/nix/store/wra7pnc8v3vk7xl597kq79bbmvncxz8j-clang-21.1.8/bin/clang-21}
LLVM=${LLVM_HOST:-/nix/store/s6v0k4cvllyp5cy03ngxz0snj7z23ljm-llvm-21.1.8-lib/lib/libLLVM.so}
"$CLANG" -emit-llvm -c -O1 "$ROOT/tests/compiler-bitcode-fixture.c" -o "$OUT/input.bc"
c++ -std=c++17 -Wall -Wextra -Werror -g -O1 -fsanitize=address,undefined \
  -pthread "$ROOT/tests/test_owned_bitcode.cpp" -ldl -o "$OUT/test-owned-bitcode"
ASAN_OPTIONS=detect_leaks=1 "$OUT/test-owned-bitcode" "$LLVM" "$OUT/input.bc" "$OUT/roundtrip.bc"
DIS=/nix/store/62xr80awfwywf5zggcx3gc0cxnpnsr24-llvm-21.1.8/bin/llvm-dis
"$DIS" "$OUT/roundtrip.bc" -o "$OUT/roundtrip.ll"
grep -q 'define.*@ga46_add' "$OUT/roundtrip.ll"
grep -q 'define.*@ga46_accumulate' "$OUT/roundtrip.ll"
echo 'CPU bitcode function/metadata retained; NOT MTL3902 or target ABI validation'
