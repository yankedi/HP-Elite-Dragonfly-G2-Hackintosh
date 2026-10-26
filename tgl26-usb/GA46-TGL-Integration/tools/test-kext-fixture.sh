#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
BIN=${LLVM_BIN:-"$ROOT/toolchain/pr204805/build/bin"}
LD=${KEXT_LD:-"$BIN/ld64.lld"}
OUT=${1:?unique output directory required}
mkdir "$OUT"
CC=${CLANG_APPLE:-/nix/store/wra7pnc8v3vk7xl597kq79bbmvncxz8j-clang-21.1.8/bin/clang-21}
"$CC" -target x86_64-apple-macos13.0 -mkernel -fapple-kext \
  -fno-use-cxa-atexit -fno-register-global-dtors-with-atexit \
  -mllvm -disable-atexit-based-global-dtor-lowering \
  -fno-exceptions -fno-rtti -fno-builtin \
  -fno-stack-protector -fno-asynchronous-unwind-tables -fno-common \
  -nostdinc -nostdinc++ -isystem "$ROOT/extern/MacKernelSDK/Headers" \
  -DKERNEL -DKERNEL_PRIVATE -DDRIVER_PRIVATE -std=gnu++17 \
  -c "$ROOT/tests/kext-fixture.cpp" -o "$OUT/fixture.o"
"$LD" -arch x86_64 -platform_version macos 13.0 13.0 \
  -kext -static -undefined error "$OUT/fixture.o" -o "$OUT/fixture.kextbin"
python3 "$ROOT/tools/macho-audit.py" --kext "$OUT/fixture.kextbin" > "$OUT/audit.json"
"$BIN/llvm-objdump" --macho --private-headers -r "$OUT/fixture.kextbin" > "$OUT/structure.txt"
"$BIN/llvm-nm" -m "$OUT/fixture.kextbin" > "$OUT/symbols.txt"
python3 - "$OUT/audit.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
names={s['name'] for s in x['symbols']}
assert {'_kmod_info','_fixture_start','_fixture_stop','_IOMalloc','_IOFree'} <= names
assert {'__mod_init_func','__mod_term_func'} <= {s['name'] for s in x['sections']}
assert all(s['name'] in {'_IOMalloc','_IOFree'} for s in x['symbols'] if s['undefined'])
assert any(r['external'] for r in x['relocations']) and any(not r['external'] for r in x['relocations'])
print('Fixture: actual kext type, KPI imports, local/external relocations, constructor/destructor sections PASS; not loaded')
PY
