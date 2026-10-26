#!/bin/bash
# Run in the existing consenting graphical Terminal; existing GA415 binary only.
set -euo pipefail
umask 077
BASE=/private/tmp/ga416-acceptance-8B9C5493
OUT="$BASE/desktop"
META="$BASE/desktop-capture"
test "$(/usr/sbin/sysctl -n kern.bootsessionuuid)" = REDACTED-SESSION-ID
mkdir "$OUT"
exec > "$OUT/run.stdout" 2> "$OUT/run.stderr"
trap 'rc=$?; echo "$rc" > "$OUT/exit"' EXIT
"$META" --metadata-only --output "$OUT/initial-metadata"
/usr/sbin/screencapture -x "$OUT/initial.png"
/usr/bin/open 'x-apple.systempreferences:com.apple.SystemProfiler.AboutExtension'
/bin/sleep 3
/usr/bin/osascript <<'APPLESCRIPT' > "$OUT/settings-position.txt"
with timeout of 15 seconds
tell application "System Events"
    tell process "System Settings"
        set frontmost to true
        set position of front window to {759, 71}
        set size of front window to {723, 960}
        return {name of front window, position of front window, size of front window}
    end tell
end tell
end timeout
APPLESCRIPT
/bin/sleep 2
"$META" --metadata-only --output "$OUT/settings-metadata"
/usr/sbin/screencapture -x "$OUT/settings.png"
ID=$(/usr/bin/python3 - "$OUT/settings-metadata/windows.json" <<'PY'
import json,sys
rows=[r for r in json.load(open(sys.argv[1])) if r.get('kCGWindowOwnerName')=='System Settings' and r.get('kCGWindowLayer')==0 and r['kCGWindowBounds']['Width']>600 and r['kCGWindowBounds']['Height']>500]
assert len(rows)==1,rows
print(rows[0]['kCGWindowNumber'])
PY
)
echo "SETTINGS_ID=$ID"
/usr/sbin/screencapture -x -o -l "$ID" "$OUT/settings-window.png"
/usr/bin/osascript <<'APPLESCRIPT' > "$OUT/finder-open.txt"
with timeout of 15 seconds
tell application "Finder"
    activate
    open home
    return name of front window
end tell
end timeout
APPLESCRIPT
/bin/sleep 2
"$META" --metadata-only --output "$OUT/finder-metadata"
/usr/sbin/screencapture -x "$OUT/finder.png"
ID=$(/usr/bin/python3 - "$OUT/finder-metadata/windows.json" <<'PY'
import json,sys
rows=[r for r in json.load(open(sys.argv[1])) if r.get('kCGWindowOwnerName')=='Finder' and r.get('kCGWindowLayer')==0 and r['kCGWindowBounds']['Width']>300 and r['kCGWindowBounds']['Height']>200]
assert rows,rows
print(rows[0]['kCGWindowNumber'])
PY
)
echo "FINDER_ID=$ID"
/usr/sbin/screencapture -x -o -l "$ID" "$OUT/finder-window.png"
/bin/date -u '+%Y-%m-%dT%H:%M:%SZ'
echo DESKTOP_CAPTURE_COMPLETE
