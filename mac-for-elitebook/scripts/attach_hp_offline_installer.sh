#!/bin/sh
# Manually attach the verified offline app data image in HP Recovery, read-only.
# Does not select an installation target or start the installer.
set -eu
umask 077

if [ "$(uname -s)" != Darwin ]; then
    echo 'Run this helper in macOS/Recovery.' >&2
    exit 2
fi
if [ "$#" -ne 1 ] || [ ! -f "$1" ]; then
    echo 'Usage: sh attach_hp_offline_installer.sh /Volumes/<volume-name>/iso/linux/Tahoe-26.6.2-Offline-App.hfs' >&2
    exit 2
fi
image=$1
if [ "$(/usr/bin/stat -f '%z' "$image")" != 19922944000 ]; then
    echo 'Offline image size differs from the verified delivery.' >&2
    exit 1
fi

work=$(/usr/bin/mktemp -d /tmp/hp-offline-app.XXXXXX)
mkdir "$work/volume"
if ! /usr/bin/hdiutil attach -readonly -nobrowse \
    -imagekey diskimage-class=CRawDiskImage -mountpoint "$work/volume" \
    "$image" > "$work/attach.txt" 2> "$work/attach.stderr"; then
    cat "$work/attach.stderr" >&2
    printf 'Attach diagnostics: %s\n' "$work" >&2
    exit 1
fi
app="$work/volume/Install macOS Tahoe.app"
if [ ! -d "$app" ] || [ ! -f "$app/Contents/SharedSupport/SharedSupport.dmg" ]; then
    printf 'Attached volume has unexpected app layout; diagnostics: %s\n' "$work" >&2
    exit 1
fi
printf 'Read-only app path: %s\n' "$app"
printf 'Attach diagnostics: %s\n' "$work"
printf 'To detach later: hdiutil detach "%s"\n' "$work/volume"
