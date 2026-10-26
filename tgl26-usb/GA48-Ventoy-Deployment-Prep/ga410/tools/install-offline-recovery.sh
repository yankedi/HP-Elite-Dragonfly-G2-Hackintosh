#!/bin/bash
# Authorized full-stack installation into the freshly verified offline Data pair.
# This script never loads a driver, writes EFI, changes SIP, registers KC or reboots.
set -euo pipefail
[[ $(uname -s) == Darwin && $EUID -eq 0 ]] || exit 1
data='/Volumes/TARGET_DATA_VOLUME'
system='/Volumes/TARGET_SYSTEM_VOLUME'
group=${EXPECTED_APFS_VOLUME_GROUP_ID:?set EXPECTED_APFS_VOLUME_GROUP_ID for the intended target}
work="$data/Users/Shared/GA410-work-20261023-0820"
source="$work/package-signed"
hasher=/tmp/ga410-policy-prep/recovery-sha256
manifest=/tmp/ga410-policy-prep/INSTALL-SHA256SUMS
[[ $(/usr/sbin/diskutil info -plist "$system" | /usr/bin/plutil -extract APFSVolumeGroupID raw -o - -) == "$group" ]] || exit 1
[[ $(/usr/sbin/diskutil info -plist "$data" | /usr/bin/plutil -extract VolumeUUID raw -o - -) == "$group" ]] || exit 1
[[ $(/usr/bin/plutil -extract ProductBuildVersion raw -o - "$system/System/Library/CoreServices/SystemVersion.plist") == 25G83 ]] || exit 1
[[ -f $data/Users/Shared/GA410-backup-20261023-0830/BACKUP-COMPLETE ]] || exit 1
[[ $(/bin/cat "$data/Users/Shared/GA410-backup-20261023-0830/backup.rc") == 0 ]] || exit 1
paths=(
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
for path in "${paths[@]}"; do
  [[ -d $source/payload$path && ! -e $data$path && ! -L $data$path ]] || exit 1
  [[ -d $(dirname "$data$path") ]] || exit 1
done
( cd "$source"; "$hasher" -c "$work/SIGNED-SHA256SUMS" )
created=()
success=0
finish() {
  rc=$?
  if [[ $success != 1 ]]; then
    echo "Installation failed rc=$rc; removing only this transaction's newly created component paths."
    rollback_rc=0
    for path in "${created[@]}"; do
      /bin/rm -rf "$data$path" || rollback_rc=$?
    done
    printf 'ROLLBACK rc=%s\n' "$rollback_rc"
    [[ $rollback_rc == 0 ]] || rc=$rollback_rc
  fi
  exit "$rc"
}
trap finish EXIT
for path in "${paths[@]}"; do
  created+=("$path")
  /usr/bin/ditto --rsrc --extattr --acl "$source/payload$path" "$data$path"
  /usr/sbin/chown -R root:wheel "$data$path"
  /bin/chmod -R go-w "$data$path"
done
( cd "$data"; "$hasher" -c "$manifest" )
for path in "${paths[@]}"; do
  printf 'COMPONENT %s\n' "$path"
  /usr/bin/plutil -extract CFBundleIdentifier raw -o - "$data$path/Contents/Info.plist"
  /usr/bin/find "$data$path" -exec /usr/bin/stat -f 'META %u %g %p %f %N' {} \;
done
/bin/sync
success=1
echo 'SYSTEM_COMPONENTS_INSTALLED: all 11 paths complete; KC registration and future boot policy still separate.'
