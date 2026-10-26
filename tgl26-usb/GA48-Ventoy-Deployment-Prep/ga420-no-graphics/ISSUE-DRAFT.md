# Title

Tiger Lake / i5-1135G7: repeated pmap panics with TGL acceleration; over 1 hour without freezing using software display

# Body

## Summary

I am testing a local HP Elite Dragonfly G2 port of this experimental Tiger Lake graphics stack on macOS Tahoe.

With the accelerated TGL stack loaded, four consecutive recent boots froze and produced kernel panics after approximately **4–6 minutes**. With the experimental graphics stack no longer loaded and the desktop using the firmware/basic framebuffer, the same macOS installation ran for approximately **62 minutes without a reported freeze**, until I initiated shutdown.

The software-display control was verified from the loaded-kext list and IORegistry, rather than inferred from boot arguments alone. This is strong evidence of a stability problem associated with the accelerated graphics configuration, although it does not yet identify the component that first corrupts memory.

## Hardware and software

- **Laptop:** HP Elite Dragonfly G2
- **CPU:** Intel Core i5-1135G7, Tiger Lake, 6 MiB L3
- **iGPU:** Intel Iris Xe, PCI `8086:9a49`, 80 EUs / 10 subslices
- **Memory:** 16 GiB LPDDR4X-4266
- **BIOS:** HP T90 01.25.00
- **macOS:** Tahoe 26.6.2, build `25G83`
- **OpenCore:** 1.0.8
- **Lilu:** 1.7.2
- **Accelerated stack:** NootedGreen + AppleIntelTGLGraphicsFramebuffer 16.0.0 + AppleIntelTGLGraphics 16.0.2 + HookCase 8.0.1

**Scope:** this is a locally modified HP port, not a clean reproduction of the current upstream HEAD or an unmodified EFI for the original target laptop. The local build includes HP/Tiger Lake adaptations for 80 EUs / 10 subslices and 6 MiB L3, plus local R6/R5, NOAUX, NOCCS3 and PLANES2 changes. I can provide the relevant source/configuration differences for review.

## Accelerated configuration: four consecutive failures

All four recent trials used the same internal EFI and accelerated graphics configuration. Runtime evidence confirmed that the experimental graphics components were loaded.

| Trial | Uptime at panic | Panic signature | Current task when the error was detected |
|---|---:|---|---|
| 1 | 334.543 s | `corrupt list around element` | ActivityMonitor |
| 2 | 339.564 s | `pmap_recycle_page: page 0x101304000 is referenced @pmap.c:1511` | iconservicesagent |
| 3 | 273.073 s | `pmap_recycle_page: page 0x101313000 is referenced @pmap.c:1511` | WindowServer |
| 4 | 252.560 s | `pmap_recycle_page: page 0x10130e000 is referenced @pmap.c:1511` | tccd |

The current tasks above are detection contexts, not established culprits.

Using the UUID-matched `25G83` kernel/KDK:

- The first panic was located at the list-consistency check in `__pending_call_enqueue+0x1f7`.
- The repeated pmap panics map to an inlined check in `_vm_page_free_list+0x2cb`.
- These identify where corruption/inconsistency was detected, not the first writer or a confirmed common cause for both signatures.

A similar pmap failure had also occurred before the latest I2C/Bluetooth/battery update, while the experimental graphics stack was already installed. Therefore, the failure pattern is not exclusive to that peripheral update.

## Software-display control

I kept the same macOS installation and the non-graphics EFI/peripheral configuration. For the control, I:

1. Removed NootedGreen injection and the TGL-specific platform property/boot arguments.
2. Enabled the existing, unmodified WhateverGreen 1.7.1 bundle.
3. Reported the iGPU device ID as `0xffff`, which does not match either installed TGL driver's PCI personality. WhateverGreen also handles the corresponding PCI configuration reads.
4. Added `-igfxvesa` as an additional guard. The PCI matching change, not this argument alone, was used to prevent the custom TGL drivers from attaching.
5. Kept the VGA device and firmware scanout available; there was no GPU power-off or display-device disable operation.

The installed TGL/Metal files and kernel collections on disk were left unchanged.

### Runtime verification

- A visible, usable **1920×1080 desktop** was available; slow software rendering was acceptable for this test.
- IORegistry showed `IGPU/.Display_boot` with class **`IONDRVFramebuffer`**, framebuffer memory **8,294,400 bytes**.
- The iGPU was still present as a VGA PCI device, reporting device ID `0xffff`.
- System Information reported that the graphics driver was not loaded.
- The complete loaded-kext list contained **none of NootedGreen, the TGL framebuffer, the TGL accelerator, or HookCase**. Their absence was checked again at about 53 minutes uptime.
- There was no actual `IntelAccelerator` service attached. A node named `IOAccelerator` under `IOKitRegistryCompatibility` was class `IOServiceCompatibility`, not an active hardware accelerator.

### Result

- The user reported no freeze during this control run.
- The last received event was at approximately **62 minutes uptime**.
- The final logs show a shutdown-confirmation result, `ShutdownLogoutUIManager shutdown:`, and the start of GUI application termination before SSH disconnected. The final physical power-off is outside the SSH capture.
- One continuous, unfiltered debug-log stream covered approximately **60 minutes**, with **2,613,574 complete events** and **2,822,835,856 received uncompressed bytes**.
- Gzip integrity and both compressed/uncompressed SHA-256 hashes were verified. The received stream ends with one preserved 386-byte partial JSON event at disconnection.

This is one control run, and the application workload was not quantitatively matched. The longer failure-free window is meaningful compared with four failures at 252–340 seconds, but it is not a claim of permanent stability or proof against a specific driver function.

## Questions

1. Are there known Tiger Lake/LPDDR4X issues in the graphics stack involving page ownership, mapping/unmapping, pinning, or memory corruption that could lead to these pmap assertions?
2. Is there a supported way to separate framebuffer-only operation from the accelerator/HookCase-dependent paths for the next controlled test?
3. Which targeted diagnostic data or local patch differences would be most useful to investigate the first corruption, rather than only the eventual panic site?

I have preserved the panic reports/recovered firmware panic text, full runtime inventories and original logs, and can provide sanitized panic files and focused extracts.

<details>
<summary>Exact accelerated-build identifiers and boot arguments</summary>

NootedGreen bundle identifier/version: `com.StezzaPilot.NootedGreen` / `1.0.0` (local build; the version alone does not identify the modifications).

NootedGreen executable SHA-256:

```text
e44ef32745cad51bd13a2006557f8d2076f96759a0afce867547a8466ab6dbbb
```

Loaded NootedGreen UUID:

```text
4C4C44D4-5555-3144-A13A-DFB86EFBE513
```

Experimental kext bundle identifiers:

```text
com.xxxxx.driver.AppleIntelTGLGraphicsFramebuffer
com.xxxxx.driver.AppleIntelTGLGraphics
org.smichaud.HookCase
```

Configured accelerated boot arguments:

```text
-v keepsyms=1 debug=0x100 slide=0 -ngreentglwithgfx ngreenSched=3 ngreen-dmc=tgl -ngreentgltahoe -ngreenfixbootmode IGLogLevel=3 amfi_get_out_of_my_way=1 -allow3d -disablegfxfirmware
```

Kernel UUID:

```text
39CC2C26-3F72-3565-89C4-94DFE36DFDF2
```

Earlier attempts using OpenCore `Kernel/Block` with `Exclude` and then `Disable` returned `Unsupported` for all three targeted kexts. Those attempts did not produce a usable desktop and are **not counted as successful software-display controls**. The control described above uses the verified PCI matching/basic-display route instead.

</details>
