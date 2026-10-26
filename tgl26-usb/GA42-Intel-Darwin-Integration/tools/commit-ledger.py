#!/usr/bin/env python3
"""Generate a local Git ledger with explicit evidence-level limits."""
import collections
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()

EVIDENCE = {
    "c40eda3": ["anv-002-sdk-inventory"],
    "57ee469": ["gem-client-unit-001"],
    "b51fe58": ["drm-ioctl-bridge-test-002"],
    "a4fba6b": ["anv-026-verify-patches"],
    "2fffbd2": ["drm-mesa-discovery-build-001", "drm-mesa-discovery-test-001"],
    "c1d81d9": ["drm-busid-test-005"],
    "bf92a3e": ["anv-026-verify-patches"],
    "f3c6387": ["anv-026-verify-patches"],
    "1b31899": ["drm-mesa-discovery-build-003"],
    "376cfa7": ["nm-004-nvidia-only-gate-u0"],
    "ed6b3b5": ["drm-unsupported-ioctl-test-001"],
    "5144499": ["anv-033-darwin-build-attempt"],
    "1074e1f": ["nm-017-final-nvidia-test"],
    "14ba6ee": ["drm-wire-offset-test-001"],
    "0f14de6": ["native-module-link-001"],
    "d09b54f": ["nm-025-nvidia-only-gate-override-final"],
    "b992acf": ["anv-065-darwin-build-attempt-fixed"],
    "5990d3f": ["truthful-query-unit-001"],
    "0ba6bd9": ["nm-037-corrected-vendor-policy-fixed"],
    "f449725": ["nm-051-device-binding-positive-gate-fixed"],
    "00b37b6": ["exec-preflight-unit-002"],
    "4b0b947": ["anv-offline-unwrapped-attempt-001"],
    "3e513b1": ["resume-quota-cpu-test-001", "resume-quota-native-001"],
    "f676974": ["deferred-reap-cpu-test-001", "deferred-reap-native-001"],
    "41f0cae": ["native3-gate-compile"],
    "520fe11": ["native3-f1-overlap-run", "native3-f1-native-compile"],
    "f50efef": ["nm-freeze-vendor-003"],
    "4e547f1": ["nm-reject-loader-002"],
    "4d7ded2": ["nm-fuzz0-series-002"],
    "a429a4d": ["nm-loader-env-001"],
}

def render():
    head = git("rev-parse", "HEAD")
    rows, counts = [], collections.Counter()
    for line in git("log", "--reverse", "--format=%H %s").splitlines():
        sha, subject = line.split(" ", 1)
        files = git("diff-tree", "--root", "--no-commit-id", "--name-only", "-r", sha).splitlines()
        if sha.startswith("0c025ca"):
            kind = "baseline"
        elif sha.startswith("87ab938"):
            kind = "tests_build"  # inherited binary removal, not driver code
        elif any(p.startswith(("i915-xnu/", "libdrm-darwin/", "anv/patches/", "nullmoth/patches/")) for p in files):
            kind = "driver"
        elif any(p.startswith(("tools/", "tests/", "nullmoth/tests/")) or p in ("CMakeLists.txt", ".gitignore") for p in files):
            kind = "tests_build"
        else:
            kind = "audit_docs"
        counts[kind] += 1
        tests = []
        for name in EVIDENCE.get(sha[:7], []):
            p = ROOT / "logs" / name / "command.json"
            if not p.is_file():
                raise RuntimeError("missing evidence: " + str(p))
            record = json.loads(p.read_text())
            tests.append(f"`{name}` exit={record.get('exit_code', 'INTERRUPTED')}")
        result = "PASS (record/diff only)" if not tests else "PASS (bounded evidence)"
        remaining = "See A–E report; no runtime inference"
        if any("exit=0" not in t for t in tests):
            result = "BLOCKED/FAIL (actual attempt)"
        if sha[:7] in ("376cfa7", "1074e1f", "d09b54f"):
            result = "FAIL (Intel policy); superseded"
            remaining = "Corrected by 0ba6bd9; original tests only tested wrong policy"
        if sha[:7] in ("3e513b1", "f676974"):
            remaining = "Refined by 41f0cae / 520fe11; original review retained"
        module = subject.split(":", 1)[0]
        rows.append(f"| `{sha}` | {kind}/{module} | {subject.replace('|', '/')} | {'; '.join(tests) or 'Documentation/index review; no runtime test claimed'} | {result} | {remaining} |")
    text = ["# GA42 本地提交台账", "", f"Repository: `{ROOT}`", "",
            f"Branch: `{git('branch', '--show-current')}`", "", f"Snapshot HEAD: `{head}`", "",
            "本表逐条读取本地 Git 历史；Test 列为 logs/ 下真实 command.json 的退出码。",
            "PASS 只限对应 CPU/源码编译/记录，不代表 Darwin 链接、原生运行或 GPU。",
            "无下载约束的历史违规另见 OFFLINE-EXCEPTION.md，不能由退出0覆盖。",
            "最终报告/本台账所在最后一次交付提交在排除的封存回执中记录，避免自身SHA循环。", "",
            f"快照合计 {sum(counts.values())} commits；分类：" + ", ".join(f"{k}={v}" for k,v in sorted(counts.items())) + "。",
            "baseline单列；driver指修改生产源码/patch；tests_build指仅测试/构建工具；audit_docs为审查/记录。", "",
            "| Full Commit | Class/Module | Change | Test (logs/) | Result | Remaining |",
            "|---|---|---|---|---|---|", *rows, ""]
    return "\n".join(text)

if __name__ == "__main__":
    (ROOT / "reports/GIT-COMMITS.md").write_text(render())
