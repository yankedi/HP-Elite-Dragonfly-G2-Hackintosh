#!/bin/bash
# REVIEW ONLY: future, separately authorized recovery after restoring files.
# Syntax is from this target's actual kmutil install --help (25G83).
set -euo pipefail
[[ $(uname -s) == Darwin && $EUID -eq 0 ]] || exit 1
[[ ${GA48_SEPARATELY_AUTHORIZED_PHASE:-} == restore-kc ]] || exit 1
backup=${1:?existing backup directory required}
volume=${2:?mounted target macOS volume root required}
[[ $backup == /*/GA48-backup-* && $backup != *..* && ! -L $backup && -f $backup/BACKUP-COMPLETE ]] || exit 1
[[ $volume == /* && $volume != *..* && -d $volume/System/Library/KernelCollections ]] || exit 1
[[ -f $backup/FILES-RESTORED && $(/bin/cat "$backup/FILES-RESTORED") == "$volume" ]] || exit 1
# Requires the matching build KDK and allowed target loading policy.
# Never use -z or --allow-missing-kdk; never swallow a failed rebuild.
set +e
/usr/bin/kmutil install --volume-root "$volume" --update-all > "$backup/restore-kc.log" 2>&1
rc=$?
set -e
/bin/cat "$backup/restore-kc.log"
printf '%s\n' "$rc" > "$backup/restore-kc.log.rc"
[[ $rc -eq 0 ]] || exit "$rc"
/usr/bin/kmutil inspect -B "$volume/System/Library/KernelCollections/BootKernelExtensions.kc" -S "$volume/System/Library/KernelCollections/SystemKernelExtensions.kc" -A "$volume/Library/KernelCollections/AuxiliaryKernelExtensions.kc" --show-extension-info > "$backup/restore-kc-inspect.txt"
echo 'Rebuild returned success. Review the inspection and active Preboot KC identity before any separately approved reboot.'
