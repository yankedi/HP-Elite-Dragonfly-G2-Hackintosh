#!/bin/bash
# One ordinary Settings navigation; inspect actual accessibility elements.
set -euo pipefail
umask 077
ROOT=/private/tmp/ga415-avatar-repro
mkdir "$ROOT/inspect"
exec > "$ROOT/inspect/run.stdout" 2> "$ROOT/inspect/run.stderr"
/usr/bin/open 'x-apple.systempreferences:com.apple.Users-Groups-Settings.extension'
/bin/sleep 2
/usr/bin/osascript <<'APPLESCRIPT' > "$ROOT/inspect/ui.txt"
with timeout of 20 seconds
tell application "System Events"
    tell process "System Settings"
        set report to ""
        set itemsToRead to entire contents of front window
        repeat with e in itemsToRead
            try
                set r to role of e as text
                if r is in {"AXButton", "AXImage", "AXStaticText", "AXRadioButton", "AXCheckBox", "AXPopUpButton"} then
                    set n to ""
                    set d to ""
                    set p to ""
                    try
                        set n to name of e as text
                    end try
                    try
                        set d to description of e as text
                    end try
                    try
                        set p to position of e as text
                    end try
                    set report to report & r & " | name=" & n & " | description=" & d & " | position=" & p & " | ref=" & (e as text) & linefeed
                end if
            end try
        end repeat
        return report
    end tell
end tell
end timeout
APPLESCRIPT
/usr/sbin/screencapture -x "$ROOT/inspect/desktop.png"
echo INSPECTION_COMPLETE
