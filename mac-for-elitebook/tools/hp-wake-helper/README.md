# hp-wake-helper (`v20261123-no-blank`)

macOS userspace LaunchDaemon helper (`com.hp.alc285.ampinit`) for the HP Elite Dragonfly G2 (`8716`) / EliteBook 840 G8 on macOS 26.6.2 (`25G83`).

## Responsibilities

1. **Post-wake eDP backlight safety & color-profile refresh**:
   - Registers a `kIOFirstMatchNotification` matcher for `IODisplayWrangler` (avoiding early-boot lookup races where `IOServiceGetMatchingService("IODisplayWrangler")` returned `MACH_PORT_NULL` and left display power callbacks unregistered).
   - Preserves hardware backlight (`bklt`) across display sleep and system sleep (`no-blank`), only recording non-zero `bklt` (`> 600`) to `/private/var/run/hp-saved-bklt` before sleep and unlinking any stale `/private/var/run/hp-wake-blank`.
   - Ignores intermediate `IODisplayWrangler` half-dim states (`wps == 3`) and `0->1->0` dark maintenance ticks.
   - At `+0.15s` and `+0.60s` after wake (`wps >= 3`), refreshes neutral RGB scale (`rgsc`/`ggsc`/`bgsc = 65536`) and `CGDisplayRestoreColorSyncSettings()`, restoring `gSavedBklt` if `bklt` unexpectedly dropped to `<= 600` when pre-sleep `bklt` was non-zero.
   - Recovers stale `/private/var/run/hp-wake-blank` at startup if the display is awake (`wps >= 3`) with `initialBklt <= 600`.
2. **ALC285 speaker amp & audio route initialization**:
   - Invokes `/usr/local/bin/hp-alc285-ampinit.sh` (`--boot` at startup, `--wake-fast` at `willPowerOn+0.2s` / `wake+0.3s` / `wake+1.5s`, and `--wake` at `wake+3.5s`).
   - Registers a CoreAudio `kAudioDevicePropertyDeviceIsRunningSomewhere` listener on the built-in speaker device (`1F,3,0,1,3`) for fast `/usr/local/bin/alc-verb` amp unlock on stream start.
3. **Wi-Fi fast-scan kickstart**:
   - Triggers `CWInterface scanForNetworksWithName:nil` at `wake+1.0s` and `wake+2.8s` if not yet associated.

## Why legacy blanking caused `bklt=0` lockups on short-lid / `R32-PCFIX63-EDPWAKE`

Prior `hp-wake-helper` builds checked for the legacy `R32-PCFIX36` IORegistry property `ngreen-wake-plane-rgb-fix` and intentionally zeroed the panel backlight during sleep by creating `/private/var/run/hp-wake-blank` and writing `bklt = 0`:

1. **Early-boot registration race**: A one-shot `IOServiceGetMatchingService("IODisplayWrangler")` call at early boot returned `MACH_PORT_NULL` (`wps = -1`), leaving `wranglerInterestCallback` unregistered.
2. **Removed legacy `PCFIX36` property on `PCFIX63`**: `NootedGreen R32-PCFIX63-EDPWAKE` (`-ngreenfbdpms` native eDP sleep/wake) no longer publishes `ngreen-wake-plane-rgb-fix`, so `hasKernelWakeColorFix()` returned `false` and `kIOMessageSystemWillSleep` created `/private/var/run/hp-wake-blank = 1` and forced `bklt = 890 -> 0`.
3. **Wake deadlock & short-lid asymmetry**: `kIOMessageSystemWillPowerOn` deadlocked on `gDisplayBlankActive == 0` and `kIOMessageSystemHasPoweredOn` never cleared `hp-wake-blank`. Long sleeps (`> 5 min` `AppleKeyStore` lock timeout) were masked because `loginwindow` `BrightenDisplayIfNeeded` forced `0.0625` (`bklt = 4095`), whereas a short `~6.5 s` lid close stayed within `AppleKeyStore` `graceperiod -> unlocked` (`screenIsLocked = 0` under `darkwakelinger`) so `loginwindow` did not intervene, `hp-bridge` was blocked by `hp-wake-blank`, and `corebrightnessd` read `0.000000` and left `bklt` trapped at `0`.

`v20261123-no-blank` removes the `PCFIX36` blanking mechanism completely and lets `R32-PCFIX63-EDPWAKE` + `TGLIshAls` drive backlight cleanly.

## Build & Sign

### Cross-compile in Nix Flake devShell (`nix develop`)

```sh
clang \
  -target x86_64-apple-macos15.0 \
  -isysroot "$SDKROOT" \
  -fuse-ld=lld \
  --ld-path="$(command -v ld64.lld)" \
  -O2 -fobjc-arc -Wall -Wextra \
  -framework Foundation \
  -framework CoreWLAN \
  -framework CoreAudio \
  -framework CoreGraphics \
  -framework IOKit \
  -framework CoreFoundation \
  hp-wake-helper.m -o hp-wake-helper
rcodesign sign hp-wake-helper
```

### Native macOS build

```sh
clang \
  -O2 -fobjc-arc -Wall -Wextra \
  -framework Foundation \
  -framework CoreWLAN \
  -framework CoreAudio \
  -framework CoreGraphics \
  -framework IOKit \
  -framework CoreFoundation \
  hp-wake-helper.m -o hp-wake-helper
codesign -s - hp-wake-helper
```

## Recorded Phase 65 Artifact Identity

- Source (`hp-wake-helper.m`): `23,921` bytes, SHA-256 `8053cd08112c69a3df69231666b4279a0a83a6add5254db2969b8988a1ba5e9e`
- Built binary (`v20261123-no-blank`, `0` compiler warnings, ad-hoc signed): `42,176` bytes, SHA-256 `d00addb6098fe521ae81e17c01f04856d2eeb4a67e453e83714049ffd09113e9`
