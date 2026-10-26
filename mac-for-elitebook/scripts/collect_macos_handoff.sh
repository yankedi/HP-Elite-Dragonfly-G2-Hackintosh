#!/bin/sh
# Run in HP macOS/Recovery. Read-only probes; private output in /tmp.
# Optional --save-usb exports only to an already mounted, checked external exFAT.
# No mount, erase, repair, installer, NVRAM or network configuration calls.
set -eu
umask 077

if [ "$(uname -s)" != Darwin ]; then
    echo 'This collector runs in macOS/Recovery, not in Linux.' >&2
    exit 2
fi
save_usb=no
budget=20
while [ "$#" -gt 0 ]; do
    case "$1" in
        --save-usb) save_usb=yes; shift ;;
        --timeout)
            [ "$#" -ge 2 ] || { echo '--timeout needs seconds (1-120).' >&2; exit 2; }
            case "$2" in ''|*[!0-9]*) echo 'Invalid timeout.' >&2; exit 2 ;; esac
            [ "$2" -ge 1 ] && [ "$2" -le 120 ] || { echo 'Timeout must be 1-120 seconds.' >&2; exit 2; }
            budget=$2; shift 2 ;;
        *) echo 'Usage: sh collect_macos_handoff.sh [--save-usb] [--timeout 1-120]' >&2; exit 2 ;;
    esac
done

work=$(/usr/bin/mktemp -d /tmp/hp-macos-observation.XXXXXX)
name=${work##*/}
status="$work/command-status.tsv"
summary="$work/SUMMARY.tsv"
printf 'observation\texit_code\tseconds\ttimed_out\tstdout_bytes\n' > "$status"
printf 'component\tobservation\tdetail\n' > "$summary"
watchdog=
probe=
cleanup() {
    [ -z "$watchdog" ] || kill "$watchdog" 2>/dev/null || :
    [ -z "$probe" ] || kill "$probe" 2>/dev/null || :
}
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM HUP
printf 'Collecting observations in %s (each command limited to %ss)\n' "$work" "$budget"

capture() {
    label=$1
    shift
    start=$(/bin/date +%s)
    if [ ! -x "$1" ]; then
        : > "$work/$label.txt"
        printf 'Tool unavailable: %s\n' "$1" > "$work/$label.stderr"
        printf '%s\t127\t0\tno\t0\n' "$label" >> "$status"
        return 0
    fi
    "$@" > "$work/$label.txt" 2> "$work/$label.stderr" &
    probe=$!
    (
        sleeper=
        trap '[ -z "$sleeper" ] || { kill "$sleeper" 2>/dev/null; wait "$sleeper" 2>/dev/null; }; exit 0' TERM INT HUP
        /bin/sleep "$budget" &
        sleeper=$!
        wait "$sleeper" || exit 0
        : > "$work/$label.timeout"
        kill -TERM "$probe" 2>/dev/null || exit 0
        /bin/sleep 2 &
        sleeper=$!
        wait "$sleeper" || exit 0
        kill -KILL "$probe" 2>/dev/null || :
    ) &
    watchdog=$!
    if wait "$probe"; then
        code=0
    else
        code=$?
    fi
    probe=
    kill "$watchdog" 2>/dev/null || :
    wait "$watchdog" 2>/dev/null || :
    watchdog=
    timed_out=no
    if [ -f "$work/$label.timeout" ]; then timed_out=yes; code=124; fi
    end=$(/bin/date +%s)
    bytes=$(/usr/bin/wc -c < "$work/$label.txt" | /usr/bin/tr -d ' ')
    printf '%s\t%s\t%s\t%s\t%s\n' "$label" "$code" "$((end-start))" "$timed_out" "$bytes" >> "$status"
}

state() {
    /usr/bin/awk -F '\t' -v key="$1" '$1 == key { if ($2 == 0) print "query_ok"; else if ($2 == 127) print "tool_unavailable"; else if ($2 == 124) print "timed_out"; else print "query_failed" }' "$status"
}

registry() {
    label=$1
    class=$2
    capture "$label" /usr/sbin/ioreg -r -c "$class" -l -w0
    observed=$(state "$label")
    detail='Query did not complete; see stderr/status'
    if [ "$observed" = query_ok ]; then
        # ioreg -c includes subclasses: IOFramebuffer may return Intel framebuffer
        # roots, not a literal IOFramebuffer class. Count returned roots instead.
        count=$(/usr/bin/grep -E '^\+-o .*<class ' "$work/$label.txt" |
            /usr/bin/grep -E -v '<class IORegistryEntry[, >]' | /usr/bin/wc -l | /usr/bin/tr -d ' ')
        if [ "$count" -gt 0 ]; then observed=registry_present; else observed=not_observed; fi
        detail="Matching registry nodes: $count; presence is not functional verification"
    fi
    printf '%s\t%s\t%s\n' "$label" "$observed" "$detail" >> "$summary"
}

plist_value() {
    /usr/libexec/PlistBuddy -c "Print :$2" "$1" 2>/dev/null || :
}

capture time /bin/date -u '+%Y-%m-%dT%H:%M:%SZ'
capture collector-sha256 /usr/bin/shasum -a 256 "$0"
capture version /usr/bin/sw_vers
capture kernel /usr/bin/uname -a
capture bootargs /usr/sbin/sysctl kern.bootargs kern.osversion kern.version
capture cpu /usr/sbin/sysctl machdep.cpu.brand_string machdep.cpu.features machdep.cpu.leaf7_features hw.memsize hw.ncpu
capture disks /usr/sbin/diskutil list
capture disks-plist /usr/sbin/diskutil list -plist
capture apfs /usr/sbin/diskutil apfs list -plist
capture mounted-filesystems /sbin/mount
capture attached-images /usr/bin/hdiutil info
capture loaded-kexts /usr/bin/kmutil showloaded --list-only
if [ "$(state loaded-kexts)" != query_ok ]; then
    capture loaded-kexts-fallback /usr/sbin/kextstat -l
fi
capture service-tree /usr/sbin/ioreg -a -l -p IOService
capture acpi-tree /usr/sbin/ioreg -p IOACPIPlane -l -w0
capture igpu /usr/sbin/ioreg -r -n IGPU -l -w0
registry pci IOPCIDevice
registry framebuffer IOFramebuffer
registry accelerator IOAccelerator
registry smc AppleSMC
capture usb /usr/sbin/ioreg -p IOUSB -l -w0
registry xhci AppleUSBXHCIPCI
registry usb-host-controller IOUSBHostController
registry usb-devices IOUSBHostDevice
registry usb-interfaces IOUSBHostInterface
registry nvme IONVMeController
registry storage IOBlockStorageDevice
registry ps2-controller ApplePS2Controller
registry ps2-keyboard ApplePS2Keyboard
registry i2c-controllers VoodooI2CPCILakeController
registry i2c-nubs VoodooI2CDeviceNub
registry i2c-hid VoodooI2CHIDDevice
registry gpio VoodooGPIO
registry precision-touchpad VoodooI2CPrecisionTouchpadHIDEventDriver
registry hid-devices IOHIDDevice
registry hid-events IOHIDEventService
registry battery AppleSmartBattery
registry audio IOAudioDevice
registry ethernet IOEthernetInterface
registry wifi IO80211Interface
registry bluetooth IOBluetoothHCIController
capture hid-list /usr/bin/hidutil list
capture interfaces /sbin/ifconfig -a
capture routes /usr/sbin/netstat -rn
capture network-state /usr/sbin/scutil --nwi
capture battery-state /usr/bin/pmset -g batt
capture power-settings /usr/bin/pmset -g custom
capture power-assertions /usr/bin/pmset -g assertions
for category in Displays USB NVMe Audio Network Bluetooth Power Thunderbolt; do
    capture "profiler-$category" /usr/sbin/system_profiler -timeout 10 -detailLevel mini "SP${category}DataType"
done
capture kernel-messages /sbin/dmesg

# Enumerate disk identifiers from diskutil, never infer a target disk by number.
printf 'device\tparent\twhole\tinternal\tvirtual_or_physical\tfilesystem\toffset_bytes\tsize_bytes\tmountpoint\n' > "$work/disk-inventory.tsv"
if [ -x /usr/libexec/PlistBuddy ] && [ "$(state disks-plist)" = query_ok ]; then
    capture disk-identifiers-plist /usr/libexec/PlistBuddy -c 'Print :AllDisks' "$work/disks-plist.txt"
    /bin/cat "$work/disk-identifiers-plist.txt" |
        /usr/bin/sed -n 's/^[[:space:]]*\(disk[0-9][0-9]*\(s[0-9][0-9]*\)*\)[[:space:]]*$/\1/p' |
        /usr/bin/head -n 64 > "$work/disk-identifiers.txt"
    printf 'disk-inventory\t%s\tUp to 64 identifiers; per-device query status and raw plists retained\n' "$(state disk-identifiers-plist)" >> "$summary"
    while IFS= read -r disk; do
        capture "disk-info-$disk" /usr/sbin/diskutil info -plist "$disk"
        if [ "$(state "disk-info-$disk")" != query_ok ]; then continue; fi
        info="$work/disk-info-$disk.txt"
        printf '%s' "$disk" >> "$work/disk-inventory.tsv"
        for key in ParentWholeDisk Whole Internal VirtualOrPhysical FilesystemType PartitionMapPartitionOffset TotalSize MountPoint; do
            value=$(plist_value "$info" "$key" | /usr/bin/tr '\t\r\n' '   ')
            printf '\t%s' "${value:-unknown}" >> "$work/disk-inventory.tsv"
        done
        printf '\n' >> "$work/disk-inventory.tsv"
    done < "$work/disk-identifiers.txt"
else
    printf 'disk-inventory\tunavailable\tdiskutil plist or PlistBuddy unavailable\n' >> "$summary"
fi

# Look for the delivered resources only in already mounted volumes.
printf 'volume\tresource\tobservation\tbytes\n' > "$work/resources.tsv"
usb_candidate=
usb_count=0
resource_index=0
for volume in /Volumes/*; do
    [ -d "$volume" ] && [ ! -L "$volume" ] || continue
    data="$volume/ISO/linux"
    [ -d "$data" ] && [ ! -L "$data" ] && [ ! -L "$volume/ISO" ] || continue
    found=no
    for resource in HP-Tahoe-VESA-Recovery.img HP-Tahoe-VESA-MMIO-Baseline.img Tahoe-26.6.2-Offline-App.hfs; do
        file="$data/$resource"
        [ -f "$file" ] && [ ! -L "$file" ] || continue
        found=yes
        capture "resource-size-$resource-$resource_index" /usr/bin/stat -f '%z' "$file"
        bytes=$(/usr/bin/tr -d '\r\n' < "$work/resource-size-$resource-$resource_index.txt")
        expected=1343225856
        [ "$resource" != Tahoe-26.6.2-Offline-App.hfs ] || expected=19922944000
        observation=size_differs
        if [ "$(state "resource-size-$resource-$resource_index")" != query_ok ]; then
            observation=query_failed
        elif [ "$bytes" = "$expected" ]; then observation=size_matches_not_hash_verified; fi
        printf '%s\t%s\t%s\t%s\n' "$volume" "$resource" "$observation" "$bytes" >> "$work/resources.tsv"
    done
    [ "$found" = yes ] || continue
    resource_index=$((resource_index+1))
    # Require both delivered inputs plus the delivery marker to identify our USB.
    if [ ! -f "$data/HP-Tahoe-VESA-Recovery.img" ] || [ ! -f "$data/Tahoe-26.6.2-Offline-App.hfs" ] ||
       [ ! -f "$data/HP-TAHOE-SHA256SUMS.txt" ]; then continue; fi
    if [ -L "$data/HP-Tahoe-VESA-Recovery.img" ] || [ -L "$data/Tahoe-26.6.2-Offline-App.hfs" ] ||
       [ -L "$data/HP-TAHOE-SHA256SUMS.txt" ]; then continue; fi
    capture "resource-volume-$resource_index" /usr/sbin/diskutil info -plist "$volume"
    info="$work/resource-volume-$resource_index.txt"
    if [ "$(state "resource-volume-$resource_index")" = query_ok ] &&
       [ "$(plist_value "$info" Internal)" = false ] &&
       [ "$(plist_value "$info" VirtualOrPhysical)" = Physical ] &&
       [ "$(plist_value "$info" FilesystemType)" = exfat ] &&
       [ "$(plist_value "$info" Writable)" = true ] &&
       [ "$(plist_value "$info" MountPoint)" = "$volume" ] &&
       [ -w "$data" ]; then
        usb_candidate=$data
        usb_count=$((usb_count+1))
    fi
done
printf 'usb-export-destination\t%s\tValidated writable external physical exFAT candidates; no volume mounted by collector\n' "$usb_count" >> "$summary"

kext_file="$work/loaded-kexts.txt"
if [ "$(state loaded-kexts)" != query_ok ]; then kext_file="$work/loaded-kexts-fallback.txt"; fi
while read -r component identifier; do
    observation=not_listed
    if [ "$(state loaded-kexts)" != query_ok ] && [ "$(state loaded-kexts-fallback)" != query_ok ]; then
        observation=query_unavailable
    elif /usr/bin/awk -v id="$identifier" '{ for (i=1; i<=NF; i++) { value=$i; sub(/\(.*/, "", value); if (value == id) found=1 } } END { exit !found }' "$kext_file"; then observation=listed; fi
    printf 'kext-%s\t%s\tExact bundle ID in loaded-kext listing; not a device functionality test\n' "$component" "$observation" >> "$summary"
done <<'EOF'
VoodooI2C com.alexandred.VoodooI2C
VoodooI2CHID com.alexandred.VoodooI2CHID
VoodooGPIO org.coolstar.VoodooGPIO
VoodooInput me.kishorprins.VoodooInput
PS2Controller as.acidanthera.voodoo.driver.PS2Controller
PS2Keyboard as.acidanthera.voodoo.driver.PS2Keyboard
Lilu as.vit9696.Lilu
VirtualSMC as.vit9696.VirtualSMC
WhateverGreen as.vit9696.WhateverGreen
AppleUSBXHCIPCI com.apple.driver.usb.AppleUSBXHCIPCI
IONVMeFamily com.apple.iokit.IONVMeFamily
EOF
/usr/bin/awk -F '\t' 'NR > 1 { total++; if ($2 != 0) failed++; if ($4 == "yes") timed++ } END { printf "commands\t%d\tFailed or missing: %d; timed out: %d\n", total, failed, timed }' "$status" >> "$summary"

cat > "$work/OBSERVATION.txt" <<'EOF'
Private read-only observation bundle, collected manually in macOS/Recovery.
SUMMARY.tsv distinguishes registry presence, absence, query failure and missing tools.
command-status.tsv records exit code, elapsed seconds, timeout and stdout length.
An exit code of zero or an empty IORegistry query is not a functional pass.
system_profiler output and accelerator class names do not prove Metal works.
No input event, network reachability, sleep, render/compute or disk-write test ran.
Disk offsets/sizes are observations, never automatic installation target selection.
Resource size matches are not hashes, signature verification or installation tests.
Missing Recovery tools and permissions are preserved as failures, not device absence.
These raw logs may contain private disk identifiers or machine identities.
Keep outside Git and review before sharing publicly.
EOF

printf 'mode\t%s\nvalidated_candidates\t%s\n' "$save_usb" "$usb_count" > "$work/export-plan.tsv"
archive="$work.tar.gz"
/usr/bin/tar -czf "$archive" -C /tmp "$name"
printf '\nPrivate logs: %s\nArchive: %s\n' "$work" "$archive"
if [ "$save_usb" = yes ]; then
    if [ "$usb_count" -eq 1 ]; then
        # A fresh directory avoids overwriting prior captures or following log symlinks.
        if export_dir=$(/usr/bin/mktemp -d "$usb_candidate/HP-Diagnostics.XXXXXX"); then
            destination="$export_dir/$name.tar.gz"
            if /bin/cp "$archive" "$destination" && /usr/bin/cmp -s "$archive" "$destination"; then
                /bin/sync
                printf 'USB archive (byte-compared): %s\n' "$destination"
            else
                printf 'USB export failed; original archive retained at %s\n' "$archive" >&2
                exit 1
            fi
        else
            printf 'Cannot create USB diagnostic directory; original archive retained.\n' >&2
            exit 1
        fi
    else
        printf 'USB export skipped: need exactly one checked mounted external exFAT volume; found %s. Original archive retained.\n' "$usb_count" >&2
        exit 1
    fi
else
    printf 'Files in /tmp disappear on restart. Copy the archive before leaving Recovery, or run with --save-usb.\n'
fi
printf 'No disks were mounted, repaired, partitioned or selected for installation.\n'
