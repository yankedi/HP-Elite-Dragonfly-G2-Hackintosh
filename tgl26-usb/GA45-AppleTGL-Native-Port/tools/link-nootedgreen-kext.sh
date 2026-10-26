#!/usr/bin/env bash
# Offline kext-link probe.  This never installs or loads anything.
# Success criterion is an actual MH_KEXT_BUNDLE; an exit 0 / MH_EXECUTE is not.
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OBJ=${1:-"$ROOT/logs/build/objects-current"}
OUT=${2:-"$ROOT/logs/build/kext-link"}
LD=${LD64_LLD:-/nix/store/3naz0qnnfax2pdvwlgmjd3j57axrass4-lld-21.1.8/bin/ld64.lld}
SDK=${SDKROOT:-"$ROOT/toolchain/MacOSX26.5.sdk"}
mkdir -p "$OUT"
for f in "$OBJ"/*.o; do [ -f "$f" ] || { echo "missing object: $f"; exit 2; }; done
set -- "$OBJ"/*.o
echo "objects=$# libkmod=$SDK/usr/lib/libkmod.a"
echo "== ld64.lld -kext =="
"$LD" -arch x86_64 -kext -platform_version macos 26.0 26.0 -syslibroot "$SDK" \
  -o "$OUT/NootedGreen.kext" "$@" "$SDK/usr/lib/libkmod.a" \
  >"$OUT/kext.stdout" 2>"$OUT/kext.stderr"
echo "kext_link_exit=$?"
cat "$OUT/kext.stderr" | tail -20
if [ -f "$OUT/NootedGreen.kext" ]; then
  echo "== produced file =="
  file "$OUT/NootedGreen.kext"
  /nix/store/62xr80awfwywf5zggcx3gc0cxnpnsr24-llvm-21.1.8/bin/llvm-readobj --file-headers "$OUT/NootedGreen.kext" | grep -E 'FileType|MH_' | head -10
else
  echo "no output produced"
fi
echo "== ld64.lld -bundle (diagnostic only; MH_BUNDLE is not a kext) =="
"$LD" -arch x86_64 -bundle -platform_version macos 26.0 26.0 -syslibroot "$SDK" -undefined dynamic_lookup \
  -o "$OUT/NootedGreen.bundle" "$@" \
  >"$OUT/bundle.stdout" 2>"$OUT/bundle.stderr"
echo "bundle_link_exit=$?"
if [ -f "$OUT/NootedGreen.bundle" ]; then
  file "$OUT/NootedGreen.bundle"
  /nix/store/62xr80awfwywf5zggcx3gc0cxnpnsr24-llvm-21.1.8/bin/llvm-readobj --file-headers "$OUT/NootedGreen.bundle" | grep -E 'FileType|MH_' | head -10
fi
