#!/bin/bash
# Run from the HP's logged-in graphical Terminal. No automatic GUI actions.
set -euo pipefail
ROOT=/private/tmp/ga415-runtime
TOOL="$ROOT/build-v1/desktop-capture"
echo 'GA415 capture: one desktop + up to three Settings/Dock window snapshots.'
echo 'Screen Recording authorization may be requested. Relaunch after granting it.'
echo 'Move/repaint/scroll manually between invocations; label each pair in your notes.'
OUT="$HOME/Desktop/GA415-capture-$(date +%Y%m%d-%H%M%S)"
"$TOOL" --request-permission --output "$OUT"
echo "Saved: $OUT"
