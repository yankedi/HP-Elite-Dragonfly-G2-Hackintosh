#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=${1:?fresh output directory required}
: "${DARWIN_CC:?}" "${DARWIN_SDK:?}" "${DARWIN_LD:?}" "${DARWIN_LLVM_BIN:?}"
mkdir "$OUT"
"$DARWIN_CC" -target x86_64-apple-macos26 -isysroot "$DARWIN_SDK" -std=c11 \
    -Wall -Wextra -Werror -I"$ROOT/libdrm-darwin/include" -I"$ROOT/i915-xnu/include" \
    -c "$ROOT/libdrm-darwin/native_transport.c" -o "$OUT/native_transport.o"
"$DARWIN_LD" -arch x86_64 -platform_version macos 26.0 26.5 -dylib \
    -undefined error -syslibroot "$DARWIN_SDK" -lSystem -framework IOKit \
    -install_name @rpath/libdrm-native-transport.dylib \
    -o "$OUT/libdrm-native-transport.dylib" "$OUT/native_transport.o"
python3 -B "$ROOT/tools/inspect-darwin-probe.py" "$OUT/libdrm-native-transport.dylib" \
    --kind dylib --id @rpath/libdrm-native-transport.dylib \
    --allow /usr/lib/libSystem.B.dylib \
    --allow /System/Library/Frameworks/IOKit.framework/Versions/A/IOKit \
    --require /usr/lib/libSystem.B.dylib \
    --require /System/Library/Frameworks/IOKit.framework/Versions/A/IOKit \
    --export _drmDarwinNativeOpen --export _drmDarwinNativeIoctl \
    --export _drmDarwinNativeMapOffset --export _drmDarwinNativeUnmap --export _drmDarwinNativeClose
"$DARWIN_LLVM_BIN/llvm-readobj" --file-headers --symbols --needed-libs \
    "$OUT/libdrm-native-transport.dylib" > "$OUT/inspection.txt"
sha256sum "$ROOT/libdrm-darwin/native_transport.c" "$ROOT/i915-xnu/include/gx_user_abi.h" \
    "$DARWIN_CC" "$DARWIN_LD" "$OUT/native_transport.o" \
    "$OUT/libdrm-native-transport.dylib" > "$OUT/SHA256SUMS"
