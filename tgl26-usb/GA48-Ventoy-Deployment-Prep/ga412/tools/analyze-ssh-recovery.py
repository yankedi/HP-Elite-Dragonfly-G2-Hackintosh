#!/usr/bin/env python3
"""Offline extraction of the recorded R6 SSH timeout/reboot evidence; no SSH."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def match(pattern, text):
    found = re.search(pattern, text, re.MULTILINE)
    if found is None:
        raise ValueError(f"Required evidence missing: {pattern}")
    return found.group(1)


def analyze(root):
    evidence = {}

    def text(relative):
        data = (root / relative).read_bytes()
        evidence[relative] = {
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()
        }
        return data.decode()

    def receipt(name):
        r = json.loads(text(f"ga412/private/commands/{name}.json"))
        if r.get("returncode") != 0:
            raise ValueError(f"Operation did not succeed: {name}")
        return r

    old_identity = json.loads(text(
        "ga410/private/commands/ga411-r8-once-preflight-identity.json"))
    timeout = json.loads(text(
        "ga410/private/commands/ga411-r8-once-preflight-media.json"))
    if (old_identity.get("returncode") != 0
            or timeout.get("error") != "LOCAL_SSH_TIMEOUT"
            or timeout.get("returncode") is not None
            or not timeout.get("remote_process_completion_unknown")):
        raise ValueError("Unexpected historical receipt classification")
    prefix = "ga412/private/previous-failure/"
    gpu = text(prefix + "Kernel_2026-10-24-024009_host.gpuRestart")
    spin = text(prefix + "WindowServer_2026-10-24-025006_host.userspace_watchdog_timeout.spin")
    ips = text(prefix + "WindowServer-2026-10-24-025002.ips")
    watchdog = json.loads(ips.split("\n", 1)[1])
    processes = watchdog["stackshot"]["processByPid"]
    old_boot = match(r"kern.bootsessionuuid: ([0-9A-F-]+)", old_identity["stdout"])
    if watchdog["bootSessionUUID"] != old_boot:
        raise ValueError("Watchdog belongs to a different historical boot")

    current = receipt("r6-reboot-identity-power")
    loaded = receipt("r6-reboot-health-loaded")
    media = receipt("r6-reboot-media-direct-stat")
    receipt("r6-reboot-caffeinate")
    health = receipt("r6-reboot-health-followup")
    receipt("r6-reboot-display-idle-assertion")
    assertion_receipt = receipt("r6-reboot-display-assertion-verified")
    assertions = assertion_receipt["stdout"]
    final_health = receipt("r6-reboot-final-health")
    new_boot = match(r"kern.bootsessionuuid: ([0-9A-F-]+)", current["stdout"])
    if (new_boot == old_boot or new_boot not in health["stdout"]
            or new_boot not in final_health["stdout"]):
        raise ValueError("New boot identity inconsistent")
    ng_uuid = "4C4C44D0-5555-3144-A111-5710B37AE86F"
    if ng_uuid not in loaded["stdout"]:
        raise ValueError("R6 NootedGreen UUID not present")
    for name in ["PreventUserIdleDisplaySleep", "PreventUserIdleSystemSleep",
                 "PreventSystemSleep", "PreventDiskIdle"]:
        if not re.search(rf"^\s*{name}\s+1\s*$", assertions, re.MULTILINE):
            raise ValueError(f"Power assertion not active: {name}")
    for name in ["HP-Tahoe-Recovery-GA410-CSR0.img", "HP-Tahoe-VESA-XHCI-RHUB.img"]:
        if f"/Volumes/TARGET_VOLUME/ISO/linux/{name} 1343225856 bytes" not in media["stdout"]:
            raise ValueError(f"Direct file stat missing: {name}")

    find_section = next(s for s in re.split(r"(?=^Process:)", spin, flags=re.MULTILINE)
                        if s.startswith("Process:          find [2078]"))
    find_proc = processes["2078"]
    ws = processes["197"]
    return {
        "scope": "SSH recovery and bounded power assertions; no pixel capture",
        "historical": {
            "classification": "HISTORICAL_RUNTIME_CONFIRMED",
            "boot_session": old_boot,
            "ssh_identity_returncode": old_identity["returncode"],
            "media_timeout_seconds": timeout["timeout_seconds"],
            "remote_completion_unknown": True,
            "gpu_reset_local_time": match(r"^Date/Time:\s+(.+)$", gpu),
            "hung_context": int(match(r"context ID\[(\d+)\]", gpu)),
            "ACTHD": match(r"ACTHD\s+= (0x[0-9a-fA-F]+)", gpu),
            "IPEHR": match(r"IPEHR=(0x[0-9a-fA-F]+)", gpu),
            "watchdog_capture_time": watchdog["captureTime"],
            "watchdog_termination": watchdog["termination"],
            "display_state_at_watchdog": watchdog["displayState"],
            "windowserver_resident_bytes": ws["residentMemoryBytes"],
            "find_pid": 2078,
            "find_name": find_proc["procname"],
            "find_samples_include_lifs": "(lifs +" in find_section,
            "find_cpu_time_seconds": float(match(r"^CPU Time:\s+([0-9.]+)s", find_section)),
            "ssh_session_pids_in_watchdog": sorted(
                int(pid) for pid, p in processes.items() if p.get("procname") == "sshd-session"),
            "ssh_service_death_proven": False,
            "sleep_as_timeout_cause_proven": False,
            "gpu_hang_as_ssh_timeout_cause_proven": False,
            "root_cause_classification": "ROOT_CAUSE_UNVERIFIED"
        },
        "reboot_observation": {
            "boot_session": new_boot,
            "NG_UUID": ng_uuid,
            "AC_power_observed": "AC Power" in current["stdout"],
            "keepalive_pid": 991,
            "keepalive_seconds_at_launch": 7200,
            "display_assertion_pid": 1082,
            "display_assertion_seconds_at_launch": 6600,
            "power_assertions_verified": True,
            "direct_recovery_media_stat_verified": True,
            "recovery_media_content_hash_verified": False,
            "last_power_assertion_receipt_utc": assertion_receipt["time_utc"],
            "last_health_receipt_utc": final_health["time_utc"],
            "windowserver_RSS_samples": [
                {"receipt_time_utc": sample["time_utc"],
                 "RSS_KiB": int(match(r"^\s*197\s+1\s+Ss\s+(\d+)\s+", sample["stdout"]))}
                for sample in [health, assertion_receipt, final_health]
            ],
            "persistent_pmset_changes": False,
            "GPU_classification": "GPU_TEST_NOT_RUN",
            "probe_execution_attempts": 0,
            "long_term_stability_proven": False
        },
        "evidence": evidence
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(analyze(args.root), indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result)
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
