#!/bin/bash
# Use the captured Users & Groups AX hierarchy; press the actual avatar button once.
set -euo pipefail
umask 077
ROOT=/private/tmp/ga415-avatar-repro
test "$(/usr/sbin/sysctl -n kern.bootsessionuuid)" = REDACTED-SESSION-ID
mkdir "$ROOT/avatar-button"
exec > "$ROOT/avatar-button/run.stdout" 2> "$ROOT/avatar-button/run.stderr"
/bin/date -u '+%Y-%m-%dT%H:%M:%SZ'
/usr/bin/osascript <<'APPLESCRIPT' > "$ROOT/avatar-button/action.txt"
with timeout of 20 seconds
tell application "System Events"
    tell process "System Settings"
        set w to front window
        if name of w is not "Users & Groups" then error "Unexpected Settings page"
        set accountGroup to group 1 of scroll area 1 of group 1 of group 3 of splitter group 1 of group 1 of w
        if value of static text 1 of accountGroup is not "user" then error "Unexpected account row"
        set targetButton to button 1 of accountGroup
        set beforeProperties to properties of targetButton
        click targetButton
        return beforeProperties
    end tell
end tell
end timeout
APPLESCRIPT
/bin/sleep 3
/usr/bin/osascript <<'APPLESCRIPT' > "$ROOT/avatar-button/ui.txt"
with timeout of 20 seconds
tell application "System Events"
    tell process "System Settings"
        return entire contents of front window
    end tell
end tell
end timeout
APPLESCRIPT
/usr/sbin/screencapture -x "$ROOT/avatar-button/desktop.png"
/bin/date -u '+%Y-%m-%dT%H:%M:%SZ'
echo AVATAR_BUTTON_CHECK_COMPLETE
