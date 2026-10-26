# GA4.2 Intel Darwin Integration

Independent local repository, branch `ga42/intel-darwin-integration`.
Inherited code is recorded in `reference/inherited-files.json`; GA40 and GA41
remain read-only external inputs. The original `mac-for-elitebook` repository
contains pre-existing uncommitted work and is not the driver repository.

Offline engineering only. No remote configured, push, target SSH, kext load,
hardware access or changes to firmware, display, power or boot media authorized.
Public MacKernelSDK is an external read-only kernel header kit, not a user SDK
or the exact Tahoe 25G83 KDK. Test levels are recorded separately.

Run commands using `python3 -B tools/run_logged.py UNIQUE-LABEL COMMAND ...`.
Every invocation refuses to overwrite a log directory. Commit each tested
unit with `python3 -B tools/commit_unit.py MESSAGE PATH ...` to serialize
concurrent local index updates. Build outputs and raw logs remain private.
