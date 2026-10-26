#!/bin/bash
# --verify performs the complete nondestructive recovery preflight on real media.
# --collect preserves evidence; --restore additionally restores the original stack.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
mode=${1:---verify}
[[ $mode == --verify || $mode == --collect || $mode == --restore ]] || exit 2
[[ $(uname -s) == Darwin && $EUID -eq 0 ]] || exit 1
base=$(cd "$(dirname "$0")" && pwd)
hasher="$base/recovery-sha256"
config="$base/target.plist"
temp=$(/usr/bin/mktemp -d /private/tmp/ga410-restore-check.XXXXXX)
/usr/sbin/diskutil info -plist / > "$temp/RecoveryRoot.plist"
if [[ $(/usr/bin/plutil -extract VolumeName raw -o - "$temp/RecoveryRoot.plist") != 'macOS Base System' ]]; then
  # The same verified BaseSystem.dmg can expose an empty HFS volume name.
  # Permit observation/preflight from that read-only Recovery disk image;
  # retain the original stricter entry condition for destructive restoration.
  [[ $mode != --restore && -d /System/Installation/CDIS &&
     $(/usr/bin/plutil -extract BusProtocol raw -o - "$temp/RecoveryRoot.plist") == 'Disk Image' &&
     $(/usr/bin/plutil -extract WritableVolume raw -o - "$temp/RecoveryRoot.plist") == false ]] || {
    echo 'Run only from the independent macOS Recovery.' >&2; exit 1;
  }
fi
group=$(/usr/bin/plutil -extract VolumeGroup raw -o - "$config")
mount_uuid() {
  local key=$1 value mount
  value=$(/usr/bin/plutil -extract "$key" raw -o - "$config")
  /usr/sbin/diskutil info -plist "$value" > "$temp/$key.plist"
  if ! mount=$(/usr/bin/plutil -extract MountPoint raw -o - "$temp/$key.plist" 2>/dev/null) || [[ -z $mount ]]; then
    /usr/sbin/diskutil mount "$value" >&2
    /usr/sbin/diskutil info -plist "$value" > "$temp/$key.plist"
    mount=$(/usr/bin/plutil -extract MountPoint raw -o - "$temp/$key.plist")
  fi
  [[ $mount == /Volumes/* && -d $mount ]] || return 1
  printf '%s\n' "$mount"
}
data=$(mount_uuid DataUUID)
system=$(mount_uuid SystemUUID)
preboot=$(mount_uuid PrebootUUID)
[[ $(/usr/bin/plutil -extract VolumeUUID raw -o - "$temp/DataUUID.plist") == "$group" ]] || exit 1
[[ $(/usr/bin/plutil -extract APFSVolumeGroupID raw -o - "$temp/DataUUID.plist") == "$group" ]] || exit 1
[[ $(/usr/bin/plutil -extract APFSVolumeGroupID raw -o - "$temp/SystemUUID.plist") == "$group" ]] || exit 1
container=$(/usr/bin/plutil -extract APFSContainerReference raw -o - "$temp/DataUUID.plist")
[[ $(/usr/bin/plutil -extract APFSContainerReference raw -o - "$temp/PrebootUUID.plist") == "$container" ]] || exit 1
[[ $(/usr/bin/plutil -extract ProductBuildVersion raw -o - "$system/System/Library/CoreServices/SystemVersion.plist") == 25G83 ]] || exit 1
if [[ $mode != --verify ]]; then
  # Collect before any integrity gate: even a subsequently rebuilt/different AuxKC
  # must not prevent retaining the failure evidence. No original is changed here.
  /bin/mkdir -p "$base/records"
  record=$(/usr/bin/mktemp -d "$base/records/recovery-$(/bin/date -u +%Y%m%dT%H%M%SZ).XXXXXX")
  /usr/sbin/nvram -xp > "$record/nvram.plist"
  /usr/bin/sw_vers > "$record/recovery-version.txt"
  /sbin/mount > "$record/mount.txt"
  printf 'mode=%s\nRecovery observation only; this is not a successful installed-system boot claim.\n' "$mode" > "$record/operation.txt"
  /bin/cp "$temp"/*.plist "$record/"
  if [[ -d $data/Users/Shared/GA410-firstboot ]]; then
    /usr/bin/tar --acls --xattrs --fflags --mac-metadata -cpf "$record/firstboot.pax" -C "$data/Users/Shared" GA410-firstboot
  fi
  /usr/bin/tar --acls --xattrs --fflags --mac-metadata -cpf "$record/current-KernelCollections.pax" -C "$data" Library/KernelCollections
  reports="$data/Library/Logs/DiagnosticReports"
  if [[ -d $reports ]]; then
    # Keep metadata inside pax, not as unsupported exFAT attributes. Unlike
    # find -exec cp, tar's error propagates directly to this script's status.
    ( cd "$reports"
      /usr/bin/find . -maxdepth 2 -type f \( -iname '*panic*' -o -iname '*WindowServer*' \) -print0 > "$record/DiagnosticReports.paths0"
      if [[ -s $record/DiagnosticReports.paths0 ]]; then
        /usr/bin/tar --null --acls --xattrs --fflags --mac-metadata -cpf "$record/DiagnosticReports.pax" -T "$record/DiagnosticReports.paths0"
      fi
    )
  fi
  ( cd "$record"
    "$hasher" *.pax *.plist *.txt > SHA256SUMS
    if [[ -f DiagnosticReports.paths0 ]]; then "$hasher" DiagnosticReports.paths0 >> SHA256SUMS; fi
    "$hasher" -c SHA256SUMS
  )
  printf 'Recovery evidence preserved at %s\n' "$record"
  [[ $mode == --restore ]] || exit 0
fi
backup="$data/Users/Shared/GA410-backup-20261023-0830"
[[ -f $backup/BACKUP-COMPLETE && $(/bin/cat "$backup/backup.rc") == 0 ]] || exit 1
( cd "$backup"; "$hasher" -c SHA256SUMS )
( cd "$data"; "$hasher" -c "$base/INSTALLED-SHA256SUMS" )
if [[ $mode == --verify ]]; then
  [[ $("$hasher" "$data/Library/KernelCollections/AuxiliaryKernelExtensions.kc") == '38f58293b7636dc7867168e670bb51a66958b10b54de515148a5e0d796543da5  '* ]] || exit 1
fi
while IFS= read -r line; do
  expected=${line%%  *}
  path=${line#*  }
  case "$path" in
    Library/KernelCollections/AuxiliaryKernelExtensions.kc) continue ;;
    Library/KernelCollections/*) file="$data/$path" ;;
    System/Library/KernelCollections/*) file="$system/$path" ;;
    System/Volumes/Preboot/*) file="$preboot/${path#System/Volumes/Preboot/}" ;;
    *) exit 1 ;;
  esac
  [[ $("$hasher" "$file") == "$expected  "* ]] || exit 1
done < "$backup/SOURCE-SHA256SUMS"
daemon="$data/Library/LaunchDaemons/com.ga410.firstboot.plist"
daemon_hash=$(/usr/bin/plutil -extract CaptureDaemonSHA256 raw -o - "$config")
[[ ! -e $daemon || $("$hasher" "$daemon") == "$daemon_hash  "* ]] || exit 1
printf 'Verified actual target pair:\nData=%s\nSystem=%s\nPreboot=%s\nBackup=%s\n' "$data" "$system" "$preboot" "$backup"
if [[ $mode == --verify ]]; then
  /bin/bash "$base/restore-recovery-native.sh" --verify-backup "$backup"
  echo 'RECOVERY_PREFLIGHT_PASS: no component/KC removal or restoration performed.'
  exit 0
fi
[[ $mode == --restore ]] || exit 0
# The full original restoration is the existing native metadata-preserving tool.
# Its checksum table is pinned, and all eleven originals were absent in backup.
set +e
/bin/bash "$base/restore-recovery-native.sh" "$data" "$preboot" "$backup" > "$record/restore.stdout" 2> "$record/restore.stderr"
rc=$?
set -e
printf '%s\n' "$rc" > "$record/restore.rc"
/bin/cat "$record/restore.stdout"
/bin/cat "$record/restore.stderr" >&2
[[ $rc == 0 ]] || exit "$rc"
if [[ -e $daemon ]]; then /bin/rm "$daemon"; fi
while IFS= read -r line; do
  expected=${line%%  *}; path=${line#*  }
  case "$path" in
    Library/KernelCollections/*) file="$data/$path" ;;
    System/Library/KernelCollections/*) file="$system/$path" ;;
    System/Volumes/Preboot/*) file="$preboot/${path#System/Volumes/Preboot/}" ;;
    *) exit 1 ;;
  esac
  [[ $("$hasher" "$file") == "$expected  "* ]] || exit 1
done < "$backup/SOURCE-SHA256SUMS"
/bin/sync
echo 'ORIGINAL_GPU_STACK_RESTORED_AND_HASHED: 11 additions removed, original KC restored, capture daemon removed.'
echo 'Logs and support tools retained. NVRAM untouched. No reboot/shutdown. Use CSR0 Recovery boot policy and inspect state before VESA.'
