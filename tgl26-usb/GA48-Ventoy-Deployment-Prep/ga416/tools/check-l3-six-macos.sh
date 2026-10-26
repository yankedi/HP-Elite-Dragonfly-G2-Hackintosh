#!/bin/bash
# Optional native read-only verification on a Mac; does not install or boot the image.
set -euo pipefail
test "$(uname -s)" = Darwin
test "$#" = 1 || { echo 'Usage: bash check-l3-six-macos.sh /path/to/HP-Tahoe-GA416-L3-6.img' >&2; exit 2; }
image="$1"
expected=46588464684092a8d9374de2341f51e5b80e5632870bcdac981540d4b97955c7
test "$(/usr/bin/shasum -a 256 "$image" | /usr/bin/awk '{print $1}')" = "$expected"
work=$(mktemp -d /private/tmp/ga416-native-check.XXXXXX)
mkdir "$work/mounted"
mounted=0
cleanup() {
    if test "$mounted" = 1; then /usr/bin/hdiutil detach "$work/mounted"; fi
}
trap cleanup EXIT
/usr/bin/hdiutil attach -readonly -nobrowse -imagekey diskimage-class=CRawDiskImage \
    -mountpoint "$work/mounted" "$image" > "$work/attach.txt"
mounted=1
bundle="$work/mounted/EFI/OC/Kexts/NootedGreen.kext"
/sbin/mount > "$work/mounts.txt"
grep -F " on $work/mounted " "$work/mounts.txt" | grep -F 'read-only'
/usr/bin/codesign --verify --strict --deep --verbose=4 "$bundle" > "$work/verify.stdout" 2> "$work/verify.stderr"
/usr/bin/codesign --display --verbose=4 "$bundle" > "$work/display.stdout" 2> "$work/display.stderr"
grep -F 'Signature=adhoc' "$work/display.stderr"
/usr/bin/dwarfdump --uuid "$bundle/Contents/MacOS/NootedGreen" | tee "$work/uuid.txt"
grep -F '4C4C44D4-5555-3144-A13A-DFB86EFBE513' "$work/uuid.txt"
test "$(/usr/bin/shasum -a 256 "$bundle/Contents/MacOS/NootedGreen" | /usr/bin/awk '{print $1}')" = e44ef32745cad51bd13a2006557f8d2076f96759a0afce867547a8466ab6dbbb
/usr/bin/plutil -lint "$work/mounted/EFI/OC/config.plist" > "$work/plutil.txt"
/usr/bin/hdiutil detach "$work/mounted"
mounted=0
test "$(/usr/bin/shasum -a 256 "$image" | /usr/bin/awk '{print $1}')" = "$expected"
echo "Native strict verification PASS. Receipts: $work"
