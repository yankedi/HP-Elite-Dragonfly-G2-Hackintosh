#!/usr/bin/env bash
# Offline object build for the GA4.5 NootedGreen source.
# This does NOT produce or load a kext; it produces x86_64 Mach-O objects only.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=${1:-"$ROOT/logs/build/objects"}
mkdir -p "$OUT"
CLANG=${CLANG:-clang++}
CFLAGS=(
  -target x86_64-apple-macos13.0 -mkernel -nostdinc -nostdinc++
  -fno-builtin -fno-common -fno-stack-protector
  -DKERNEL -DKERNEL_PRIVATE -DDRIVER_PRIVATE -DAPPLE -DNeXT
  -DDEBUG=1 -DAPPLE_KEXT_ASSERTIONS=1
  -DPRODUCT_NAME=NootedGreen -DMODULE_VERSION=1.0.0
  -isystem "$ROOT/extern/MacKernelSDK/Headers"
  -I"$ROOT/extern/Lilu"
  -I"$ROOT/src/NootedGreen"
  -std=gnu++17 -fno-exceptions -fno-rtti -fapple-kext
  -Wno-deprecated-declarations -Wno-inconsistent-missing-override
  -Wno-unused-parameter
)
status=0
for src in "$ROOT"/src/NootedGreen/*.cpp; do
  case "$(basename "$src")" in
    # Optional network debug helper needs libc++ (<cstdarg>); not part of the
    # 12-object NootedGreen build baseline.
    kern_netdbg.cpp) echo "SKIP kern_netdbg.cpp (needs libc++)"; continue ;;
  esac
  obj="$OUT/$(basename "${src%.cpp}").o"
  echo "CC $(basename "$src")"
  if ! "$CLANG" "${CFLAGS[@]}" -c "$src" -o "$obj"; then status=1; fi
done
# Lilu plugin entry point used by the stock project layout.
echo "CC plugin_start.cpp"
if ! "$CLANG" "${CFLAGS[@]}" -I"$ROOT/extern/Lilu" -c "$ROOT/extern/Lilu/Library/plugin_start.cpp" -o "$OUT/plugin_start.o"; then status=1; fi
exit "$status"
