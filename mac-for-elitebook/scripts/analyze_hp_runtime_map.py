#!/usr/bin/env python3
"""Compare a failed Apple booter RT request with a read-only Linux EFI runtime map."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", required=True)
    args = parser.parse_args()
    capture = (ROOT / args.capture).resolve(strict=True)
    if not capture.is_relative_to(ROOT / ".local"):
        raise ValueError("Evidence must remain private")
    log = capture / "opencore.txt"
    firmware = capture / "linux-efi-runtime-map.txt"
    text = log.read_bytes().decode(errors="replace").rstrip("\0")
    rows, totals = [], Counter()
    for match in re.finditer(r"\[EB\|MMD\]\[#\s*(\d+)\]\s+((?:0x[0-9A-Fa-f]+\s*){5})", text):
        kind, start, virtual, pages, attributes = [int(word, 16) for word in match[2].split()]
        row = {"type": kind, "start": start, "bytes": pages * 4096, "attributes": attributes}
        rows.append(row)
        totals[kind] += row["bytes"]
    request = re.search(r"\[EB.BST.FBS\|RT!\].*?AKMr2\s+(0x[0-9a-fA-F]+)", text)
    args_match = re.search(r"\[EB\|MBA:OUT\]\s+<\"([^\"]*)", text)
    if not request or not rows or not args_match:
        raise ValueError("Missing booter RT request, map or effective boot arguments")
    actual = int(request[1], 16)
    firmware_mmio = []
    for section in firmware.read_text().split("ENTRY ")[1:]:
        lines = section.splitlines()
        entry = {key: int(value, 16) for key, value in (line.split("=", 1) for line in lines[1:] if "=" in line)}
        if entry["type"] == 11 and entry["attribute"] & (1 << 63):
            firmware_mmio.append({"start": entry["phys_addr"], "bytes": entry["num_pages"] * 4096,
                                  "attributes": entry["attribute"]})
    booter_mmio = [row for row in rows if row["type"] == 11]
    mmio_match = sorted((r["start"], r["bytes"]) for r in booter_mmio) == sorted((r["start"], r["bytes"]) for r in firmware_mmio)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    report = {"schema_version": 1, "boot_log_sha256": sha(log), "linux_runtime_map_sha256": sha(firmware),
              "effective_boot_args": args_match[1], "slide_zero_retry_still_failed": "slide=0" in args_match[1] and "[EB.MM.AKM|!]" in text,
              "kernel_collection_read_ok": "[EB.LD.LKC|-?] Ok(0)" in text,
              "runtime_request_bytes": actual, "booter_mmio": booter_mmio,
              "booter_mmio_total_bytes": totals[11], "runtime_code_and_data_bytes": totals[5] + totals[6],
              "unaccounted_request_bytes_after_mmio_and_runtime": actual - totals[11] - totals[5] - totals[6],
              "linux_runtime_mmio": firmware_mmio, "booter_mmio_ranges_match_linux_runtime_mmio": mmio_match,
              "candidate": "Enable Booter.Quirks.DevirtualiseMmio; retain slide=0 for a single-setting comparison",
              "limit": "Linux runtime-map comes from a separate boot; booter failure map is post-failure. Size/range correspondence motivates a trial, not proof of its outcome.",
              "runner_sha256": sha(Path(__file__))}
    (capture / "runtime-analysis.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
