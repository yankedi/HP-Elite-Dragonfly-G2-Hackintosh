#!/bin/bash
# Recovery-only restoration of GA410's exact files and backed-up Data/Preboot KC.
# The backup archive must first be SHA-verified and extracted with native ditto.
set -euo pipefail
[[ $(uname -s) == Darwin && $EUID -eq 0 ]] || exit 1
hash_map="$(cd "$(dirname "$0")" && pwd)/recovery-checksums.tsv"
verify_hash() {
  local expected=$1 file=$2 actual mapped
  if [[ -x /usr/bin/shasum ]]; then
    actual=$(/usr/bin/shasum -a 256 "$file")
    [[ ${actual%% *} == "$expected" ]] || return 1
  else
    # This map was independently derived from the SHA256-verified originals.
    # Be explicit: native Recovery fallback checks MD5, not native SHA256.
    [[ $(/sbin/md5 -q "$hash_map") == 3daad14eceb3f6d139b5f7ff5bf58997 ]] || return 1
    mapped=$(/usr/bin/awk -v key="$expected" '$1 == key {print $2; n++} END {if (n != 1) exit 1}' "$hash_map")
    actual=$(/sbin/md5 -q "$file")
    [[ $actual == "$mapped" ]] || return 1
  fi
}
verify_backup() {
  local directory=$1 line expected relative
  while IFS= read -r line; do
    expected=${line%%  *}
    relative=${line#*  }
    [[ $relative != /* && $relative != *..* ]] || return 1
    verify_hash "$expected" "$directory/$relative"
  done < "$directory/SHA256SUMS"
}
if [[ ${1:-} == --verify-backup ]]; then
  verify_backup "${2:?extracted backup directory}"
  echo 'Backup archive contents verified; native MD5 fallback when shasum absent. No restoration performed.'
  exit 0
fi
data=${1:?mounted target Data volume root}
preboot=${2:?mounted target Preboot volume root}
backup=${3:?verified extracted backup directory}
[[ $data == /Volumes/* && $preboot == /Volumes/* && $data != *..* && $preboot != *..* ]] || exit 1
[[ -f $backup/files.pax && -f $backup/SOURCE-SHA256SUMS && -f $backup/SHA256SUMS ]] || exit 1
group=$(/usr/sbin/diskutil info -plist "$data" | /usr/bin/plutil -extract APFSVolumeGroupID raw -o - -)
expected_group=${EXPECTED_APFS_VOLUME_GROUP_ID:?set EXPECTED_APFS_VOLUME_GROUP_ID for the intended target}
[[ $group == "$expected_group" ]] || exit 1
[[ -d $preboot/$group/boot/System/Library/KernelCollections ]] || exit 1
/usr/sbin/diskutil info "$data"
/usr/sbin/diskutil info "$preboot"
verify_backup "$backup"
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
# This machine's actual baseline has all eleven paths absent. Refuse to apply
# this deletion-only logic to any different backup state.
for path in "${paths[@]}"; do
  /usr/bin/grep -Fx "$path" "$backup/absent.txt" > /dev/null
done
for path in "${paths[@]}"; do
  /bin/rm -rf "$data$path"
done
# Restore archived metadata only from Recovery, not to a live rootless mirror.
/usr/bin/tar -xpf "$backup/files.pax" --acls --xattrs --fflags --mac-metadata -C "$data" Library/KernelCollections
/usr/bin/tar -xpf "$backup/files.pax" --acls --xattrs --fflags --mac-metadata --strip-components 4 -C "$preboot" "System/Volumes/Preboot/$group/boot/System/Library/KernelCollections"
# Verify every restored regular file against the original absolute-path records.
while IFS= read -r line; do
  expected=${line%%  *}
  relative=${line#*  }
  case $relative in
    Library/KernelCollections/*) target="$data/$relative" ;;
    System/Volumes/Preboot/*) target="$preboot/${relative#System/Volumes/Preboot/}" ;;
    System/Library/KernelCollections/*) continue ;; # sealed System was not modified
    *) exit 1 ;;
  esac
  verify_hash "$expected" "$target"
done < "$backup/SOURCE-SHA256SUMS"
echo 'Exact Data files and backed-up Data/Preboot KC restored and hashed.'
echo 'STOP: compare sealed System KC and NVRAM/policy baseline before deciding to boot. No automatic reboot or blanket nvram restore.'
