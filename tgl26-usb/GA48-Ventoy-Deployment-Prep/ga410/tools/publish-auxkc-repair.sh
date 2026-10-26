#!/bin/bash
# Publish the inspected native AuxKC only. No rebuilding, Preboot copying,
# approval-database edits, NVRAM changes, driver loading or rebooting.
set -euo pipefail
[[ $(uname -s) == Darwin && $EUID -eq 0 ]] || exit 1
data='/Volumes/TARGET_DATA_VOLUME'
system='/Volumes/TARGET_SYSTEM_VOLUME'
group=${EXPECTED_APFS_VOLUME_GROUP_ID:?set EXPECTED_APFS_VOLUME_GROUP_ID for the intended target}
work="$data/Users/Shared/GA410-work-20261023-0820/kc-repair-aux-20261023"
candidate="$work/AuxiliaryKernelExtensions.kc"
destination="$data/Library/KernelCollections/AuxiliaryKernelExtensions.kc"
temporary="$destination.ga410-repair-new"
rollback="$destination.ga410-repair-rollback"
hasher=/tmp/ga410-policy-prep/recovery-sha256
old_hash=5d6170588133eae3fe1d4f0024f67960f0ce6aeb6d2f3266e9865d96ddfa8fcd
new_hash=38f58293b7636dc7867168e670bb51a66958b10b54de515148a5e0d796543da5
[[ $(/usr/sbin/diskutil info -plist "$system" | /usr/bin/plutil -extract APFSVolumeGroupID raw -o - -) == "$group" ]] || exit 1
[[ $(/usr/sbin/diskutil info -plist "$data" | /usr/bin/plutil -extract VolumeUUID raw -o - -) == "$group" ]] || exit 1
[[ $("$hasher" "$destination") == "$old_hash  "* ]] || exit 1
[[ $("$hasher" "$candidate") == "$new_hash  "* ]] || exit 1
[[ ! -e $temporary && ! -L $temporary && ! -e $rollback && ! -L $rollback ]] || exit 1
[[ $(/usr/bin/stat -f '%u %g %p %f' "$destination") == '0 0 100744 524288' ]] || exit 1
"$hasher" -c /tmp/ga410-policy-prep/CURRENT-KC-SHA256SUMS
# Exclusive, permanent publication guard and a native metadata-preserving backup.
/bin/mkdir "$work/publication"
previous="$work/publication/previous-AuxiliaryKernelExtensions.kc"
/usr/bin/ditto --rsrc --extattr --acl "$destination" "$previous"
[[ $("$hasher" "$previous") == "$old_hash  "* ]] || exit 1
switched=0
success=0
finish() {
  rc=$?
  if [[ $success != 1 && $switched == 1 ]]; then
    echo 'Publication verification failed; restoring only the original AuxKC.' >&2
    /usr/bin/ditto --rsrc --extattr --acl "$previous" "$rollback" || exit 1
    /bin/mv -f "$rollback" "$destination" || exit 1
    [[ $("$hasher" "$destination") == "$old_hash  "* ]] || exit 1
    /bin/sync
    echo 'Original AuxKC restored and SHA256 verified.' >&2
  fi
  exit "$rc"
}
trap finish EXIT
# Clone the old file's metadata, replace only its contents, then rename atomically
# within Library/KernelCollections. Preserve its existing restricted flag.
/usr/bin/ditto --rsrc --extattr --acl "$destination" "$temporary"
/bin/cat "$candidate" > "$temporary"
[[ $("$hasher" "$temporary") == "$new_hash  "* ]] || exit 1
[[ $(/usr/bin/stat -f '%u %g %p %f' "$temporary") == '0 0 100744 524288' ]] || exit 1
/bin/mv -f "$temporary" "$destination"
switched=1
"$hasher" -c /tmp/ga410-policy-prep/KC-REPAIR-EXPECTED-SHA256SUMS
( cd "$data"; "$hasher" -c /tmp/ga410-policy-prep/INSTALL-SHA256SUMS )
/usr/bin/stat -f 'INSTALLED_META %u %g %p %f %N' "$destination"
"$hasher" "$destination"
/bin/cp /tmp/ga410-policy-prep/KC-REPAIR-EXPECTED-SHA256SUMS "$work/publication/POST-KC-SHA256SUMS"
/bin/sync
success=1
echo 'AUXKC_INSTALLED: six entries, original Boot/System/Preboot unchanged; runtime authorization not proven.'
