#!/usr/bin/env bash
# Run each pinned translator integration test target separately.
# Separate targets let us distinguish "test logic executed" from targets that
# cannot compile because the vendored subtree omits the unpublished validation/
# fixture workspace. CPU only.
set -u
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
CRATE=$ROOT/metal/translator-prototype/build-source/translator
OUT=$ROOT/logs/translator-test-002/per-test
mkdir -p "$OUT"
export CARGO_HOME=$ROOT/cache/translator-cargo
export CARGO_TARGET_DIR=$ROOT/build/translator-test
export TMPDIR=$ROOT/tmp/translator-tmp
RUSTC=${RUSTC:-$(command -v rustc || true)}
CARGO=${CARGO:-$(command -v cargo || true)}
: "${RUSTC:?rustc is required}"
: "${CARGO:?cargo is required}"
export RUSTC
export METAL2VULKAN_SPIRV_VAL=${METAL2VULKAN_SPIRV_VAL:-$ROOT/build/translator-spirv-tools/tools/spirv-val}
export CARGO_PROFILE_TEST_DEBUG=0
export CARGO_PROFILE_DEV_DEBUG=0
cd "$CRATE" || exit 1
: > "$OUT/summary.tsv"
for f in tests/*.rs; do
  name=$(basename "$f" .rs)
  timeout 300 "$CARGO" test --test "$name" > "$OUT/$name.stdout.txt" 2> "$OUT/$name.stderr.txt"
  rc=$?
  if [ "$rc" -eq 0 ]; then
    line=$(grep -h '^test result:' "$OUT/$name.stdout.txt" | tail -1)
    printf '%s\tPASS\t%s\n' "$name" "$line" >> "$OUT/summary.tsv"
  else
    if grep -q 'error\[\|error: couldn.t read\|error: could not compile' "$OUT/$name.stderr.txt"; then
      printf '%s\tBUILD_ERROR\t%s\n' "$name" "$(grep -m1 'error' "$OUT/$name.stderr.txt")" >> "$OUT/summary.tsv"
    else
      line=$(grep -h '^test result:' "$OUT/$name.stdout.txt" | tail -1)
      printf '%s\tTEST_FAIL\t%s\n' "$name" "$line" >> "$OUT/summary.tsv"
    fi
  fi
done
cat "$OUT/summary.tsv"
