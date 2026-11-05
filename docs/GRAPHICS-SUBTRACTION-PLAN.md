# Graphics repair subtraction experiments

**Latest strategy correction:** the sampled AUX/pool/RESFREE matrix below is
historical preparation, not the next agreed test series. The active method is
complete-set coarse-to-fine subtraction: inventory all actual runtime graphics
repairs and dependencies, partition the eligible set into two complementary
large groups with explicit coverage, independently remove each group from the
same full reference, then recursively refine based on reproducible outcomes.
The [first functional partition](GRAPHICS-COARSE-PARTITION.md) is now defined:
L covers display/platform integration; R covers rendering/resources/user-space
graphics. File/config coverage and dependencies are recorded, including fixed
compatibility and unresolved binary mapping. The two OFF artifacts have not
been implemented or booted. Preserve explicit
unknown/fixed components; do not infer one culprit when both trials fail, both
avoid the target failure, or either cannot reach a comparable working state.
Previously built additional candidates remain preserved, undelivered artifacts.

**USB housekeeping, 2026-10-29:** at the user's request, old experimental images
and root-level experiment handouts were privately archived with byte/hash
verification and removed from the locally attached USB. The post-boot F image
was retained byte-identically under
`ISO/HP-Tahoe-GA419-Bluetooth-Peripherals.img`; its entire OC tree matches the
delivered GA419/GA416 reference. Installer/recovery and unrelated files remain.
A/B OC trees also match their delivered stages; their newly recovered OC logs
end at `EXITBS:START` and do not establish loaded NG UUIDs or an independent A
panic. Historical paths below describe the original deliveries.

## Historical sampled-series scope and reference

The candidate definitions, fixed-component rules and A/B protocol below describe
the earlier sampled series. The linked coarse partition supersedes that protocol
for future preparation; existing observations and artifact hashes remain valid.

The 2026-10-29 series starts from the **historically loaded GA419 EFI and GA416
cumulative NootedGreen**, rather than adding patches to new upstream source.
The objective is to identify a repair or interaction associated with the
accelerated pmap panics. Existing evidence establishes a graphics-stack
association, not the first corrupting operation.

- Source: `f93dc2447631553d2dcc2f6d5a8a495acf57990c`.
- Executable SHA-256: `e44ef32745cad51bd13a2006557f8d2076f96759a0afce867547a8466ab6dbbb`.
- F is the cumulative version that reached an accelerated desktop but was
  unstable; it is not a stable control.
- Keep OS, installed TGL/HookCase/Metal components, HP ACPI/device configuration,
  topology and original boot arguments fixed.

## First batch: identical binaries, existing switches

| Candidate | Sole configuration delta from F | Meaning |
| --- | --- | --- |
| F-FULL | None | Exact archived GA419 OC files and cumulative GA416 binary |
| A-AUX-OFF | Append `-ngreenccs` | Skip guarded NOAUX application; retain NOCCS3 |
| B-POOL-OFF | Append `-ngreennopoolfix` | Disable pool enlargement and 64-byte padding; retain wrappers/logging |

Each candidate starts independently from F. Every kext, OpenCore executable,
ACPI table and other OC file is byte-identical. A and B change only boot-args
in `config.plist`; F uses the original config bytes. No new upstream EU/L3 or
test-marker arguments are added. Existing boot-args replacement behavior and
`WriteFlash=false` are preserved.

Source audit:

- [kern_gen11.cpp](../graphics/src/NootedGreen/kern_gen11.cpp) has one
  `checkKernelArgument("-ngreenccs")` call, at line 2308. It controls NOAUX,
  not NOCCS3. AUX means auxiliary compression surface state, **not DisplayPort
  AUX**. The old "experiment INVALID" disable message refers to historical
  NOAUX-enabled acceptance; an intentional OFF trial expects that message when
  the HP gate passes.
- [kern_green.cpp](../graphics/src/NootedGreen/kern_green.cpp) has two
  `-ngreennopoolfix` checks, in `wrapPoolInit` and `wrapPoolGetPtr`. B is a
  two-operation group; subsequent finer-grained comparison must distinguish
  sizing from alignment if this group is implicated.

## Compatibility repairs retained after evidence review

- **R2 f13b:** port-probe pure-virtual-call bypass.
- **R3 scratch:** page-rounded allocation following a scratch+0xd000 fault.
- **R4 NOCCS3:** compatibility bypass for `resolve_ccs+0xc7`; the preceding
  R3 trial recorded that write fault at approximately 64.180 seconds.
- **PLANES2:** IOSurface plane-count ABI +0xb0 to +0x98 repair. Historical
  evidence includes a divide-by-zero panic and a passing targeted retest after
  enabling it. Retain it in the first batch.
- **R5/L3:** native TGL topology and L3=6 fallback.

These are fixed initially, not permanently exonerated. If implicated, compare
a compatible replacement or narrower implementation rather than blindly
returning to a known incompatible path. HookCase and other installed component
changes remain candidates for later work; EFI changes cannot restore them or
kernel collections.

## Trial and decision protocol

1. Boot F; verify OS/build, boot identity, effective args, loaded driver UUIDs,
   topology and accelerator attachment. Capture full off-machine logs without
   predicates or sampling. Record desktop arrival and boot uptime.
2. Test A using the same power source, desktop operation sequence and workload.
   Verify intended OFF behavior and retained repairs where runtime evidence is
   available. Decide the next trial before booting B.
3. Screen for at least 15 minutes; extend promising candidates to at least
   60 minutes. Neither window establishes stability.
4. Startup failure or lost acceleration is not a cure or valid comparison for
   the original pmap fault. An unrelated early panic is a separate regression.
   Record observed freezes separately from panic text; SSH loss alone is not
   proof of panic.
5. Confirm a candidate with F/OFF/F/OFF under comparable conditions. If isolated
   subtraction is inconclusive, test interactions such as AUX+POOL OFF, then
   narrow the implementation. Expand beyond these groups when required.

## Preparation evidence

All three images passed OpenCore 1.0.8 validation, exact semantic config diff,
enabled-kext file checks, complete FAT-file readback, read-only FAT checks,
partition/header checks and independent ad-hoc signature integrity verification.
Executable, Info.plist and CodeResources corruption controls were rejected.
Retained source matched historical inventory; published files matched immutable
commit objects. No rebuild was needed.

| Image | SHA-256 before boot |
| --- | --- |
| `HP-GFX-SUB-F-FULL.img` | `b6eca006c9d9f44933ec6ff8548424deb33b3d5e2615d2aa9eee5df102da4a9d` |
| `HP-GFX-SUB-A-AUX-OFF.img` | `93940f507f1662e3948c851d5dbbbaaa8785a42a1d69606d167cca784b3e0d82` |
| `HP-GFX-SUB-B-POOL-OFF.img` | `ec22b4578a743bafb677875b5a7823fb3f4e476cd24e597e71c6fd11cf8440fa` |

These are artifact-integrity checks, not hardware acceptance. Image hashes can
change when OpenCore writes logs. Private identities, images and raw evidence
remain outside the public tree. Subsequent F and user-reported A/B observations
are recorded below.

All three were subsequently copied to the test USB's `ISO` directory with full
readback SHA-256 and size verification.

### F-FULL initial runtime observation

The user subsequently reported reaching the desktop. A read-only same-boot
snapshot on 25G83 confirmed the original NootedGreen UUID
`4C4C44D4-5555-3144-A13A-DFB86EFBE513`, TGL framebuffer/accelerator and HookCase
loaded, and IntelAccelerator/command-queue services present. Full dmesg showed
NOAUX gate/preflight/postflight success, NOCCS3 and PLANES2 applied, 80 EU/L3=6,
R6 enabled and R3 scratch size 0xe000. Kernel-visible args omit `slide=0` from
the configured list; the other F arguments match and both OFF flags are absent.
The unfiltered stream handshake and a real event were verified. Nine snapshot
commands succeeded and 187 installed graphics files were hashed privately.
This is initial runtime identity/patch-hit evidence, **not stability or a
completed observation window**. Early collection adds workload and must be
matched in the OFF trial; no claim of a GPU workload benchmark is made.

### F-FULL ended observation

The full stream and separate health connection subsequently ended with SSH
server timeouts. All 4,333,919,070 received raw bytes (354,212,059 gzip bytes)
passed independent full decompression/CRC, length and both SHA-256 checks.
There were 4,143,141 complete JSON events and no unparsed partial lines. The
last event was at uptime 2068.732 s (34 min 29 s); 30 health records retained
the same boot. This is **not a stable 34-minute result**:

- Explicit kernel GPU-restart Fault messages began at uptime 1404.224 s
  (23 min 24 s), with IOAccel hardware-error messages.
- `corebrightnessd` WindowServer initialization failures began at uptime
  1708.938 s (28 min 29 s) and continued through the final event.
- No full panic text was recovered. Absence of selected panic/sleep/shutdown
  keywords in the received stream does not establish the reason for lost SSH.
  Follow-up macOS and Linux connections timed out. No unattended power action
  or alternate trial was performed.

Earlier XProtect file-open messages containing `ReportGPURestart` are not GPU
faults; counts of actual restart messages are also not counts of separate
crashes. The outcome is graphics errors followed by loss of connection,
**not yet a confirmed recurrence of the historical pmap panic**. The next
comparable OFF observation should cover at least 60 minutes: a 15-minute
screen would miss this F trial's explicit GPU-failure onset. Preserve any
recoverable panic and on-site observation before interpreting the next trial.

### Subsequent A/B reports and recovered panic

The user later reported independently testing A and B, both eventually freezing,
then booting Linux. No live A/B event stream was collected. Read-only firmware
recovery preserved 375 variables with remote length/SHA checks. Six contiguous
numeric panic chunks decoded and re-encoded byte-for-byte with the existing
packA decoder; the nonnumeric metadata variable was retained separately.

The recovered text reports a **WindowServer userspace watchdog timeout** after
120 seconds without a successful checkin, at uptime **752.416 seconds**. It
includes `-ngreennopoolfix` and no `-ngreenccs`, consistent with B's intended
configuration on 25G83. Text SHA-256:
`0062ed130fc9bf8d0383471124dda00700f1b77425720471e9fd6dd3b4390458`.

This is not the historical pmap signature. The panic does not include loaded
NootedGreen UUID or patch-hit evidence, so the arguments alone are not complete
runtime identity verification. A currently has only the user's freeze report;
no separate A panic was recovered. These observations cannot exonerate AUX or
pool changes for the original pmap fault, nor establish that A and B share one
failure mechanism. The test USB was not enumerated at collection time, so its
new per-image OpenCore logs remain to be recovered.

## Expanded matrix after A/B observations

The watchdog signature is also a previously known failure class according to
the user. More subtraction tests are needed; the two freeze reports do not
exclude AUX/pool involvement in the original pmap fault or interactions.

The next independent dimension is **RESFREE**: the common accelerator route
hooks `IGAccelResource::free` and its implementation has no native-TGL early
return. `-ngreennoresfree` disables pre-free table/pointer neutralization while
retaining the original free call. Its implementation is at
`kern_gen11.cpp:6967–6990`, with the sole argument check at6970. This is a
resource-lifetime hypothesis, not a finding of culpability. Its original
comment also describes a kfree panic, which may recur when disabled.

| Candidate | Disabled repair(s) | Preparation |
| --- | --- | --- |
| F-FULL | None | Existing reference |
| A-AUX-OFF | AUX | Existing single-factor trial |
| B-POOL-OFF | pool enlargement + padding | Existing single-factor trial |
| C-RESFREE-OFF | RESFREE | New |
| D-AUX-POOL-OFF | AUX + pool | New |
| E-AUX-RESFREE-OFF | AUX + RESFREE | New |
| G-POOL-RESFREE-OFF | pool + RESFREE | New |
| H-ALL3-OFF | AUX + pool + RESFREE | New |

This is the full eight-combination matrix for three dimensions, not an
exhaustive enumeration of all graphics modifications. All five new images were
built from the exact original signed driver and archived configuration, changing
only boot arguments. The longest list is227bytes. Source/signature audits,
negative controls, exact config diff, OC validation, FAT/partition/header checks
and full readback passed. USB delivery and runtime trials are pending.

Source review also excluded misleading no-op tests: PAGEON/PAGESYNC/CSB/POSH and
NOORPHAN routes require `-ngreenxefix`, absent in the original F configuration;
native-TGL IDLEBOUND/GTFREQ return directly to originals, and xeFixEnabled()
explicitly returns false on real TGL. Appending their disable flags would not
constitute subtraction of active repairs. HP startup/ABI compatibility repairs
remain fixed, while other active hooks and system components remain later
candidates. Prioritize C, then D, and choose E/G/H from actual outcomes; retain
separate classifications for pmap, watchdog, other panic, GPU error and freeze.

Repository checks on 2026-10-29 passed: `python3 scripts/check-publication.py`
(1328 public-tree files), `make -C mac-for-elitebook check`, and
`git diff --check`. The retained original engineering workspace's `make check`
and diff whitespace check also passed. These checks are not hardware tests.

## Superseded clean-upstream trial

The clean upstream BASE was reported stuck at verbose boot. Read-only collection
recovered an OpenCore log with `Prelinked injection NootedGreen.kext ... - Invalid
Parameter`. Its config and executable matched delivered hashes. This establishes
an injection failure, not that removing a particular HP patch caused the freeze.
The log does not establish loaded driver identity or a new pmap panic.
The firmware capture contained only nonnumeric `PanicInfo000K`, not a numeric
panic-text sequence. The photo is a conversation observation, not an archived
local original. Raw evidence is private. The old clean-upstream-plus-single-group
images are superseded for this series and preserved as historical artifacts.
