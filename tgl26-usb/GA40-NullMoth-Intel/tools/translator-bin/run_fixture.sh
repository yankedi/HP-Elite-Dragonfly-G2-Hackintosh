#!/usr/bin/env bash
# Translate one LLVM-IR text fixture with the pinned metal2vulkan release CLI
# and independently validate the emitted module. CPU-only, no GPU access.
set -u
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
SPVVAL=${SPVVAL:-$(command -v spirv-val || true)}
: "${SPVVAL:?set SPVVAL to a local spirv-val executable}"
BIN=${BIN:-$ROOT/build/translator-release/release/metal2vulkan}
OUT=${OUT:-$ROOT/metal/translator-prototype/results/run-001}
name=$1
stage=$2
input=$3
base=$(basename "$input" .ll)
dir="$OUT/$name"
mkdir -p "$dir" "$OUT/spv"
METAL2VULKAN_SPIRV_VAL="$SPVVAL" \
METAL2VULKAN_REPRO_DIR="$ROOT/tmp/translator-tmp/repros" \
TMPDIR="$ROOT/tmp/translator-tmp" \
timeout 120 "$BIN" "$input" "$OUT/spv/$base.spv" --stage "$stage" \
  > "$dir/stdout.txt" 2> "$dir/stderr.txt"
rc=$?
printf '%s\n' "$rc" > "$dir/status.txt"
if [ "$rc" -ne 0 ]; then
  echo "$name rc=$rc"
  tail -5 "$dir/stdout.txt" "$dir/stderr.txt"
  exit "$rc"
fi
sha256sum "$OUT/spv/$base.spv" > "$dir/output.sha256"
"$SPVVAL" --target-env vulkan1.2 "$OUT/spv/$base.spv" \
  > "$dir/spirv-val.stdout.txt" 2> "$dir/spirv-val.stderr.txt"
vrc=$?
printf '%s\n' "$vrc" > "$dir/spirv-val.status.txt"
echo "$name translate=0 validate=$vrc bytes=$(stat -c %s "$OUT/spv/$base.spv")"
exit "$vrc"
