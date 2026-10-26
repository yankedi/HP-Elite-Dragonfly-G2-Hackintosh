#!/usr/bin/env bash
# Required offline checks; Darwin binaries are inspected, never executed.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=${1:?unique output directory required}
mkdir "$OUT"
cc -std=c11 -Wall -Wextra -Werror -I "$ROOT/src" "$ROOT/tests/test_xe_abi.c" -o "$OUT/test-xe-abi"
"$OUT/test-xe-abi"
python3 "$ROOT/tests/test_compiler_bridge.py" "$OUT/adapter"
bash "$ROOT/tools/test-owned-bitcode.sh" "$OUT/bitcode"
bash "$ROOT/tools/test-kext-fixture.sh" "$OUT/fixture"
bash "$ROOT/tools/build-nootedgreen-kext.sh" "$OUT/kernel"
bash "$ROOT/tools/build-darwin-components.sh" "$OUT/userspace"
python3 "$ROOT/tools/audit-userspace.py" "$OUT/userspace" > "$OUT/userspace-audit.json"
python3 "$ROOT/tools/compiler-dependency-graph.py" --new "$OUT/userspace" > "$OUT/compiler-graph.json"
python3 "$ROOT/tools/verify-donor-stage.py" "$ROOT/staging/donor-native-001"
python3 "$ROOT/tools/stage-donor.py" "$ROOT/staging/donor-$(basename "$OUT")" > "$OUT/donor-repeat.json"
python3 "$ROOT/tools/verify-donor-stage.py" "$ROOT/staging/donor-$(basename "$OUT")"
python3 - "$ROOT/staging/donor-native-001/PATCH-PLAN.json" "$OUT/donor-repeat.json" <<'PY'
import json,sys
a,b=[json.load(open(p)) for p in sys.argv[1:]]
assert a['records']==b['records'],'staging not reproducible'
print('Real donor repeat staging yields identical hashes and reverse evidence PASS')
PY
python3 "$ROOT/toolchain/pr204805/llvm-project-d575e43643f7c90a1a2728352a24867d7105d9e9/llvm/utils/lit/lit.py" \
  -v "$ROOT/toolchain/pr204805/build/tools/lld/test/MachO/kext.s" \
  "$ROOT/toolchain/pr204805/build/test/tools/llvm-objcopy/MachO/kext-relocations.test" > "$OUT/upstream-tests.log" 2>&1
git -C "$ROOT" diff --check
echo 'GA46 required offline checks PASS; target/GPU never executed'
