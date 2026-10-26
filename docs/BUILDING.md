# Build and validation navigation

## Public repository checks

Python3 and Git are sufficient for the root publication check:

```sh
python3 scripts/check-publication.py
make -C mac-for-elitebook check
git diff --check
```

These check source/configuration/document structure; they do not establish bootability or GPU stability.

## OpenCore configuration

See [EFI/README.md](../EFI/README.md). The examples correspond to OpenCore **1.0.8**. Use that release's `ocvalidate` for schema validation. Populate dependencies from the upstream sources in the component manifest, compile the required ACPI source, and generate local machine identities before testing.

The unstable accelerated and basic-display control templates are separate. Preserve a working recovery path and use the configuration appropriate to the intended test.

## Graphics

The final source, patch lineage, tested binary identities and build limitations are described in [graphics/README.md](../graphics/README.md). Existing recipes include Linux cross-build/native-signing stages. Published source plus a recipe is not a fresh bit-for-bit rebuild claim; see its provenance report for what was verified.

Apple driver/KDK/Metal inputs must be obtained locally where required; the repository identifies them without redistributing them. Historical experiments under `tgl26-usb/` have per-directory instructions and may require their original private inputs.

## Installation and peripherals

`mac-for-elitebook/` includes original build/inspection/collection scripts and ACPI source. Its local `.local/` evidence/cache tree is intentionally absent from public Git. Configure explicit SSH targets, known hosts and local credentials for tools that collect hardware; no personal credentials are distributed.
