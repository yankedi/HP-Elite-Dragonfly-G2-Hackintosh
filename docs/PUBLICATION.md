# Initial source publication — 2026-10-27

Repository: [yankedi/HP-Elite-Dragonfly-G2-Hackintosh](https://github.com/yankedi/HP-Elite-Dragonfly-G2-Hackintosh).

## Uploaded source/evidence snapshot

**Commit:** [`20b790a31bd4bb3e180ce622cbc32d2daffe02e8`](https://github.com/yankedi/HP-Elite-Dragonfly-G2-Hackintosh/commit/20b790a31bd4bb3e180ce622cbc32d2daffe02e8).

The initial snapshot contains **1,324 tracked files**, approximately **11.5 MB** of source/documentation content. It includes both curated original projects, the final local graphics source/patch chain, sanitized EFI examples, source provenance and reviewed failure/control evidence. The original workspaces and private evidence remain locally preserved.

The snapshot was committed with a clean working tree and uploaded to `main` using the user-provided **SSH remote**. A subsequent `git ls-remote origin refs/heads/main` returned the identical commit, confirming the remote branch accepted the source upload. The issue draft was then updated to pin its links to that actual source/evidence revision.

## Verified checks

- Root static publication checks: **1,324 files, 59 JSON records, 382 Python AST checks and 5 plists**; no rejected binary/private artifacts or retained original personal endpoints.
- Exact private EFI serial/MLB/UUID/ROM encodings absent from the inspected public content; public OpenCore identity fields blank.
- Public `mac-for-elitebook` repository checks: **46 Python scripts, 42 JSON records, 28 Markdown files**. Missing private evidence is optional/unavailable, not declared reverified.
- Syntax checks: **89 shell/command recipes**; none executed as deployment/build operations.
- Both exported EFI examples: **OpenCore1.0.8 ocvalidate exit0**.
- Three included HP ACPI DSL tables compile with **zero errors, warnings or remarks**.
- Explicit non-graphics EFI comparison: equal after excluding the recorded graphics-group inputs.
- **25 NootedGreen source files** byte-match the recorded GA416 Git commit `f93dc2447631553d2dcc2f6d5a8a495acf57990c`.
- Cumulative source diffs replayed from pinned upstream `95f81898be65cb9f7b3d370ca78054be4cc8a62d` Git objects reproduce **29 published NootedGreen/HookCase files**.
- **50 graphics checksum entries**, four panic texts with exact uptimes/hashes, and both complete loaded-kext inventories checked.
- `git diff --cached --check` passed. Explicit `.gitattributes` exemptions preserve byte-exact imported source snapshots, patch context, original license texts and hash-verified panic endings; they do not reformat those inputs.

The detailed generated check report is in [evidence/publication-checks.json](../evidence/publication-checks.json); source and configuration checks have their own evidence records.

## New upstream issue draft

[ISSUE-DRAFT.md](ISSUE-DRAFT.md) contains a complete title/body with pinned source, configuration, panic, loaded-kext and comparison links. It asks for targeted page-ownership/lifetime diagnostics and a supported framebuffer/accelerator isolation test. No upstream issue was automatically opened.

The conclusion remains: four accelerated failures at252–340s versus one basic-display control reaching3755s without user-reported freeze. The workload was not quantitatively matched, the exact corrupting component remains unknown, and no fresh binary rebuild or physical retest is claimed by this publication.
