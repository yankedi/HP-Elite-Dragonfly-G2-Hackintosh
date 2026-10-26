#!/usr/bin/env python3
"""Verify and decode a private Intel VBT capture into private and sanitized records."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True

from verify_evidence import verify


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = (ROOT / ".local/hardware").resolve()
INVENTORY_PATH = ROOT / "hardware/elite-dragonfly-g2.json"
PUBLIC_SUMMARY_PATH = ROOT / "hardware/display-analysis.json"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def json_read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_private_capture(value):
    capture = Path(value).expanduser().resolve(strict=True)
    if not capture.is_dir() or not capture.is_relative_to(PRIVATE_ROOT):
        raise ValueError(f"Capture must be a directory under {PRIVATE_ROOT}")
    return capture


def manifest_entries(capture):
    manifest = json_read(capture / "manifest.json")
    return {item["path"]: item for item in manifest["files"]}


def evidence_path(entries, suffix):
    matches = [name for name in entries if name.endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"Expected one verified evidence path ending in {suffix!r}, found {matches}")
    return matches[0]


def default_device_id(capture, explicit):
    if explicit:
        return explicit if explicit.lower().startswith("0x") else f"0x{explicit}"
    inventory = json_read(INVENTORY_PATH)
    inventory_capture = (ROOT / inventory["capture_directory"]).resolve()
    if inventory_capture == capture:
        return f"0x{inventory['gpu']['pci_id'].split(':', 1)[1]}"
    raise ValueError("Pass --devid for captures not referenced by hardware/elite-dragonfly-g2.json")


def resolve_decoder(value):
    candidate = Path(value).expanduser()
    if candidate.parent != Path(".") or "/" in value:
        executable = candidate.resolve()
    else:
        found = shutil.which(value)
        if not found:
            raise ValueError(f"Decoder not found in PATH: {value}")
        executable = Path(found).resolve()
    if not executable.is_file():
        raise ValueError(f"Decoder is not a file: {executable}")
    return executable


def detect_decoder_version(executable, supplied):
    if supplied:
        return supplied, "--decoder-version"
    for parent in executable.parents:
        match = re.search(r"(?:^|-)intel-gpu-tools-([0-9][A-Za-z0-9.+_-]*)$", parent.name)
        if match:
            return match.group(1), "Nix package output path"
    return None, "not exposed by intel_vbt_decode; use --decoder-version to record it"


def reduce_nixpkgs_metadata(capture):
    path = capture / "analysis/vbt/nixpkgs-metadata.json"
    if not path.is_file():
        return None
    metadata = json_read(path)
    locked = metadata.get("locked", metadata.get("nixpkgs_locked", {}))
    if not locked:
        locked = metadata
    return {
        "source_type": locked.get("type"),
        "last_modified": locked.get("lastModified"),
        "narHash": locked.get("narHash"),
        "git_revision": locked.get("rev"),
        "revision_note": "path pin; no Git revision recorded" if locked.get("type") == "path" else None,
    }


def raw_vbt_facts(vbt):
    if len(vbt) < 32 or not vbt.startswith(b"$VBT"):
        raise ValueError("Verified VBT evidence has no valid Intel VBT header")
    declared_size = int.from_bytes(vbt[24:26], "little")
    bdb_offset = int.from_bytes(vbt[28:32], "little")
    if declared_size < 32 or declared_size > len(vbt):
        raise ValueError(f"Invalid VBT declared size {declared_size} for {len(vbt)} captured bytes")
    if bdb_offset + 18 > declared_size or vbt[bdb_offset:bdb_offset + 16] != b"BIOS_DATA_BLOCK ":
        raise ValueError("VBT BDB signature or offset is invalid")
    bdb_version = int.from_bytes(vbt[bdb_offset + 16:bdb_offset + 18], "little")
    return {
        "declared_size_bytes": declared_size,
        "captured_size_bytes": len(vbt),
        "trailing_bytes": len(vbt) - declared_size,
        "trailing_bytes_are_zero": not any(vbt[declared_size:]),
        "bdb_version": bdb_version,
    }


def first_match(pattern, text, cast=str):
    match = re.search(pattern, text, re.MULTILINE)
    return cast(match.group(1)) if match else None


def profile_facts(decoded):
    block42 = re.search(r"^BDB block 42 .*?\n(.*?)(?=^BDB block 43 )", decoded, re.MULTILINE | re.DOTALL)
    block43 = re.search(r"^BDB block 43 .*?\n(.*?)(?=^BDB block 44 )", decoded, re.MULTILINE | re.DOTALL)
    profiles = []
    for panel_number, panel_name in ((2, "LFP1"), (3, "LFP2")):
        timing = None
        backlight = None
        if block42:
            timing_match = re.search(
                rf"^\s*Panel {panel_number} \({panel_name}\)\s*\n(.*?)(?=^\s*Panel |\Z)",
                block42.group(1),
                re.MULTILINE | re.DOTALL,
            )
            if timing_match:
                resolution = re.search(r"^\s*Resolution: (\d+x\d+)", timing_match.group(1), re.MULTILINE)
                timing = resolution.group(1) if resolution else None
        if block43:
            backlight_match = re.search(
                rf"^\s*Panel {panel_number} \({panel_name}\)\s*\n(.*?)(?=^\s*Panel |\Z)",
                block43.group(1),
                re.MULTILINE | re.DOTALL,
            )
            if backlight_match:
                content = backlight_match.group(1)
                frequency = re.search(r"^\s*PWM freq: (\d+)", content, re.MULTILINE)
                minimum = re.search(r"^\s*Minimum brightness: (\d+)", content, re.MULTILINE)
                backlight = {
                    "pwm_frequency_hz": int(frequency.group(1)) if frequency else None,
                    "minimum_brightness_code": int(minimum.group(1)) if minimum else None,
                }
        profiles.append({
            "panel_number": panel_number,
            "panel_name": panel_name,
            "decoded_dtd_resolution": timing,
            "vbt_backlight_profile": backlight,
        })
    return {
        "panel_type": first_match(r"^\s*Panel type: (\d+)", decoded, int),
        "panel_type_2": first_match(r"^\s*Panel type 2: (\d+)", decoded, int),
        "profiles": profiles,
    }


def logical_port_facts(decoded):
    section = re.search(r"^BDB block 2 .*?\n(.*?)(?=^BDB block 9 )", decoded, re.MULTILINE | re.DOTALL)
    if not section:
        return []
    records = []
    for chunk in section.group(1).split("Child device info:")[1:]:
        handle = re.search(r"Device handle: .*?\(([^)]+)\)", chunk)
        port = re.search(r"DVO Port: (DP-[A-Z])", chunk)
        if not port:
            continue
        records.append({
            "device_handle": handle.group(1) if handle else None,
            "logical_dvo_port": port.group(1),
            "aux_channel": first_match(r"^\s*Aux channel: ([^\n]+)", chunk),
            "thunderbolt_flag": first_match(r"^\s*Thunderbolt port: (yes|no)", chunk) == "yes",
            "usb_type_c_flag": first_match(r"^\s*DP USB type C support: (yes|no)", chunk) == "yes",
        })
    return records


def edid_preferred_resolution(edid):
    if len(edid) < 72:
        return None
    descriptor = edid[54:72]
    if int.from_bytes(descriptor[0:2], "little") == 0:
        return None
    horizontal = descriptor[2] | ((descriptor[4] & 0xF0) << 4)
    vertical = descriptor[5] | ((descriptor[7] & 0xF0) << 4)
    return f"{horizontal}x{vertical}"


def observed_i915(graphics):
    if not graphics:
        return None
    pipe = re.search(r"^\[CRTC:[^\n]*pipe A\]:\n(.*?)(?=^\[CRTC:[^\n]*pipe B\]:)", graphics, re.MULTILINE | re.DOTALL)
    if not pipe:
        return None
    body = pipe.group(1)
    active = "enable=yes, active=yes" in body
    mode = first_match(r'mode="([0-9]+x[0-9]+)"', body)
    clock = first_match(r"port_clock=(\d+), lane_count=\d+", body, int)
    lanes = first_match(r"port_clock=\d+, lane_count=(\d+)", body, int)
    encoder = first_match(r"\[ENCODER:\d+:([^\]]+)\]", body)
    connector = first_match(r"\[CONNECTOR:\d+:([^\]]+)\]", body)
    return {
        "pipe": "A",
        "active": active,
        "mode": mode,
        "route": encoder,
        "connector": connector,
        "lane_count": lanes,
        "link_rate_mbps_per_lane": (clock * 10 + 500) // 1000 if clock is not None else None,
        "source": "captured i915 display state (text/graphics.txt)",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", help="private .local/hardware/<capture> directory")
    parser.add_argument("--decoder", default="intel_vbt_decode", help="intel_vbt_decode executable or PATH name")
    parser.add_argument("--decoder-version", help="version to record when it cannot be inferred from the executable path")
    parser.add_argument("--devid", help="Intel PCI device ID (default: from matching sanitized inventory)")
    args = parser.parse_args()

    try:
        capture = ensure_private_capture(args.capture)
        # Verify every manifest-listed source before reading or decoding the raw evidence.
        verify(capture)
        entries = manifest_entries(capture)
        vbt_rel = evidence_path(entries, "/i915_vbt")
        edid_rel = evidence_path(entries, "/edid")
        graphics_rel = next((name for name in entries if name.endswith("text/graphics.txt")), None)
        vbt_path = capture / vbt_rel
        edid_path = capture / edid_rel
        vbt = vbt_path.read_bytes()
        edid = edid_path.read_bytes()
        header = raw_vbt_facts(vbt)
        decoder = resolve_decoder(args.decoder)
        devid = default_device_id(capture, args.devid)
        version, version_source = detect_decoder_version(decoder, args.decoder_version)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise SystemExit(f"decode_vbt.py: {error}") from error

    output_dir = capture / "analysis/vbt"
    output_dir.mkdir(parents=True, exist_ok=True)
    if not output_dir.resolve().is_relative_to(capture):
        raise SystemExit("decode_vbt.py: analysis output directory escapes the private capture")

    argv = [
        str(decoder),
        f"--file={vbt_path}",
        f"--devid={devid}",
        f"--panel-edid={edid_path}",
    ]
    completed = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    decoded_bytes = completed.stdout
    warning_bytes = completed.stderr
    (output_dir / "decoded.txt").write_bytes(decoded_bytes)
    (output_dir / "stderr.txt").write_bytes(warning_bytes)

    nixpkgs = reduce_nixpkgs_metadata(capture)
    command_record = {
        "command": [
            decoder.name,
            f"--file={vbt_rel}",
            f"--devid={devid}",
            f"--panel-edid={edid_rel}",
        ],
        "exit_code": completed.returncode,
        "decoder_version": version,
        "decoder_version_source": version_source,
        "nixpkgs_locked": nixpkgs,
    }
    (output_dir / "command.json").write_text(
        json.dumps(command_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if completed.returncode:
        raise SystemExit(f"intel_vbt_decode failed with exit status {completed.returncode}; see {output_dir}")

    decoded = decoded_bytes.decode("utf-8", errors="replace")
    warning_text = warning_bytes.decode("utf-8", errors="replace")
    decoded_header_size = first_match(r"^\s*VBT size:\s+0x[0-9a-fA-F]+ \((\d+)\)", decoded, int)
    decoded_bdb_version = first_match(r"^\s*BDB version:\s+(\d+)", decoded, int)
    if decoded_header_size != header["declared_size_bytes"] or decoded_bdb_version != header["bdb_version"]:
        raise SystemExit("Decoder summary does not match the VBT/BDB header parsed from raw bytes")

    panels = profile_facts(decoded)
    logical_ports = logical_port_facts(decoded)
    internal_ports = [record for record in logical_ports if record["device_handle"] == "LFP1"]
    internal_route = None
    if len(internal_ports) == 1:
        internal = internal_ports[0]
        internal_route = {
            "dvo_port": internal["logical_dvo_port"],
            "aux_channel": internal["aux_channel"].split()[0] if internal["aux_channel"] else None,
        }
    tb_ports = [record for record in logical_ports if record["thunderbolt_flag"] and record["usb_type_c_flag"]]
    graphics = (capture / graphics_rel).read_text(encoding="utf-8", errors="replace") if graphics_rel else ""
    inventory = json_read(INVENTORY_PATH)
    inventory_capture = (ROOT / inventory["capture_directory"]).resolve()
    display_inventory = inventory.get("display", {}) if inventory_capture == capture else {}
    observed = observed_i915(graphics)
    if not observed and display_inventory:
        observed = {
            "pipe": "A",
            "active": True,
            "mode": "x".join(str(value) for value in display_inventory.get("native_pixels", [])),
            "route": display_inventory.get("route"),
            "connector": "eDP-1",
            "lane_count": display_inventory.get("active_lanes"),
            "link_rate_mbps_per_lane": display_inventory.get("active_link_rate_mbps_per_lane"),
            "source": "sanitized hardware inventory; graphics text unavailable",
        }
    edid_resolution = edid_preferred_resolution(edid)
    source_facts = {
        "vbt": {
            "path": vbt_rel,
            "bytes": len(vbt),
            "sha256": sha256(vbt),
            **header,
        },
        "edid": {
            "path": edid_rel,
            "bytes": len(edid),
            "sha256": sha256(edid),
            "preferred_dtd_resolution": edid_resolution,
        },
    }
    if graphics_rel:
        graphics_bytes = (capture / graphics_rel).read_bytes()
        source_facts["i915_graphics"] = {
            "path": graphics_rel,
            "sha256": sha256(graphics_bytes),
        }
    summary = {
        "schema_version": 1,
        "capture_id": capture.name,
        "status": "sanitized read-only display evidence; no macOS bootability claim",
        "source_evidence": source_facts,
        "decoder": {
            "name": "intel_vbt_decode",
            "package": "intel-gpu-tools" if version else None,
            "version": version,
            "version_source": version_source,
            "exit_code": completed.returncode,
            "output_sha256": sha256(decoded_bytes),
            "warning_sha256": sha256(warning_bytes),
            "warnings": warning_text.splitlines(),
            "nixpkgs": nixpkgs,
            "confidence": (
                "limited: decoder reports block-size diagnostics and generated LFP data-table pointers; "
                "treat decoded table details as tentative and cross-check against raw evidence and observed EDID/i915 state"
            ),
        },
        "decoded_vbt": {
            "bdb_version": header["bdb_version"],
            "internal_lfp1_route": internal_route,
            "logical_dp_child_records": logical_ports,
            "thunderbolt_usb_c_logical_records": [record["logical_dvo_port"] for record in tb_ports],
            "panel_types": {
                "panel_type": panels["panel_type"],
                "panel_type_2": panels["panel_type_2"],
            },
            "panel_profiles": panels["profiles"],
            "physical_external_port_count": None,
            "port_mapping_note": (
                "VBT DVO/Thunderbolt/USB-C child entries describe logical routes, not a one-to-one count or mapping of physical connectors."
            ),
        },
        "observed_display": {
            "edid_preferred_resolution": edid_resolution,
            "i915": observed,
            "interpretation": (
                "Prefer captured EDID and active i915 pipe/link state for the observed panel. "
                "A mismatch with VBT default profiles alone does not establish corruption."
            ),
        },
        "backlight_caution": (
            "VBT PWM frequency/minimum-brightness profile values are firmware-table metadata, not verified live MMIO PWM settings."
        ),
    }
    PUBLIC_SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote private decode to {output_dir} and sanitized summary to {PUBLIC_SUMMARY_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
