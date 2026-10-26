Thank you — your NOAUX suggestion works for the Managed RT / CPU readback issue on this native Tiger Lake machine. **However, the desktop rendering artifacts are still present.**

My hardware is an HP Elite Dragonfly G2 with an i5-1135G7 / Iris Xe 80EU (`8086:9A49`), running macOS Tahoe 26.6.2 / `25G83`.

I moved the existing NOAUX block so it also runs on my native-TGL path, kept both arrays `static const uint8_t[]`, and retained NOCCS3. I checked the actual installed 16.0.32 donor: the original pattern occurs exactly once. The new boot confirms:

```text
GA414 NOAUX: preflight first=1 original=1 patched=0 expected=1/0
GA414 NOAUX: postflight original=0 patched=1 verified=1 expected=0/1
XeNG NOAUX: fillSurfaceStateAuxInfo sempre AUX_NONE: aplicado
```

I then ran the **same R8Unorm → RGBA8 Managed RT test once**, using the exact same probe and tracer binaries, shader, dimensions (257×65), command sequence, row pitches, and getBytes parameters. Results below exclude row padding:

| Comparison | Before NOAUX: bad pixels / 16,705 | After NOAUX: bad pixels / 16,705 |
|---|---:|---:|
| GPU copy vs expected | 0 | **0** |
| CPU getBytes vs expected | 16,705 | **0** |
| CPU getBytes vs GPU copy | 16,705 | **0** |

All three comparisons now have **0 differing active bytes**. The command buffer completed successfully (`status=4`, no error), and the independent verifier reports **PIXEL_PASS**. There is no GPU-copy regression.

The desktop still has visible corruption, including damaged areas in the System Settings sidebar, black rectangles, and abnormal stripes/color blocks around the Dock. **These artifacts are visible in the macOS screenshot itself**, which I have attached.

One difference from your suggested combination: native NODEPTH was not enabled in my R6 baseline, so I left it unchanged for this NOAUX-only test. No additional RPL-only patches were enabled.

I did not observe a new gpuRestart or RCS/PIPE_CONTROL hang during the short test window. I have not yet established whether the previous `+0x7e4` hangs improve over a normal-length session, so I am not claiming a stability fix.

**Summary: NOAUX fixes this reproducible CPU readback failure, but it does not resolve the remaining desktop artifacts on my machine.** Given the passing readback test and the attached screenshot, what would you recommend checking next?
