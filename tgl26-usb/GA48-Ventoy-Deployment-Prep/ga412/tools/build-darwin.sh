#!/bin/bash
# Build and CPU-test only. This script NEVER invokes managed-rt-probe.
set -euo pipefail
if [ "$#" -ne 1 ]; then
    echo "usage: build-darwin.sh NEW_BUILD_DIRECTORY" >&2
    exit 2
fi
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
OUT=$1
umask 077
mkdir "$OUT"
FLAGS=(-fobjc-arc -fno-modules -Wall -Wextra -Werror -framework Foundation -framework Metal)
/usr/bin/clang "${FLAGS[@]}" "$HERE/managed-rt-probe.m" -o "$OUT/managed-rt-probe"
/usr/bin/clang "${FLAGS[@]}" -dynamiclib "$HERE/trace-managed-cpu.m" -o "$OUT/trace-managed-cpu.dylib"
/usr/bin/clang "${FLAGS[@]}" "$HERE/inspect-texture-abi.m" -o "$OUT/inspect-texture-abi"
/usr/bin/clang "${FLAGS[@]}" "$HERE/test-trace-cpu.m" -o "$OUT/test-trace-cpu"
/usr/bin/clang "${FLAGS[@]}" -DBAD_ABI "$HERE/test-trace-cpu.m" -o "$OUT/test-trace-bad-abi"
"$OUT/test-trace-cpu" "$OUT/trace-managed-cpu.dylib" >"$OUT/cpu-test.stdout" 2>"$OUT/cpu-test.stderr"
"$OUT/test-trace-bad-abi" "$OUT/trace-managed-cpu.dylib" >"$OUT/bad-abi-test.stdout" 2>"$OUT/bad-abi-test.stderr"
/usr/bin/shasum -a 256 "$HERE"/*.m "$OUT/managed-rt-probe" "$OUT/trace-managed-cpu.dylib" "$OUT/inspect-texture-abi"
