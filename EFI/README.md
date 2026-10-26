# OpenCore configuration examples

These **OpenCore 1.0.8** examples are sanitized exports of the actual GA419 accelerated configuration and GA420C basic-display control. They are configuration/source examples; assemble the required dependencies locally.

| File | Role |
| --- | --- |
| `config-accelerated.example.plist` | GA419 experimental accelerated stack; four recent panics, not a stable release |
| `config-software-display.example.plist` | GA420C visible firmware/basic-display control |
| `components.json` | Enabled kext versions, bundle IDs and actual executable hashes |
| `export-manifest.json` | Original/private config hashes, public template hashes and explicit redactions |
| `ACPI/*.dsl` | HP-specific source included where available |

## Assembly

1. Obtain OpenCore 1.0.8 and its drivers from [Acidanthera/OpenCorePkg](https://github.com/acidanthera/OpenCorePkg/releases/tag/1.0.8).
2. Obtain the dependencies identified by `components.json`; final local graphics source is under [`graphics/`](../graphics/README.md). This repository does not contain Apple TGL/Metal binary inputs.
3. Compile the ACPI tables and place them under `EFI/OC/ACPI/`. The standard `SSDT-PLUG.aml` is identified by its tested hash in the manifest; obtain the appropriate upstream/source variant rather than assuming a different sample compiles to identical bytes.
4. Populate `EFI/OC/Kexts/` and `EFI/OC/Drivers/` to match all enabled paths. Copy the chosen example to `EFI/OC/config.plist` and supply locally generated SMBIOS identity fields.
5. Run the matching OpenCore 1.0.8 `ocvalidate` and verify enabled file paths and dependencies. These public examples were schema-checked; the newly assembled reader-specific EFI has not been physically tested by this publication.

`SystemSerialNumber`, `MLB`, `SystemUUID`, `ROM`, password hash/salt and cached Bluetooth controller data are blanked/removed in public templates. Diagnostic/security settings otherwise describe the experimental configuration as tested; read them before adoption.

The control still publishes the VGA device and `IONDRVFramebuffer`; it does not power off the GPU or remove the display. Its device-ID spoof prevents the installed custom TGL personalities from attaching; `-igfxvesa` alone was not used as proof of that absence.
