# MIT / Mesa material in `nvk/`

The repository does **not** ship a standalone MIT licence text. The only
explicit MIT statements are inside `sources/nullmoth/nvk/nvk-macos.patch` at
these lines:

- `2462: # SPDX-License-Identifier: MIT`
- `2917: - * SPDX-License-Identifier: MIT`
- `2934: + * Copyright © 2023 Valve Corporation (the lavapipe implementation this follows) — SPDX-License-Identifier: MIT`
- `3975`, `4022`, `4788`, `6316: * SPDX-License-Identifier: MIT`

`README.md:179` says `nvk/`: changes to Mesa (MIT), and `NOTICE` says the NVK
Vulkan driver is Mesa (MIT) with NullMoth changes shipped as patches.

This note does not reproduce the MIT text; obtain it from the upstream Mesa
distribution that the patch applies to (`MESA_BASE` = `17ca6174`). Do not
apply the root PolyForm licence to the Mesa-derived patch, and do not apply
MIT to the NullMoth `plugin/`, `kexts/`, `build/` or `package/` code.

The patch is a diff over Mesa, so the surrounding Mesa source retains Mesa's
own copyright notices and MIT terms; those notices are not all present in the
patch file itself.
