#!/usr/bin/env bash
#
# build.sh - repeatable, non-destructive build entry for the Intel Graphics
#            Assembler (iga64) used by this lab.
#
# What it does, in order:
#   1. verifies (or, if the clone is absent, creates) tools/iga/source at the
#      exact pinned commit;
#   2. makes sure the sparse checkout contains the two trees IGA actually
#      needs (visa/iga and inc) - adding them only if they are missing;
#   3. configures tools/iga/build with CMake/Ninja in Release mode if it is
#      not configured yet, then (re)builds IGAExe/iga64;
#   4. smoke-checks the resulting binary with --help.
#
# It never runs git reset, git clean, git checkout -f, or deletes a build
# directory: an existing source tree with the wrong commit is reported, not
# rewritten.  Safe to run repeatedly; a second run is largely a no-op.
#
# Environment overrides:
#   IGA_REPO_URL, IGA_REPO_COMMIT, IGA_SRC, IGA_BUILD, CC, CXX, CMAKE, JOBS

set -euo pipefail

# ---- pinned identity --------------------------------------------------------
IGA_REPO_URL="${IGA_REPO_URL:-https://github.com/intel/intel-graphics-compiler.git}"
# intel/intel-graphics-compiler, "[Autobackout] ... Revert of change:
# 55227b75... Use a corrected register pressure for GRF selection" (2026-10-17)
IGA_REPO_COMMIT="${IGA_REPO_COMMIT:-c36a504a4e6c68030c3302646aa396b8b59b22cb}"

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
IGA_SRC="${IGA_SRC:-$script_dir/source}"
IGA_BUILD="${IGA_BUILD:-$script_dir/build}"
CMAKE="${CMAKE:-cmake}"
JOBS="${JOBS:-$( (command -v nproc >/dev/null && nproc) || echo 4 )}"

log() { printf '[iga-build] %s\n' "$*"; }
die() { printf '[iga-build] error: %s\n' "$*" >&2; exit 1; }

[ -d "$script_dir" ] || die "cannot resolve script directory"

# ---- 1. source tree ---------------------------------------------------------
if [ ! -d "$IGA_SRC/.git" ]; then
  command -v git >/dev/null || die "git not found"
  log "no source clone at $IGA_SRC - creating a sparse, blob-filtered clone"
  # Partial clone: no blobs upfront, only the two trees IGA needs.  cone mode
  # (the default) understands plain paths, so no leading slash is used.
  git clone --filter=blob:none --sparse --no-checkout \
      "$IGA_REPO_URL" "$IGA_SRC"
  git -C "$IGA_SRC" sparse-checkout set --cone visa/iga inc
  # The pinned commit is not necessarily the remote tip of the default branch.
  log "fetching pinned commit $IGA_REPO_COMMIT"
  git -C "$IGA_SRC" fetch --depth 1 origin "$IGA_REPO_COMMIT"
  git -C "$IGA_SRC" checkout --detach "$IGA_REPO_COMMIT"
else
  log "using existing source clone at $IGA_SRC"
fi

# ---- 2. pinned commit check + sparse repair (non-destructive) ---------------
head_commit="$(git -C "$IGA_SRC" rev-parse HEAD 2>/dev/null || true)"
if [ "$head_commit" != "$IGA_REPO_COMMIT" ]; then
  cat >&2 <<EOF
[iga-build] error: source commit mismatch at $IGA_SRC
[iga-build]   want: $IGA_REPO_COMMIT
[iga-build]   have: ${head_commit:-<none>}
[iga-build] Refusing to reset or rewrite the working tree.
[iga-build] Fetch and check out the pinned commit yourself if that is intended:
[iga-build]   git -C "$IGA_SRC" fetch --depth 1 origin $IGA_REPO_COMMIT
[iga-build]   git -C "$IGA_SRC" checkout --detach $IGA_REPO_COMMIT
EOF
  exit 1
fi
log "source commit verified: $head_commit"

# The two files IGA's build genuinely needs.  Their absence is exactly the
# failure mode seen on the first build (missing inc/common/secure_mem.h).
need_inc="$IGA_SRC/inc/common/secure_mem.h"
need_iga="$IGA_SRC/visa/iga/CMakeLists.txt"
if [ ! -f "$need_inc" ] || [ ! -f "$need_iga" ]; then
  log "sparse checkout is missing visa/iga and/or inc - adding them"
  git -C "$IGA_SRC" sparse-checkout add --cone visa/iga inc
  [ -f "$need_inc" ] || die "inc/common/secure_mem.h still missing after sparse add"
  [ -f "$need_iga" ] || die "visa/iga/CMakeLists.txt still missing after sparse add"
else
  log "sparse checkout already contains visa/iga and inc"
fi

# ---- 3. configure + build ---------------------------------------------------
if [ ! -f "$IGA_BUILD/CMakeCache.txt" ]; then
  log "configuring $IGA_BUILD (Release, Ninja)"
  "$CMAKE" -S "$IGA_SRC/visa/iga" -B "$IGA_BUILD" \
      -G Ninja -DCMAKE_BUILD_TYPE=Release
else
  log "build directory already configured at $IGA_BUILD"
fi

log "building (parallelism $JOBS)"
"$CMAKE" --build "$IGA_BUILD" --target iga64 -- -j "$JOBS"

iga64="$IGA_BUILD/IGAExe/iga64"
[ -x "$iga64" ] || die "expected binary not found: $iga64"

# ---- 4. smoke check ---------------------------------------------------------
log "smoke check:"
"$iga64" --help 2>&1 | sed -n '1p'

log "done: $iga64"
