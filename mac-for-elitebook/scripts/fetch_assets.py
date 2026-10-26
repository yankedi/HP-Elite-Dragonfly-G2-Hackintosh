#!/usr/bin/env python3
"""Cache pinned official release assets locally and record verified download hashes."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def fetch(source):
    commit = source["commit"]
    if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise ValueError("Source must have a full commit pin")
    receipts = []
    license_receipt = None
    license_url = source.get("license", {}).get("evidence_url")
    if license_url:
        parsed = urllib.parse.urlparse(license_url)
        parts = parsed.path.strip("/").split("/")
        if parsed.scheme != "https" or parsed.netloc != "github.com" or len(parts) < 5 or parts[2] != "blob":
            raise ValueError("License evidence must be a GitHub blob URL")
        pinned_url = "https://raw.githubusercontent.com/" + "/".join(parts[:2] + [commit] + parts[4:])
        path = ROOT / ".cache/licenses" / source["name"] / (commit + ".txt")
        if not path.exists():
            request = urllib.request.Request(pinned_url, headers={"User-Agent": "elitebook-hardware-research/1.0"})
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read(1024 * 1024 + 1)
            if len(data) > 1024 * 1024:
                raise ValueError("Unexpectedly large license document")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        license_receipt = {"url": pinned_url, "local_path": str(path.relative_to(ROOT)),
                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    for asset in source["release"]["assets"]:
        url = urllib.parse.urlparse(asset["url"])
        name = asset["name"]
        if url.scheme != "https" or url.netloc != "github.com" or "/releases/download/" not in url.path:
            raise ValueError("Only official GitHub release URLs are accepted")
        if Path(name).name != name:
            raise ValueError("Invalid asset filename")
        destination = ROOT / ".cache/assets" / source["name"] / source["tag"] / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            request = urllib.request.Request(asset["url"], headers={"User-Agent": "elitebook-hardware-research/1.0"})
            temporary = destination.with_suffix(destination.suffix + ".partial")
            try:
                with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as output:
                    size = 0
                    while chunk := response.read(1024 * 1024):
                        size += len(chunk)
                        if size > 256 * 1024 * 1024:
                            raise ValueError("Unexpectedly large asset")
                        output.write(chunk)
                temporary.replace(destination)
            finally:
                temporary.unlink(missing_ok=True)
        data = destination.read_bytes()
        measured = hashlib.sha256(data).hexdigest()
        expected = asset.get("official_digest")
        if len(data) != asset["size_bytes"]:
            raise ValueError(f"Asset size mismatch: {destination}")
        if expected and expected != "sha256:" + measured:
            raise ValueError(f"Official asset digest mismatch: {destination}")
        receipts.append({"source": source["name"], "tag": source["tag"], "commit": commit,
                         "url": asset["url"], "local_path": str(destination.relative_to(ROOT)),
                         "bytes": len(data), "sha256": measured,
                         "upstream_digest_verified": bool(expected),
                         "license": license_receipt,
                         "note": "A locally measured digest is not an independently published upstream digest." if not expected else "Digest matches the pinned GitHub API release metadata."})
    return receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--names", nargs="+", required=True)
    args = parser.parse_args()
    sources = json.loads(args.manifest.read_text())["sources"]
    selected = [s for s in sources if s["name"] in args.names]
    if {s["name"] for s in selected} != set(args.names):
        parser.error("Unknown source name")
    receipt = {"schema_version": 1, "downloaded_at": datetime.now(timezone.utc).isoformat(),
               "manifest": str(args.manifest), "assets": []}
    for source in selected:
        receipt["assets"].extend(fetch(source))
    output = ROOT / ".local/downloads" / ("-".join(args.names) + ".json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
