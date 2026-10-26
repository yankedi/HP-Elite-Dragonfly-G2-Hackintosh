#!/usr/bin/env bash
set -euo pipefail
# Offline target attempt. A successful -r link is only DARWIN_LINK(unit),
# never a resolved Tahoe kext. KDK symbol resolution is a separate required step.
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OUT=${GA42_XNU_LINK_OUT:?set a fresh output directory}
mkdir "$OUT"
GA41_XNU_OUT="$OUT/objects" bash "$ROOT/tools/compile-xnu.sh"
LLVM=/nix/store/62xr80awfwywf5zggcx3gc0cxnpnsr24-llvm-21.1.8/bin
"$LLVM/llvm-nm" -u "$OUT/objects"/*.o > "$OUT/undefined-before-link.txt"
python3 -B - "$ROOT/i915-xnu/native/Info.plist" <<'PY'
import plistlib,sys
d=plistlib.load(open(sys.argv[1],'rb'))
p=d['IOKitPersonalities']['GA42IntelGEMDiagnostics']
assert p['IOPCIPrimaryMatch']=='0x9a498086'
assert p['IOClass']=='GX42Service' and p['IOProviderClass']=='IOPCIDevice'
assert not any(k in p for k in ['MetalPluginName','MetalPluginClassName','nmxgpu-claimed'])
print('Personality: real CPU-only IOService; no accelerator identity')
PY
if command -v ld64.lld >/dev/null; then
    ld64.lld -r -arch x86_64 -platform_version macos 26.0 26.0 \
        -o "$OUT/GX42-unit.o" "$OUT/objects"/*.o
elif command -v ld64 >/dev/null; then
    ld64 -r -arch x86_64 -o "$OUT/GX42-unit.o" "$OUT/objects"/*.o
else
    # Preserve the actual toolchain diagnostic instead of manufacturing a link
    # by archiving .o files or accepting unresolved symbols in a fake dylib.
    /nix/store/jmgw1yz3xm3bpgrk9r84jkcynskdbd40-clang-21.1.8/bin/clang++ \
        -target x86_64-apple-macos26 -nostdlib -fuse-ld=lld -Wl,-r \
        -o "$OUT/GX42-unit.o" "$OUT/objects"/*.o
fi
file "$OUT/GX42-unit.o"
"$LLVM/llvm-nm" -u "$OUT/GX42-unit.o" > "$OUT/undefined-after-link.txt"
echo 'PARTIAL: unit link only; exact 25G83 KDK symbol resolution absent'
