#!/usr/bin/env python3
"""Record only locally visible Darwin SDK/toolchain candidates.

This inventory is deliberately conservative: an Apple user SDK must be a local
directory with the expected SDK layout.  The public MacKernelSDK headers used
by the GA41 kernel probe are recorded as a separate non-user-SDK input and are
never accepted as a sysroot.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "anv" / "sdk-inventory.json"
MAC_KERNEL_SDK = ROOT / "sources" / "mackernelsdk"


def command_result(argv: list[str]) -> dict[str, object]:
    try:
        result = subprocess.run(argv, text=True, capture_output=True, check=False)
    except OSError as exc:
        return {"argv": argv, "available": False, "error": str(exc)}
    return {
        "argv": argv,
        "available": True,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def sdk_shape(path: Path) -> dict[str, object]:
    resolved = path.expanduser()
    exists = resolved.is_dir()
    required = {
        "usr_include_stdint": resolved / "usr/include/stdint.h",
        "usr_include_sys_types": resolved / "usr/include/sys/types.h",
        "usr_lib": resolved / "usr/lib",
        "system_library": resolved / "System/Library",
    }
    shape = {name: item.exists() for name, item in required.items()} if exists else {}
    is_user_sdk = exists and all(shape.values())
    return {
        "path": str(resolved),
        "exists": exists,
        "shape": shape,
        "apple_user_sdk_candidate": is_user_sdk,
        "rejected_if_only_public_kernel_headers": (
            exists and resolved.resolve() == MAC_KERNEL_SDK.resolve()
        ),
    }


def candidate_paths() -> list[Path]:
    candidates: list[Path] = []
    sdkroot = os.environ.get("SDKROOT")
    if sdkroot:
        candidates.append(Path(sdkroot))
    candidates.extend(
        [
            Path("/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk"),
            Path("/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk"),
            Path("/Library/Developer/SDKs/MacOSX.sdk"),
        ]
    )
    developer = Path("/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs")
    if developer.is_dir():
        candidates.extend(sorted(developer.glob("MacOSX*.sdk")))
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.expanduser())
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def main() -> int:
    commands = []
    for name in ("clang", "clang++", "ld", "xcrun", "xcode-select", "otool", "lipo"):
        path = shutil.which(name)
        commands.append(
            {
                "name": name,
                "path": path,
                "probe": command_result([path, "--version"] if path else [name, "--version"]),
            }
        )
    clang = shutil.which("clang")
    if clang:
        commands.append({"name": "clang-targets", "probe": command_result([clang, "-print-targets"])})

    sdk_candidates = [sdk_shape(path) for path in candidate_paths()]
    accepted = [item["path"] for item in sdk_candidates if item["apple_user_sdk_candidate"]]
    inventory = {
        "schema": "ga42-anv-darwin-sdk-inventory-v1",
        "offline": True,
        "root": str(ROOT),
        "mac_kernel_sdk": {
            "path": str(MAC_KERNEL_SDK),
            "exists": MAC_KERNEL_SDK.is_dir(),
            "accepted_as_user_sdk": False,
        },
        "sdk_candidates": sdk_candidates,
        "accepted_user_sdks": accepted,
        "toolchain": commands,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(OUTPUT), "accepted_user_sdks": accepted}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
