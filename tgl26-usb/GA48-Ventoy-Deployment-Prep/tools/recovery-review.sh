#!/bin/bash
# REVIEW COPY ONLY. Generated in GA48, never run on the target.
# Restore only the exact GA48 destinations, from the complete pre-deployment backup.
set -euo pipefail
umask 077
fail() { echo "STOP: $*" >&2; exit 1; }
[[ $(uname -s) == Darwin && $EUID -eq 0 ]] || fail 'future macOS root operation required'
[[ ${GA48_SEPARATELY_AUTHORIZED_PHASE:-} == restore-files ]] || fail 'restore-files authorization required'
backup=${1:?absolute GA48 backup directory required}
volume=${2:?mounted target macOS volume root required, use / only from VESA maintenance}
[[ $backup == /*/GA48-backup-* && $backup != *..* && ! -L $backup ]] || fail 'unexpected backup path'
[[ -f $backup/BACKUP-COMPLETE ]] || fail 'incomplete backup'
[[ $volume == /* && $volume != *..* && -d $volume/System/Library/KernelCollections ]] || fail 'unverified target volume'
# Offline Recovery may not synthesize the target's firmlinks. This review copy
# supports live VESA maintenance only until paired System/Data mapping is approved.
[[ $volume == / ]] || fail 'offline System/Data mapping needs a separately reviewed recovery procedure'
( cd "$backup"; /usr/bin/shasum -a 256 -c SHA256SUMS )
logical=$(/usr/bin/stat -f '%d:%i' /System/Library/Caches)
physical=$(/usr/bin/stat -f '%d:%i' /System/Volumes/Data/System/Library/Caches)
[[ $logical == "$physical" ]] || fail 'Caches firmlink target not verified'
allowed=(
 /Library/Extensions/HookCase.kext
 /Library/Extensions/AppleIntelTGLGraphics.kext
 /Library/Extensions/AppleIntelTGLGraphicsFramebuffer.kext
 /Library/Extensions/AppleIntelTGLGraphicsMTLDriver.bundle
 /Library/Extensions/AppleIntelTGLGraphicsGLDriver.bundle
 /Library/Extensions/AppleIntelTGLGraphicsVADriver.bundle
 /Library/Extensions/AppleIntelTGLGraphicsVAME.bundle
 /Library/Extensions/AppleIntelGraphicsShared.bundle
 /Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle
 /Library/GPUBundles/AppleIntelGraphicsShared.bundle
 /System/Library/Caches/xe.bundle
)
for path in "${allowed[@]}"; do
  dest="$volume$path"
  # GA49: resolve the actual parent volume; Caches is normally a Data firmlink.
  device=$(/bin/df -P "$(/usr/bin/dirname "$dest")" | /usr/bin/awk 'NR==2 {print $1}')
  [[ $device == /dev/* ]] || fail 'unverified backing volume'
  writable=$(/usr/sbin/diskutil info -plist "$device" | /usr/bin/plutil -extract WritableVolume raw -o - -)
  if [[ $path == /System/* && $writable != true ]]; then
    if /usr/bin/grep -Fx "$path" "$backup/absent.txt" >/dev/null; then
      [[ ! -e $dest && ! -L $dest ]] || fail 'xe.bundle changed on RO root; offline recovery needed'
    else
      /usr/bin/diff -rq "$backup/files$path" "$dest"
    fi
    continue
  fi
  if /usr/bin/grep -Fx "$path" "$backup/present.txt" >/dev/null; then
    [[ -e $backup/files$path || -L $backup/files$path ]] || fail 'backup item missing'
    /bin/rm -rf "$dest"
    /usr/bin/ditto --rsrc --extattr --acl "$backup/files$path" "$dest"
    /usr/bin/diff -rq "$backup/files$path" "$dest"
  elif /usr/bin/grep -Fx "$path" "$backup/absent.txt" >/dev/null; then
    /bin/rm -rf "$dest"
  else
    fail "missing presence record: $path"
  fi
done
printf '%s\n' "$volume" > "$backup/FILES-RESTORED"
echo 'Files restored. STOP before reboot: authorized AuxKC repair/rebuild and any approved snapshot/security restoration still required.'
echo 'Do not overwrite an active AuxKC blindly. Compare aux-before/after, rebuild for restored files using the verified target kmutil workflow, inspect result and stop on error.'
echo 'Internal EFI, default boot selection and security settings are not changed by this script.'
