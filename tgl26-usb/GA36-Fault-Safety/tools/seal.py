#!/usr/bin/env python3
"""Private GA36 immutable delivery manifest. verify never writes into the seal."""
import argparse
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXCLUDE = {"manifest.json", "manifest.sha256", "logs/manifest-verification.txt"}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def entries():
    rows = []
    for p in sorted(ROOT.rglob("*")):
        if p.is_symlink():
            raise ValueError("symlinks not allowed in private seal: " + str(p))
        if p.is_file() and p.relative_to(ROOT).as_posix() not in EXCLUDE:
            rows.append({"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size, "sha256": digest(p)})
    return rows


def historical_sources():
    inventory = json.loads((ROOT / "reference/inventory/sources.json").read_text())
    rows = []
    for r in inventory["sources"]:
        p = pathlib.Path(r["path"])
        if not p.is_absolute():
            p = ROOT.parent / p
        if p.is_relative_to(ROOT) or not p.is_relative_to(ROOT.parent):
            continue  # GA36 snapshots changed deliberately; external staging not history
        assert p.is_file() and digest(p) == r["sha256"], "historical source changed: " + str(p)
        rows.append({"path": str(p), "bytes": p.stat().st_size, "sha256": r["sha256"]})
    return rows


def create():
    p = ROOT / "manifest.json"
    if p.exists() or (ROOT / "manifest.sha256").exists():
        raise ValueError("already sealed; copy to a new private work directory for new analysis")
    m = {"schema": "ga36-private-seal-v1", "files": entries(), "historical_sources": historical_sources(), "excluded": sorted(EXCLUDE), "receipt_policy": "verification receipt excluded to avoid self-reference; manifest.sha256 binds manifest; stdout can be saved as logs/manifest-verification.txt", "scope": "offline only; no real backend or hardware approval"}
    p.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n")
    (ROOT / "manifest.sha256").write_text(digest(p) + "  manifest.json\n")
    verify()


def verify():
    p = ROOT / "manifest.json"
    expected = (ROOT / "manifest.sha256").read_text().split()
    assert expected == [digest(p), "manifest.json"], "manifest hash mismatch"
    m = json.loads(p.read_text())
    assert m["schema"] == "ga36-private-seal-v1"
    assert entries() == m["files"], "local file set, size or hash changed"
    for r in m["historical_sources"]:
        q = pathlib.Path(r["path"])
        assert q.stat().st_size == r["bytes"] and digest(q) == r["sha256"], "historical source changed: " + str(q)
    print("PASS", len(m["files"]), "local files;", len(m["historical_sources"]), "historical sources unchanged; manifest SHA256", expected[0])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("create", "verify"))
    args = parser.parse_args()
    (create if args.action == "create" else verify)()
