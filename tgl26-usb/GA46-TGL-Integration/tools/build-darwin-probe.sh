#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=${1:-"$ROOT/logs/build/darwin-probe"}
mkdir -p "$OUT"
CC=${CC:-clang}
LD=${LD64_LLD:-/nix/store/3naz0qnnfax2pdvwlgmjd3j57axrass4-lld-21.1.8/bin/ld64.lld}
"$CC" -target x86_64-apple-macos15.0 -c -fPIC -nostdlib -fno-stack-protector \
  "$ROOT/tools/minimal-darwin-probe.c" -o "$OUT/probe.o"
"$LD" -dylib -arch x86_64 -platform_version macos 15.0 15.0 \
  -install_name @rpath/libxeabi_probe.dylib \
  -o "$OUT/libxeabi_probe.dylib" "$OUT/probe.o"
