# Target TGL bundles: NOT_INSTALLED_ON_TARGET

Evidence collected read-only from the target macOS 26.6.2 / 25G83 on
2026-10-22 (see `logs/remote/probe-006-sanitized.txt` and
`input/kernel-metadata/`).

## Result

The target **does not contain**:

- `AppleIntelTGLGraphics.kext`
- `AppleIntelTGLGraphicsFramebuffer.kext`
- `AppleIntelTGLGraphicsMTLDriver.bundle`
- `AppleIntelTGLGraphicsVADriver.bundle` / `VAME.bundle`
- `AppleIntelTGLGraphicsGLDriver.bundle`

`kmutil path-for-identifier --bundle-id com.apple.driver.AppleIntelTGLGraphics`
fails. `kmutil find` lists only CFL/ICL/KBL Intel graphics bundles. The system
kernel collection's prelink identifiers contain
`AppleIntelCFLGraphicsFramebuffer`, `AppleIntelICLGraphics`,
`AppleIntelICLLPGraphicsFramebuffer`, `AppleIntelKBLGraphics` and
`AppleIntelKBLGraphicsFramebuffer`, but **no TGL identifier**. The generic
`IntelAccelerator`/`IGAccelTask` symbols present in the kernel collection are
therefore not evidence of a stock TGL driver.

## Stock Intel graphics on target

| Bundle | Version | Role |
|---|---|---|
| `AppleIntelICLGraphics.kext` | 24.5.8 | Gen11 ICL accelerator |
| `AppleIntelICLLPGraphicsFramebuffer.kext` | 24.5.8 | Gen11 ICL-LP framebuffer |
| `AppleIntelICLGraphicsMTLDriver.bundle` | 24.5.8 | Gen11 ICL Metal driver |
| `AppleIntelKBLGraphics*.kext/bundle` | 24.5.8 | Gen9.5 KBL |
| `AppleIntelCFLGraphicsFramebuffer.kext` | 24.5.8 | Gen9.5 CFL framebuffer |
| `IOAcceleratorFamily2.kext` | 487.4.3 | IOAF2 (binary embedded in KC) |
| `AppleIntelGraphicsShared.bundle` | no Info.plist | Newer shared IGC plugin; **no Gen12/TGL support** |

## Compiler consequence

The stock 25G83 `libMTLIGCCompilerPlugin.dylib` is a **new-API** plugin:
it exports `MTLCompilerBuildRequestWithSerializedBitcode` but not the old
`MTLCompilerBuildRequestWithOptions`. Its `libigc.dylib` lists
`gen11`, `gen11lp`, `gen13`, `gen83`, `gen93` — **no `gen12`/`gen12lp`**.
The donor 16.0.32 `libigc.dylib` does list `gen12`, `gen12lp` and `TGLLP`.
Therefore the stock target compiler cannot compile TGL shaders, and the
donor compiler/bridge remains necessary for TGL.

This is a `NEEDS_TARGET_BINARY` result for TGL, not a failure of the stock
framework evidence: the stock frameworks were collected and verified
independently.
