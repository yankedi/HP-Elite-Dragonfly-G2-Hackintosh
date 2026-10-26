#!/usr/bin/env python3
"""Disassemble captured AML on the local host without changing the target."""

import json
from pathlib import Path
import shutil
import subprocess
import sys

from verify_evidence import verify


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: disassemble_acpi.py <capture-directory>")
    capture = Path(sys.argv[1]).resolve()
    verify(capture)
    tool = shutil.which("iasl")
    if not tool:
        raise SystemExit("iasl is required on the local development host")
    source = capture / "raw/sys/firmware/acpi/tables"
    output = capture / "analysis/acpi"
    output.mkdir(parents=True, exist_ok=True)
    tables = [source / "DSDT"] + sorted(source.glob("SSDT*")) + sorted((source / "dynamic").glob("SSDT*"))
    names = []
    for table in tables:
        # Preserve a unique name for dynamic tables, even on firmware reusing indices.
        name = ("dynamic-" if table.parent.name == "dynamic" else "") + table.name + ".aml"
        shutil.copyfile(table, output / name)
        names.append(name)
    # HP tables contain conditional duplicate names, and dynamic CPU tables
    # overlap other definitions. Loading every table into one namespace (-da)
    # fails with AE_ALREADY_EXISTS. Keep every original intact and disassemble
    # separately, recording unresolved-external diagnostics rather than hiding them.
    results = []
    generated = []
    for name in names:
        command = [tool, "-dl", name]
        dsl = output / Path(name).with_suffix(".dsl")
        if dsl.exists():
            dsl.unlink()
        result = subprocess.run(command, cwd=output, capture_output=True, timeout=30)
        (output / (name + ".stdout.txt")).write_bytes(result.stdout)
        (output / (name + ".stderr.txt")).write_bytes(result.stderr)
        if dsl.is_file() and dsl.stat().st_size:
            generated.append(dsl.name)
        diagnostics = result.stdout + result.stderr
        results.append({"command": command, "exit_code": result.returncode,
                        "output": dsl.name if dsl.is_file() else None,
                        "namespace_diagnostics": any(token in diagnostics for token in
                                                     (b"AE_NOT_FOUND", b"AE_ALREADY_EXISTS", b"Warning", b"Warning -"))})
    failed = any(r["exit_code"] or not r["output"] for r in results)
    report = {"mode": "independent-tables", "exit_code": 1 if failed else 0,
              "input_tables": names, "generated_dsl": generated, "results": results,
              "note": "Independent disassembly preserves diagnostics and does not resolve the complete firmware namespace. It is not ASL recompilation validation or proof of macOS bootability."}
    (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    if failed or len(generated) != len(names):
        raise SystemExit(f"ACPI disassembly incomplete; inspect {output}")
    print(f"Disassembled {len(generated)} AML tables locally: {output}")


if __name__ == "__main__":
    main()
