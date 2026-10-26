# NullMoth licence map (pinned 47f818b)

Source: `sources/nullmoth`, commit `47f818b11cef59acb480210afdf9065fdd44e356`
(tag `v2.4.3`, tree `5c3425d8764ca9fa2217c76bb2b79099128474f5`). This is an
inventory of what the tree says, not legal advice and not a clearance.

## Exact texts archived here

| File | Origin | SHA-256 |
|---|---|---|
| `LICENSE-PolyForm-Noncommercial-1.0.0.txt` | `sources/nullmoth/LICENSE` | `1b5c7a92697863d38fd2779af76732acfb8f521b758781eab057ad966701b0b7` |
| `NOTICE-NullMoth.txt` | `sources/nullmoth/NOTICE` | `d3eb6510e54feef70d510af1ab74e8c3c57b796e5656da6b73e44bd89a07aa48` |
| `LICENSE-LGPL-3.0.txt` | `sources/nullmoth/translator/LICENSE` | `f56039b5ee783a50114de388f95ffe7173001d63c32ed4c00649045eec0cf506` |
| `COPYING-GPL-3.0.txt` | `sources/nullmoth/translator/COPYING` | `bc2d6664f6276fa0a72d57633b3ae68dc7dcb677b71018bf08c8e93e509f1357` |
| `NVIDIA-modeset-header-excerpt.txt` | first 26 lines of `kexts/NVRM/nvidia-modeset-os-interface.h` | `e9de52d9d23e1a3b155fd535e586fa304192be9b90360220214a498e6f7bc0e8` |
| `MIT-MESA-NOTE.md` | inventory note; no MIT text is shipped in the repo | n/a |

The full per-file table is `reference/nullmoth-api-inventory/file-provenance.json`
(639 tracked files, each with SHA-256, SPDX header if any, inferred scope and
confidence).

## Inventory counts (639 tracked files)

| Classification | Files |
|---|---:|
| LGPL-3.0-or-later (`translator/`) | 380 |
| PolyForm Noncommercial 1.0.0, explicit scope/header | 111 |
| PolyForm root default, scope not separately enumerated (`docs/`, `tools/`, root docs) | 107 |
| PolyForm header on reconstructed Apple private ABI (status limited) | 26 |
| `NOASSERTION` (no licence statement) | 9 |
| **CONFLICT** PolyForm SPDX vs NVIDIA MIT-style text | 2 |
| PolyForm + libdrm UAPI facts (MIT) | 1 |
| PolyForm + generated Linux PCI ID data (MIT) | 1 |
| MIT Mesa-derived patch (`nvk/nvk-macos.patch`) | 1 |
| GPL-3.0 text (`translator/COPYING`) | 1 |

Only **one** tracked file is classified as MIT code. The repository as a
whole is **not** MIT. The counts are generated from
`reference/nullmoth-api-inventory/file-provenance.json`.

## Scope table

| Scope | Stated licence | Evidence | Reuse position |
|---|---|---|---|
| `plugin/`, `kexts/`, `build/`, `package/` | PolyForm Noncommercial 1.0.0 | `README.md:172-180`; 85 files carry `SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0` (24 plugin + 61 kexts) | Source-available, **noncommercial only**. Modification and redistribution are allowed only for permitted (noncommercial) purposes, with the licence and Required Notice. |
| `translator/` | LGPL-3.0-or-later | `translator/translator/Cargo.toml` `license = "LGPL-3.0-or-later"`, `translator/README.md`, `NOTICE`; `translator/LICENSE` is the LGPL text | Weak copyleft. Modifying the library triggers LGPL source/relink obligations. It is based on `metal2vulkan` (Anees Iqbal). |
| `nvk/` changes | MIT (Mesa) | `nvk/nvk-macos.patch` contains MIT SPDX lines; `README.md:179`, `NOTICE`; patch applies to Mesa `17ca6174` | MIT for the patch/Mesa-derived material. No full MIT text is shipped in this tree. |
| NVIDIA r610 kernel modules | MIT / GPL-2.0 (upstream) | `NOTICE`; `kexts/NVRM` builds against external `open-gpu-kernel-modules` tag `610.57.04` | Not vendored as a whole. Per-file lineage of the NullMoth port is not documented; do not assume the entire `kexts/NVRM` port is MIT/GPL. |
| GSP firmware | NVIDIA redistributable firmware licence | `NOTICE`, `README.md:180` | Not in this repository; installed from `/Users/Shared/nvfw/nvidia/610.57.04`. |

## PolyForm Noncommercial 1.0.0: operative points

From the archived text (not a substitute for reading it):

- **Permitted purpose = any noncommercial purpose.** Personal research,
  experiment, testing, study and hobby use are expressly permitted; charitable,
  educational, public-research, public-safety/health, environmental and
  government organisations are permitted regardless of funding.
- **Commercial use is not granted.** Selling the software or using it to make
  money is outside the licence. A company's use is not automatically
  "noncommercial".
- Distribution is allowed only with the licence terms/URL and the
  `Required Notice:` lines. This tree supplies:
  `Required Notice: Copyright (c) 2026 NullMoth Systems (https://nullmothsystems.com)`.
- Changes and new works are allowed only for a permitted purpose. There is no
  sublicensing or transfer; patent licence terminates on a patent challenge;
  a first violation can be cured within 32 days.
- Extracting a header or a function into another project creates a changed/new
  work. It does **not** become MIT, Apache or public domain. The PolyForm terms
  and Required Notice travel with it.
- PolyForm is not an OSI open-source licence. Calling the plugin "open source"
  (as the README does) does not make it OSI-approved or commercially reusable.

## Translator (LGPL-3.0-or-later)

- The Rust crate declares LGPL-3.0-or-later. Most source files have no
  per-file SPDX header; the ancestor `translator/` declaration is the evidence.
- `translator/COPYING` is the GPL-3.0 text shipped alongside the LGPL text. It
  is not a second grant for the translator code.
- If GA40 links a **modified** translator into a combined work, LGPL section 4
  requires the Minimal Corresponding Source and the relink/installation
  information. Using an unmodified shared library is the simpler path.
- Translation output (SPIR-V) is not itself a copy of the translator library,
  but that conclusion is a technical/legal judgement that has not been tested
  here. Do not represent it as cleared.
- The translator calls external `llvm-dis` and `spirv-val`; their licences are
  separate (LLVM Apache-2.0-with-LLVM-exception; SPIRV-Tools Apache-2.0).

## Conflicts and gaps found

1. **NVIDIA header conflict.** `kexts/NVRM/nvidia-modeset-os-interface.h` and
   `kexts/NVRMFB/nvidia-modeset-os-interface.h` say
   `SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0` while retaining
   `Copyright (c) 2015 NVIDIA CORPORATION` and the MIT-style permission grant
   ("permission is hereby granted, free of charge ... without restriction,
   including ... sell"). The two statements cannot both be the whole answer.
   Do not redistribute these files on the SPDX line alone. The excerpt is
   archived for review; resolution requires the rightsholder.
2. **`docs/` and `tools/` are not enumerated** in the README licence section.
   The repository-root `LICENSE` is the only general statement. The inventory
   labels these as "root default; not separately enumerated" (ambiguous), not
   as verified PolyForm.
3. **`.github/` and `.gitignore`** have no licence statement. Inventory:
   `NOASSERTION`.
4. **`nvk/2.0.5/README.md` and `nvk/MESA_BASE`** are not covered by the MIT
   sentence with the same clarity as the patch. `MESA_BASE` is a bare commit
   id; the README is project prose. Inventory: `NOASSERTION`/unknown.
5. **Reconstructed Apple ABI.** `kexts/NVRM/accel/iofam/*` and
   `kexts/NVRM/accel/re/*` are reconstructed IOGraphicsFamily/
   IOAcceleratorFamily2 interfaces. Apple ships no header or licence for them.
   The files carry a NullMoth PolyForm header, but the copyright status of the
   interface facts is untested. Do not describe them as Apple-licensed.
6. **Generated data.** `kexts/NMIntelFB/display_ids.inc` is generated from
   Linux `include/drm/intel/pciids.h` (MIT); `kexts/NMDRM/nmdrm.cpp` records
   libdrm UAPI facts (MIT). Those upstream facts do not relicense the
   NullMoth files around them.
7. **NVIDIA code is not vendored wholesale.** `NOTICE` says the build uses
   NVIDIA's r610 modules; the repository contains porting glue and a copied
   modeset header, not the full NVIDIA tree. The GSP firmware and
    `air-opt`, `NVIDIAShared.bundle` and `air-runtime/libLLVM.dylib` are external
    payloads, not in this tree and not archived here. Their licences are
    **Unknown / not established**; translator LGPL does not cover them.
    Do not redistribute these payloads or claim licence clearance from this
    inventory. Firmware similarly requires its own verified terms.

## Reuse rules for GA40

- Do not copy `plugin/`, `kexts/`, `build/` or `package/` code into a
  commercially distributed product.
- A noncommercial research extraction of the pure-C headers listed in
  `reports/REUSE-MATRIX.md` must carry the PolyForm text, the Required Notice
  and a clear "modified/ extracted from NullMoth 47f818b" statement.
- The translator can be used as an LGPL shared library; if modified, publish
  its corresponding source and permit relinking.
- Never relicense NullMoth code as MIT/Apache/BSD. Never describe the whole
  repository as MIT because `nvk/` is MIT.
- Treat all `NOASSERTION`, `ambiguous`, `limited` and `CONFLICT` rows as
  unresolved, not as permission.
