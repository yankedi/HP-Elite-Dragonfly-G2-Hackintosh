#!/usr/bin/env python3
"""Evidence consistency audit, not a replacement for tests or hardware proof."""
import ast
import hashlib
import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
REQUIRED = ["README.md", "FINAL-REPORT.md", "NEXT-EXPERIMENT.md", "state.json", "continuation.md", "history.json", "audit/REQUIREMENTS-CHECKLIST.md", "audit/writer-review/AUDIT.md", "audit/writer-review/FINAL-CLOSURE.md"]
REQUIRED += ["track-a/" + n for n in ("CAS-ROOT-CAUSE.md", "CAS-FIX.patch", "CAPTURE-PIPELINE.md", "TEST-REPORT.md")]
REQUIRED += ["track-b/" + n for n in ("FORCEWAKE-BRANCHES.md", "GT-POWER-LIFETIME.md", "RESET-AND-CLEAR-TIMELINE.md", "SAFE-SAMPLING-POINTS.md", "CALLGRAPH.md")]
REQUIRED += ["track-c/" + n for n in ("FAULT-CAPTURE-DESIGN.md", "FAULT-TUPLE-CONSISTENCY.md", "HOOK-ABI-REVIEW.md")]
STATES = {"CAS_WRITER_FIX": "VERIFIED", "CAPTURE_PIPELINE": "PARTIAL", "APPLE_GT_LIFETIME": "PARTIAL", "RUNTIME_POWER": "PARTIAL", "FORCEWAKE_ACK": "PARTIAL", "RESET_CLEAR_ORDER": "PARTIAL", "FAULT_TUPLE_CONSISTENCY": "UNKNOWN", "SAFE_SAMPLING_POINT": "BLOCKED", "HOOK_ABI": "PARTIAL", "FAULT_DIAGNOSTIC": "MOCK_ONLY", "READY_FOR_HARDWARE_APPROVAL": "NO"}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read_json(name):
    return json.loads((ROOT / name).read_text())


def main():
    for name in REQUIRED:
        assert (ROOT / name).is_file() and (ROOT / name).stat().st_size > 0, name
    report = (ROOT / "FINAL-REPORT.md").read_text()
    assert [int(n) for n in re.findall(r"^(\d+)\. \*\*", report, re.M)] == list(range(1, 16))
    for key, value in STATES.items():
        assert re.search(r"^" + key + " = " + value + r"$", report, re.M), key
    state = read_json("state.json")
    assert state["statuses"] == STATES
    assert state["new_real_mmio_backend"] == "NONE" and state["hardware_approval"] == "NO"

    src = ROOT / "track-a/candidate/kern_igfx.cpp"
    text = src.read_text()
    assert "if (!OSCompareAndSwap(0, 1, &self->hangWriting))" in text
    assert "Capture36::beginAttempt(r, attempts)" in text
    assert "err ? 2U : 0U" in text
    assert re.search(r'PE_parse_boot_argn\("igfxtglhang"[^\n]+\n(?:\s*//[^\n]*\n)*\s*hangDump = 0;', text)
    legacy = read_json("track-a/logs/legacy/tracka-results.json")
    assert legacy["pass"] and len(legacy["runs"]) == 8
    assert legacy["provenance"]["candidate_sha256"] == sha(src)
    for run in legacy["runs"]:
        assert run["pass"] and run["compile_returncode"] == run["returncode"] == 0
        assert run["report"]["failed"] == 0 and all(c["pass"] for c in run["report"]["checks"])
        assert pathlib.Path(run["binary"]).is_file() and pathlib.Path(run["run_log"]).is_file()
    assert legacy["thag_parser"]["pass"]
    pipeline = read_json("track-a/logs/pipeline/results.json")
    assert len(pipeline) == 4 and all(r["exit"] == 0 and not r["stderr"] for r in pipeline)
    assert all("16 producers, terminal races, retry reasons" in r["stdout"] for r in pipeline)
    closure = (ROOT / "audit/writer-review/FINAL-CLOSURE.md").read_text()
    for name in ("track-a/candidate/kern_capture36.hpp", "track-a/candidate/kern_igfx.cpp", "track-a/tests/pipeline.cpp"):
        assert sha(ROOT / name) in closure, "independent closure stale: " + name

    wire = read_json("track-a/logs/wire/results.json")
    assert len(wire["negative_cases"]) == 10
    assert wire["v3_generated_sha256"] == sha(ROOT / "track-a/logs/wire/clangpp.thag") == sha(ROOT / "track-a/logs/wire/gpp.thag")
    macho = ROOT / "track-a/logs/freestanding/capture36.o"
    assert macho.read_bytes()[:4] == bytes.fromhex("cffaedfe")
    assert sha(macho) == read_json("track-a/logs/freestanding/results.json")["sha256"]

    c = read_json("track-c/results.json")
    assert c["status"] == "OFFLINE_TESTS_PASS" and c["tests_summary"]["passed"] == 8
    assert not c["project_evidence_assessment"]["admission_allowed"]
    assert c["scope"]["real_mmio_backend"] == "NONE"
    for row in c["source_copies"]:
        assert sha(ROOT / "track-c" / row["path"]) == row["sha256"] == sha(pathlib.Path(row["ga34_reference"]))
    assert sha(ROOT / "track-c" / c["gate_model_source"]["path"]) == c["gate_model_source"]["sha256"]
    for build in c["builds"]:
        for test in build["tests"]:
            assert test["build_exit"] == test["run_exit"] == 0
            assert test["last_output_line"] in (ROOT / "track-c" / test["run_log"]).read_text()
    ctest = (ROOT / "track-c/tests/test_evidence_gate.cpp").read_text()
    assert "within_capture_mutation_tears_tuple_in_mock" in ctest and "repeated_cec4_same_a_is_not_proof" in ctest
    assert "Repository checks passed" in (ROOT / "logs/repository-check.txt").read_text()
    assert not (ROOT.parent / "GA33-research/analysis/__pycache__/parse_thag.cpython-313.pyc").exists()
    incident = read_json("audit/bytecode-sideeffect/incident.json")
    assert incident["explicit_scope_violation_acknowledged"]
    assert sha(ROOT / "audit/bytecode-sideeffect/parse_thag.cpython-313.pyc") == incident["sha256"]
    for p in ROOT.rglob("*.py"):
        ast.parse(p.read_text(), filename=str(p))
    for p in ROOT.rglob("*.json"):
        if p == ROOT / "logs/delivery-audit.json":
            continue  # caller may be streaming this audit's stdout here
        json.loads(p.read_text())
    check = subprocess.run(["python3", "-B", str(ROOT / "track-b/analysis/verify_track_b.py")], capture_output=True, text=True, timeout=120)
    check.check_returncode()
    patch = subprocess.run(["patch", "--dry-run", "--batch", "-p1", "-i", str(ROOT / "track-a/CAS-FIX.patch")], cwd=ROOT / "track-a/baseline", capture_output=True, text=True, timeout=30)
    patch.check_returncode()
    output = {"status": "OFFLINE_DELIVERY_AUDIT_PASS", "required_files": len(REQUIRED), "answers": 15, "statuses": STATES, "source_sha256": sha(src), "legacy_runs": 8, "pipeline_runs": 4, "track_c_pairs": 8, "track_b": check.stdout.strip(), "scope": "Evidence consistency audit; full XNU/GPU pipeline remains PARTIAL/BLOCKED; seal and history verification separate"}
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
