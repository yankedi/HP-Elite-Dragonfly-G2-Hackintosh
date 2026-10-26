#!/usr/bin/env python3
"""Exercise Recovery collection control flow with native, isolated command fixtures.

These tests do not run macOS, a VM, or real disk/network/power probes. Only the
private test copy's absolute tool/volume/tmp paths are redirected to fixtures.
"""

import csv
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/collect_macos_handoff.sh"
MOCK = r'''#!/usr/bin/env python3
import os, sys, plistlib, signal, time
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
mode = os.environ.get("HANDOFF_MODE", "normal")
with open(os.environ["HANDOFF_CALLS"], "a") as log:
    log.write(name + " " + " ".join(args) + "\n")
if name == "uname":
    print("Darwin" if args == ["-s"] else "Darwin fixture")
elif name == "ioreg":
    if "-c" in args:
        cls = args[args.index("-c")+1]
        if cls == "ApplePS2Keyboard":
            print("permission denied", file=sys.stderr); sys.exit(1)
        if cls in ("AppleUSBXHCIPCI", "VoodooI2CPCILakeController", "IOHIDDevice"):
            if cls == "AppleUSBXHCIPCI": cls = "AppleUSBXHCISPT"
            print("+-o fixture  <class " + cls + ", id 0x1, registered, matched, active>")
        else:
            print("+-o Root  <class IORegistryEntry, id 0x1>")
    else:
        print("fixture registry tree")
elif name == "kmutil":
    print("kmutil unavailable here", file=sys.stderr); sys.exit(42)
elif name == "kextstat":
    print("1 0 0x1 0x1 0x1 com.alexandred.VoodooI2CHID (2.9.1)")
    print("2 0 0x1 0x1 0x1 as.acidanthera.voodoo.driver.PS2Controller (2.3.7)")
elif name == "system_profiler":
    if mode == "timeout" and "SPDisplaysDataType" in args:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(60)
    print("fixture profile")
elif name == "diskutil":
    if args == ["list", "-plist"]:
        if mode == "invalid-plist": print("invalid plist"); sys.exit(0)
        sys.stdout.buffer.write(plistlib.dumps({"AllDisks": ["disk0", "disk0s1", "../../bad", "disk1"]}))
    elif args[:2] == ["info", "-plist"]:
        target = args[2]
        if target.startswith(os.environ["HANDOFF_VOLUMES"]):
            info = {"Internal": mode == "internal", "VirtualOrPhysical": "Virtual" if mode == "virtual" else "Physical",
                    "FilesystemType": "exfat", "Writable": mode != "readonly", "MountPoint": target}
        else:
            info = {"DeviceIdentifier": target, "ParentWholeDisk": "disk0", "Internal": True,
                    "Whole": target == "disk0", "VirtualOrPhysical": "Physical",
                    "TotalSize": 100000, "PartitionMapPartitionOffset": 1048576}
        sys.stdout.buffer.write(plistlib.dumps(info))
    else:
        print("fixture disk query")
elif name == "PlistBuddy":
    try:
        data = plistlib.loads(Path(args[-1]).read_bytes())
        for key in args[1].removeprefix("Print :").split(":"): data = data[key]
        if isinstance(data, list): print("Array {\n" + "\n".join("    " + str(v) for v in data) + "\n}")
        elif isinstance(data, bool): print(str(data).lower())
        else: print(data)
    except Exception: sys.exit(1)
elif name == "stat":
    print(19922944000 if args[-1].endswith(".hfs") else 1343225856)
elif name == "cp":
    print("fixture write failure", file=sys.stderr); sys.exit(1)
else:
    print("fixture " + name)
'''


class HandoffTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / ".local" / "tests"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="handoff-", dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tmp = self.root / "tmp"
        self.tmp.mkdir()
        self.volumes = self.root / "Volumes"
        self.volumes.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.calls = self.root / "calls.txt"
        self.env = dict(os.environ, HANDOFF_CALLS=str(self.calls),
                        HANDOFF_VOLUMES=str(self.volumes), PATH=str(self.bin) + ":" + os.environ["PATH"])
        self.text = SOURCE.read_text().replace("/tmp", str(self.tmp)).replace("/Volumes", str(self.volumes))
        mocked = {"uname", "ioreg", "kmutil", "kextstat", "system_profiler", "diskutil",
                  "PlistBuddy", "stat", "sw_vers", "sysctl", "ifconfig", "netstat", "scutil", "pmset", "hdiutil", "dmesg", "hidutil"}
        paths = set(re.findall(r"/(?:usr/(?:bin|sbin|libexec)|bin|sbin)/[A-Za-z_]+", self.text))
        for tool in paths:
            name = Path(tool).name
            if name not in mocked:
                executable = shutil.which(name)
                if executable:
                    self.text = self.text.replace(tool, executable)
                continue
            target = self.bin / name
            if name != "hidutil":  # Missing Recovery tool is a normal observation.
                target.write_text(MOCK)
                target.chmod(0o700)
            self.text = self.text.replace(tool, str(target))
        self.script = self.root / "collector.sh"
        self.script.write_text(self.text)

    def add_usb(self, name="DEV-USB"):
        data = self.volumes / name / "ISO/linux"
        data.mkdir(parents=True)
        for filename in ("HP-Tahoe-VESA-Recovery.img", "Tahoe-26.6.2-Offline-App.hfs", "HP-TAHOE-SHA256SUMS.txt"):
            (data / filename).write_text("fixture")
        return data

    def run_collector(self, *args, mode="normal"):
        env = dict(self.env, HANDOFF_MODE=mode)
        result = subprocess.run(["sh", str(self.script), *args], env=env, capture_output=True, text=True, timeout=40)
        bundles = list(self.tmp.glob("hp-macos-observation.*.tar.gz"))
        self.assertEqual(len(bundles), 1, result.stderr)
        with tarfile.open(bundles[0]) as archive:
            contents = {Path(member.name).name: archive.extractfile(member).read().decode()
                        for member in archive.getmembers() if member.isfile()}
        return result, bundles[0], contents

    @staticmethod
    def rows(contents, name):
        return {row[0]: row[1:] for row in csv.reader(io.StringIO(contents[name]), delimiter="\t") if row}

    def test_default_reports_presence_absence_failure_and_no_usb_writes(self):
        usb = self.add_usb()
        result, _, contents = self.run_collector()
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = self.rows(contents, "SUMMARY.tsv")
        self.assertEqual(summary["xhci"][0], "registry_present")
        self.assertEqual(summary["i2c-hid"][0], "not_observed")
        self.assertEqual(summary["ps2-keyboard"][0], "query_failed")
        self.assertEqual(summary["kext-VoodooI2CHID"][0], "listed")
        self.assertEqual(summary["kext-VoodooI2C"][0], "not_listed")
        status = self.rows(contents, "command-status.tsv")
        self.assertEqual(status["hid-list"][0], "127")
        self.assertEqual(status["loaded-kexts"][0], "42")
        self.assertEqual(status["loaded-kexts-fallback"][0], "0")
        self.assertIn("disk-info-disk0s1.txt", contents)
        self.assertNotIn("../../bad", self.calls.read_text())
        self.assertFalse(list(usb.glob("HP-Diagnostics.*")))
        self.assertNotRegex(self.calls.read_text(), r"diskutil (erase|mount|repair)|hdiutil attach|pmset (sleep|displaysleep)")

    def test_timeout_for_term_resistant_tool_keeps_other_results(self):
        result, _, contents = self.run_collector("--timeout", "1", mode="timeout")
        self.assertEqual(result.returncode, 0, result.stderr)
        row = self.rows(contents, "command-status.tsv")["profiler-Displays"]
        self.assertEqual(row[0], "124")
        self.assertEqual(row[2], "yes")
        self.assertIn("profiler-Thunderbolt.txt", contents)

    def test_usb_export_is_unique_byte_compared_and_does_not_overwrite(self):
        usb = self.add_usb("DEV-USB with spaces")
        existing = usb / "HP-Diagnostics.old"
        existing.mkdir()
        (existing / "keep.txt").write_text("keep")
        result, archive, _ = self.run_collector("--save-usb")
        self.assertEqual(result.returncode, 0, result.stderr)
        copies = list(usb.glob("HP-Diagnostics.*/*.tar.gz"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(archive.read_bytes(), copies[0].read_bytes())
        self.assertEqual((existing / "keep.txt").read_text(), "keep")

    def test_internal_volume_is_never_export_destination(self):
        self.check_rejected_volume("internal")

    def test_virtual_volume_is_never_export_destination(self):
        self.check_rejected_volume("virtual")

    def test_readonly_volume_is_never_export_destination(self):
        self.check_rejected_volume("readonly")

    def check_rejected_volume(self, mode):
        usb = self.add_usb()
        result, _, _ = self.run_collector("--save-usb", mode=mode)
        self.assertEqual(result.returncode, 1)
        self.assertIn("found 0", result.stderr)
        self.assertFalse(list(usb.glob("HP-Diagnostics.*")))

    def test_ambiguous_usb_preserves_tmp_without_choosing(self):
        self.add_usb("One")
        self.add_usb("Two")
        result, _, _ = self.run_collector("--save-usb")
        self.assertEqual(result.returncode, 1)
        self.assertIn("found 2", result.stderr)
        self.assertFalse(list(self.volumes.glob("*/ISO/linux/HP-Diagnostics.*")))

    def test_symlinked_iso_is_not_followed_for_export(self):
        data = self.add_usb()
        moved = self.root / "moved-ISO"
        (data.parent).rename(moved)
        (data.parent).symlink_to(moved, target_is_directory=True)
        result, _, _ = self.run_collector("--save-usb")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(list(moved.glob("linux/HP-Diagnostics.*")))

    def test_export_error_preserves_local_archive(self):
        self.add_usb()
        cp = self.bin / "cp"
        cp.write_text(MOCK)
        cp.chmod(0o700)
        self.script.write_text(self.text.replace(shutil.which("cp"), str(cp)))
        result, archive, _ = self.run_collector("--save-usb")
        self.assertEqual(result.returncode, 1)
        self.assertIn("original archive retained", result.stderr)
        self.assertTrue(archive.is_file())

    def test_invalid_disk_plist_does_not_stop_other_observations(self):
        result, _, contents = self.run_collector(mode="invalid-plist")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SUMMARY.tsv", contents)
        self.assertNotIn("disk-info-disk0.txt", contents)
        self.assertEqual(self.rows(contents, "SUMMARY.tsv")["disk-inventory"][0], "query_failed")

    @unittest.skipUnless(sys.platform.startswith("linux"), "Production platform refusal is a Linux-only check")
    def test_linux_refusal_and_argument_validation(self):
        result = subprocess.run(["sh", str(SOURCE)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("not in Linux", result.stderr)
        for args in (["--timeout"], ["--timeout", "0"], ["--timeout", "121"], ["--timeout", "x"], ["--unknown"]):
            result = subprocess.run(["sh", str(self.script), *args], env=self.env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, args)
        self.assertFalse(list(self.tmp.iterdir()))


if __name__ == "__main__":
    unittest.main()
