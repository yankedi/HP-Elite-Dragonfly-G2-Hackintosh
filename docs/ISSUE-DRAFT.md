# Title

HP i5-1135G7 / Tahoe 25G83: repeated pmap/list panics with locally patched TGL graphics; 62-minute basic-display control

# Body

## Summary

I am maintaining a local macOS port for the **HP Elite Dragonfly G2 (i5-1135G7 / Iris Xe 8086:9a49)**.

With our experimental accelerated Tiger Lake stack loaded, four consecutive recent boots froze and produced kernel panics at **252–340 seconds uptime**. With that stack absent and a visible firmware/basic-framebuffer desktop, the same installed macOS system ran to **3755 seconds (~62 min 35 s)** without a user-reported freeze, ending in a recorded user-initiated shutdown sequence.

I have now published the local source, patch/provenance records, configuration examples and reviewed panic texts so the actual HP adaptations can be inspected:

- Project: https://github.com/yankedi/HP-Elite-Dragonfly-G2-Hackintosh
- [Graphics source and provenance](https://github.com/yankedi/HP-Elite-Dragonfly-G2-Hackintosh/tree/main/graphics)
- [Accelerated/control EFI examples](https://github.com/yankedi/HP-Elite-Dragonfly-G2-Hackintosh/tree/main/EFI)
- [Complete panic texts and hash manifest](https://github.com/yankedi/HP-Elite-Dragonfly-G2-Hackintosh/tree/main/evidence)
- [Detailed comparison](https://github.com/yankedi/HP-Elite-Dragonfly-G2-Hackintosh/blob/main/docs/GRAPHICS-STABILITY.md)

**This is a locally modified HP port, not a clean reproduction of current upstream HEAD or an unmodified EFI for another laptop.** The control strongly implicates the accelerated configuration as a group; it does not yet isolate the first memory corruptor or prove a bug in an unmodified upstream component.

## Hardware and software

| Item | Value |
| --- | --- |
| Laptop | HP Elite Dragonfly G2, board8716 |
| CPU | i5-1135G7, Tiger Lake, 4C/8T, 6 MiB L3 |
| iGPU | 8086:9a49, 80 EUs / 10 Gen12 subslices |
| Memory | 16 GiB LPDDR4X-4266 |
| BIOS | HP T90 01.25.00 |
| macOS | Tahoe26.6.2 / 25G83 |
| OpenCore / Lilu | 1.0.8 / 1.7.2 |
| Accelerated stack | Local NootedGreen1.0.0 + AppleIntelTGLGraphicsFramebuffer16.0.0 + AppleIntelTGLGraphics16.0.2 + HookCase8.0.1 |

The local source includes adaptations identified in our records as R5/R6, 80EU/10SS, L3=6, NOAUX, NOCCS3 and PLANES2. The public source/provenance index explains their lineage and which binary was actually tested. The bundle version alone does not identify these changes.

The source base is [`sgiammori/NootedGreen@95f81898be65cb9f7b3d370ca78054be4cc8a62d`](https://github.com/sgiammori/NootedGreen/tree/95f81898be65cb9f7b3d370ca78054be4cc8a62d). The recorded local GA416 commit is `f93dc2447631553d2dcc2f6d5a8a495acf57990c`; all 25 included NootedGreen source files were checked byte-for-byte against that Git object. Cumulative/staged patches and separate HookCase deltas are included. Firmware payload headers and proprietary Apple binaries remain external inputs, identified by hashes where available; no new bit-for-bit rebuild is claimed.

## Four recent accelerated failures

| Trial | Uptime | Signature | Current task at detection |
| --- | ---: | --- | --- |
| 1 | 334.543 s | `corrupt list around element` | ActivityMonitor |
| 2 | 339.564 s | `pmap_recycle_page: page 0x101304000 is referenced @pmap.c:1511` | iconservicesagent |
| 3 | 273.073 s | `pmap_recycle_page: page 0x101313000 is referenced @pmap.c:1511` | WindowServer |
| 4 | 252.560 s | `pmap_recycle_page: page 0x10130e000 is referenced @pmap.c:1511` | tccd |

The current tasks are detection contexts, not established culprits. Trials1–3 include the complete native `macOSPanicString`; trial4 was recovered from the firmware panic chunks with exact packA re-encoding/cross-validation. See the linked panic manifest for original and exported text hashes.

The UUID-matched 25G83 kernel/KDK places the list check at `__pending_call_enqueue+0x1f7`, and the repeated pmap check at `_vm_page_free_list+0x2cb`. These locate detection, not the first write. A similar pmap failure already occurred before the latest peripheral update, while the experimental graphics stack was installed.

## Visible basic-display control

I kept the same installed OS and the non-graphics peripheral configuration. The control changed the graphics group:

1. Removed NootedGreen injection and TGL-specific properties/boot arguments.
2. Enabled the existing official WhateverGreen1.7.1.
3. Spoofed the GPU PCI device ID to `0xffff` so the installed custom TGL personalities did not match; added `-igfxvesa` as an extra guard.
4. Kept the VGA device and firmware scanout enabled. No GPU power-off or display disable was used.

Installed TGL/Metal files and kernel collections were left unchanged. Runtime verification showed:

- User-confirmed usable **1920×1080 desktop** with slow basic/software display.
- `IGPU/.Display_boot` class **IONDRVFramebuffer**, memory **8,294,400 bytes**.
- Complete loaded-kext inventories with **no NootedGreen, TGL framebuffer, TGL accelerator or HookCase**; checked again around 53 min uptime.
- No actual IntelAccelerator service. The compatibility node named IOAccelerator was class IOServiceCompatibility and was not counted as an accelerator.
- No separate per-application renderer API probe was performed.

Earlier Kernel/Block Exclude/Disable attempts returned `Unsupported` and did not reach a usable desktop; those are not successful controls or additional confirmed memory panics.

## Result and limits

The last received control event was at **3755.014 s uptime**. At 02:20:55+0800, loginwindow recorded shutdown confirmation, `ShutdownLogoutUIManager shutdown:` and GUI termination; SSH disconnected afterward. Final physical power-off was outside the capture.

A continuous unfiltered debug stream covered about **60 min 30 s**, with **2,613,574 complete events / 2,822,835,856 received bytes**. Gzip integrity and both hashes were verified. The disconnect left one preserved 386-byte partial JSON event. The public repository contains a reviewed summary and hashes; personal raw unified-log content remains locally archived.

This is **one** basic-display control, with no quantitatively matched workload. It considerably extends the failure-free window compared with the four recent accelerated boots, but does not establish permanent stability or isolate NootedGreen versus TGL framebuffer/accelerator, HookCase or user-space Metal.

## Exact tested identities

NootedGreen executable SHA-256:

```text
e44ef32745cad51bd13a2006557f8d2076f96759a0afce867547a8466ab6dbbb
```

Loaded UUID: `4C4C44D4-5555-3144-A13A-DFB86EFBE513`.

Kernel UUID: `39CC2C26-3F72-3565-89C4-94DFE36DFDF2`.

Configured accelerated boot arguments (public config preserves the configured value; runtime panic text is provided separately):

```text
-v keepsyms=1 debug=0x100 slide=0 -ngreentglwithgfx ngreenSched=3 ngreen-dmc=tgl -ngreentgltahoe -ngreenfixbootmode IGLogLevel=3 amfi_get_out_of_my_way=1 -allow3d -disablegfxfirmware
```

## Help requested

1. Are there known page ownership, pin/unpin, mapping/unmapping or callback-lifetime issues in this TGL graphics path that could explain these detection sites?
2. Is there a supported way to retain the framebuffer while disabling only the accelerator/HookCase-dependent paths for the next minimal-variable test?
3. Which source differences or targeted diagnostic data would best identify the first corrupting write? The current panic does not expose failing-time managed-page/PV/PTE contents or the corrupted call's callback owner.

I can provide focused extracts from the preserved full logs and additional source details. I have not yet claimed that a particular component or upstream commit is responsible.
