# Hardware and support status

Snapshot: **2026-11-11**. Machine: HP Elite Dragonfly G2 (`8716`) / i5-1135G7 / Iris Xe `8086:9a49` (80 EU / 5 DualSubslices) / 16 GiB LPDDR4X / macOS 26.6.2 (`25G83`).

| Function | Current result | Evidence and remaining scope |
| --- | --- | --- |
| macOS installation / internal NVMe boot | **Installed and booting independently (`R32-PCFIX38` cold-boot live-verified)** | Installed on internal Micron 2210 NVMe SSD (`disk0s6` `/dev/nvme0n1p6` `1.0 GB` `/boot/EFI/OC`; `disk0s1` is `314.6 MB` Windows EFI; OpenCore `1.0.8` `config.plist` `60,234` B SHA-256 `f1f6b95569b7167ce3b166ca38b3f6bac7f8570dd14938187ebdb22090d3cf6b` + `R32-PCFIX38` `NootedGreen.kext` `540,880` B SHA-256 `46c21a3f853aada549dd2a18dee3a2f773667fe0c8cc6d3ef6ff5d21d5b717bb`, UUID `4C4C4414-5555-3144-A1AA-872C6E2C7F61`, `111/111` ESP `/EFI/OC` files and `112/112` recovery image files verified; steady screen-on battery draw `7.23 W` avg / `5.03–5.63 W` light browsing; see [clean-install-guide.md](../mac-for-elitebook/docs/clean-install-guide.md)) |
| Internal-boot `pmap_recycle_page` stability (`PMAPFIX`) | **Resolved (0 panics across 28+ endurance trials & multi-day daily use)** | `UEFI -> ReservedMemory` reserves `0x101000000..0x101400000` (`4 MiB`, `Type = Reserved`) with `debug=0x100000`, eliminating the `pmap_recycle_page: page 0x101310000` crash ([details](../mac-for-elitebook/docs/repair32-gpu-stability-and-pmapfix-20261106.md)) |
| Tiger Lake Iris Xe 80 EU Metal acceleration | **100% 3-Stage Endurance Plan passed (`705,024` encoders, 0 hangs; Phase 8 `enc#2,341,120`)** | `R32-PCFIX27` ([nootedgreen-pcfix27-20261106.patch](../graphics/patches/nootedgreen-pcfix27-20261106.patch)) passed 3 consecutive Geekbench 6.5.0 Metal runs (`24/24` workloads, `enc=75,264`) + 90s 4-worker concurrent stress (`404,570` encoders) + 60s RC6 idle & 30s burst wake (`135,068` encoders, total `705,024` encoders) with `0` `GPU hang:` and `0` `GPURestart` ([details](../mac-for-elitebook/docs/repair32-gpu-stability-and-pmapfix-20261106.md)) |
| `420v` NV12 H.264/HEVC video rendering (`HP-BLITALIGN`) | **Working (0 green/corrupted frames)** | `R32-PCFIX35` ([nootedgreen-pcfix35-blitalign-20261108.patch](../graphics/patches/nootedgreen-pcfix35-blitalign-20261108.patch)) aligns NV12 `IOSurface` row pitch to 64 B and routes non-aligned `420v` blits cleanly via BCS0 Blit2D / SIMD16; `xe-h264sw-fixd` patches `AppleH264SW` `fill_frame_num_gap` while omitting unstable VDBOX bundles |
| Firmware/basic display | Usable 1920×1080 desktop | IONDRVFramebuffer, no active Intel accelerator; one ~62 min run without user-reported freeze ([comparison](GRAPHICS-STABILITY.md)) |
| Bluetooth | **Working (hardened against APFS `decmpfs` eviction)** | Intel AX201 Bluetooth (`v8787`); `hp-syslogger.py` wires `/usr/sbin/bluetoothd` (`MAP_PRIVATE | PROT_READ` + `mlock()`, `11,206,656` B) in RAM to prevent `decmpfs_pagein_compressed` `EBADMSG` (`error 94`) `SIGBUS` crashes on `BlueToolFixup`-patched pages |
| Bluetooth audio output + microphone | User confirmed both working | Registered input/output endpoints corroborate route; successful use is user evidence |
| Touchpad | **Working (multi-touch gestures verified)** | Synaptics `SYNA30B6` (`06cb:cd74`), GPIO-based `TPD0` via `VoodooGPIO` Tiger Lake LP / `INT34C5` + `VoodooI2C` / `VoodooPS2` |
| Keyboard & top-row Fn hotkeys | **Working (`Fn+F1`..`Fn+F11`, velocity brightness & zero-TCC native screenshot verified)** | PS/2 keyboard (`VoodooPS2Controller.kext` `2.3.7`) + `hp-bridge` v3 Aqua LaunchAgent (`79,776` B, SHA-256 `aadfbf21e6e26281c4436ec99a058b875ab2480078b6bb93717970d1c3712252`, `SkyLight` `AppleSymbolicHotKeys` `30`/`31` `SystemUIServer` screenshot + 64-step OSD); [`SSDT-HP-Hotkeys.dsl`](../EFI/ACPI/SSDT-HP-Hotkeys.dsl) is retained as an archived ACPI reference and remains disabled in production |
| Battery display & zero-error early ACPI | **Working (1% granularity, 118 SMC keys, 0 ACPI errors)** | `VirtualSMC 1.3.7` + `SMCBatteryManager` + `ECEnabler 1.0.6` + [`SSDT-EC-USBX-HP.dsl`](../EFI/ACPI/SSDT-EC-USBX-HP.dsl) + `SSDT-EC0-ITLB.aml` (`1,572` B SHA-256 `122a5b9d778c6429d32f73f1da7e695ba7498e6714e172f708b22894bd8ddaf8`) |
| Camera | **Working (720p@30fps UVC verified)** | Quanta HP Wide Vision HD Camera (`0408:5349`), verified via `UVCAssistant` + `AVFoundation` capture (`13` formats, ~5 ms software MJPEG decode) |
| Wi-Fi | **Working (native `en0` 802.11ax + Tailscale coexistence verified)** | Intel Wi-Fi 6 AX201 (`AirportItlwm.kext` `2.4.0` native `IO80211` `en0`); Clash Verge `find-process-mode: 'off'` + Tailscale TUN/DNS/proxy bypass verified |
| Internal speakers & 3.5 mm jack (`ALC285`) | **Working (quad-speakers + auto-switching + headset mic)** | Realtek ALC285 (`10ec:0285`, `layout-id = 71`) via `SimpleHDA.kext` (`1.0.1`) + `AppleALC.kext` (`1.9.8`) + `hp-alc285-ampinit.sh` (`Node 0x20 Coef 0x65 = 0x0000`) across boot & wake |
| Internal microphone / Intel SST DMIC | **Working (48 kHz 4-ch PCM default input)** | Custom `TGLDmic.kext` (`v0.5.0`, `1,199,424` B, SHA-256 `b0d0715dfb49b6ea15208cdfa0f99373e2e62ee4e2a02448462252ef6721b416`) + `TGLDmic.driver` CoreAudio HAL driving Tiger Lake Intel cAVS 2.5 DSP (`sof-tgl.ri`) quad-DMIC |
| Actual backlight brightness | **Working (native Control Center slider + `Fn+F3`/`F4` OSD)** | `R32-PCFIX31` ([nootedgreen-pcfix31-backlight-20261107.patch](../graphics/patches/nootedgreen-pcfix31-backlight-20261107.patch)) `AppleBacklightDisplay` + `0xc8254` PCH PWM sync + `libhp_cb_shim.dylib` (`hp-cb-shim-loader.sh`) + `hp-bridge` native OSD |
| Sleep, wake, Modern Standby (`S0ix` Deep Idle) | **Working (`62.4 min` uninterrupted clamshell S0ix & `R32-PCFIX38` verified; Phase 22 `S0ixStandby` staged)** | [`SSDT-DEEPIDLE.dsl`](../EFI/ACPI/SSDT-DEEPIDLE.dsl) (`371` B AML SHA-256 `280e3a4ad5541bb482c357b785d10d74e95b0128dc309bc10f2617bc585effe1`, `\USWE = Zero`) + `S0ixStandby.kext` (`v0.4.4`, `74,824` B SHA-256 `79f27da6a2124f9d476500f8bebde51af09d5b230d78d7833a0ab2dcb060ba55` with `syncPowerSourcesAfterWake` `_Q06`/`_Q09` AC sync + pure `PMCSR` `D3hot` `CNVW` `PC8` fix, staged in bundle/recovery image pending wake sync to `disk0s6` over `f5088340...`) + `R32-PCFIX32`..`PCFIX38` ([nootedgreen-pcfix38-wakecolor-20261111.patch](../graphics/patches/nootedgreen-pcfix38-wakecolor-20261111.patch), preserving native 10-bit `XRGB_2101010` `0x82000400` in `PLANE_CTL_1_A [0x70180]` and normalizing `PLANE_COLOR_CTL_1_A [0x701CC] = 0x2000`, `CSC_MODE_A [0x4A480] = 0`) + `hp-wake-helper` (`830 ms` backlight hold + ICC/Gamma refresh) |
| Fingerprint authentication (`Synaptics 06cb:00f0`) | **Working (`sudo`, admin prompt & Lock Screen unlock)** | `RidgeKey 1.0.0` (`ridgekeyd` + `pam_ridgekey.so` + `RidgeKey.app` + `RidgeKeyAgent.app`) natively drives the built-in Synaptics `06cb:00f0` USB fingerprint sensor (`2` enrolled fingers + Keychain integration) |
| Touchscreen | Working (`WACF4233` I²C HID enumerated & driven) | Wacom `WACF4233` (`056a:4924` I²C `TPL0`) via `VoodooI2C` + `VoodooI2CHID`; full pressure-pen acceptance not claimed |
| USB & Thunderbolt 4 / USB-C | PCH USB 3.1 & TB4/USB4 `XHCI@D` enumerated (`TDM0@D,2` in `D3hot`) | USB/XDCI/TBT wake disabled on Darwin via `\USWE = Zero` + PCI `PME_EN` clear; full downstream TB4 PCIe tunnelling matrix not claimed |
| Persistent system & daemon logging | **Configured and verified** | Unified Log subsystem `level:info,persist:info` + `com.hp.syslogger` (`/var/log/hp/boot-<STAMP>-<UUID8>/` 15-boot archive + `SIGTERM` shutdown capture) + `/etc/newsyslog.d/com.hp.conf` |
| Advanced Continuity | Partial (`AirportItlwm 2.4.0` native `en0` `IO80211`) | Apple ID / iCloud work via `en0`; AWDL-dependent AirDrop / Sidecar wireless Continuity not claimed |

## Graphics configuration identities

## 2026-11-05 ~ 2026-11-11 Complete GPU Endurance (`R32-PCFIX27`), eDP Backlight (`PCFIX31`), `420v` `HP-BLITALIGN` (`PCFIX35`), Modern Standby `S0ix` & Native 10-bit Post-Wake Color (`PCFIX32`..`PCFIX38`)

Full technical analysis, disassembly offsets, and the 28-trial `CSFLTRK [0x2208]` hardware truth table are documented in [repair32-gpu-stability-and-pmapfix-20261106.md](../mac-for-elitebook/docs/repair32-gpu-stability-and-pmapfix-20261106.md) and [repair32-pcfix2-20261105.md](../mac-for-elitebook/docs/repair32-pcfix2-20261105.md):

1. **Internal SSD `pmap_recycle_page` Resolution (`PMAPFIX`)**:
   - Decoded EFI NVRAM `AAPL,PanicInfo0000..0003` (`d1c3e3018b832b524cd3a7df730de77428f372222540c8a42e6d29ec11b628e6`) proved that the internal-SSD freeze at 394.46 s was `pmap_recycle_page: page 0x101310000 is referenced @pmap.c:1511` in the same `128 KiB` physical window (`0x101304000..0x10131c000`) as the four earlier GA416/GA419 crashes (`0x101304000`, `0x10130e000`, `0x101313000`).
   - Adding a `4 MiB` `UEFI -> ReservedMemory` entry (`Address = 0x101000000`, `Size = 0x00400000`, `Type = Reserved`) and changing `debug=0x100100` to `debug=0x100000` achieved **0 `pmap_recycle_page` panics across 28 consecutive real-machine endurance trials**.
2. **Execlist Submission, Preemption Control, and Lossless Single-Port RCS Scheduler (`ELSQWAIT` + `PCFIX5` + `PCFIX6`)**:
   - Unconditional `EXECLIST_STATUS [0x2234]` bit 30 wait (`elsqWait`, polling up to 2000 µs in 5 µs steps whenever `(EXECLIST_STATUS_LO & 0x40000000) != 0` before writing ELSP/ELKICK in `submitToRing` and `prepareExecListAndSubmit`), plus skipping empty `prepareExecListAndSubmit` calls when both `port0` and `port1` are null.
   - Masked write `0xc100c100` to `GEN8_ROW_CHICKEN2` (`0xe4f4`), `0x00020002` to `GFXREG_CS_CHICKEN1` (`0x2580`, `WaDisableGPGPUMidThreadPreemption`), and clearing bit 14 of `0x20e0` (`GEN9_FFSC_PERCTX_PREEMPT_CTRL`).
   - Host software mid-batch preemption block (`IGScheduler5::updateOptions` `0x385e0`, `allowPreemption` `0x3d9a6`, `isPreemptionAllowed` `0x3d9d2` in [nootedgreen-pcfix5-20261105.patch](../graphics/patches/nootedgreen-pcfix5-20261105.patch)) and lossless Single-Port RCS Execlist policy (`HP-SINGLEPORT-RCS` in [nootedgreen-pcfix6-20261105.patch](../graphics/patches/nootedgreen-pcfix6-20261105.patch): `xeDequeueExecList` + `f_rcs1_hp` at `0x3d5d0` + `f_wait1_hp` at `0x3b971`), **100% eliminating `Port1` (`EL[1]`) submissions (`ELR1 = 0`), same-context `LITE_RESTORE` (`0x8002`), and `0x3098 -> 0x40002098` (`NO ACTIVE ELEMENTS`) hardware freezes**, and enabling 100% clean `XeNG GPUREC: reset RCS ret=1` self-healing recovery.
3. **Gen8 Compute Encoder `PIPE_CONTROL` / `L3ALLOC` / `MEDIA_STATE_FLUSH` Sanitization & `_WA_TABLE` Persistence (`PCFIX2` ~ `PCFIX27`)**:
   - Hooked `IntelMTLComputeFunctions::execute` (`0x6bf20`, gated strictly on `eToken == 0x40001U`) to sanitize 151-dword sub-allocated `COCLGen8CommandTransport` compute encoders (`hpSanitizeComputeEncoder`) in-place before submission:
     - Preserves Packet 1 (`dw[+1] = 0x001010a0U` = `CS_STALL | RT_CACHE_FLUSH | FLUSH_ENABLE | DC_FLUSH_ENABLE`, before `PIPELINE_SELECT = GPGPU` at `dw[+12]`) in `ResetPreambleCmds` (`dw[0..32]`) to drain 3D/ring Render Target Cache while EUs are idle, adds `CS_STALL` to `dw[+7]` and `dw[+25]` (`0x00100480U`), replaces the invalid Gen8 `L3ALLOC` `MI_LOAD_REGISTER_IMM 0xb134` (`dw[15..17]`) with `MEDIA_STATE_FLUSH` (`0x70040000U, 0U`) + `MI_NOOP` (`0U`), and changes Packet 3 (`dw[+19]`, immediately after `MEDIA_STATE_FLUSH` in GPGPU mode) from `0x001010a0U` to `0x001000a0U` (stripping `0x1000 RT_CACHE_FLUSH` so `CSFLTRK bit 28` retires to `0`).
     - Decouples `AddPipeFlushCmd` (`dw[83..94]`) into separate write-flush (`0x001000a0U`) and read-invalidate (`0x00100480U`) packets, removing the unretired Gen8 `Post-Sync Write Immediate` (`0x00004000`) to `m_pScratchPage + 0x10`.
   - In **`R32-PCFIX27`** (`NootedGreen` UUID `4C4C44D2-5555-3144-A1F9-D192CDF39360`, binary SHA-256 `56c2d0758770803190b70b897e06b1ed5ab5318df97fef0c1fc4c07a2de2ffd9`, source `kern_gen11.cpp` SHA-256 `5749ea41e6ead86e240b81d6c4f12f092488ecdf5a2782477dd12d59978e4882`, [nootedgreen-pcfix27-20261106.patch](../graphics/patches/nootedgreen-pcfix27-20261106.patch)), combining this `ResetPreambleCmds` Packet 3 (`dw[+19] = 0x001000a0U`) fix with the clean `PCFIX20` 2-packet `AddPipeFlushCmd` baseline (after `PCFIX25` [nootedgreen-pcfix25-20261106.patch](../graphics/patches/nootedgreen-pcfix25-20261106.patch) and `PCFIX26` [nootedgreen-pcfix26-20261106.patch](../graphics/patches/nootedgreen-pcfix26-20261106.patch) verified `_WA_TABLE` `CS_DBG1=00000010` / `CHKN3=00002000` golden context image persistence and isolated the `0x7010`/`0x20d8`/`0x2050` regression) **passed 100% of all three stages of the Real-Machine GPU Stability & Endurance Test Plan (`705,024` compute encoders across 3 consecutive full Geekbench 6.5.0 Metal runs + 90s 4-worker concurrent stress + 60s RC6 idle & 30s 4-worker burst wake) with ZERO `GPU hang:` and ZERO `GPURestart` events**, and has been deployed to the internal NVMe EFI partition (`/boot/EFI/OC`) with byte-for-byte SHA-256 readback verification (`99/99` files).

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
