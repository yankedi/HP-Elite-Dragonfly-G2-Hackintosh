# Third-party notices

This tree contains original GA4.4 evidence, analysis, tooling, and a proposed
patch. It does **not** commit Apple binaries.

| Source | Use | License |
|---|---|---|
| `JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe` @ `54d514f…` | NootedGreen fork and GA4.3 analysis baseline | Thou Shalt Not Profit License 1.0 |
| `sgiammori/NootedGreen` @ `95f8189…` | 16.0.32 donor binaries and source baseline | Thou Shalt Not Profit License 1.0 |
| `m4j2rpf766-crypto/IntelIGPU-Tahoe` @ `9baa4bb…` | 25G83 ABI cross-reference only | GPL-3.0 |

Apple 25G83 system files were read from the user's target machine under the
explicit read-only SSH authorization. They are stored only under
`input/tahoe-frameworks/` (Git-ignored) with SHA-256 in
`evidence/tahoe-frameworks-SHA256SUMS`. They are not redistributed.

The GA4.3 tool was inherited and extended for optional/absent target bundles.
Its patch definitions remain attributed to the GA4.3 audit.
