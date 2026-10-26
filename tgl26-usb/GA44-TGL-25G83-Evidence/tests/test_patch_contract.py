#!/usr/bin/env python3
"""Static contract checks for the GA4.4 NootedGreen native-TGL patch.

This does not execute kernel code. It verifies that the proposed patch keeps
the native-TGL fixes separate from the RPL/display-13 master switch.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches" / "nootedgreen-tgl-native.patch"


class PatchContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = PATCH.read_text()

    def test_native_tgl_switch_is_separate(self) -> None:
        self.assertIn("-ngreentgltahoe", self.text)
        self.assertIn("static bool xeTglTahoeEnabled()", self.text)

    def test_layout_fixes_are_not_inside_rpl_only_block(self) -> None:
        self.assertIn("applyTglTahoeLayoutFixes", self.text)
        self.assertIn("XE-FMT", self.text)
        self.assertIn("XE-PLANES2", self.text)
        self.assertIn("0x8b, 0x83, 0xa4, 0x00, 0x00, 0x00", self.text)
        self.assertIn("0x8b, 0x83, 0xb0, 0x00, 0x00, 0x00", self.text)

    def test_display13_filter_is_gated_for_real_tgl(self) -> None:
        self.assertIn("xefix's display-13 register filter is not a native-TGL fix", self.text)
        self.assertIn("getIsRealTGL() && !checkKernelArgument(\"-ngreenallowrplfixes\")", self.text)

    def test_rpl_power_and_idle_paths_are_gated(self) -> None:
        self.assertIn("wrapSetGTFrequencyMMIO", self.text)
        self.assertIn("wrapWaitForGpuIdle", self.text)
        self.assertIn("wrapSetFramebufferPowerState", self.text)
        self.assertIn("ngreenallowrplfixes", self.text)

    def test_forcewake_replacement_is_skipped_for_native_tgl(self) -> None:
        self.assertIn("!wegCoexist || forceFullMTL", self.text)
        self.assertIn("getIsRealTGL() && xeTglTahoeEnabled()", self.text)

    def test_no_blanket_xefix_activation(self) -> None:
        self.assertNotIn("checkKernelArgument(\"-ngreenxefix\") ? 1 : 1", self.text)
        self.assertNotIn("-ngreenxefix\");\n+\t}\n+\treturn", self.text)


if __name__ == "__main__":
    unittest.main()
