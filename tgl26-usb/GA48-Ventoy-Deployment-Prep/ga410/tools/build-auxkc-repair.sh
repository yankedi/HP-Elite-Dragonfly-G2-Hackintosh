#!/bin/bash
# One user-requested repair attempt. Only a new candidate is written.
# Native create's default local authentication mode is retained; authorization
# checks are not disabled. A candidate is not proof of trusted loading.
set -euo pipefail
[[ $(uname -s) == Darwin && $EUID -eq 0 ]] || exit 1
system='/Volumes/TARGET_SYSTEM_VOLUME'
data='/Volumes/TARGET_DATA_VOLUME'
group=${EXPECTED_APFS_VOLUME_GROUP_ID:?set EXPECTED_APFS_VOLUME_GROUP_ID for the intended target}
relative=/Users/Shared/GA410-work-20261023-0820/kc-repair-aux-20261023
work="$data$relative"
kdk="$data/Library/Developer/KDKs/KDK_26.6.2_25G83.kdk"
hasher=/tmp/ga410-policy-prep/recovery-sha256
[[ $(/usr/sbin/diskutil info -plist "$system" | /usr/bin/plutil -extract APFSVolumeGroupID raw -o - -) == "$group" ]] || exit 1
[[ $(/usr/sbin/diskutil info -plist "$data" | /usr/bin/plutil -extract VolumeUUID raw -o - -) == "$group" ]] || exit 1
[[ $(/usr/bin/plutil -extract ProductBuildVersion raw -o - "$system/System/Library/CoreServices/SystemVersion.plist") == 25G83 ]] || exit 1
[[ -f $kdk/System/Library/Kernels/kernel ]] || exit 1
[[ $("$hasher" "$kdk/System/Library/Kernels/kernel") == '1542ae9efea6d3a212248446d610b677d66fec02da5a5bfacf2b1a67f544b47e  '* ]] || exit 1
"$hasher" -c /tmp/ga410-policy-prep/CURRENT-KC-SHA256SUMS
( cd "$data"; "$hasher" -c /tmp/ga410-policy-prep/INSTALL-SHA256SUMS )
# mkdir is an exclusive attempt guard. Never retry this script automatically.
/bin/mkdir "$work"
command=(
 /usr/bin/kmutil create --new aux
 --volume-root "$system" --kdk "$kdk"
 --variant-suffix release --arch x86_64 --verbose
 --boot-path /System/Library/KernelCollections/BootKernelExtensions.kc
 --system-path /System/Library/KernelCollections/SystemKernelExtensions.kc
 --auxiliary-path "$relative/AuxiliaryKernelExtensions.kc"
 --repository "$system/Library/Extensions"
 --repository "$system/Library/StagedExtensions/Library/Extensions"
 --repository "$system/Library/Apple/System/Library/Extensions"
 --explicit-only
 --bundle-identifier org.smichaud.HookCase
 --bundle-identifier com.xxxxx.driver.AppleIntelTGLGraphics
 --bundle-identifier com.xxxxx.driver.AppleIntelTGLGraphicsFramebuffer
 --bundle-identifier com.highpoint-tech.kext.HighPointIOP
 --bundle-identifier com.highpoint-tech.kext.HighPointRR
 --bundle-identifier com.apple.driver.AppleMobileDevice
)
printf '%q ' "${command[@]}" > "$work/command.txt"
printf '\n' >> "$work/command.txt"
set +e
"${command[@]}" > "$work/stdout.txt" 2> "$work/stderr.txt"
rc=$?
set -e
printf '%s\n' "$rc" > "$work/returncode"
/bin/cat "$work/command.txt" "$work/stdout.txt"
/bin/cat "$work/stderr.txt" >&2
[[ $rc == 0 ]] || exit "$rc"
[[ -f $work/AuxiliaryKernelExtensions.kc ]] || exit 1
"$hasher" "$work/AuxiliaryKernelExtensions.kc"
echo 'AUXKC_CANDIDATE_BUILT: original installed KC untouched; inspect before publication.'
