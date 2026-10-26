# Tiger Lake accelerated graphics stability comparison

## Observation

The same installed macOS 26.6.2 / 25G83 system was used for the accelerated trials and a visible basic-display control. Non-graphics EFI/peripheral settings were retained in the control. The changed **graphics group** includes NootedGreen removal, WhateverGreen enablement, PCI device-ID spoofing, and graphics boot/property changes; this is not an isolation of one driver function.

| Trial | Configuration | Panic uptime | Detection context | Signature |
| --- | --- | ---: | --- | --- |
| 1 | GA419 accelerated | 334.543 s | ActivityMonitor | `corrupt list around element` |
| 2 | GA419 accelerated | 339.564 s | iconservicesagent | `pmap_recycle_page: page 0x101304000 is referenced @pmap.c:1511` |
| 3 | GA419 accelerated | 273.073 s | WindowServer | `pmap_recycle_page: page 0x101313000 is referenced @pmap.c:1511` |
| 4 | GA419 accelerated | 252.560 s | tccd | `pmap_recycle_page: page 0x10130e000 is referenced @pmap.c:1511` |
| Control | GA420C basic display | Last event at 3755.014 s | Shutdown sequence followed | No user-reported freeze during this run |

The process names are the current tasks when the kernel detected an error, not established memory corruptors. Panic texts and provenance are in [evidence](../evidence/README.md).

## Control construction and runtime evidence

- Kept the VGA device, framebuffer memory and firmware scanout; no GPU power-off or display-device disable operation.
- Removed NootedGreen injection and custom TGL properties/arguments; enabled the existing official WhateverGreen 1.7.1.
- Spoofed the GPU `device-id` to `0xffff` so that the custom installed TGL PCI personalities did not match. Added `-igfxvesa` as an additional guard.
- Kept system TGL/Metal files, kernel collections, SIP/AMFI settings and the peripheral group unchanged.
- User confirmed a usable, slow **1920×1080 desktop**.
- IORegistry: `IGPU/.Display_boot`, class **IONDRVFramebuffer**, memory **8,294,400 bytes**.
- Complete loaded-kext inventories: **no NootedGreen, TGL framebuffer, TGL accelerator or HookCase**; absence independently checked again at about 53 minutes uptime.
- No actual IntelAccelerator attached. A compatibility node named IOAccelerator had class IOServiceCompatibility and was not an accelerator.
- No separate per-application renderer API probe was performed.

Earlier GA420/GA420B attempts using OpenCore Kernel/Block returned `Unsupported` and failed to provide a usable desktop. They are not successful software-display controls and do not add confirmed memory panics.

## Captured window and integrity

The control stream began about 125 seconds after boot and ran from **2026-10-27 01:20:27.497155 to 02:20:57.069752 +0800**: approximately 60 min 30 s of received events, ending at 62 min 35 s uptime.

- Received uncompressed bytes: **2,822,835,856**.
- Complete JSON events: **2,613,574**.
- Gzip bytes: **198,641,921**.
- Final partial event: **386 bytes**, preserved exactly; this is the one invalid JSON line.
- Gzip integrity and compressed/uncompressed SHA-256 were verified locally.
- Uncompressed SHA-256: `3583e3ee91bc5c7ec35d8357e376885331ea0aea62f76d60b8442cbe62ed9f6d`.
- Gzip SHA-256: `41910347c68afc6f5bcff585251b2ab4148dc2ca8d8059372ba3263c2c406d69`.

At 02:20:55, loginwindow recorded a shutdown confirmation result, `ShutdownLogoutUIManager shutdown:`, and GUI application termination. SSH then disconnected. This supports a user-initiated shutdown sequence; final physical power-off was outside the SSH capture. SSH exit255 alone is not treated as a panic.

## What this supports

The much longer failure-free window strengthens the association with the accelerated graphics configuration. The user also recalls that the system was slow but did not exhibit these panics before the graphics changes; that is useful historical evidence, not a matched measurement.

There has been **one successful basic-display control run**, and application workloads were not quantitatively matched. The result does not establish permanent stability, isolate NootedGreen versus framebuffer/accelerator/HookCase/user-space Metal, or identify the first corrupting write.

Using the exact UUID-matched kernel/KDK, the list panic maps to `__pending_call_enqueue+0x1f7`, while the repeated pmap check maps to `_vm_page_free_list+0x2cb`. These are detection sites. The panic does not contain the failing-time managed-page/PV/PTE details or callback owner needed to identify the first writer.

## Next diagnostic target

Ask the graphics maintainers for a supported framebuffer-only / accelerator isolation path and which mapping, page ownership, pin/unpin or callback diagnostic data would be most useful. No new variant has been represented as tested.
