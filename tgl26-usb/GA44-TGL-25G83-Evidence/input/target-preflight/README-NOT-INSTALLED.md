# target-preflight

This directory is intentionally empty of TGL binaries.

The target 25G83 does not have `AppleIntelTGLGraphics*` installed. The
GA4.4 checker therefore reports these entries as `NOT_INSTALLED_ON_TARGET`
instead of treating absence as a framework-evidence failure.

If the target later gets a TGL bundle, populate the paths required by
`configs/25g83-evidence.json`:

```text
AppleIntelTGLGraphics.kext/Contents/{Info.plist,version.plist,MacOS/AppleIntelTGLGraphics}
AppleIntelTGLGraphicsFramebuffer.kext/Contents/{Info.plist,version.plist,MacOS/AppleIntelTGLGraphicsFramebuffer}
AppleIntelTGLGraphicsMTLDriver.bundle/Contents/{Info.plist,MacOS/AppleIntelTGLGraphicsMTLDriver}
```

Do not copy donor 16.0.32 files into this directory and call them target
files. Record their source class explicitly.
