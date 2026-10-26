#!/usr/bin/env python3
"""Collect read-only Linux evidence over SSH; write files only on this host."""

import argparse
import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import subprocess

ROOT = Path(__file__).resolve().parents[1]

# These are fixed read-only observations, not user-supplied shell fragments.
COMMANDS = {
    "system.txt": "uname -a; cat /etc/os-release; id; uptime; lscpu; free -h",
    "dmi.txt": "for a in sys_vendor product_name product_version board_name bios_version bios_date; do printf '%s=' \"$a\"; cat /sys/class/dmi/id/\"$a\"; done",
    "pci.txt": "lspci -Dnnk; lspci -tv; sudo -n lspci -vv -s 00:02.0; readlink -f /sys/class/nvme/nvme0/device",
    "usb.txt": "lsusb; lsusb -t",
    "storage.json": "lsblk --json -b -e7 -o NAME,MODEL,SIZE,TYPE,FSTYPE,MOUNTPOINTS,TRAN",
    "nvme-controller.json": "sudo -n nvme id-ctrl /dev/nvme0 -o json",
    "nvme-health.json": "sudo -n nvme smart-log /dev/nvme0 -o json",
    "audio.txt": "cat /proc/asound/cards; for f in /proc/asound/card*/codec*; do if [ -f \"$f\" ]; then cat \"$f\"; fi; done",
    "inputs.txt": "cat /proc/bus/input/devices; for d in /sys/bus/hid/devices/0018:*; do if [ -d \"$d\" ]; then printf '\\n%s\\n' \"$d\"; cat \"$d/uevent\"; readlink -f \"$d/driver\"; fi; done",
    "acpi-devices.txt": "for d in /sys/bus/acpi/devices/*; do if [ -r \"$d/path\" ]; then printf '%s ' \"${d##*/}\"; cat \"$d/path\"; if [ -r \"$d/status\" ]; then cat \"$d/status\"; fi; if [ -r \"$d/modalias\" ]; then cat \"$d/modalias\"; fi; fi; done",
    "i2c.txt": "for f in /sys/bus/i2c/devices/*/name /sys/bus/i2c/devices/*/modalias; do if [ -r \"$f\" ]; then printf '%s: ' \"$f\"; cat \"$f\"; fi; done",
    "sensors.txt": "for d in /sys/bus/iio/devices/iio:device*; do if [ -d \"$d\" ]; then printf '%s ' \"${d##*/}\"; cat \"$d/name\"; fi; done",
    "power.txt": "cat /sys/power/mem_sleep; for d in /sys/class/power_supply/BAT*; do for a in manufacturer model_name technology charge_full_design charge_full charge_now energy_full_design energy_full energy_now voltage_min_design voltage_now cycle_count status; do if [ -r \"$d/$a\" ]; then printf '%s=' \"$a\"; cat \"$d/$a\"; fi; done; done",
    "graphics.txt": "for a in i915_display_info i915_capabilities i915_sseu_status; do sudo -n cat /sys/kernel/debug/dri/0000:00:02.0/\"$a\" || exit; done; for d in /sys/class/drm/card*-eDP-*; do printf '\\n%s\\n' \"$d\"; cat \"$d/status\" \"$d/modes\"; edid-decode \"$d/edid\"; done; for d in /sys/class/backlight/*; do printf '\\n%s\\n' \"$d\"; for a in type brightness actual_brightness max_brightness; do printf '%s=' \"$a\"; cat \"$d/$a\"; done; done",
    "firmware.txt": "for n in 'Secure Boot' 'Fast Boot' 'Configure Storage Controller for VMD' 'Video Memory Size' 'Virtualization Technology for Directed I!O (VTd)' 'Virtualization Technology (VTx)' 'Thunderbolt Mode' 'Thunderbolt Type-C Ports' 'USB Storage Boot' 'USB Type-C Connector System Software Interface (UCSI)' 'Force enable HP Sure View' 'Video BIOS Version' 'Sure Start BIOS Settings Protection'; do f=\"/sys/class/firmware-attributes/hp-bioscfg/attributes/$n/current_value\"; if [ -r \"$f\" ]; then printf '%s=' \"$n\"; cat \"$f\"; fi; done; for f in /sys/firmware/efi/efivars/SecureBoot-* /sys/firmware/efi/efivars/SetupMode-*; do if [ -f \"$f\" ]; then printf '%s ' \"${f##*/}\"; sudo -n od -An -tu1 \"$f\"; fi; done; printf 'GGC_00_00_0_50w='; sudo -n setpci -s 00:00.0 50.w",
}

# Explicit whitelist: never dump MSDM, EFI variable stores, keys or whole disks.
BINARY_SCRIPT = r"""set -eu
for f in \
 /sys/firmware/acpi/tables/DSDT \
 /sys/firmware/acpi/tables/SSDT* \
 /sys/firmware/acpi/tables/dynamic/SSDT* \
 /sys/firmware/acpi/tables/APIC \
 /sys/firmware/acpi/tables/DMAR \
 /sys/firmware/acpi/tables/FACP \
 /sys/firmware/acpi/tables/FACS \
 /sys/firmware/acpi/tables/HPET \
 /sys/firmware/acpi/tables/LPIT \
 /sys/firmware/acpi/tables/MCFG \
 /sys/firmware/acpi/tables/NHLT \
 /sys/firmware/dmi/tables/DMI \
 /sys/firmware/dmi/tables/smbios_entry_point \
 /sys/kernel/debug/dri/0000:00:02.0/i915_vbt \
 /sys/kernel/debug/dri/0000:00:02.0/i915_opregion \
 /sys/class/drm/card*-eDP-*/edid \
 /sys/bus/hid/devices/0018:*/report_descriptor
do
 if [ -f "$f" ]; then
  value=$(base64 -w0 "$f")
  printf '%s\t%s\n' "${f#/}" "$value"
 fi
done
"""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Existing SSH host or user@host")
    args = parser.parse_args()
    if args.host.startswith("-") or any(c.isspace() for c in args.host):
        parser.error("host must be a single SSH destination, not command options")
    now = datetime.now(timezone.utc)
    dest = ROOT / ".local/hardware" / now.strftime("%Y%m%dT%H%M%S.%fZ")
    dest.mkdir(parents=True, mode=0o700)
    ssh = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", args.host]
    subprocess.run(ssh + ["sudo -n true"], check=True, timeout=20)
    evidence = {"schema_version": 1, "captured_at": now.isoformat(), "host": args.host,
                "remote_policy": "read-only; no reboot, firmware, EFI or filesystem changes",
                "files": [], "commands": []}

    def save(relative, data):
        path = dest / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o600)
        evidence["files"].append({"path": relative, "bytes": len(data), "sha256": digest(data)})

    for name, command in COMMANDS.items():
        result = subprocess.run(ssh + ["LC_ALL=C sh -s"], input=command.encode(),
                                capture_output=True, timeout=60)
        save("text/" + name, result.stdout)
        if result.stderr:
            save("stderr/" + name + ".txt", result.stderr)
        evidence["commands"].append({"file": "text/" + name, "command": command,
                                     "exit_code": result.returncode})
    result = subprocess.run(ssh + ["sudo -n sh -s"], input=BINARY_SCRIPT.encode(),
                            capture_output=True, timeout=90)
    if result.stderr:
        save("stderr/binary-collection.txt", result.stderr)
    seen = set()
    for line in result.stdout.splitlines():
        raw_path, encoded = line.split(b"\t", 1)
        relative = PurePosixPath(raw_path.decode())
        if relative.is_absolute() or ".." in relative.parts or str(relative) in seen:
            raise RuntimeError("Invalid or duplicated evidence path")
        seen.add(str(relative))
        save("raw/" + str(relative), base64.b64decode(encoded, validate=True))
    evidence["binary_collection_exit_code"] = result.returncode
    (dest / "manifest.json").write_text(json.dumps(evidence, indent=2) + "\n")
    (dest / "manifest.json").chmod(0o600)
    print(dest.relative_to(ROOT))
    if result.returncode or any(c["exit_code"] for c in evidence["commands"]):
        raise SystemExit("Some observations failed; inspect the manifest and stderr before using this capture.")


if __name__ == "__main__":
    main()
