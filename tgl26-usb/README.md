# `tgl26-usb`: curated research and code archive

This subtree is a **public-oriented archival copy** of selected Tiger Lake graphics, driver-integration, and HP Elite Dragonfly G2 research from the source worktree. It is not an installer, a supported driver distribution, or a complete reproduction of the private working tree. It is organized in experiment order; retained reports may include more precise timestamps.

For the current repository-level status and evidence, see [hardware/support status](../docs/STATUS.md), [graphics stability](../docs/GRAPHICS-STABILITY.md), and the [repository guide](../docs/REPOSITORY.md). Licensing notes are in [`../LICENSING.md`](../LICENSING.md). The full final GA416 NootedGreen source chain is maintained separately in [`../graphics/`](../graphics/README.md); it is intentionally not duplicated here.

## Chronology and retained material

| Order | Archive area | Main contents and status |
| --- | --- | --- |
| 1 | [`GA32-ISA-Lab/`](GA32-ISA-Lab/) | Tiger Lake command-stream/ISA analysis, decoder tests, and hang reports. `tools/batch_decode.py` is retained as project-authored code; raw capture input is not included and must be supplied explicitly. |
| 2 | [`GA33-research/`](GA33-research/) | GA31/GA32 comparison, review diffs, tests, and documented root-cause work. |
| 3 | [`GA34-Offline-Lab/`](GA34-Offline-Lab/) – [`GA37-Engineering-Closure/`](GA37-Engineering-Closure/) | Offline analysis and fault-safety experiments, reversing notes, patches, tests, and reusable record/snapshot-writer work. |
| 4 | [`GA38-Shader-IR-Lab/`](GA38-Shader-IR-Lab/) – [`GA39-Translator-Repair/`](GA39-Translator-Repair/) | Shader/message IR modeling, translator repair, semantic checks, and regression/proof tests. |
| 5 | [`GA40-NullMoth-Intel/`](GA40-NullMoth-Intel/) – [`GA42-Intel-Darwin-Integration/`](GA42-Intel-Darwin-Integration/) | Licensing/reuse analysis and Intel/ANV/i915 Darwin integration research. Large upstream trees, build products, and local tool environments are not vendored. |
| 6 | [`GA43-AppleTGL-Tahoe/`](GA43-AppleTGL-Tahoe/) – [`GA44-TGL-25G83-Evidence/`](GA44-TGL-25G83-Evidence/) | Apple TGL compatibility research, evidence summaries, and selected patches. Reports distinguish static compatibility work from verified runtime behavior. |
| 7 | [`GA45-AppleTGL-Native-Port/`](GA45-AppleTGL-Native-Port/) – [`GA47-JulioNectar-HP-Port/`](GA47-JulioNectar-HP-Port/) | Native-port and integration experiments, selected project code, patches, tests, licensing notices, and hardware-support documentation. |
| 8 | [`GA48-Ventoy-Deployment-Prep/`](GA48-Ventoy-Deployment-Prep/) | A selected, chronological GA410–GA420/GA49 record of deployment preparation, troubleshooting, peripheral research, and test tooling. This is an archival subset, not a runnable deployment bundle. |

The phase/order labels are preserved from the work. They provide the chronology where a complete date ledger was not available; dated reports remain dated in place. The GA32 research refers to the 2026-10-18 investigation, while the latest retained GA48 material reaches 2026-10-27.

## Publication curation and omissions

The source worktree was left untouched. This subtree excludes source-control histories, unmodified vendor snapshots, per-attempt clones, build/cache/toolchain outputs, disk and package archives, EFI/configuration plists containing generated machine identities, raw panic/log/sysdiagnose captures, private receipts, credentials, and Apple/proprietary binary artifacts (including Mach-O, kext, dylib, and EFI outputs). The original GA32 capture and other raw evidence are not present. Project-authored code, tests, patches, recipes, licensing material, and research conclusions were retained selectively.

The GA414/GA416 deployment/source bundles and redundant GA45–GA47 NootedGreen source copies are omitted. Refer to `../graphics/` for the separately curated final source chain. Earlier GA1/GA2/GA31 binary/configuration trees and loose disk images are not included. The standalone `make-experiment.py` is retained as an archival, config-only generator; its earlier platform-specific descriptions are not current HP acceptance results.

## Safety and reproducibility

- Remote helpers no longer contain the original account, host address, SSH-key path, known-hosts file, or sudo-password file path. Where retained, they require caller-provided configuration such as `GA410_SSH_TARGET`, `GA416_SSH_TARGET`, `GA418_SSH_TARGET`, `GA410_SSH_KEY`, `GA410_KNOWN_HOSTS`, and `GA410_SUDO_PASSWORD`. **Do not store credentials in this tree or its history.**
- Several historical deployment or capture helpers are intentionally guarded by explicit target/session configuration, but still contain operations that can collect private diagnostics or alter a target. Read the script and review its paths before any use; no remote host or HP device was accessed while curating this archive.
- Build tools require separately obtained SDKs/toolchains and external source inputs. No driver or binary was built as part of publication. The GA32 decoder needs a separately supplied capture and Mesa genxml input; the capture is not distributed here.
- No claim is made that every preserved script is independently runnable against this pruned snapshot. Some analysis helpers expect private inputs or external dependencies that were intentionally excluded.

## Archive status

Snapshot date: **2026-10-27**. The curated subset contains **1,103 files** with approximately **8.1 MiB** of file content. It retains experimental source and research records rather than a ready-to-install binary release.
