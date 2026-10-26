#!/usr/bin/env python3
"""Inspect an existing USB layout without mounting or opening it for writing."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("device", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    device = args.device.resolve(strict=True)
    if device.parent != Path("/dev") or not device.is_block_device():
        parser.error("device must resolve to a block device directly under /dev")
    layout = json.loads(subprocess.check_output([
        "lsblk", "--json", "-b", "-o", "NAME,SIZE,TRAN,TYPE,PTTYPE,PARTTYPE,LABEL,FSTYPE,MOUNTPOINTS", str(device)
    ]))
    disk, = layout["blockdevices"]
    if disk["tran"] != "usb" or disk["type"] != "disk":
        parser.error("selected device is not a whole USB disk")
    properties = dict(line.split("=", 1) for line in subprocess.check_output(
        ["udevadm", "info", "--query=property", "--name", str(device)], text=True).splitlines() if "=" in line)
    # Explicitly exclude serial numbers and persistent identifiers.
    safe = {key: properties.get(key) for key in ("ID_USB_VENDOR", "ID_USB_VENDOR_ID", "ID_USB_MODEL", "ID_USB_MODEL_ID", "ID_USB_DRIVER")}
    data = {"schema_version": 1, "captured_at": datetime.now(timezone.utc).isoformat(),
            "device_at_capture": str(device), "usb": safe, "layout": disk,
            "policy": "Preserve existing data and Ventoy partitions; metadata inspection only.",
            "free_space_bytes": None,
            "free_space_note": "Not mounted or read at filesystem level; total partition capacity is not free space.",
            "installation_target": "Not selected. This USB is currently only an existing Ventoy data/boot device."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
