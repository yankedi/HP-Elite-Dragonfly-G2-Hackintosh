# Hardware and support status

Snapshot: **2026-10-27**. Machine: HP Elite Dragonfly G2 / i5-1135G7 / Iris Xe 8086:9a49 / 16 GiB LPDDR4X / macOS 26.6.2 (25G83).

| Function | Current result | Evidence and remaining scope |
| --- | --- | --- |
| macOS installation / desktop | Installed and booted | Both accelerated and basic-display configurations reached the desktop |
| Experimental TGL GPU acceleration | **Unstable** | Four recent panics at 252–340 s; [comparison](GRAPHICS-STABILITY.md) |
| Firmware/basic display | Usable 1920×1080 desktop | IONDRVFramebuffer, no active Intel accelerator; one ~62 min run without user-reported freeze |
| Bluetooth | User confirmed working | Firmware, patcher and BlueToolFixup loaded; long-term reconnect coverage not established |
| Bluetooth audio output + microphone | User confirmed both working | Registered input/output endpoints corroborate route; successful use is user evidence |
| Touchpad | User confirmed working | GPIO-based TPD0, VoodooGPIO Tiger Lake LP / INT34C5, pin 175 |
| Keyboard | Usable during testing | Complete Fn/JIS/special-key coverage not established |
| Battery display | User confirmed visible | SMCBatteryManager + ECEnabler; full charge/discharge/suspend validation pending |
| Camera | User confirmed working | USB UVC enumeration alone was not counted as success; later user test supplied the functional result |
| Wi-Fi | Tested during installation/SSH work | AirportItlwm-based configuration; all advanced Continuity features not established |
| Internal speakers / HDA | **Not working** | ALC285 10ec:0285 / subsystem103c:8716; no verified working internal output path |
| Internal microphone / SOF DMIC | **Not working** | Bluetooth microphone success does not resolve the internal SOF path |
| Actual backlight brightness | **Not working** | BrightnessKeys/PNLF/AppleBacklightDisplay registration does not prove panel PWM control |
| Touchscreen / pen | Incomplete acceptance | A registered HID service is not a complete physical test |
| USB mapping | Incomplete acceptance | Earlier boot/ownership work preserved; full per-port USB2/3/Type-C orientation mapping pending |
| Thunderbolt/USB4 tunnelling | No verified complete implementation/test | Requires actual downstream hardware and implementation validation |
| ISH / fingerprint | No verified complete macOS implementation | No success claimed from PCI matching alone |
| Sleep, wake, advanced power management | Not fully validated | Display sleep is not system sleep; no blanket success claim |
| Advanced Continuity | Not fully supported/validated | Bluetooth and Wi-Fi functionality do not establish complete Apple integration |

## Graphics configuration identities

## 2026-11-05 Horizon Detection breakthrough update

On 2026-11-05, building on the native 80-EU/L3=6 topology, NOAUX/NOCCS3, `FF_DOP_CLOCK_GATE_DISABLE` (`0x20ec = 0x13`), `CS_CHICKEN1` (`0x2580 = 0x00020002`, thread-group preemption), and `IOAccelCommandBufferPool2` end-of-buffer guard, we added:
1. Unconditional `EXECLIST_STATUS` (`0x2234`) bit 30 wait (`elsqWait`, polling up to 2000 µs in 5 µs steps whenever `(EXECLIST_STATUS_LO & 0x40000000) != 0` before writing ELSP/ELKICK in `submitToRing` and `prepareExecListAndSubmit`), plus skipping empty `prepareExecListAndSubmit` calls when both `port0` and `port1` are null.
2. Masked write `0xc100c100` (enabling bits 8, 14, 15: `DISABLE_PARTIAL_INSTRUCTION_SHOOTDOWN`, `DISABLE_DOP_GATING`, `DISABLE_EARLY_READ`) to `GEN8_ROW_CHICKEN2` (`0xe4f4`) in the native engine startup sequence (verified runtime readback `0xffffc100`).

With this configuration (`NootedGreen` UUID `4C4C440C-5555-3144-A1CF-CF98321C87D2`, binary SHA-256 `e0d6fe75c2d4f4e488d3ff936f70f3551f71d5ea10a29158d364fd194139ad7c`), Geekbench 6.5.0 Metal completed `Background Blur`, `Face Detection`, and **`Horizon Detection` (100%)** with zero GPU resets during those three workloads, before encountering a separate RCS compute hang in `Edge Detection` (`ACTHD = 0x4ecfe3a8`, `IPEHR = 0x7a000004`). See [repair32-elsqwait-20261105.md](../mac-for-elitebook/docs/repair32-elsqwait-20261105.md) and [nootedgreen-elsqwait-20261105.patch](../graphics/patches/nootedgreen-elsqwait-20261105.patch).

2026-10-29 experiment update: the clean-upstream BASE trial was reported stuck
and its recovered log records NootedGreen injection failure. The new
[subtraction plan](GRAPHICS-SUBTRACTION-PLAN.md) reuses the historical cumulative
driver and preserves HP compatibility repairs. Candidate static checks passed.
F-FULL subsequently loaded the expected driver and patches, then recorded GPU
errors from uptime ~23 min and lost SSH at ~34 min; its complete received log
was verified, but no F panic text was recovered. The user later reported A/B
freezes; firmware recovery found a WindowServer watchdog panic at ~12 min32 s
with B's pool-OFF argument. A's separate panic/runtime identity remains unverified.
This does not establish a new root cause or supersede the historical hardware
results in the table above.

The next strategy is now documented as a
[coarse two-way partition](GRAPHICS-COARSE-PARTITION.md): display/platform versus
rendering/resources/user-space graphics. Source/configuration and captured-file
ownership checks passed; compatibility-retained and unmapped binary changes are
explicit. New L-OFF/R-OFF candidates have not been built or tested.

The user-authorized local USB cleanup retained the latest cumulative peripheral
boot as `ISO/HP-Tahoe-GA419-Bluetooth-Peripherals.img`, with its OC files unchanged
from F. Old experiments were privately archived and removed; installer/recovery
entries were retained. This maintenance does not change graphics acceptance.

- Accelerated EFI: GA419 combined peripheral test, using the GA416 L3=6 NootedGreen binary.
- Control EFI: GA420C, retains visible firmware scanout while avoiding custom TGL driver attachment.
- NootedGreen executable SHA-256: `e44ef32745cad51bd13a2006557f8d2076f96759a0afce867547a8466ab6dbbb`.
- Kernel UUID: `39CC2C26-3F72-3565-89C4-94DFE36DFDF2`.

The public configuration examples have machine identities removed. They describe the tested settings, not a newly assembled and physically retested release.
