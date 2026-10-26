# Repository layout and publication scope

```text
EFI/                 Sanitized accelerated/control configuration examples, ACPI source
graphics/            Final local graphics source snapshot, changes and provenance
mac-for-elitebook/   Installation, ACPI, peripheral and diagnostics engineering
tgl26-usb/           Historical Tiger Lake experiments, custom code and reports
evidence/            Reviewed panic texts, experiment summaries and file hashes
docs/                Current status, build navigation and upstream issue draft
scripts/             Public export and repository validation helpers
```

The two original workspaces remain preserved locally. This is a new, curated publication with clean Git history, rather than an import of private operational history. Source files and third-party license notices retain their attribution.

## Files kept locally

Original unfiltered logs, hardware/firmware dumps, NVRAM variables, SSH credentials, generated SMBIOS identities, installation/boot disk images, proprietary Apple drivers/frameworks, KDK binaries and native signing material remain in the original private workspaces. Published hashes allow source/build/test identities to be checked without distributing those files.

Historical reports sometimes refer to local-only inputs or old experiment names. They document earlier results; their presence does not turn an unfinished experiment into working hardware support. The current acceptance matrix is [STATUS.md](STATUS.md).

Machine-specific serial/UUID/ROM fields and cached Bluetooth controller data are removed from the public EFI templates. They must be configured locally when assembling an EFI. The source hashes of private configurations and binaries are provenance records, not the hash of a public redacted template.

## Contribution scope

Useful contributions include minimal HP/Tiger Lake source changes, reproducible build steps, source-pinned peripheral fixes, and controlled observations. Describe exactly what was tested and distinguish loading/enumeration from functional acceptance.
