#!/usr/bin/env bash
set -euo pipefail

# Compile only the four GA41 native adapter translation units.  This is a
# Darwin Mach-O object probe, not a KDK link, kext build, install, or load.
# MacKernelSDK is an open/public header kit; it is not an Apple user SDK.

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SDK="${GA43_KERNEL_SDK:-$ROOT/sources/mackernelsdk}"
HEADERS="$SDK/Headers"
OUT="${GA41_XNU_OUT:-$ROOT/build/xnu-header-check}"

if [[ ! -d "$HEADERS" ]]; then
    printf 'error: MacKernelSDK headers are absent: %s\n' "$HEADERS" >&2
    exit 2
fi

# Nix's clang++ wrapper injects a Linux linker/toolchain.  Discover the real
# compiler and its resource directory from the wrapper and nix-support rather
# than invoking the wrapped driver with a Darwin target.
CLANG_WRAPPER=${CLANG_WRAPPER:-$(readlink -f "$(command -v clang++)")}
NIX_SUPPORT=$(dirname "$CLANG_WRAPPER")/../nix-support
if [[ ! -f "$NIX_SUPPORT/cc-cflags" ]]; then
    printf 'error: clang wrapper nix-support/cc-cflags not found: %s\n' "$NIX_SUPPORT" >&2
    exit 2
fi
CC_REAL=${CC_REAL:-$(grep -m1 -oE '/nix/store/[^[:space:]]+/bin/clang\+\+' "$CLANG_WRAPPER" || true)}
RESOURCE_DIR=${RESOURCE_DIR:-$(sed -n 's/.*-resource-dir=\([^[:space:]]*\).*/\1/p' "$NIX_SUPPORT/cc-cflags")}
if [[ -z "$CC_REAL" || ! -x "$CC_REAL" ]]; then
    printf 'error: failed to discover an unwrapped clang++ from %s\n' "$CLANG_WRAPPER" >&2
    exit 2
fi
if [[ -z "$RESOURCE_DIR" || ! -d "$RESOURCE_DIR" ]]; then
    printf 'error: failed to discover clang resource directory from %s\n' "$NIX_SUPPORT/cc-cflags" >&2
    exit 2
fi

mkdir -p "$(dirname "$OUT")"
mkdir "$OUT" # immutable output, never silently overwrite a former build

# The C++ adapters use XNU kernel headers.  The C adapters consume the Linux
# UAPI structs only; leaving __KERNEL__ unset selects the UAPI/BSD branch of
# drm.h and avoids pretending that the partial Linux source tree is a Linux
# kernel build tree.  No header is generated or redefined here.
COMMON=(
    -target x86_64-apple-macos26
    -ffreestanding
    -mkernel
    -mno-red-zone
    -fno-stack-protector
    -fno-builtin
    -nostdinc
    -resource-dir "$RESOURCE_DIR"
    -DKERNEL=1
    -D__user=
    '-D__packed=__attribute__((packed))'
    -I "$HEADERS/sys"
    -I "$HEADERS"
    -I "$ROOT/i915-xnu/include"
    -I "$ROOT/sources/linux/include/uapi/drm"
    -I "$ROOT/sources/linux/include/uapi"
)
# LLVM's Mach-O LowerGlobalDtors pass can reintroduce __cxa_atexit even after
# the driver selected -fno-use-cxa-atexit for kexts. Keep real mod_term_funcs,
# not user-runtime registration; no destructor or system function is stubbed.
CXX=("$CC_REAL" "${COMMON[@]}" -fapple-kext -fno-exceptions -fno-rtti -D__KERNEL__=1
     -mllvm -disable-atexit-based-global-dtor-lowering)
C=("$CC_REAL" "${COMMON[@]}")

printf 'root=%s\n' "$ROOT"
printf 'clang_wrapper=%s\n' "$CLANG_WRAPPER"
printf 'nix_support=%s\n' "$NIX_SUPPORT"
printf 'cc_real=%s\n' "$CC_REAL"
printf 'resource_dir=%s\n' "$RESOURCE_DIR"
printf 'mackernelsdk=%s\n' "$SDK"
printf 'target=x86_64-apple-macos26\n'
printf 'output=%s\n' "$OUT"
printf 'clang_version:\n'
"$CC_REAL" --version | head -4

run() {
    printf '$ '
    printf '%q ' "$@"
    printf '\n'
    "$@"
}

run "${CXX[@]}" -fapple-kext -mno-red-zone -c "$ROOT/i915-xnu/native/GX42Service.cpp" -o "$OUT/GX42Service.o"
if [[ ${GA43_SERVICE_ONLY:-0} == 1 ]]; then
    file "$OUT/GX42Service.o"
    sha256sum "$OUT/GX42Service.o"
    exit 0
fi
if [[ ${GA43_CHANGED_ONLY:-0} != 1 ]]; then
run "${CXX[@]}" -c "$ROOT/i915-xnu/os-compat/xnu_memory.cpp" -o "$OUT/xnu_memory.o"
run "${CXX[@]}" -c "$ROOT/i915-xnu/os-compat/xnu_copy.cpp" -o "$OUT/xnu_copy.o"
fi
run "${C[@]}" -x c -c "$ROOT/i915-xnu/gem/gx_gem.c" -o "$OUT/gx_gem.o"
run "${C[@]}" -x c -c "$ROOT/i915-xnu/drm/gx_ioctl.c" -o "$OUT/gx_ioctl.o"
run "${C[@]}" -x c -c "$ROOT/i915-xnu/drm/gx_client.c" -o "$OUT/gx_client.o"
run "${C[@]}" -x c -c "$ROOT/i915-xnu/gem/gx_vm.c" -o "$OUT/gx_vm.o"
if [[ ${GA43_CHANGED_ONLY:-0} != 1 ]]; then
run "${C[@]}" -x c -c "$ROOT/i915-xnu/drm/gx_exec_validate.c" -o "$OUT/gx_exec_validate.o"
run "${C[@]}" -x c -c "$ROOT/i915-xnu/native/module.c" -o "$OUT/module.o"
run "${C[@]}" -x c -c "$ROOT/tests/abi_compile.c" -o "$OUT/abi_compile.o"
fi

printf 'objects:\n'
file "$OUT"/*.o
sha256sum "$OUT"/*.o
