#!/usr/bin/env python3
"""Calculate the selected p5/p6/p7 space transfer from saved sfdisk JSON.

Offline arithmetic only: no partition commands, filesystem resizing or device
access. The output is a review document, never input for sfdisk or a formatter.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def plan(table, gib):
    if table["label"] != "gpt" or table["unit"] != "sectors":
        raise ValueError("Expected a GPT sector inventory")
    sector_size = table["sectorsize"]
    if sector_size not in (512, 4096) or not 1 <= gib <= 128:
        raise ValueError("Unexpected sector size or transfer size")
    device = table["device"]
    entries = {item["node"]: item for item in table["partitions"]}
    p5, p6, p7 = [entries[device + "p" + str(number)] for number in (5, 6, 7)]
    linux = "0fc63daf-8483-4772-8e79-3d69d8477de4"
    esp = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"
    if [item["type"].lower() for item in (p5, p6, p7)] != [linux, esp, linux]:
        raise ValueError("Expected Linux p5, EFI p6, Linux p7; inspect changed layout manually")
    if p5["start"] + p5["size"] != p6["start"] or p6["start"] + p6["size"] != p7["start"]:
        raise ValueError("p5/p6/p7 are no longer contiguous in the expected order")
    # GPT partition numbers are not physical order: p4 is physically after p8.
    physical = sorted(table["partitions"], key=lambda item: item["start"])
    for left, right in zip(physical, physical[1:]):
        if left["start"] + left["size"] > right["start"]:
            raise ValueError("Source partition ranges overlap")
    shift = gib * 2**30 // sector_size
    if p5["size"] <= shift:
        raise ValueError("Transfer consumes all of p5")
    new_p5 = {"start": p5["start"], "size": p5["size"] - shift}
    new_p6 = {"start": p6["start"] - shift, "size": p6["size"]}
    vacant = {"start": p7["start"] - shift, "size": p7["size"] + shift}
    if new_p5["start"] + new_p5["size"] != new_p6["start"]:
        raise ValueError("Invalid proposed p5/p6 boundary")
    if new_p6["start"] + new_p6["size"] != vacant["start"]:
        raise ValueError("Invalid proposed p6/macOS boundary")
    if vacant["start"] + vacant["size"] != p7["start"] + p7["size"]:
        raise ValueError("Proposed target crosses old p7 end")
    result = []
    for item, after, action in ((p5, new_p5, "Shrink btrfs filesystem before shrinking partition; keep start"),
                                (p6, new_p6, "Move EFI partition left, preserving filesystem, size and identity"),
                                (p7, vacant, "Delete authorized Debian p7; reserve resulting contiguous range for macOS")):
        result.append({"partition": item["node"], "before": {key: item[key] for key in ("start", "size")},
                       "proposed_range": after, "proposed_gib": after["size"] * sector_size / 2**30,
                       "action_for_review_only": action})
    return {"sector_size": sector_size, "transfer_gib": gib, "transfer_mib": gib * 1024,
            "physical_order": [item["node"] for item in physical], "review": result,
            "other_partitions_preserved": [item["node"] for item in physical if item not in (p5, p6, p7)],
            "filesystem_used_space_checked": False,
            "filesystem_health_checked": False,
            "operations_executed": False,
            "scope": "Geometry only; inspect live UI and btrfs usage before applying. Not an executable partition recipe."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, help="Private saved sfdisk --json output")
    parser.add_argument("--transfer-gib", type=int, default=40)
    args = parser.parse_args()
    source = (ROOT / args.inventory).resolve(strict=True)
    if not source.is_relative_to(ROOT / ".local") or not source.is_file():
        raise ValueError("Use a saved regular JSON file in .local; never a block device")
    payload = source.read_bytes()
    report = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
              "inventory_sha256": hashlib.sha256(payload).hexdigest(),
              **plan(json.loads(payload)["partitiontable"], args.transfer_gib)}
    base = ROOT / ".local/install-prep"
    base.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="space-plan-", dir=base))
    (directory / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str((directory / "report.json").relative_to(ROOT)), **report}, indent=2))


if __name__ == "__main__":
    main()
