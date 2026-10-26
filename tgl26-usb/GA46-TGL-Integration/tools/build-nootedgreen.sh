#!/usr/bin/env bash
# Offline kernel object build; matches the upstream kext target semantics.
# This does NOT produce or load a kext; it produces x86_64 Mach-O objects only.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=${1:-"$ROOT/logs/build/objects"}
mkdir -p "$OUT"
CLANG=${CLANG:-/nix/store/wra7pnc8v3vk7xl597kq79bbmvncxz8j-clang-21.1.8/bin/clang-21}
CFLAGS=(
  -target x86_64-apple-macos13.0 -mkernel -nostdinc -nostdinc++
  -fno-builtin -fno-common -fno-stack-protector
  -DKERNEL -DKERNEL_PRIVATE -DDRIVER_PRIVATE -DAPPLE -DNeXT
  -DDEBUG=1 -DAPPLE_KEXT_ASSERTIONS=1
  -DPRODUCT_NAME=NootedGreen -DMODULE_VERSION=1.0.0
  -DGA46_NATIVE_ONLY=1
  -isystem "$ROOT/extern/MacKernelSDK/Headers"
  -I"$ROOT/extern/Lilu"
  -I"$ROOT/src/NootedGreen"
  -std=gnu++17 -fno-exceptions -fno-rtti -fapple-kext
  -fno-use-cxa-atexit -fno-register-global-dtors-with-atexit
  -mllvm -disable-atexit-based-global-dtor-lowering
  -fno-asynchronous-unwind-tables -fvisibility=hidden
  -mmmx -msse -msse2 -msse3 -mssse3 -msse4.1
  -Wno-deprecated-declarations -Wno-inconsistent-missing-override
  -Wno-unused-parameter
)
status=0
for src in "$ROOT"/src/NootedGreen/*.cpp; do
  obj="$OUT/$(basename "${src%.cpp}").o"
  echo "CC $(basename "$src")"
  if ! "$CLANG" "${CFLAGS[@]}" -c "$src" -o "$obj"; then status=1; fi
done
# Lilu plugin entry point used by the stock project layout.
echo "CC plugin_start.cpp"
if ! "$CLANG" "${CFLAGS[@]}" -I"$ROOT/extern/Lilu" -c "$ROOT/extern/Lilu/Library/plugin_start.cpp" -o "$OUT/plugin_start.o"; then status=1; fi
"$CLANG" -target x86_64-apple-macos13.0 -mkernel -fno-builtin \
  -fno-stack-protector -fno-asynchronous-unwind-tables -fvisibility=hidden \
  -nostdinc -isystem "$ROOT/extern/MacKernelSDK/Headers" \
  -DKERNEL -DKERNEL_PRIVATE -DDRIVER_PRIVATE \
  -c "$ROOT/nootedgreen/module-info.c" -o "$OUT/module-info.o"
exit "$status"
