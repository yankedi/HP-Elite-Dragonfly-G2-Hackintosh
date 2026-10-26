#!/usr/bin/env bash
set -euo pipefail
# GNU find/sort/sha256sum content seal; no custom hash implementation.
# Generated scratch builds are reproducible, not part of the handoff seal.
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
SEAL=${GA42_SEAL_DIR:-$ROOT/evidence-manifest}
case "$SEAL" in "$ROOT"/*) ;; *) echo 'seal must be inside GA42' >&2; exit 2 ;; esac
REL=${SEAL#"$ROOT"/}

inventory() {
    find . \( -type d \( -name .git -o -name __pycache__ -o -name 'build*' \) \
          -o -path './anv/work' -o -path './evidence-manifest' \
          -o -path "./$REL" -o -path './logs/seal-verification' \) -prune \
        -o "$@" | LC_ALL=C sort -z
}
case "${1:-}" in
create)
    mkdir "$SEAL" # Never replace an existing seal.
    inventory -type f -print0 > "$SEAL/files.nul"
    inventory -type l -printf '%p -> %l\0' > "$SEAL/symlinks.nul"
    xargs -0 -r sha256sum -- < "$SEAL/files.nul" > "$SEAL/local.sha256"
    find -L sources/mackernelsdk -type f -print0 | LC_ALL=C sort -z |
        xargs -0 -r sha256sum -- > "$SEAL/kernel-headers.sha256"
    sha256sum ../GA40-NullMoth-Intel/manifest.json ../GA41-i915-XNU/manifest.json \
        > "$SEAL/historical-seals.sha256"
    (cd "$SEAL" && sha256sum files.nul symlinks.nul local.sha256 \
        kernel-headers.sha256 historical-seals.sha256 > SHA256SUMS)
    ;;
verify) ;;
*) echo 'usage: seal-evidence.sh create|verify' >&2; exit 2 ;;
esac
TMP=$(mktemp -d /tmp/opencode/ga42-seal-verify.XXXXXX)
trap 'rm -f "$TMP/files.nul" "$TMP/symlinks.nul"; rmdir "$TMP"' EXIT
inventory -type f -print0 > "$TMP/files.nul"
inventory -type l -printf '%p -> %l\0' > "$TMP/symlinks.nul"
cmp "$SEAL/files.nul" "$TMP/files.nul"
cmp "$SEAL/symlinks.nul" "$TMP/symlinks.nul"
(cd "$SEAL" && sha256sum --check SHA256SUMS)
sha256sum --check "$SEAL/local.sha256"
sha256sum --check "$SEAL/kernel-headers.sha256"
sha256sum --check "$SEAL/historical-seals.sha256"
echo 'PASS: source/artifact/log content, symlink inventory, kernel headers and historical seal hashes'
