#!/usr/bin/env python3
"""Produce a deliberately allowlisted, serial-free inventory from a private capture."""

import argparse
import json
from pathlib import Path
import re
import struct

from verify_evidence import verify


def memory_devices(data):
    records = []
    offset = 0
    while offset + 4 <= len(data):
        kind, length, _ = struct.unpack_from("<BBH", data, offset)
        if length < 4 or offset + length > len(data):
            raise ValueError("Invalid SMBIOS record")
        end = data.find(b"\0\0", offset + length)
        if end < 0:
            raise ValueError("Unterminated SMBIOS string set")
        strings = data[offset + length:end].split(b"\0")

        def text(field):
            index = data[offset + field] if field < length else 0
            return strings[index - 1].decode(errors="replace").strip() if 0 < index <= len(strings) else ""

        if kind == 17 and length >= 27:
            size = struct.unpack_from("<H", data, offset + 12)[0]
            if size == 0x7FFF and length >= 32:
                mib = struct.unpack_from("<I", data, offset + 28)[0] & 0x7FFFFFFF
            elif size in (0, 0xFFFF):
                mib = None
            else:
                mib = (size & 0x7FFF) / 1024 if size & 0x8000 else size
            records.append({"location": text(16), "bank": text(17), "size_mib": mib,
                            "form_factor_code": data[offset + 14], "type_code": data[offset + 18],
                            "speed_mts": struct.unpack_from("<H", data, offset + 21)[0],
                            "manufacturer": text(23), "part_number": text(26)})
        offset = end + 2
        if kind == 127:
            break
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify(args.capture)
    manifest = json.loads((args.capture / "manifest.json").read_text())
    entries = {item["path"]: item for item in manifest["files"]}

    def read(name):
        return (args.capture / "text" / name).read_text()

    def fields(text):
        return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)

    def match(pattern, text):
        result = re.search(pattern, text, re.MULTILINE)
        if not result:
            raise ValueError(f"Expected observation not found: {pattern}")
        return result.group(1)

    def evidence(*paths):
        return [{"path": p, "bytes": entries[p]["bytes"], "sha256": entries[p]["sha256"]} for p in paths]

    raw = "raw/sys/"
    edid_path = next(p for p in entries if p.endswith("/edid"))
    edid = (args.capture / edid_path).read_bytes()
    memory_path = raw + "firmware/dmi/tables/DMI"
    memory = memory_devices((args.capture / memory_path).read_bytes())
    system = read("system.txt")
    pci = read("pci.txt")
    audio = read("audio.txt")
    graphics = read("graphics.txt")
    inputs = read("inputs.txt")
    firmware = fields(read("firmware.txt"))
    panel_model = next(edid[i+5:i+18].decode("ascii").strip() for i in range(54, 126, 18)
                       if edid[i:i+5] == b"\x00\x00\x00\xfe\x00")
    native_clock = int.from_bytes(edid[54:56], "little") * 10000
    width = edid[56] + ((edid[58] >> 4) << 8)
    height = edid[59] + ((edid[61] >> 4) << 8)
    for required in ("SYNA30B6", "WACF4233", "06CB:CD74", "056A:4924"):
        if required not in inputs:
            raise ValueError(f"Expected input device missing: {required}")
    alsa = audio.split("Codec: Realtek ALC285", 1)[1].split("Codec:", 1)[0]
    nvme = json.loads(read("nvme-controller.json"))
    health = json.loads(read("nvme-health.json"))
    acpi_paths = [p for p in entries if "/acpi/tables/" in p]
    inventory = {
        "schema_version": 1,
        "captured_at": manifest["captured_at"],
        "capture_directory": str(args.capture),
        "status": "read-only hardware evidence; macOS not boot-tested",
        "system": {"values": fields(read("dmi.txt")), "evidence": evidence("text/dmi.txt")},
        "cpu": {"model_name": match(r"^Model name:\s*(.+)$", system),
                "family": int(match(r"^CPU family:\s*(\d+)", system)),
                "model": int(match(r"^Model:\s*(\d+)", system)),
                "stepping": int(match(r"^Stepping:\s*(\d+)", system)),
                "logical_processors": int(match(r"^CPU\(s\):\s*(\d+)", system)),
                "evidence": evidence("text/system.txt")},
        "memory": {"total_mib": sum(d["size_mib"] or 0 for d in memory), "devices": memory,
                   "note": "SMBIOS reports LPDDR4 (type 30), 4267 MT/s, onboard. LPDDR4X voltage subtype is user-reported, not independently measured.",
                   "evidence": evidence(memory_path)},
        "gpu": {"pci_id": match(r"0000:00:02.0.*\[([0-9a-f]{4}:[0-9a-f]{4})\] \(rev", pci),
                "pci_address": "0000:00:02.0", "subsystem_id": "103c:8716", "revision": "01",
                "linux_driver": "i915", "graphics_stepping": match(r"^graphics stepping:\s*(\S+)", graphics),
                "available_eus": int(match(r"^EU total:\s*(\d+)", graphics)),
                "available_subslices": int(match(r"^subslice total:\s*(\d+)", graphics)),
                "evidence": evidence("text/pci.txt", "text/graphics.txt")},
        "display": {"edid_id": f"IVO{int.from_bytes(edid[10:12], 'little'):04X}",
                    "model_string": panel_model, "native_pixels": [width, height],
                    "pixel_clock_hz": native_clock, "route": "pipe A / DDI A / PHY A / eDP-1",
                    "active_lanes": int(match(r"port_clock=\d+, lane_count=(\d+)", graphics)),
                    "active_link_rate_mbps_per_lane": int(match(r"port_clock=(\d+)", graphics)) // 100,
                    "brightness_sysfs_max": int(match(r"^max_brightness=(\d+)", graphics)),
                    "note": "Route/rate are the observed Linux configuration. sysfs brightness is not a verified MMIO PWM ceiling. Sure View/1000-nit SKU is user-reported.",
                    "evidence": evidence(edid_path, "text/graphics.txt", raw + "kernel/debug/dri/0000:00:02.0/i915_vbt")},
        "audio": {"codec": "Realtek ALC285", "vendor_id": match(r"Vendor Id: (\S+)", alsa),
                  "subsystem_id": match(r"Subsystem Id: (\S+)", alsa),
                  "controller_id": "8086:a0c8", "linux_driver": "sof-audio-pci-intel-tgl",
                  "note": "Codec enumeration does not establish digital microphone/DSP compatibility in macOS.",
                  "evidence": evidence("text/audio.txt", "text/pci.txt", raw + "firmware/acpi/tables/NHLT")},
        "input": {"keyboard_transport": "i8042/PS2", "keyboard_layout": "JIS (user-reported; keys not tested)",
                  "touchpad": {"acpi_hid": "SYNA30B6", "hid_id": "06cb:cd74", "acpi_path": "\\_SB.PC00.I2C0.TPD0", "linux_driver": "hid-multitouch"},
                  "touchscreen_and_pen": {"acpi_hid": "WACF4233", "hid_id": "056a:4924", "acpi_path": "\\_SB.PC00.I2C1.TPL0", "linux_driver": "wacom"},
                  "evidence": evidence("text/inputs.txt", "text/acpi-devices.txt", "text/i2c.txt")},
        "network_usb": {"wifi": "Intel AX201 8086:a0f0", "bluetooth": "8087:0026 / XHCI HS10",
                        "camera_rgb_ir": "0408:5349 / XHCI HS02 / four USB interfaces",
                        "fingerprint": "06cb:00f0 / XHCI HS07",
                        "note": "Populated internal ports only; physical USB-A/C port mapping and external monitor routes are incomplete.",
                        "evidence": evidence("text/pci.txt", "text/usb.txt")},
        "storage": {"model": nvme["mn"].strip(), "firmware": nvme["fr"].strip(), "pci_id": "1344:5404",
                    "linux_pci_route": "0000:00:1d.0 -> 0000:55:00.0; direct NVMe, not VMD remapped",
                    "layout": json.loads(read("storage.json"))["blockdevices"],
                    "health": {key: health[key] for key in ("critical_warning", "percent_used", "media_errors", "power_on_hours")},
                    "note": "Existing NixOS, NTFS and other partitions are occupied; NTFS presence alone does not prove the Windows install boots or its encryption state.",
                    "evidence": evidence("text/storage.json", "text/pci.txt", "text/nvme-controller.json", "text/nvme-health.json")},
        "firmware_settings": {"values": firmware, "evidence": evidence("text/firmware.txt")},
        "power_sensors": {"linux_mem_sleep": read("power.txt").splitlines()[0],
                          "battery": fields(read("power.txt")),
                          "iio_devices": read("sensors.txt").splitlines(),
                          "note": "Physical ST chip models, rotation behavior, sleep/resume and measured brightness are not verified.",
                          "evidence": evidence("text/power.txt", "text/sensors.txt")},
        "acpi": {"static_ssdt_count": sum('/dynamic/' not in p and Path(p).name.startswith('SSDT') for p in acpi_paths),
                 "dynamic_ssdt_count": sum('/dynamic/' in p for p in acpi_paths),
                 "evidence": evidence(raw + "firmware/acpi/tables/DSDT", raw + "firmware/acpi/tables/DMAR")},
        "unverified": ["macOS bootability and system volume build", "Metal/OpenGL/video acceleration",
                       "Complete USB mapping, hotplug, Type-C orientations and Thunderbolt", "Windows boot health and BitLocker status",
                       "GPIO runtime routing and complete ACPI namespace resolution", "macOS audio, microphone and input behavior"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
