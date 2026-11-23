# OpenCore configuration examples

These **OpenCore 1.0.8** examples are sanitized exports of the finalized HP EliteBook 840 G8 / Elite Dragonfly G2 (`25G83`) accelerated configuration (`Option A2` native DC9 S0ix + `R32-PCFIX63-EDPWAKE` + `TGLIshAls.kext v0.5.2` + `S0ixStandby.kext v0.5.4` + `TGLDmic.kext v0.5.1`, `Timeout=3`, `HideAuxiliary=true`, `LauncherOption=Full`, `PollAppleHotKeys=true`, `AllowSetDefault=false`, `ApplePanic=false`, `DisableWatchDog=false`, `amfi=0x7`, `csr-active-config <07020000>`, `-ngreenfbdpms -s0ixd3 -s0ixwifipm -s0ixacnortc`) and the earlier `GA420C` basic-display control. They are configuration/source examples; assemble the required binaries/kexts and generate unique SMBIOS values locally.

| File | Role |
| --- | --- |
| `config-accelerated.example.plist` | Daily-use `Option A2` + `R32-PCFIX63-EDPWAKE` accelerated stack (`TGLIshAls v0.5.2`, `S0ixStandby v0.5.4`, `TGLDmic v0.5.1`, `Timeout=3`, `HideAuxiliary=true`, `LauncherOption=Full`, `PollAppleHotKeys=true`, `AllowSetDefault=false`, `ApplePanic=false`, `DisableWatchDog=false`, `amfi=0x7`, `csr-active-config <07020000>`, `PMAPFIX`, `PT04->XT04`, `BAT0._BST->XBST`, `-ngreenfbdpms -s0ixd3 -s0ixwifipm -s0ixacnortc`) |
| `config-software-display.example.plist` | Earlier `GA420C` visible firmware/basic-display control |
| `components.json` | Enabled kext versions, bundle IDs, dependencies, and actual executable/ACPI/driver SHA-256 hashes |
| `export-manifest.json` | Original/private config hashes, public template hashes and explicit redactions |
| `ACPI/*.dsl` | HP-specific ACPI DSL sources (`SSDT-EC0-ITLB.dsl`, `SSDT-EC-USBX-HP.dsl`, `SSDT-RHUB-HP.dsl`, `SSDT-PNLF-HP-GA419.dsl`, `SSDT-DEEPIDLE-optionA.dsl` compiled as `SSDT-DEEPIDLE.aml`, `SSDT-BATFULL.dsl`, `SSDT-LIDWAKE.dsl`, plus `SSDT-PLUG.dsl` and superseded `SSDT-DEEPIDLE.dsl`; archived early Fn hotkey reference `SSDT-HP-Hotkeys.dsl` remains disabled in production) |

## Assembly

1. Obtain OpenCore 1.0.8 and its drivers from [Acidanthera/OpenCorePkg](https://github.com/acidanthera/OpenCorePkg/releases/tag/1.0.8).
2. Obtain the dependencies identified by `components.json`; final local graphics source is under [`graphics/`](../graphics/README.md). This repository does not contain Apple TGL/Metal binary inputs.
3. Compile the ACPI tables and place them under `EFI/OC/ACPI/` (`SSDT-DEEPIDLE-optionA.dsl` must be compiled as `EFI/OC/ACPI/SSDT-DEEPIDLE.aml`). All 8 enabled production SSDT sources (including [`SSDT-PLUG.dsl`](../mac-for-elitebook/acpi/SSDT-PLUG.dsl)) are also tracked in [`mac-for-elitebook/acpi/`](../mac-for-elitebook/acpi/) and compile byte-for-byte with `iasl -ve` to the tested `.aml` hashes in the manifest.
4. Populate `EFI/OC/Kexts/` and `EFI/OC/Drivers/` to match all enabled paths. Copy the chosen example to `EFI/OC/config.plist` and supply locally generated SMBIOS identity fields.
5. Run the matching OpenCore 1.0.8 `ocvalidate` and verify enabled file paths and dependencies. These public examples were schema-checked; the newly assembled reader-specific EFI has not been physically tested by this publication.

`SystemSerialNumber`, `MLB`, `SystemUUID`, `ROM`, password hash/salt and cached Bluetooth controller data are blanked/removed in public templates. Daily-use boot and security settings otherwise match the finalized `config.plist` (`ShowPicker=true`, `ScanPolicy=0` for MBR recovery compatibility); read them before adoption.

The control still publishes the VGA device and `IONDRVFramebuffer`; it does not power off the GPU or remove the display. Its device-ID spoof prevents the installed custom TGL personalities from attaching; `-igfxvesa` alone was not used as proof of that absence.
