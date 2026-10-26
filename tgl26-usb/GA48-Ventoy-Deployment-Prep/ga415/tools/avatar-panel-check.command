#!/bin/bash
# One observed avatar-coordinate click, followed by passive UI and screenshot capture.
set -euo pipefail
umask 077
ROOT=/private/tmp/ga415-avatar-repro
test "$(/usr/sbin/sysctl -n kern.bootsessionuuid)" = REDACTED-SESSION-ID
mkdir "$ROOT/panel"
exec > "$ROOT/panel/run.stdout" 2> "$ROOT/panel/run.stderr"
/bin/date -u '+%Y-%m-%dT%H:%M:%SZ'
/usr/bin/osascript <<'APPLESCRIPT' > "$ROOT/panel/click.txt"
with timeout of 20 seconds
tell application "System Settings" to activate
tell application "System Events"
    tell process "System Settings"
        set frontmost to true
        click at {1268, 149}
    end tell
end tell
end timeout
APPLESCRIPT
/bin/sleep 3
/usr/bin/osascript <<'APPLESCRIPT' > "$ROOT/panel/ui.txt"
with timeout of 20 seconds
tell application "System Events"
    tell process "System Settings"
        return entire contents of front window
    end tell
end tell
end timeout
APPLESCRIPT
/usr/sbin/screencapture -x "$ROOT/panel/desktop.png"
/bin/date -u '+%Y-%m-%dT%H:%M:%SZ'
echo PANEL_CHECK_COMPLETE
