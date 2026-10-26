# GA4.3 Darwin Driver Stack

Independent local repository, branch `ga43/darwin-toolchain-and-i915`.
GA43 inherits sealed GA42 `ebc63b2bf254cc867b544ad7232ed7860580cb3f`;
see `reports/GA43-INHERITANCE.md`. Earlier inheritance metadata in
`reference/inherited-files.json` describes GA41→GA42 history. GA40/41/42
remain read-only external inputs. The companion `mac-for-elitebook` repository
contains pre-existing uncommitted work and is not the driver repository.

Offline engineering only. No remote configured, push, target SSH, kext load,
hardware access or changes to firmware, display, power or boot media authorized.
Public MacKernelSDK is an external read-only kernel header kit, not a user SDK
or the exact Tahoe 25G83 KDK. Test levels are recorded separately.

Run commands using `python3 -B tools/run_logged.py UNIQUE-LABEL COMMAND ...`.
Every invocation refuses to overwrite a log directory. Commit each tested
unit with `python3 -B tools/commit_unit.py MESSAGE PATH ...` to serialize
concurrent local index updates. Build outputs and raw logs remain private.

Start with `FINAL-REPORT.md`, `reports/PROMPT-ARTIFACT-CHECKLIST.md`,
`reports/ACCEPTANCE.md`, and `reports/GIT-COMMITS.md`. There is no successful
ANV Darwin ICD, final XNU module, native fd mmap, or GPU execution claim.
Host VM/context/request ownership and real GEM-backed mapping code are
distinct from GPU residency/fences; strict toolchain and target inputs remain
external blockers. Historical reports retained under their GA42 titles are
inherited evidence, not GA43 success declarations.
