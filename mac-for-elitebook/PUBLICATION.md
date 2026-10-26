# Public-copy notes

Updated 2026-10-27. This document describes only the `mac-for-elitebook/` subtree.

## Scope and exclusions

- The project-authored ACPI DSL, configuration example, hardware inventory, patches, scripts, tests, docs, manifests, licenses, `Makefile`, and `.gitignore` were retained in the public copy.
- Private/generated trees and machine evidence (`.local/`, `.cache/`, `build/`, `dist/`, raw EFI/AML captures, runtime logs, and private identity material) are not included.
- The source orchestration files `AGENTS.md`, `docs/continuation.md`, `configs/install-preparation.json`, `manifests/experiment-history.json`, and `docs/cleanup-proposal-20261027.md` were not copied verbatim. The first four public entry points now contain concise, sanitized status/evidence indexes; the cleanup proposal remains omitted.
- Personal paths, the removable-volume label, host-specific ESP PARTUUIDs, and network endpoint examples were generalized or removed. No credentials or private-key material are published intentionally.

## Evidence limits

The status summaries are derived from the supplied project progress record and the retained public documentation. Private evidence files are not present in this copy, so their hashes and detailed raw contents cannot be independently rechecked here. Do not treat missing private evidence as a pass, or treat the software-display comparison as proof of graphics causation. The current state and explicit limitations are in `README.md`, `configs/install-preparation.json`, and `manifests/experiment-history.json`.

## Validation

The public subtree passed `make check` from the initialized destination repository. The check tolerates absent optional `.local/` evidence, but does not reproduce the private hardware trials. Whole-repository publication checks and the actual source revision are recorded in the parent project's publication report and issue draft.
