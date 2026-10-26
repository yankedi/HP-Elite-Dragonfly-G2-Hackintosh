# Crash context and source limits

This note summarizes selected local crash evidence without copying raw panic
reports, unified logs, screenshots, or user/session identifiers into the
publication subtree. It is context, not a root-cause analysis.

## What was observed

The selected later crash series covers macOS build `25G83` and includes four
recent panic records: two `pmap_recycle_page` assertions reporting a referenced
page, one zone-allocation assertion reporting an object outside its expected
zone, and one watchdog timeout with no check-ins from `watchdogd`. The captured
records have differing task contexts; the named task is not by itself evidence
of the corruptor. The panic text did not contain the tested NootedGreen Mach-O
UUID, and a usable full panic stackshot was not available for the selected
records. A separate historical WindowServer watchdog record should not be
conflated with these four incidents.

The pmap and zone assertions identify where the kernel detected an invalid
memory-management state; they do not establish which earlier component caused
it. The watchdog record likewise does not identify a graphics-driver cause.
No causal attribution to NootedGreen, HookCase, Apple graphics components, or
another device/driver is made here. The later incidents mean that the bounded
healthy observations and one successful graphics test do not establish
long-term stability.

## Public XNU reference (version caveat)

Apple's TGL graphics-driver implementation is proprietary and no matching
redistributable source is included here. For general context only, public XNU
source at tag [`xnu-12377.121.6`](https://github.com/apple-oss-distributions/xnu/tree/xnu-12377.121.6)
contains the x86-64 `pmap_recycle_page` implementation in
[`osfmk/x86_64/pmap.c`](https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.121.6/osfmk/x86_64/pmap.c)
and the zone allocator panic path in
[`osfmk/kern/zalloc.c`](https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.121.6/osfmk/kern/zalloc.c).
This public source tag reports XNU `12377.121.6`; the target OS evidence
reports XNU `12377.161.14`. It is therefore a related reference, **not an exact
source match** for the tested OS, and cannot identify the cause of these
incidents or prove that the implementation at the target's panic line is
identical.

## Evidence policy

Only the high-level count and assertion categories are summarized above. Raw
panic files, crash-series JSON, boot/session UUIDs, user names, personal paths,
and full logs are deliberately excluded. For the tested artifact's hash,
runtime conditions, and limits, see [`MANIFEST.md`](MANIFEST.md).
