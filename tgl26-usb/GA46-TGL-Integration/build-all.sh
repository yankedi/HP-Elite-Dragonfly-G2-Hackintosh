#!/usr/bin/env bash
# Offline GA46 build; explicit unique directory, no signing/install steps.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")" && pwd)
RUN=${1:?usage: bash build-all.sh UNIQUE_RUN_ID}
[[ "$RUN" =~ ^[a-zA-Z0-9_-]+$ ]]
bash "$ROOT/tools/build-nootedgreen-kext.sh" "$ROOT/logs/kext-$RUN"
bash "$ROOT/tools/build-darwin-components.sh" "$ROOT/logs/user-$RUN"
python3 "$ROOT/tools/stage-donor.py" "$ROOT/staging/donor-$RUN"
python3 "$ROOT/tools/verify-donor-stage.py" "$ROOT/staging/donor-$RUN"
