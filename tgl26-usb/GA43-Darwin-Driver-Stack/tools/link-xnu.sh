#!/usr/bin/env bash
set -euo pipefail
# GA43 real offline module link attempt. All ABI-affected units are compiled
# together; four unchanged objects must match the pinned inherited seal.
# Module link/import inspection is NOT target KPI/KernelCollection acceptance.
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OUT=${GA43_XNU_LINK_OUT:?set a fresh output directory}
OLD=${GA43_INHERITED_OBJECTS:?set the verified GA42 native-final-001 directory}
SDK=${GA43_KERNEL_SDK:?set actual public kernel SDK root (not user SDK)}
LD=${GA43_DARWIN_LD:?set actual linker executable}
LLVM=${GA43_LLVM_BIN:?set LLVM Mach-O inspection tools directory}
python3 -B "$ROOT/tools/verify-inherited-native.py" "$OLD" "$SDK"
mkdir -p "$(dirname "$OUT")"
mkdir "$OUT"
GA43_CHANGED_ONLY=1 GA41_XNU_OUT="$OUT/objects" bash "$ROOT/tools/compile-xnu.sh"
OBJECTS=("$OUT/objects/GX42Service.o" "$OUT/objects/gx_gem.o"
    "$OUT/objects/gx_ioctl.o" "$OUT/objects/gx_client.o" "$OUT/objects/gx_vm.o"
    "$OLD/xnu_memory.o" "$OLD/xnu_copy.o" "$OLD/gx_exec_validate.o" "$OLD/module.o")
sha256sum "${OBJECTS[@]}" "$SDK/Library/x86_64/libkmod.a" "$LD" > "$OUT/link-inputs.sha256"
git -C "$ROOT" rev-parse HEAD > "$OUT/source-head.txt"
git -C "$ROOT" diff -- i915-xnu tools/compile-xnu.sh > "$OUT/source-diff.patch"
find "$ROOT/i915-xnu" -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > "$OUT/source.sha256"
for obj in "${OBJECTS[@]}"; do
    "$LLVM/llvm-readobj" --file-headers "$obj" > "$OUT/$(basename "$obj").header.txt"
    grep -q 'Format: Mach-O 64-bit x86-64' "$OUT/$(basename "$obj").header.txt"
    grep -q 'FileType: Relocatable' "$OUT/$(basename "$obj").header.txt"
done
"$LLVM/llvm-nm" -u "${OBJECTS[@]}" > "$OUT/undefined-inputs.txt"
file "${OBJECTS[@]}"
FLAGS=(-arch x86_64 -kext -o "$OUT/GX43-module")
if [[ ${GA43_LINK_RELOCATABLE:-0} == 1 ]]; then
    FLAGS=(-arch x86_64 -r -o "$OUT/GX43-unit.o")
fi
if [[ ${GA43_LEGACY_LLD:-0} == 1 ]]; then
    FLAGS=(-flavor darwin "${FLAGS[@]}" -macosx_version_min 26.0 -sdk_version 26.0)
else
    FLAGS+=( -platform_version macos 26.0 26.0 )
fi
# No -undefined dynamic_lookup, -U wildcard, fabricated kernel export list,
# dylib stand-in, or archive renamed as a module.
printf 'link command: '
printf '%q ' "$LD" "${FLAGS[@]}" "${OBJECTS[@]}" "$SDK/Library/x86_64/libkmod.a"
printf '\n'
"$LD" "${FLAGS[@]}" "${OBJECTS[@]}" "$SDK/Library/x86_64/libkmod.a"
if [[ ${GA43_LINK_RELOCATABLE:-0} == 1 ]]; then
    "$LLVM/llvm-readobj" --file-headers --symbols "$OUT/GX43-unit.o" > "$OUT/unit-inspection.txt"
    grep -q 'FileType: Relocatable' "$OUT/unit-inspection.txt"
    "$LLVM/llvm-nm" -u "$OUT/GX43-unit.o" > "$OUT/unit-imports.txt"
    if grep -E '(^|[[:space:]])_gx_' "$OUT/unit-imports.txt"; then
        echo 'FAIL unresolved internal gx symbol' >&2; exit 3
    fi
    sha256sum "$OUT/GX43-unit.o"
    echo 'PARTIAL: verified MH_OBJECT combination, not a kext'
    exit 0
fi
"$LLVM/llvm-readobj" --file-headers --symbols "$OUT/GX43-module" > "$OUT/module-inspection.txt"
"$LLVM/llvm-objdump" --macho --private-headers "$OUT/GX43-module" > "$OUT/module-loadcommands.txt"
"$LLVM/llvm-nm" -u "$OUT/GX43-module" > "$OUT/module-imports.txt"
if grep -Eq '(^|[[:space:]])___cxa_atexit$' "$OUT/module-imports.txt"; then
    echo 'FAIL: kernel module requires user atexit runtime' >&2; exit 3
fi
grep -q 'KextBundle' "$OUT/module-inspection.txt" || {
    echo 'FAIL: output is not MH_KEXT_BUNDLE' >&2; exit 3;
}
sha256sum "$OUT/GX43-module"
echo 'PARTIAL: module container only; imports/target KPI/KernelCollection validation still required'
