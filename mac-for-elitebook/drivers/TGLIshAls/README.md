# TGLIshAls (`v0.5.0`)

Clean-room `BSD-3-Clause` macOS kernel driver (`com.labrouss.TGLIshAls`) for the **Intel Tiger Lake-LP Integrated Sensor Hub (ISH)** (`PCI 00:12.0`, `8086:a0fc`, subsystem `103c:8716`, `IOAPIC` IRQ `26`/`0x1a`) and **Capella `CM32183H` Ambient Light Sensor** on HP Elite Dragonfly G2 (`macOS 26.6.2` `25G83`).

## Why a native ISH driver (zero fake EC / zero `_OSI` spoofing)

On HP Elite Dragonfly G2 (`8716`, EC firmware `37.41.00`), the ambient light sensor connects exclusively through the Intel Tiger Lake-LP ISH micro-controller rather than an ACPI `ACPI0008._ALI` method:

1. Without an attached macOS PCI driver on `ISHD@12`, macOS auto-brightness (`AppleLMUController` / `DisplayALSManager`) has no sensor input, and the uninitialized ISH prevents EC ambient-light tracking needed for native `F9` keyboard backlight sustain/extinguish behavior.
2. `TGLIshAls.kext` initializes the hardware ISH firmware directly without faking EC values or spoofing `_OSI`:
   - Maps BAR0 MMIO registers (`HOST2ISH_DRBL`, `ISH2HOST_DRBL`, `PISR`/`PIMR`, `HOST_COMM`, `FWSTS`, `RMP2`) and evaluates `_DSM` for Intel ISH DMA/firmware power management.
   - Runs **HBM 1.0** client discovery, connects fixed client `13` (`SYSTEM_STATE_SUBSCRIBE`) and HID-over-ISHTP client (`HIDClientAddress = 3`), enumerates `5` HID devices, and completes the full **317-byte Capella `CM32183H`** `GET_FEATURE_REPORT -> SET_FEATURE_REPORT (PowerState=D0, ReportingState=AllEvents) -> Verify` handshake.
   - Submits live illuminance samples (`lux << 14`) via `VirtualSMCAPI::Plugin` (`RMde`, `ALRV`, `ALI0`, `ALV0`, `ALV1`, `AL! `, `LKSB`, `LKSS`, `MSLD`) and publishes an `ACPI0008` `IOService` nub so macOS built-in `AppleSMCLMU.kext` (`AppleLMUController`) + `corebrightnessd` (`DisplayALSManager`) enable native **Automatically adjust brightness** without modifying Apple system binaries.

## Key fixes in `v0.5.0` (`R35-PCFIX58-ISH-ALS-V050`)

- **`PIMR` interrupt storm fix (`computeInitPimr`)**: Preserves bit 11 (`kPimrIsh2HostClrMaskBit`) while clearing bit 8 (`kPimrHost2IshBusyClrMaskBit`) and setting bit 0 (`kPimrIntEnBit`), matching Intel TGL ISH hardware behavior and preventing `18.4k–39.7k/s` `Vector 0x5a(ISHD)` interrupt storms (reduced to `10.85–11.85 interrupts/sec`).
- **XNU native `IOInterruptEventSource` (`INTx-AutoDisable`)**: Uses shared `drainRx()` across `irqOccurred()` and `timerFired()`, reads `FWSTS` after every `HOST2ISH_DRBL` write to flush posted PCIe writes, and includes a `500`-empty-IRQ circuit-breaker (`100 ms` polling fallback).
- **Exclusive driver matching**: Sets `IOMatchCategory = IODefaultMatchCategory` in `Info.plist` so `com.apple.DriverKit-Apple16X50PCI` does not probe `ISHD@12`.
- **TX flow-control & keepalive safety**: Guards the `5000 ms` streaming keepalive (`!host2IshBusy && !hidTxPending_ && hidTxCredits_ > 0 && tx_.freeSlots() >= 2`), adds `rxFlowControlPending_` recovery, and reasserts `needHostReady_` on `MNG_RESET_NOTIFY`.

## Files

- `TGLIshAls.hpp`, `TGLIshAls.cpp`, `kmod_info.c`, `Info.plist`: `IOService` driver, MMIO mailbox, `IOInterruptEventSource`, `VirtualSMC` plugin, `ACPI0008` nub, and IORegistry telemetry properties.
- `IshProtocol.hpp`: Pure C++ ISH IPC / HBM 1.0 / `HOSTIF` protocol state machine and RX/TX queues.
- `IshHidAls.hpp`: HID report descriptor parser (`CM32183H` `317`-byte feature layout, unit exponent illuminance decoder, and Apple `ALV0` Q16/Q14 packer).
- `tests/test_ish_als.cpp`: Host-side unit tests for protocol state machine, HID descriptor parsing, 317-byte feature fragmentation, `PIMR` mask computation, and flow-control recovery (`697` checks).
- `LICENSE`: `BSD-3-Clause` license.

## Host unit test verification

```sh
clang++ -std=c++17 -O1 -g -fsanitize=address,undefined -I. tests/test_ish_als.cpp -o /tmp/test_ish_als && /tmp/test_ish_als && rm -f /tmp/test_ish_als
```
