#!/bin/bash
# Offline installation only: launchd will first run this job in installed macOS.
set -euo pipefail
data='/Volumes/TARGET_DATA_VOLUME'
source=/tmp/ga410-firstboot-prep
destination="$data/Library/Application Support/GA410"
daemon="$data/Library/LaunchDaemons/com.ga410.firstboot.plist"
[[ $(uname -s) == Darwin && $EUID -eq 0 ]] || exit 1
[[ $(/usr/sbin/diskutil info -plist "$data" | /usr/bin/plutil -extract VolumeUUID raw -o - -) == REDACTED-SESSION-ID ]] || exit 1
[[ ! -e $destination && ! -L $destination && ! -e $daemon && ! -L $daemon ]] || exit 1
[[ ! -e $data/private/var/db/ga410-firstboot-once ]] || exit 1
[[ ! -e $data/Users/Shared/GA410-firstboot ]] || exit 1
/bin/bash -n "$source/collect-firstboot.sh"
/usr/bin/plutil -lint "$source/com.ga410.firstboot.plist"
/bin/mkdir "$destination"
for name in collect-firstboot.sh csr-readonly-probe recovery-sha256; do
  /bin/cp "$source/$name" "$destination/$name"
  /usr/sbin/chown root:wheel "$destination/$name"
  /bin/chmod 755 "$destination/$name"
done
/usr/sbin/chown root:wheel "$destination"
/bin/chmod 755 "$destination"
/bin/mkdir "$data/Users/Shared/GA410-firstboot"
/usr/sbin/chown root:admin "$data/Users/Shared/GA410-firstboot"
/bin/chmod 2750 "$data/Users/Shared/GA410-firstboot"
/bin/cp "$source/com.ga410.firstboot.plist" "$daemon"
/usr/sbin/chown root:wheel "$daemon"
/bin/chmod 644 "$daemon"
/usr/bin/plutil -lint "$daemon"
/bin/bash "$destination/collect-firstboot.sh" --check
/usr/bin/stat -f 'ADDED %u %g %p %N' "$destination" "$destination"/* "$daemon" "$data/Users/Shared/GA410-firstboot"
/bin/sync
echo 'First-boot capture installed, NOT bootstrapped in Recovery; no marker or GPU work created.'
