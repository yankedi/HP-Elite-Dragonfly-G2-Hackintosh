#!/usr/bin/env bash
# GA4.5 offline Darwin userspace build.  No target execution and no installation.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SDK=${SDKROOT:-"$ROOT/toolchain/MacOSX26.5.sdk"}
CLANG=${CLANG_APPLE:-/nix/store/wra7pnc8v3vk7xl597kq79bbmvncxz8j-clang-21.1.8/bin/clang-21}
LD=${LD64_LLD:-/nix/store/3naz0qnnfax2pdvwlgmjd3j57axrass4-lld-21.1.8/bin/ld64.lld}
OUT=${1:-"$ROOT/logs/build/darwin-components"}
mkdir -p "$OUT"
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
link_dylib "$OUT/libMTLIGCCompilerPluginOld.dylib" @rpath/libMTLIGCCompilerPluginOld.dylib \
  -undefined dynamic_lookup -lc++ -lSystem "$OUT/compiler-adapter.o"

cc_obj "$ROOT/src/llvm-bridge.cpp" "$OUT/llvm-bridge.o" -std=c++17 -fno-exceptions -fno-rtti -Isrc
link_dylib "$OUT/libLLVMbridge.dylib" @rpath/libLLVMbridge.dylib \
  -undefined dynamic_lookup -lc++ -lSystem "$OUT/llvm-bridge.o"

cc_obj "$ROOT/tools/metal-abi-probe.m" "$OUT/metal-abi-probe.o" -fobjc-runtime=macosx-10.15 -Isrc
"$LD" -execute -arch x86_64 -platform_version macos 26.0 26.0 -syslibroot "$SDK" \
  -framework Foundation -framework Metal -lSystem -lobjc \
  -o "$OUT/metal-abi-probe" "$OUT/metal-abi-probe.o"

cc_obj "$ROOT/tools/compiler-runtime-probe.cpp" "$OUT/compiler-runtime-probe.o" -std=c++17 -fno-exceptions -fno-rtti
"$LD" -execute -arch x86_64 -platform_version macos 26.0 26.0 -syslibroot "$SDK" \
  -lc++ -lSystem -o "$OUT/compiler-runtime-probe" "$OUT/compiler-runtime-probe.o"

for f in libxedrv.dylib libMTLIGCCompilerPluginOld.dylib libLLVMbridge.dylib metal-abi-probe compiler-runtime-probe; do
  file "$OUT/$f"
done
