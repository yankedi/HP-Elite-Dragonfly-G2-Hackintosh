# Applied fixes and evidence lineage

Original REVIEW.md, repro_fd_path_swap.c and its vulnerable-run output are
preserved verbatim. `applied-patches/*.patch` exports the exact two parent
`patchText` tool payloads from the private managed transcript, not a guessed
diff. They implement rdev/full-PCI identity consistency, pair major/slot
checks even for count-only enumeration, device-number validation, strict node
names, padding-safe field comparison, post-enumeration fd revalidation and
their regression tests.

`FOLLOWUP.md` is the independent review of those changes and array ownership.
Its separate logs preserve independent test reruns. Parent final executed
checks are in `logs/reviewed-tests-001/`. The original reproducer is purposely
a proof of the former vulnerable behavior, not a passing test for current code;
current negative expectations are in tests/test_drm_darwin.c.

Do not apply these patches to a sealed delivery or modify original review
evidence to pretend the bug never existed.
