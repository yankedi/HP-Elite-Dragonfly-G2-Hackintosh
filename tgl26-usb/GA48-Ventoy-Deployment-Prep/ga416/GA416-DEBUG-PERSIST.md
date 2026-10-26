# GA416 Debug persistence retry — 2026-10-25

User manually rebooted and requested retrying `persist:debug`. Current boot
`REDACTED-MACHINE-ID`, release kernel; reported boot time 20:35:59 +0800.

## Verified outcome

- Commands run under sudo; an independent identity readback confirms **uid=0, euid=0**.
- Both combined `level:debug,persist:debug,stream:live` and isolated `persist:debug`
  at system scope return zero but print
  `Ignoring some flags 0x310000 because they are process/subsystem only`.
  Readback remains global Level=debug, Persist=default, Stream=live.
- This build's `log help config` lists system-wide persist support, contradicting
  its observed behavior. The precise internal reason is not established; there
  is no evidence that an interactive privacy authorization would resolve it.
- Process scope works. Applied `level:debug,persist:debug,stream:live` to every
  PID in one saved process snapshot, saving each before/enable/after response.
  **504 attempted, 477 independently read back Level=debug, Persist=debug,
  Stream=live**. Other 27 include disabled logging, unavailable modes, exited
  processes and zombies. A zero command exit alone was not counted as success.
- Later readback again confirms WindowServer PID197 and watchdogd PID117
  retain all three settings. `--process 0` reports PID not found, so kernel
  process persistence was not configured by this method.
- These are overrides for the observed processes, not verified coverage for
  subsequently launched/restarted processes or a future boot. Configuration
  readback does not prove every message survives an abrupt crash.
- Unfiltered, untimed Debug off-host stream restarted at 20:39:55, child PID854.
  Handshake matches this boot; gzip prefix contains real Debug/Info/default
  events from multiple processes including kernel. No completion has yet been
  inferred. Original bytes are losslessly compressed on the development host.

## Evidence

All under `private/crash-series/`:

- `persist-debug-retry-20261025T123941Z.json`
- `persist-debug-scopes-20261025T124006Z.json`
- `persist-debug-all-current-processes-20261025T124033Z.json`
- `persist-debug-root-verification-20261025T124124Z.json`
- `all-debug-20261025T123957Z.start.json`
- `all-debug-20261025T123957Z.ndjson.gz` (live output)

No SIP/TCC changes were needed or performed for successful process overrides.

## Subsequent capture completion

The stream ended with SSH rc255 at 20:57:46.972914 +0800. Offline gzip traversal,
uncompressed byte count, compressed byte count and both receipt SHA256 values
were verified. It retained 909661588 original bytes, losslessly compressed to
64522626 bytes: 861962 parsed events from449 distinct process names, including
734199 Debug events. First event20:39:55.617719, last20:57:43.010140 +0800;
last machTimestamp1305404935285. Fifteen messages matched the retained panic/
GPU/watchdog/synchronize-timeout search terms, all were WindowServer synchronize
timeouts; the last was20:52:59.801991. No explicit loss-event records were found,
which does not prove every produced message was received. One non-JSON,
non-handshake line remains outside the parsed event count; raw bytes retained.

No new panic is inferred from stream termination. Manual reboot/power-off,
network failure or a crash must be distinguished by user observation and the
next available boot evidence. The stream is no longer running.

Offline summary: `private/crash-series/all-debug-20261025T123957Z.summary.json`.
