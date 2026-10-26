#!/bin/sh
# Short entry point for a collector staged on an already readable internal data volume.
# Only /tmp output; no mounts, internal-volume writes or installation actions.
set -eu
umask 077
if [ "$(uname -s)" != Darwin ]; then
    echo 'Run this helper in macOS/Recovery.' >&2
    exit 2
fi
if [ "$#" -ne 0 ]; then
    echo 'Usage: sh /Volumes/*/hp/h' >&2
    exit 2
fi
here=$(CDPATH= cd "$(dirname "$0")" && pwd)
collector="$here/collect_macos_handoff.sh"
if [ ! -f "$collector" ]; then
    echo 'The adjacent collect_macos_handoff.sh is missing.' >&2
    exit 1
fi
log=$(/usr/bin/mktemp /tmp/hp-observer-launch.XXXXXX)
printf 'Collecting hardware observations; this may take a few minutes.\n'
if sh "$collector" > "$log" 2>&1; then code=0; else code=$?; fi
work=$(/usr/bin/sed -n 's/^Private logs: //p' "$log" | /usr/bin/tail -n 1)
case "$work" in
    /tmp/hp-macos-observation.*)
        if [ -f "$work/SUMMARY.tsv" ]; then
            printf '\nINPUT / USB SUMMARY\n'
            /usr/bin/awk -F '\t' '$1 ~ /^(ps2-keyboard|i2c-controllers|i2c-nubs|i2c-hid|precision-touchpad|xhci|usb-host-controller|usb-devices|usb-interfaces|nvme)$/ { printf "%s: %s\n", $1, $2 }' "$work/SUMMARY.tsv"
            printf '\nI2C INTERRUPT MODE (if available)\n'
            /usr/bin/grep -i 'Interrupt Mode' "$work/i2c-nubs.txt" || :
            printf '\nDISKS\n'
            /bin/cat "$work/disks.txt"
        fi
        ;;
esac
printf '\nCOLLECTOR OUTPUT / PRIVATE ARCHIVE PATH\n'
/bin/cat "$log"
printf 'Launcher log: %s\n' "$log"
exit "$code"
