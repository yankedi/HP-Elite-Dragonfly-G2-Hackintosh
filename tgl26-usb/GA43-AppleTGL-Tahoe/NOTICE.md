# Third-party notices

This repository contains only original analysis, configuration, tooling, and
logs. Upstream sources are cloned into `inputs/upstream/` and are intentionally
excluded from Git.

| Source | Commit | License |
|---|---|---|
| `JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe` | `54d514f079bad088eb2002eb931686216f141fc5` | Thou Shalt Not Profit License 1.0 |
| `sgiammori/NootedGreen` | `95f81898be65cb9f7b3d370ca78054be4cc8a62d` | Thou Shalt Not Profit License 1.0 |
| `m4j2rpf766-crypto/IntelIGPU-Tahoe` | `9baa4bbe36c4a0085efac41d07feb420f841ac6a` | GPL-3.0 (reference only; no code copied) |

The NootedGreen tree contains a vendor `sle_Internal/` donor set of Apple
GPUDriversIntel **16.0.32** binaries. Those files were obtained as part of the
pinned public repository, not by a separate Apple download. They are Apple
proprietary artifacts: this repository records only their hashes and does not
copy or redistribute them. Their presence is input data for static analysis,
not a license grant.

All conclusions in `reports/` distinguish upstream claims, source inspection,
local CPU tests, and target-system facts that remain unknown. No upstream
`install.sh` or deployment script was executed.
