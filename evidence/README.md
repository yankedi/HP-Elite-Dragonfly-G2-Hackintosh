# Public graphics evidence

The original complete private captures remain preserved locally. This directory publishes reviewed panic text and a focused, machine-readable control summary.

| File | Meaning |
| --- | --- |
| [panics/ga419-trial-1.txt](panics/ga419-trial-1.txt) | Complete panic string: list corruption, 334.543 s |
| [panics/ga419-trial-2.txt](panics/ga419-trial-2.txt) | Complete panic string: pmap page0x101304000, 339.564 s |
| [panics/ga419-trial-3.txt](panics/ga419-trial-3.txt) | Complete panic string: pmap page0x101313000, 273.073 s |
| [panics/ga419-trial-4.txt](panics/ga419-trial-4.txt) | Firmware-recovered panic text: page0x10130e000, 252.560 s |
| [panics-manifest.json](panics-manifest.json) | Original and exported text hashes, transformation description |
| [software-control-summary.json](software-control-summary.json) | Verified runtime/control facts, stream counts and integrity hashes |
| [accelerated-loaded-kexts.txt](accelerated-loaded-kexts.txt) | Complete reviewed loaded-kext inventory from the accelerated trial |
| [software-display-loaded-kexts.txt](software-display-loaded-kexts.txt) | Complete reviewed inventory showing absence of the experimental stack |
| [loaded-kexts-manifest.json](loaded-kexts-manifest.json) | Original inventory hashes and entry counts |
| [config-validation.json](config-validation.json) | Matching ocvalidate results, ACPI source compilation and non-graphics equality check |
| [source-validation.json](source-validation.json) | 25 source files compared with the recorded GA416 Git object and graphics checksum verification |

Trials1–3 were exported from the native report's `macOSPanicString` field; the native report envelope and encoded stackshot field are not distributed. The panic text itself was not rewritten. Trial4 was recovered from the numeric firmware panic chunks and validated by exact packA re-encoding/cross-checks; no native incident UUID is invented for it.

Kernel UUIDs, kernel addresses, model identifiers and driver identifiers are retained for technical analysis. Private serials, network identifiers and operational access data are not needed for this public evidence bundle.

The control summary intentionally omits the first raw event's Wi-Fi SSID/BSSID and other personal unified-log content. Its full unfiltered stream is locally preserved with its original gzip and uncompressed hashes; the public summary is a derived report, not a substitute claim that the raw stream was uploaded.

See [comparison and limitations](../docs/GRAPHICS-STABILITY.md) and [source/build provenance](../graphics/README.md).
