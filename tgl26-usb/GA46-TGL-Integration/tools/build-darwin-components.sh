#!/usr/bin/env bash
# GA46 offline Darwin userspace build. No target execution or installation.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SDK=${SDKROOT:?set SDKROOT to a legally obtained complete macOS SDK}
CLANG=${CLANG_APPLE:-$(command -v clang-21 || command -v clang || true)}
LD=${LD64_LLD:-$(command -v ld64.lld || true)}
: "${CLANG:?set CLANG_APPLE to an Apple-targeting Clang executable}"
: "${LD:?set LD64_LLD to ld64.lld}"
OUT=${1:-"$ROOT/logs/build/darwin-components"}
test ! -e "$OUT"
mkdir -p "$(dirname "$OUT")"
mkdir "$OUT"
if [ ! -d "$SDK" ]; then echo "BLOCKED_SDK: $SDK absent"; exit 2; fi
TARGET=x86_64-apple-macos26.0
COMMON=(-target "$TARGET" -isysroot "$SDK" -O2 -fPIC)

cc_obj() { local src=$1 obj=$2; shift 2; "$CLANG" "${COMMON[@]}" "$@" -c "$src" -o "$obj"; }
link_dylib() { local out=$1 install=$2; shift 2; "$LD" -dylib -arch x86_64 -platform_version macos 26.0 26.0 -syslibroot "$SDK" -install_name "$install" -o "$out" "$@"; }

cc_obj "$ROOT/src/libxedrv.m" "$OUT/libxedrv.o" -fobjc-runtime=macosx-10.15 -Isrc
link_dylib "$OUT/libxedrv.dylib" @rpath/libxedrv.dylib \
  -framework Foundation -framework Metal -framework IOSurface -framework IOKit -lSystem -lobjc \
  "$OUT/libxedrv.o"

cc_obj "$ROOT/src/compiler-adapter.cpp" "$OUT/compiler-adapter.o" -std=c++17 -fno-exceptions -fno-rtti -Isrc
link_dylib "$OUT/libMTLIGCCompilerPlugin.dylib" @rpath/libMTLIGCCompilerPlugin.dylib \
  -lc++ -lSystem "$OUT/compiler-adapter.o"

cc_obj "$ROOT/src/llvm-bridge.cpp" "$OUT/llvm-bridge.o" -std=c++17 -fno-exceptions -fno-rtti -Isrc
link_dylib "$OUT/libLLVMbridge.dylib" @rpath/libLLVMbridge.dylib \
  -lc++ -lSystem "$OUT/llvm-bridge.o"

cc_obj "$ROOT/tools/metal-abi-probe.m" "$OUT/metal-abi-probe.o" -fobjc-runtime=macosx-10.15 -Isrc
"$LD" -execute -arch x86_64 -platform_version macos 26.0 26.0 -syslibroot "$SDK" \
  -framework Foundation -framework Metal -lSystem -lobjc \
  -o "$OUT/metal-abi-probe" "$OUT/metal-abi-probe.o"

cc_obj "$ROOT/tools/compiler-runtime-probe.cpp" "$OUT/compiler-runtime-probe.o" -std=c++17 -fno-exceptions -fno-rtti
"$LD" -execute -arch x86_64 -platform_version macos 26.0 26.0 -syslibroot "$SDK" \
  -lc++ -lSystem -o "$OUT/compiler-runtime-probe" "$OUT/compiler-runtime-probe.o"

for f in libxedrv.dylib libMTLIGCCompilerPlugin.dylib libLLVMbridge.dylib metal-abi-probe compiler-runtime-probe; do
  test -f "$OUT/$f"
  file "$OUT/$f"
  python3 "$ROOT/tools/macho-audit.py" "$OUT/$f" > "$OUT/$f.macho.json"
done
