#!/usr/bin/env bash
set -euo pipefail
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3 "$here/build_core.py" --compiler clang++ --label clang
if command -v g++ >/dev/null 2>&1; then
    python3 "$here/build_core.py" --compiler g++ --label gcc
else
    nix-shell -p gcc --run "python3 '$here/build_core.py' --compiler g++ --label gcc"
fi
