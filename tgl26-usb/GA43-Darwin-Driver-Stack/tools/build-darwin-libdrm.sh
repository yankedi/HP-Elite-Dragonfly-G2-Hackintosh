#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=${1:?fresh absolute output prefix required}
HEADERS=/nix/store/6g92fqnx6cwza2243r78p7rqmay8ssik-libdrm-2.4.131-dev
: "${DARWIN_CC:?}" "${DARWIN_SDK:?}" "${DARWIN_LD:?}"
mkdir "$OUT"
mkdir "$OUT/include" "$OUT/include/libdrm" "$OUT/lib"
# Public DRM API/UAPI headers only, never Linux libc or kernel implementation.
cp "$HEADERS/include/xf86drm.h" "$HEADERS/include/xf86drmMode.h" "$OUT/include/"
cp "$HEADERS/include/libdrm/"*.h "$OUT/include/libdrm/"
"$DARWIN_CC" -target x86_64-apple-macos26 -isysroot "$DARWIN_SDK" \
    -std=c11 -Wall -Wextra -Werror -I"$OUT/include" -I"$OUT/include/libdrm" \
    -I"$ROOT/libdrm-darwin/include" -c "$ROOT/libdrm-darwin/drm_darwin.c" \
    -o "$OUT/drm_darwin.o"
"$DARWIN_CC" -target x86_64-apple-macos26 -isysroot "$DARWIN_SDK" \
    -std=c11 -Wall -Wextra -Werror -I"$OUT/include" -I"$OUT/include/libdrm" \
    -c "$ROOT/libdrm-darwin/drm_syncobj.c" -o "$OUT/drm_syncobj.o"
"$DARWIN_LD" -arch x86_64 -platform_version macos 26.0 26.5 -dylib \
    -undefined error -syslibroot "$DARWIN_SDK" -lSystem \
    -install_name @rpath/libdrm.dylib -o "$OUT/lib/libdrm.dylib" "$OUT/drm_darwin.o" "$OUT/drm_syncobj.o"
python3 -B "$ROOT/tools/inspect-darwin-probe.py" "$OUT/lib/libdrm.dylib" \
    --kind dylib --id @rpath/libdrm.dylib --allow /usr/lib/libSystem.B.dylib \
    --require /usr/lib/libSystem.B.dylib --export _drmIoctl --export _drmGetVersion \
    --export _drmGetDevices2
"$DARWIN_LLVM_BIN/llvm-readobj" --file-headers --symbols --needed-libs \
    "$OUT/lib/libdrm.dylib" > "$OUT/inspection.txt"
sha256sum "$ROOT/libdrm-darwin/drm_darwin.c" "$ROOT/libdrm-darwin/drm_syncobj.c" "$DARWIN_CC" "$DARWIN_LD" \
    "$OUT/drm_darwin.o" "$OUT/drm_syncobj.o" "$OUT/lib/libdrm.dylib" > "$OUT/SHA256SUMS"
echo 'PASS strict Darwin libdrm subset link; fd transport/runtime NOT_TESTED'
