#!/usr/bin/env python3
"""Read Apple booter failure logs and compare observed allocation/slide ranges.

The memory map is captured after failure. Its overlaps are diagnostic evidence,
not proof that a candidate slide was free at every earlier boot stage.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    log = (ROOT / args.log).resolve(strict=True)
    output = (ROOT / args.output).resolve()
    if not log.is_relative_to(ROOT / ".local") or not output.is_relative_to(ROOT / ".local"):
        raise ValueError("Raw logs and reports stay in .local")
    raw = log.read_bytes()
    text = raw.decode(errors="replace").rstrip("\0")
    rows = []
    pattern = r"\[EB\|MMD\]\[#\s*(\d+)\]\s+((?:0x[0-9A-Fa-f]+\s*){5})"
    for match in re.finditer(pattern, text):
        kind, start, virtual, pages, attributes = [int(word, 16) for word in match[2].split()]
        rows.append({"index": int(match[1]), "type": kind, "start": start,
                     "end_exclusive": start + pages * 4096, "pages": pages})
    if not rows:
        raise ValueError("No Apple booter failure memory map")
    allocation = re.search(r"\[EB.BST.FBS\|RT!\].*?AKMr2\s+(0x[0-9a-fA-F]+)", text)
    slide = re.search(r"\[EB\|MBA:OUT\].*?\bslide=(\d+)", text)
    if not allocation or not slide:
        raise ValueError("Missing allocation size or effective slide")
    requested = int(allocation[1], 16)
    actual_slide = int(slide[1])

    def evaluate(value):
        start = 0x100000 + value * 0x200000
        end = start + requested
        overlaps = [row for row in rows if row["start"] < end and row["end_exclusive"] > start and row["type"] != 7]
        conventional = sum(max(0, min(end, row["end_exclusive"]) - max(start, row["start"]))
                           for row in rows if row["type"] == 7)
        return {"slide": value, "start": start, "end_exclusive": end,
                "fully_conventional_in_failure_map": conventional == requested and not overlaps,
                "nonconventional_overlaps": overlaps}

    valid = [value for value in range(256) if evaluate(value)["fully_conventional_in_failure_map"]]
    result = {"schema_version": 1, "log_sha256": hashlib.sha256(raw).hexdigest(),
              "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "kernel_collection_read_succeeded": "[EB.LD.LKC|-?] Ok(0)" in text,
              "memory_allocator_error_observed": "[EB.MM.AKM|!] Err(0xE) <- EB.MM.MKP" in text,
              "stop_code": re.findall(r"\[EB\|STOP\]\s+(0x[0-9a-fA-F]+)", text),
              "start_image_aborted": "OCB: StartImage failed - Aborted" in text,
              "runtime_allocation_request_bytes": requested, "memory_map_descriptors": len(rows),
              "observed_slide_analysis": evaluate(actual_slide), "slide_zero_analysis": evaluate(0),
              "fully_conventional_slides_in_postfailure_map": valid,
              "limit": "Post-failure map, assuming slide range base+allocation size. Does not prove allocation entry semantics or retry success.",
              "retry_status": "slide=0 image statically checked; HP retry pending"}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
