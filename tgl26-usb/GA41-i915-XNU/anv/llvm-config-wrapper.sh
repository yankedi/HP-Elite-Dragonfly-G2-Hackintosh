#!/usr/bin/env bash
set -Eeuo pipefail

# Meson asks llvm-config for LLVM's libdir and then searches that one directory
# for clang's static component libraries.  Nix intentionally splits LLVM and
# Clang outputs, so expose a private symlink directory for that lookup without
# modifying /nix/store or copying the large archives.
REAL_LLVM_CONFIG="${GA41_LLVM_CONFIG_REAL:?GA41_LLVM_CONFIG_REAL is required}"
CLANG_COMPONENT_DIR="${GA41_CLANG_COMPONENT_DIR:?GA41_CLANG_COMPONENT_DIR is required}"

if [ "$#" -eq 1 ] && [ "$1" = "--libdir" ]; then
  printf '%s\n' "$CLANG_COMPONENT_DIR"
else
  exec "$REAL_LLVM_CONFIG" "$@"
fi
