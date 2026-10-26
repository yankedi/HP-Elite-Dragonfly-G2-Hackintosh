#!/usr/bin/env python3
"""Offline checks for syntax, source pins, evidence links and repository hygiene."""

import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def walk(value):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from walk(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from walk(nested)


def check_private_reference(path, record, errors):
    """Verify optional local evidence without requiring private files in a clone."""
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT / ".local"):
        errors.append("Evidence reference escapes .local")
    elif resolved.is_file():
        payload = resolved.read_bytes()
        if hashlib.sha256(payload).hexdigest() != record["sha256"]:
            errors.append(f"Private evidence hash differs: {path.relative_to(ROOT)}")
        if "bytes" in record and len(payload) != record["bytes"]:
            errors.append(f"Private evidence length differs: {path.relative_to(ROOT)}")


def main():
    names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT).decode().split("\0")
    paths = sorted({ROOT / name for name in names if name})
    errors = []
    counts = {"python": 0, "json": 0, "markdown": 0}
    for path in paths:
        relative = path.relative_to(ROOT)
        if relative.parts[0] in (".local", ".cache", "build", "dist") or path.suffix in (".aml", ".key", ".pem", ".p12"):
            errors.append(f"Private or generated artifact is visible to Git: {relative}")
        if path.suffix == ".py":
            counts["python"] += 1
            try:
                ast.parse(path.read_text(), filename=str(relative))
            except (SyntaxError, UnicodeError) as error:
                errors.append(str(error))
        if path.suffix == ".json":
            counts["json"] += 1
            try:
                data = json.loads(path.read_text())
            except (ValueError, UnicodeError) as error:
                errors.append(f"{relative}: {error}")
                continue
            for obj in walk(data):
                for key, value in obj.items():
                    if key in ("commit", "commit_sha", "resolved_commit", "upstream_commit", "base_commit") and value is not None and not re.fullmatch(r"[a-fA-F0-9]{40}", str(value)):
                        errors.append(f"Non-immutable commit value in {relative}: {key}={value}")
                    if key == "sha256" and value is not None and not re.fullmatch(r"[a-fA-F0-9]{64}", str(value)):
                        errors.append(f"Invalid SHA-256 in {relative}: {value}")
                if relative.parts[0] == "hardware" and set(obj) & {"sn", "serial_number", "serial", "system_serial", "SystemSerialNumber", "SystemUUID", "MLB"}:
                    errors.append(f"Identity field in sanitized hardware data: {relative}")
            if relative.parts[0] == "hardware":
                if "private_evidence_directory" in data:
                    for item in data.get("evidence", []):
                        check_private_reference(ROOT / data["private_evidence_directory"] / item["path"], item, errors)
                if "source_evidence" in data and "capture_id" in data:
                    for item in data["source_evidence"].values():
                        check_private_reference(ROOT / ".local/hardware" / data["capture_id"] / item["path"], item, errors)
                if "readonly_inspection" in data:
                    item = data["readonly_inspection"]
                    check_private_reference(ROOT / item["private_evidence"], item, errors)
            if relative.parts[0] == "manifests" and "private_report_sha256" in data:
                check_private_reference(ROOT / data["private_report"], {"sha256": data["private_report_sha256"]}, errors)
            if relative.parts[0] == "manifests" and "runner_sha256" in data:
                runner = (ROOT / data["runner"]).resolve()
                if not runner.is_relative_to(ROOT / "scripts") or hashlib.sha256(runner.read_bytes()).hexdigest() != data["runner_sha256"]:
                    errors.append(f"Component validation runner differs from evidence: {relative}")
        if path.suffix == ".md":
            counts["markdown"] += 1
            for link in re.findall(r"\]\(([^)\s]+)(?:\s+[^)]*)?\)", path.read_text()):
                if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", link) or link.startswith("#"):
                    continue
                target = link.split("#", 1)[0]
                if target and not (path.parent / target).exists():
                    errors.append(f"Broken local document link: {relative} -> {target}")
    for required in ("README.md", "docs/roadmap.md", "docs/hardware.md", "docs/verification.md", "hardware/elite-dragonfly-g2.json", "hardware/development-usb.json"):
        if not (ROOT / required).is_file():
            errors.append(f"Required project record missing: {required}")
    for protected in (".local/probe", "build/probe", "dist/probe"):
        if subprocess.run(["git", "check-ignore", "-q", protected], cwd=ROOT).returncode:
            errors.append(f"Missing ignore protection: {protected}")
    inventory_path = ROOT / "hardware/elite-dragonfly-g2.json"
    if inventory_path.exists():
        inventory = json.loads(inventory_path.read_text())
        capture = (ROOT / inventory["capture_directory"]).resolve()
        if not capture.is_relative_to(ROOT / ".local/hardware"):
            errors.append("Inventory points outside the private hardware capture directory")
        elif (capture / "manifest.json").exists():
            manifest = json.loads((capture / "manifest.json").read_text())
            entries = {item["path"]: item for item in manifest["files"]}
            for obj in walk(inventory):
                for item in obj.get("evidence", []):
                    actual = entries.get(item["path"])
                    if not actual or item["sha256"] != actual["sha256"] or item["bytes"] != actual["bytes"]:
                        errors.append(f"Inventory evidence differs from capture manifest: {item['path']}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit(1)
    print(f"Repository checks passed: {counts['python']} Python scripts, {counts['json']} JSON records, {counts['markdown']} Markdown files; private/generated outputs ignored.")


if __name__ == "__main__":
    main()
