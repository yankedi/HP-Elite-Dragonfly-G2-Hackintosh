#!/bin/bash
# Execute in the logged-in Terminal, whose screen-capture consent is established.
set -euo pipefail
umask 077
ROOT=/private/tmp/ga415-runtime
OUT="$ROOT/desktop-window-pair-v1"
mkdir "$OUT"
exec > "$OUT/run.stdout" 2> "$OUT/run.stderr"
/usr/bin/osascript -e 'tell application "System Settings" to activate'
/bin/sleep 2
"$ROOT/build-v2/desktop-capture" --metadata-only --output "$OUT/before-metadata"
/usr/sbin/screencapture -x "$OUT/before.png"
/usr/bin/osascript <<'APPLESCRIPT' > "$OUT/window-move.txt"
tell application "System Events"
    tell process "System Settings"
        set w to front window
        set p to position of w
        set sz to size of w
        set nx to (item 1 of p) - 240
        if nx < 0 then set nx to (item 1 of p) + 120
        set position of w to {nx, item 2 of p}
        return {p, sz, position of w, size of w}
    end tell
end tell
APPLESCRIPT
/bin/sleep 2
"$ROOT/build-v2/desktop-capture" --metadata-only --output "$OUT/after-metadata"
/usr/sbin/screencapture -x "$OUT/after.png"
echo CAPTURE_PAIR_COMPLETE
