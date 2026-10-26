#!/bin/bash
# Execute only for the explicitly authorized GA4.10 installation.
set -euo pipefail
umask 077
[[ $(uname -s) == Darwin && $EUID -eq 0 ]] || exit 1
[[ $(/usr/bin/sw_vers -buildVersion) == 25G83 ]] || exit 1
backup=${1:?fresh absolute backup directory}
[[ $backup == /Users/Shared/GA410-backup-* && ! -e $backup && ! -L $backup ]] || exit 1
/bin/mkdir -m 700 "$backup"
exec > >(tee "$backup/backup.log") 2>&1
trap 'rc=$?; printf "%s\n" "$rc" > "$backup/backup.rc"; exit "$rc"' EXIT
/usr/bin/sw_vers > "$backup/sw_vers.txt"
/usr/bin/uname -a > "$backup/kernel.txt"
/usr/sbin/diskutil info -plist / > "$backup/root-info.plist"
group=$(/usr/bin/plutil -extract APFSVolumeGroupID raw -o - "$backup/root-info.plist")
[[ $group =~ ^[A-F0-9-]{36}$ ]] || exit 1
preboot="/System/Volumes/Preboot/$group/boot/System/Library/KernelCollections"
[[ -d $preboot ]] || exit 1
printf '%s\n' "$preboot" > "$backup/preboot-path.txt"
/usr/sbin/nvram -xp > "$backup/nvram.plist"
/usr/sbin/sysctl -n kern.bootargs > "$backup/bootargs.txt"
/usr/bin/csrutil status > "$backup/sip.txt"
/usr/bin/csrutil authenticated-root status > "$backup/authenticated-root.txt"
/usr/sbin/diskutil apfs list > "$backup/apfs-list.txt"
/usr/sbin/diskutil apfs listVolumeGroups > "$backup/apfs-groups.txt"
/usr/sbin/diskutil apfs listSnapshots / > "$backup/snapshots.txt"
/sbin/mount > "$backup/mount.txt"
/usr/bin/kmutil showloaded > "$backup/showloaded.txt"
/usr/bin/kmutil inspect -A /Library/KernelCollections/AuxiliaryKernelExtensions.kc --show-extension-info > "$backup/aux-inspect.txt"
/usr/bin/kmutil inspect -B /System/Library/KernelCollections/BootKernelExtensions.kc -S /System/Library/KernelCollections/SystemKernelExtensions.kc --show-extension-info > "$backup/system-inspect.txt"
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
 /Library/KernelCollections
 "$preboot"
 /System/Library/KernelCollections
)
: > "$backup/present.txt"
: > "$backup/absent.txt"
: > "$backup/relative-paths.txt"
: > "$backup/SOURCE-SHA256SUMS"
/bin/mkdir "$backup/metadata"
for path in "${paths[@]}"; do
  name=${path//\//_}
  /bin/ls -ldeO@ "$(/usr/bin/dirname "$path")" > "$backup/metadata/$name.parent.txt"
  if [[ -e $path || -L $path ]]; then
    printf '%s\n' "$path" >> "$backup/present.txt"
    /bin/ls -ldeO@ "$path" > "$backup/metadata/$name.txt"
    /usr/bin/stat -f '%d %i %p %u %g %f %z %N' "$path" >> "$backup/metadata/$name.txt"
    /usr/bin/xattr -lr "$path" > "$backup/metadata/$name.xattrs.txt"
    printf '%s\n' "${path#/}" >> "$backup/relative-paths.txt"
    ( cd /; /usr/bin/find "${path#/}" -type f -exec /usr/bin/shasum -a 256 {} \; ) >> "$backup/SOURCE-SHA256SUMS"
  else
    printf '%s\n' "$path" >> "$backup/absent.txt"
  fi
done
# Archive original metadata without applying protected rootless xattrs to a live
# backup copy. Preserve these in pax; restore their flags only in Recovery.
/usr/bin/tar --format pax --acls --xattrs --fflags --mac-metadata -cpf "$backup/files.pax" -C / -T "$backup/relative-paths.txt"
/usr/bin/tar -tvf "$backup/files.pax" > "$backup/archive-list.txt"
/bin/mkdir "$backup/content-check"
COPYFILE_DISABLE=1 /usr/bin/tar -xpf "$backup/files.pax" --no-mac-metadata --no-xattrs --no-fflags --no-acls -C "$backup/content-check"
( cd "$backup/content-check"; /usr/bin/shasum -a 256 -c ../SOURCE-SHA256SUMS ) > "$backup/content-check.txt"
/bin/rm -rf "$backup/content-check"
( cd "$backup"; /usr/bin/shasum -a 256 files.pax SOURCE-SHA256SUMS; /usr/bin/find metadata -type f -exec /usr/bin/shasum -a 256 {} \; ) > "$backup/SHA256SUMS"
( cd "$backup"; /usr/bin/shasum -a 256 -c SHA256SUMS ) > "$backup/hash-verify.txt"
/usr/bin/touch "$backup/BACKUP-COMPLETE"
# Finalize the directory's recovery inputs before packaging it. The EXIT trap
# still replaces backup.rc with any later packaging failure, so callers must
# require both successful execution and a verified portable archive.
printf '0\n' > "$backup/backup.rc"
# The portable unit includes its checksum manifest and completion indicators.
/usr/bin/ditto -c -k --rsrc --extattr --acl --sequesterRsrc --keepParent "$backup" "$backup.restore.zip"
/usr/bin/shasum -a 256 "$backup.restore.zip" > "$backup.restore.zip.sha256"
echo 'BACKUP_FILES_COMPLETE: archive and off-machine checks still required.'
