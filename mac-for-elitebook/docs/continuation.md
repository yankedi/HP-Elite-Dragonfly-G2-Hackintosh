# Public continuation and current state

Updated 2026-10-27. This is a concise public handoff, not a transcript. Read this page and [`README.md`](../README.md) before relying on older runbooks.

## Current state

- macOS Tahoe **26.6.2 / 25G83** was installed and reached the desktop. The software-display capture later showed a shutdown sequence; the live OS after that capture was not independently observed. This public copy contains no private runtime capture.
- Four accelerated Tiger Lake graphics boots panicked after approximately 252–340 seconds. A single software-display control retained basic firmware display and ran for approximately 62 minutes 35 seconds without a user-reported freeze. The workload was not controlled or repeated, the final physical power-off was not independently observed, and the observation neither proves causation nor identifies a component.
- Runtime graphics inventory: **80 EUs / 10 subslices**. This is not proof of framebuffer or Xe acceleration.
- User-reported working: Bluetooth, touchpad, battery display, camera, Bluetooth audio input and output.
- Unresolved: built-in HDA audio, built-in DMIC, brightness control, long-term stability, and Xe/Metal acceleration. The first memory corrupter and panic root cause are unknown.

## Evidence and privacy boundary

`../manifests/experiment-history.json` is a high-level index to retained public docs. It does not contain transcripts or private raw captures. Private `.local/` evidence, orchestration history, machine identities, credentials, and original personal paths were excluded. A referenced private artifact not present in this clone is **unavailable**, not verified. No user-specific target endpoint is recorded here.

## Suggested next steps

1. Preserve the existing boot evidence and avoid claiming the software-display run is a causal fix.
2. For future stability comparisons, record configuration, workload, duration, and complete panic evidence without exposing machine identity or raw private logs.
3. Keep framebuffer output, graphics acceleration, and Metal as separate acceptance claims; the hardware runtime count alone is not an acceleration result.
4. Continue peripheral work as separately scoped experiments. Do not treat upstream source compatibility as proof of HP runtime support.

Older preparation and Recovery instructions elsewhere in `docs/` are historical records. Their former “next step” instructions and `.local/` paths are not a current execution queue.
