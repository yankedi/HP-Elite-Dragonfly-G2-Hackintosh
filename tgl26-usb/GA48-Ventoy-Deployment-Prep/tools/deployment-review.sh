#!/bin/bash
# REVIEW COPY: generated locally, never executed on the target in GA48.
# Each mutating phase needs a separately authorized invocation in a later round.
# No SIP/SSV/AMFI changes, no signing, no reboot, no EFI writes are implemented.
set -euo pipefail
umask 077

fail() { echo "STOP: $*" >&2; exit 1; }
[[ $(uname -s) == Darwin ]] || fail 'macOS required'
phase=${1:-help}
case "$phase" in
  backup|preflight|install-kexts|install-userland|register) ;;
  *) echo 'Review only. Phases: backup, preflight, install-kexts, install-userland, register'; exit 0 ;;
esac
[[ ${GA48_SEPARATELY_AUTHORIZED_PHASE:-} == "$phase" ]] || fail 'phase-specific user authorization required'
[[ $(/usr/bin/sw_vers -buildVersion) == 25G83 ]] || fail 'target build changed'
[[ $EUID -eq 0 ]] || fail 'root needed for the future backup/install operation'
package=${2:?absolute unpacked package directory required}
backup=${3:?absolute fresh backup directory required}
[[ $package == /Users/Shared/GA48-preflight/package ]] || fail 'unexpected staging path'
[[ $backup == /Users/Shared/GA48-backup-* && $backup != *..* ]] || fail 'unexpected backup path'
[[ -d $package && ! -L $package ]] || fail 'package absent or symlink'
# PACKAGE-SHA256SUMS must be supplied from the audited local archive extraction.
( cd "$package"; /usr/bin/shasum -a 256 -c ../PACKAGE-SHA256SUMS )

LE_KEXTS=(HookCase.kext AppleIntelTGLGraphicsFramebuffer.kext AppleIntelTGLGraphics.kext)
LE_BUNDLES=(AppleIntelTGLGraphicsMTLDriver.bundle AppleIntelTGLGraphicsGLDriver.bundle AppleIntelTGLGraphicsVADriver.bundle AppleIntelTGLGraphicsVAME.bundle AppleIntelGraphicsShared.bundle)
GPU_BUNDLES=(AppleIntelTGLGraphicsMTLDriver.bundle AppleIntelGraphicsShared.bundle)
PATHS=()
for name in "${LE_KEXTS[@]}" "${LE_BUNDLES[@]}"; do PATHS+=("/Library/Extensions/$name"); done
for name in "${GPU_BUNDLES[@]}"; do PATHS+=("/Library/GPUBundles/$name"); done
PATHS+=(/System/Library/Caches/xe.bundle /Library/KernelCollections)
preboot=${GA48_PREBOOT_KC:?current active Preboot KC path from read-only evidence required}
[[ $preboot == /System/Volumes/Preboot/*/boot/System/Library/KernelCollections && $preboot != *..* && -d $preboot ]] || fail 'unverified Preboot KC path'
PATHS+=("$preboot")

case "$phase" in
backup)
  [[ ! -e $backup ]] || fail 'backup already exists'
  /bin/mkdir -m 700 "$backup"
  /usr/bin/sw_vers > "$backup/sw_vers.txt"
  /usr/bin/csrutil status > "$backup/sip.txt"
  /usr/bin/csrutil authenticated-root status > "$backup/authenticated-root.txt"
  /usr/sbin/nvram -xp > "$backup/nvram.plist"
  /usr/sbin/sysctl -n kern.bootargs > "$backup/bootargs.txt"
  /usr/bin/kmutil showloaded > "$backup/loaded.txt"
  /usr/bin/kmutil inspect -A /Library/KernelCollections/AuxiliaryKernelExtensions.kc --show-extension-info > "$backup/aux-inspect.txt"
  /usr/sbin/diskutil apfs listSnapshots / > "$backup/snapshots.txt"
  /sbin/mount > "$backup/mount.txt"
  : > "$backup/present.txt"
  : > "$backup/absent.txt"
  for path in "${PATHS[@]}"; do
    if [[ -e $path || -L $path ]]; then
      printf '%s\n' "$path" >> "$backup/present.txt"
      /bin/mkdir -p "$backup/files$(/usr/bin/dirname "$path")"
      /usr/bin/ditto --rsrc --extattr --acl "$path" "$backup/files$path"
      # ditto preserves metadata. Compare content before recording backup complete.
      logname=${path//\//_}
      /usr/bin/diff -rq "$path" "$backup/files$path" > "$backup/compare-$logname.txt"
    else
      printf '%s\n' "$path" >> "$backup/absent.txt"
    fi
  done
  ( cd "$backup"; /usr/bin/find files -type f -exec /usr/bin/shasum -a 256 {} \; ) > "$backup/SHA256SUMS"
  /usr/bin/touch "$backup/BACKUP-COMPLETE"
  ;;
preflight)
  [[ -f $backup/BACKUP-COMPLETE ]] || fail 'verified backup required'
  # Native validation can fail on upstream ad-hoc/unsigned inputs. Stop, do not auto-sign.
  for name in Lilu.kext NootedGreen.kext; do
    /usr/bin/codesign --verify --strict --deep --verbose=4 "$package/efi-add/OC/Kexts/$name"
  done
  for name in "${LE_KEXTS[@]}" "${LE_BUNDLES[@]}"; do
    /usr/bin/codesign --verify --strict --deep --verbose=4 "$package/payload/Library/Extensions/$name"
  done
  for name in "${GPU_BUNDLES[@]}"; do
    /usr/bin/codesign --verify --strict --deep --verbose=4 "$package/payload/Library/GPUBundles/$name"
  done
  /usr/bin/codesign --verify --strict --deep --verbose=4 "$package/payload/System/Library/Caches/xe.bundle"
  # This receipt means structural signature verification only, not Apple trust or loadability.
  /usr/bin/touch "$backup/NATIVE-STRUCTURAL-SIGNATURES-PASS"
  ;;
install-kexts|install-userland|register)
  [[ -f $backup/BACKUP-COMPLETE && -f $backup/NATIVE-STRUCTURAL-SIGNATURES-PASS ]] || fail 'backup and signature verification required'
  # A reviewed out-of-band receipt is required: actual loading policy / SSV layout,
  # trusted/resigned package hashes, VESA path and recovery method must be approved.
  [[ -f $backup/LOADING-AND-RECOVERY-PLAN-APPROVED ]] || fail 'loading/recovery prerequisites unresolved'
  ( cd "$backup"; /usr/bin/shasum -a 256 -c SHA256SUMS )
  if [[ $phase == install-kexts ]]; then
    for name in "${LE_KEXTS[@]}"; do
      path="/Library/Extensions/$name"
      /bin/rm -rf "$path"
      /usr/bin/ditto --rsrc --extattr --acl "$package/payload$path" "$path"
      /usr/sbin/chown -R root:wheel "$path"
      /usr/bin/diff -rq "$package/payload$path" "$path"
    done
    /usr/bin/touch "$backup/KEXT-FILES-INSTALLED"
  elif [[ $phase == install-userland ]]; then
    # GA49 correction: Caches is a Data firmlink, not the sealed root volume.
    # Check the exact destinations, not mount /; W_OK does not prove sandbox/trust.
    for parent in /Library/Extensions /Library/GPUBundles /System/Library/Caches; do
      /bin/ls -ldeO "$parent"
      /bin/df -P "$parent"
      [[ -d $parent && -w $parent ]] || fail "destination not writable under current policy: $parent"
    done
    for name in "${LE_BUNDLES[@]}"; do
      path="/Library/Extensions/$name"
      /bin/rm -rf "$path"
      /usr/bin/ditto --rsrc --extattr --acl "$package/payload$path" "$path"
      /usr/sbin/chown -R root:wheel "$path"
      /usr/bin/diff -rq "$package/payload$path" "$path"
    done
    for name in "${GPU_BUNDLES[@]}"; do
      path="/Library/GPUBundles/$name"
      /bin/rm -rf "$path"
      /usr/bin/ditto --rsrc --extattr --acl "$package/payload$path" "$path"
      /usr/sbin/chown -R root:wheel "$path"
      /usr/bin/diff -rq "$package/payload$path" "$path"
    done
    path=/System/Library/Caches/xe.bundle
    /bin/rm -rf "$path"
    /usr/bin/ditto --rsrc --extattr --acl "$package/payload$path" "$path"
    /usr/sbin/chown -R root:wheel "$path"
    /usr/bin/diff -rq "$package/payload$path" "$path"
    /usr/bin/touch "$backup/USERLAND-FILES-INSTALLED"
  else
    [[ -f $backup/KEXT-FILES-INSTALLED && -f $backup/USERLAND-FILES-INSTALLED ]] || fail 'complete system-side stack must precede registration'
    # Inspect is read-only; load below IS mutating and requires separate registration approval.
    # This script does NOT copy upstream -z/--no-authorization.
    # Preserve exact failure exit status. Never append || true.
    for name in "${LE_KEXTS[@]}"; do
      log="$backup/register-$name.log"
      set +e
      /usr/bin/kmutil load --load-style match-only -p "/Library/Extensions/$name" > "$log" 2>&1
      rc=$?
      set -e
      /bin/cat "$log"
      printf '%s\n' "$rc" > "$log.rc"
      [[ $rc -eq 0 ]] || exit "$rc"
    done
    /usr/bin/kmutil inspect -A /Library/KernelCollections/AuxiliaryKernelExtensions.kc --show-extension-info > "$backup/aux-after.txt"
  fi
  ;;
esac
