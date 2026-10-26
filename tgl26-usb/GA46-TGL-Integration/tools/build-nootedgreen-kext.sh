#!/usr/bin/env bash
# Actual MH_KEXT_BUNDLE, then an independent symbol-provider gate. No loading.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=${1:?unique output directory required}
mkdir "$OUT"
bash "$ROOT/tools/build-nootedgreen.sh" "$OUT/objects"
BIN=${NOOTEDGREEN_TOOLCHAIN_BIN:-"$ROOT/toolchain/pr204805/build/bin"}
SDK=${SDKROOT:?set SDKROOT to a legally obtained complete macOS SDK}
BUNDLE="$OUT/NootedGreen.kext"
mkdir -p "$BUNDLE/Contents/MacOS"
"$BIN/ld64.lld" -arch x86_64 -platform_version macos 26.5 26.5 -kext -static \
  -o "$BUNDLE/Contents/MacOS/NootedGreen" "$OUT"/objects/*.o "$SDK/usr/lib/libkmod.a"
python3 - "$ROOT" "$BUNDLE" <<'PY'
from pathlib import Path
import plistlib,sys
r,b=map(Path,sys.argv[1:]);p=plistlib.loads((r/'src/NootedGreen/Info.plist').read_bytes())
def expand(v):
    if isinstance(v,dict):return {k:expand(x) for k,x in v.items()}
    if isinstance(v,list):return [expand(x) for x in v]
    if isinstance(v,str):return v.replace('$(PRODUCT_NAME)','NootedGreen').replace('${PRODUCT_NAME}','NootedGreen').replace('$(MODULE_VERSION)','1.0.0').replace('$(PRODUCT_BUNDLE_IDENTIFIER)','com.StezzaPilot.NootedGreen')
    return v
p=expand(p)
assert p['CFBundleExecutable']=='NootedGreen' and p['CFBundlePackageType']=='KEXT'
assert p['CFBundleIdentifier']=='com.StezzaPilot.NootedGreen'
assert 'as.vit9696.Lilu' in p['OSBundleLibraries']
(b/'Contents/Info.plist').write_bytes(plistlib.dumps(p))
PY
python3 "$ROOT/tools/macho-audit.py" --kext "$BUNDLE/Contents/MacOS/NootedGreen" > "$OUT/structure.json"
python3 "$ROOT/tools/audit-kernel-symbols.py" "$BUNDLE/Contents/MacOS/NootedGreen" > "$OUT/symbol-providers.json"
"$BIN/llvm-objdump" --macho --private-headers -r "$BUNDLE/Contents/MacOS/NootedGreen" > "$OUT/structure.txt"
echo 'KEXT_LINKED; KEXT_FILETYPE_VALID; KEXT_RELOCATIONS_VALID; KERNEL_SYMBOLS_AUDITED; ABI_UNVERIFIED; GPU_NOT_TESTED'
