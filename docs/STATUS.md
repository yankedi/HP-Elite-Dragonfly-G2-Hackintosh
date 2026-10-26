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

- Accelerated EFI: GA419 combined peripheral test, using the GA416 L3=6 NootedGreen binary.
- Control EFI: GA420C, retains visible firmware scanout while avoiding custom TGL driver attachment.
- NootedGreen executable SHA-256: `e44ef32745cad51bd13a2006557f8d2076f96759a0afce867547a8466ab6dbbb`.
- Kernel UUID: `39CC2C26-3F72-3565-89C4-94DFE36DFDF2`.

The public configuration examples have machine identities removed. They describe the tested settings, not a newly assembled and physically retested release.
