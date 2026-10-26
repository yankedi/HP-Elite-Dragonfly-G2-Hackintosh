# Suggested title

Native Tiger Lake 9A49: Managed texture GPU copy is correct, but getBytes is corrupted after resolveCCS reports success

---

## Summary

I am investigating desktop graphics corruption on a **genuine Tiger Lake** HP laptop. A single offscreen Metal test now gives a useful, independently verified distinction: **the GPU texture-to-buffer copy matches the expected image exactly, while CPU `getBytes` from the same Managed render target corrupts every pixel**, even though the normal `resolveCCS(..., wait=1)` call returns success.

This is a **locally modified HP port**, not a clean-upstream reproduction. In particular, my build extends **XE-NOCCS3 to native TGL on Tahoe**. I am reporting that modification explicitly because it may be central to the result.

## Hardware / software

- HP Elite Dragonfly G2, Intel Core i5-1135G7.
- Genuine Iris Xe-LP **8086:9A49**, 80 EU; observed topology: 1 slice / 10 subslices / 5 dispatchers. This is not an ADL/RPL GPU spoofed as TGL.
- macOS **26.6.2, build 25G83**, Darwin 25.6.0.
- Apple TGL user-mode driver **16.0.32**, with this project's compiler/adapter/libxedrv stack retained.
- Upstream source base: **`6a1afb337d1fb1ff07ca032b5c1868fe2bd005ef`**, plus local HP changes, internally named “R6”.
- Important local changes: native-TGL/Tahoe device/compatibility adaptations, XE-FMT, native-TGL/Tahoe **NOCCS3**, and command-pool allocation/padding fixes. This is not an exhaustive patch list; I can provide the exact source diff.
- The local pool expansion was already active during this capture. It did not eliminate the corruption.
- NOAUX, NODEPTH, RCPOLICY and BLITALIGN remain outside the native branch in this build; PLANES2 is disabled, and `-ngreenxefix` / PAGESYNC is not enabled.
- The newer **XE-BLITFIX / GPUREC v2 commit `df7ab78` has not been installed or tested** on this machine.

## One completed diagnostic capture

Only one case was executed in this boot. I am not claiming repeatability across multiple runs yet.

- Source: `R8Unorm`, **257×65**, Shared / ShaderRead, input row pitch **512**.
- Source byte pattern: `(13*x + 29*y) & 255`.
- Target: `RGBA8Unorm`, **Managed / RenderTarget**, single sample/mip/slice, no explicitly supplied IOSurface.
- Fullscreen triangle, nearest sampling; expected output `(R, 0, 0, 255)`.
- `allowGPUOptimizedContents = NO` was requested. I do **not** interpret that request as proof that compression was disabled.
- One explicit command buffer, preserving this order:

```text
render → synchronizeResource(target) → texture-to-Shared-buffer copy
→ waitUntilCompleted
→ deep-copy and save GPU readback bytes
→ target.getBytes into a separate CPU allocation
```

The Shared output buffer was 332800 bytes, preserving the earlier workload's allocation size. Only **83200 bytes** were snapshotted at row pitch **1280**, of which **66820 bytes** are active pixels. Row padding was excluded from comparisons.

Command buffer status was **Completed (4)**, error nil; the wait and completion callback both completed. GPU bytes were frozen and written before CPU `getBytes`. CPU, GPU and expected files use independent allocations and files.

An independent Python verifier on Linux reconstructed the expected image and compared every active byte:

| Comparison | Different active bytes | Bad pixels / 16705 |
|---|---:|---:|
| GPU copy vs expected | **0** | **0** |
| CPU getBytes vs expected | **47639** | **16705** |
| CPU getBytes vs GPU copy | **47639** | **16705** |

This is a **valid capture with failing CPU pixels**, not an incomplete/failed command buffer. The GPU result is still a copy/readback proxy, not an independent dump of raw GPU storage.

## Normal CPU access chain observed

A process-local observer recorded the normal calls, without initiating extra resolves or changing resource flags. All four method ABIs were checked against the installed GPUBundles driver before hook installation. The old observer's incorrect pointer-return assumption for `lockForCPUAccess` was fixed to the actual 64-bit `Q` ABI.

For the target texture:

```text
getBytes enter
  lockForCPUAccess(readOnly=1, level=0, slice=0)
    resolveCCS(level=0, slice=0, waitForCompletion=1) → 1
  lock → 0x108ac3000
  unlockForCPUAccess(seed=1, readOnly=1) → 1
getBytes exit
```

Observed user-mode fields remained unchanged through this chain:

```text
m_Info+0x108 = 1536
m_Info+0x10c = 1040
m_Info+0x114 = 4
m_Info+0x134 = 3
m_Info+0x16a = 0x0208
m_Info+0x1ac = 0x1206
shared-resource+0x1c = 1
```

These are user-mode observations, **not** a capture of kernel ResourceInfoEntry/AUX state.

## Offline findings and suspected mechanism

The installed GPUBundles MTLDriver is byte-identical to the image used for disassembly (SHA256 `e3242693959408c9cef14140df81ce98ff1e04d5dd83aa9aeaddb463271ac65d`).

1. With these flags, `getBytes` takes **CpuSwizzleBlt**, not the linear row-memcpy branch. The actual table selection is **Tile Y**, masks `X=0x0e0f`, `Y=0x01f0`, `Z=0`, with source pitch **1536**. The caller's linear destination pitch is **1280**; those differing pitches alone do not demonstrate a bug.
2. An offline model was cross-checked against Intel's original `SwizzleOffset` and `CpuSwizzleBlt`: **267280 addresses** and four synthetic full-image reads passed. Nine zero-origin, uncompressed layout/pitch hypotheses all disagree with the real CPU bytes on their defined overlapping regions; unknown backing/padding bytes were not fabricated.
3. A simple spatial permutation of valid RGBA pixels is insufficient: CPU data has **7415 nonzero G values, 6987 nonzero B values, and 16573 alpha values other than 255**, although the expected G/B/A are constant.
4. The local NOCCS3 patch makes `IntelAccelerator::submitCCSResolve` return immediately. In the donor resource-layer caller, the call at `0x73e99` is followed by dirty-bit clearing at `0x73eb1` and clearing `entry+0x64` at `0x73eb6`, without checking the accelerator return; the upper layer returns true at `0x73f0f`.

**Working hypothesis:** the GPU copy path can interpret the resource correctly, while CPU access gets an unresolved/compressed representation and only detiles it after the resolve chain reports success. The NOCCS3 skip could leave software state inconsistent with actual content.

However, I have **not** dynamically correlated this texture with that exact kernel resource/resolve branch, captured its AUX/dirty state, or decoded a compression format from its backing. Wrong backing, offsets or CPU visibility remain alternatives. This is not yet a proven root cause or a fix.

## Related upstream issues

- **#3:** similar missing/stale graphics, but its non-TGL hardcoded 96-EU topology diagnosis does not directly apply to this genuine TGL case.
- **#6 / XE-BLITFIX:** potentially relevant to other desktop IOSurface corruption. This small test does not match the stated large-copy/odd-pitch trigger: active copy size is 66820 bytes, observed upload/readback/swizzle pitches are 64-byte aligned, and the target is not explicitly IOSurface-backed. The oversized buffer allocation is not the copy area. I have not measured this machine's desktop submitBlit arguments.
- **#2:** later hangs exist here too, but the signature below differs from the dummy-page/compute-stamp backlog described there.

## Secondary observation: later RCS hangs

The capture completed at approximately **07:58, 24 Oct 2026 (UTC+8)**; SSH worked immediately afterward and no new reset report was visible then.

A later read-only check in the same boot found **at least eight new gpuRestart reports** between 10:32 and 11:07. Two inspected reports identify WindowServer/context 5:

| Time | IPEHR | ACTHD | Offset from batch start |
|---|---|---|---|
| 10:32:25 | `0x7a000004` | `0x447517e4` | `+0x7e4` |
| 11:07:46 | `0x7a000004` | `0x453117e4` | `+0x7e4` |

They indicate a recurring RCS PIPE_CONTROL hang family. Active DSS0–4 shader/sampler units are reported done; DSS5 is flagged as unreliable/zero. Compute stamps24–31 have no submitted/returned backlog in either report. The visible ring includes `0x50105021` PIPE_CONTROL words, but the batch contents at ACTHD are missing, so I cannot identify the stuck command's full flags.

I have not established a causal link between these later hangs, the CPU readback failure, and every desktop artifact.

## Questions

1. Is native-TGL/Tahoe NOCCS3 without the non-TGL compression workarounds an unsupported/inconsistent combination, given that CPU access still expects a completed color resolve?
2. Which existing diagnostics would best correlate the user-mode texture/handle with kernel ResourceInfoEntry, compression/dirty state and its actual CPU backing?
3. Does this Tile-Y CPU path match a known unresolved-CCS readback failure, or is a backing/offset incompatibility with Tahoe more likely?

I can provide the diagnostic source, independent verifier, exact local source diff and captured evidence. I can currently retrieve existing logs over SSH, but **cannot presently reboot or test replacement EFI/driver builds**. I am not requesting that an unverified workaround be merged.

---

## Local attachment checklist — omit this section from the submitted issue

Useful attachments, in priority order:

1. `ga412/tools/managed-rt-probe.m`, `trace-managed-cpu.m`, `build-darwin.sh`, `expected-pattern.py`, `verify-pixel-dump.py`.
2. `ga412/reports/R8-LEGACY-PIXEL-VERIFY.json` and `R8-LEGACY-VERIFICATION-RECEIPT.json`.
3. The target's eight `CPU_TRACE_JSON` events and command completion events from `ga412/private/r8-legacy-capture/probe.stderr` / `probe.stdout`.
4. The two representative reset reports under `ga412/private/followup-readonly/` if the maintainer wants the hang comparison.
5. Exact local R6 source diff against upstream `6a1afb337d1fb1ff07ca032b5c1868fe2bd005ef`, especially NOCCS3 native gating and pool changes. Local commit IDs alone are not publicly accessible evidence.

No attachment archive has been created or uploaded by preparing this draft. The archived Apple driver binary is not an issue attachment.
