#!/bin/bash
# Capture the current Settings page, then move that same window once.
set -euo pipefail
umask 077
ROOT=/private/tmp/ga415-desktop-v2
test "$(/usr/sbin/sysctl -n kern.bootsessionuuid)" = REDACTED-SESSION-ID
OUT="$ROOT/pair-v3"
mkdir "$OUT"
exec > "$OUT/run.stdout" 2> "$OUT/run.stderr"
/bin/date -u '+%Y-%m-%dT%H:%M:%SZ'
/usr/bin/osascript <<'APPLESCRIPT' > "$OUT/title-before.txt"
with timeout of 20 seconds
tell application "System Events"
    tell process "System Settings"
        set frontmost to true
        perform action "AXRaise" of front window
        return name of front window
    end tell
end tell
end timeout
APPLESCRIPT
/bin/sleep 1
"$ROOT/desktop-capture" --metadata-only --output "$OUT/before-metadata"
/usr/sbin/screencapture -x "$OUT/before.png"
ID=$(/usr/bin/python3 - "$OUT/before-metadata/windows.json" "$OUT/title-before.txt" <<'PY'
import json,sys
title=open(sys.argv[2]).read().strip()
windows=[r for r in json.load(open(sys.argv[1])) if r.get('kCGWindowOwnerName')=='System Settings' and r.get('kCGWindowName')==title and r.get('kCGWindowLayer')==0 and r['kCGWindowBounds']['Width']>600 and r['kCGWindowBounds']['Height']>500]
assert len(windows)==1, windows
print(windows[0]['kCGWindowNumber'])
PY
)
echo "WINDOW_ID=$ID"
/usr/sbin/screencapture -x -o -l "$ID" "$OUT/before-window.png"
/usr/bin/osascript - "$OUT/title-before.txt" <<'APPLESCRIPT' > "$OUT/window-move.txt"
on run argv
set expectedTitle to do shell script "/bin/cat " & quoted form of item 1 of argv
with timeout of 20 seconds
tell application "System Events"
    tell process "System Settings"
        set frontmost to true
        set w to front window
        if name of w is not expectedTitle then error "Settings page changed during pair"
        set p to position of w
        set sz to size of w
        set nx to (item 1 of p) - 240
        if nx < 0 then set nx to (item 1 of p) + 120
        set position of w to {nx, item 2 of p}
        return {name of w, p, sz, position of w, size of w}
    end tell
end tell
end timeout
end run
APPLESCRIPT
/bin/sleep 2
"$ROOT/desktop-capture" --metadata-only --output "$OUT/after-metadata"
/usr/sbin/screencapture -x "$OUT/after.png"
/usr/sbin/screencapture -x -o -l "$ID" "$OUT/after-window.png"
/bin/date -u '+%Y-%m-%dT%H:%M:%SZ'
echo LAYER_PAIR_COMPLETE
