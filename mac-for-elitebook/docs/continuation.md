# Public continuation and current state

Updated 2026-11-06. This is a concise public handoff, not a transcript. Read this page, [`README.md`](../README.md), and [`repair32-gpu-stability-and-pmapfix-20261106.md`](repair32-gpu-stability-and-pmapfix-20261106.md) before relying on older runbooks.

## Current state (2026-11-06)

- **Internal NVMe Boot & `pmap_recycle_page` Resolution (`PMAPFIX`)**: macOS Tahoe **26.6.2 / 25G83** is installed on the internal Micron 2210 NVMe SSD and boots independently via OpenCore 1.0.8 (`/boot/EFI/OC`). Decoded EFI NVRAM `AAPL,PanicInfo0000..0003` (`d1c3e3018b832b524cd3a7df730de77428f372222540c8a42e6d29ec11b628e6`) proved that the earlier internal-boot freezes at ~252–394 s were `pmap_recycle_page: page 0x101310000 is referenced @pmap.c:1511` within the physical window `0x101304000..0x10131c000` combined with `debug=0x100100` (`DB_HALT`). Reserving `0x101000000..0x101400000` (`4 MiB`, `Type = Reserved`) under `UEFI -> ReservedMemory` and switching to `debug=0x100000` achieved **0 `pmap_recycle_page` panics across 25 consecutive high-load real-machine endurance trials**.
- **Iris Xe 80 EU Metal Compute Acceleration (100% 8/8 Geekbench 6.5.0 Metal Workloads Passed)**:
  - Unconditional `EXECLIST_STATUS [0x2234]` bit 30 wait (`elsqWait`), `GFXREG_CS_CHICKEN1 [0x2580] = 0x00020002` (`WaDisableGPGPUMidThreadPreemption`), `GEN8_ROW_CHICKEN2 [0xe4f4] = 0xc100c100`, host software mid-batch preemption block (`PCFIX5`), and lossless Single-Port RCS Execlist scheduling (`HP-SINGLEPORT-RCS` in `PCFIX6`) **100% eliminated Port1 population (`ELR1 = 0`), same-context `LITE_RESTORE` (`0x8002`), and `0x3098 -> 0x40002098` (`NO ACTIVE ELEMENTS`) hardware freezes**, enabling 100% clean `XeNG GPUREC: reset RCS ret=1` self-healing recovery.
  - In-place sanitization of `AppleIntelTGLGraphicsMTLDriver` (`COCLGen8CommandTransport`) 151-dword compute encoders (`hpSanitizeComputeEncoder` on `IntelMTLComputeFunctions::execute`, `eToken == 0x40001U`) enabled **100% completion of all 8 Geekbench 6.5.0 Metal compute workloads (`25,088` compute encoders) with 0 `GPU hang:` and 0 `GPURestart` events** in `R32-PCFIX2` (`f52f0d44d304e55e95b9875adb2c198b0950578b0ce4cc07191cc534962b1a54`) and repeatedly in endurance trials `R32-PCFIX14`, `R32-PCFIX16`, `R32-PCFIX19`, and `R32-PCFIX20` (advancing to Stage 1 Run 2 `enc=32,202+`).
  - In `R32-PCFIX25` ([`patches/nootedgreen-r32-pcfix25-20261106.patch`](../patches/nootedgreen-r32-pcfix25-20261106.patch)), enabling 64-bit shifted Tiger Lake `_WA_TABLE` bits `that[0xf5f] |= 0x80` (`0x7010 = 0x20002000`, `Wa_1409142259:tgl`) and `that[0xf68] |= 0x01` (`0x20d8 = 0x00100010`, `Wa_1606700617:tgl`) with RCS submission reinforcement persisted `CS_DBG1=00000010` and `CHKN3=00002000` across context switches and **cleared all cache-flush tracking bits (`bits 31..1`) in `CSFLTRK [0x2208]` to `0x00000001`** for the first time across all 25 trials.
- **Nix Flake Reproducible Toolchain**: [`flake.nix`](../flake.nix) and [`flake.lock`](../flake.lock) provide a declarative `devShell` (`clang_21`, `llvm_21`, `lld_21`, `rcodesign`, `grub2`, `mtools`, `dosfstools`, `acpica-tools`, `python3`, `openssh`, `rsync`, `jq`, `gnumake`, `git`).
- **Working Peripherals**: Wi-Fi (`itlwm` AX201), Bluetooth + Bluetooth bidirectional audio, I²C touchpad (`06cb:cd74`), PS/2 keyboard, battery readout, camera, and PCH USB. Built-in speakers/DMIC (ALC285 SOF), eDP PWM brightness control, and fingerprint (`06cb:00f0`) remain open items; see [`peripheral-adaptation-status-20261104.md`](peripheral-adaptation-status-20261104.md).

## Evidence and privacy boundary

`../manifests/experiment-history.json` is a high-level index to retained public docs and patches. Private `.local/` evidence, orchestration history, machine identities, credentials, and original personal paths were excluded.

## Suggested next steps

1. Combine the `CSFLTRK = 0x00000001` (`bits 31..1 = 0`) persistence from `R32-PCFIX25` with post-`GPGPU_WALKER` `PIPE_CONTROL` retirement to complete all 3 consecutive Geekbench 6.5.0 Metal runs (`75,264` compute encoders) in Stage 1 without triggering a single `GPURestart`.
2. Continue peripheral adaptation for ALC285 SOF audio and eDP backlight control as separately scoped experiments.
