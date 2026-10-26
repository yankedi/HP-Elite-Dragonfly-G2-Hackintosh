# Project engineering notes

- Current acceptance status lives in `docs/STATUS.md`; older experiment reports retain historical results and may describe superseded configurations.
- Preserve source provenance, upstream licenses, tested artifact hashes and the distinction between user observations, runtime evidence and hypotheses.
- Do not commit generated SMBIOS identities, SSH/signing keys, credentials, raw firmware/hardware dumps or unfiltered personal logs. Local private originals remain outside this public tree.
- Keep accelerated TGL, framebuffer-only and firmware/basic-display configurations separate. Schema validation, driver loading and enumeration do not prove functionality or stability.
- Hardware deployment, firmware/EFI/NVRAM changes and power actions require an applicable explicit user instruction. Local source/analysis work does not imply permission to change the HP machine.
- Validate changes with `python3 scripts/check-publication.py`, `make -C mac-for-elitebook check` and `git diff --check`. Build checks are not hardware acceptance tests.
- When updating the public EFI examples, record redactions separately from the private tested configuration hashes. Do not embed identities to make the examples appear deployable.
- Keep private operational handoffs separate from public research reports. Record publication/check evidence in repository documentation without publishing conversations or access data.
