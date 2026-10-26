PYTHON ?= python3

.PHONY: check collect verify-evidence acpi prototype vbt framebuffer-objects framebuffer nonboot-graphics nonboot-vm nonboot-hid recovery-probe

check:
	$(PYTHON) scripts/check_repository.py

collect:
	@test -n "$(HOST)" || (echo 'Usage: make collect HOST=<ssh-host>' >&2; exit 2)
	$(PYTHON) scripts/collect_hardware.py --host "$(HOST)"

verify-evidence:
	@test -n "$(CAPTURE)" || (echo 'Set CAPTURE=.local/hardware/<capture>' >&2; exit 2)
	$(PYTHON) scripts/verify_evidence.py "$(CAPTURE)"

acpi:
	@test -n "$(CAPTURE)" || (echo 'Set CAPTURE=.local/hardware/<capture>' >&2; exit 2)
	$(PYTHON) scripts/disassemble_acpi.py "$(CAPTURE)"

prototype:
	$(PYTHON) scripts/build_vesa_prototype.py

vbt:
	@test -n "$(CAPTURE)" || (echo 'Set CAPTURE=.local/hardware/<capture>' >&2; exit 2)
	$(PYTHON) scripts/decode_vbt.py "$(CAPTURE)" $(if $(DECODER),--decoder "$(DECODER)",)

framebuffer-objects:
	@test -n "$(LLVM_BIN)" || (echo 'Set LLVM_BIN=<LLVM tools bin directory>' >&2; exit 2)
	$(PYTHON) scripts/build_framebuffer.py --compile-only --llvm-bin "$(LLVM_BIN)"

framebuffer:
	@test -n "$(LLVM_BIN)" -a -n "$(LINKER)" || (echo 'Set LLVM_BIN=<LLVM bin> LINKER=<ld64 supporting -kext>' >&2; exit 2)
	$(PYTHON) scripts/build_framebuffer.py --llvm-bin "$(LLVM_BIN)" --linker "$(LINKER)"

nonboot-graphics:
	$(PYTHON) scripts/check_nonboot_graphics.py --mutations

nonboot-vm:
	@test -n "$(QEMU)" -a -n "$(OVMF_DIR)" -a -n "$(EFI_INCLUDE)" -a -n "$(LLD_LINK)" || (echo 'Set QEMU=<qemu-system-x86_64> OVMF_DIR=<directory with CODE/VARS fd> EFI_INCLUDE=<gnu-efi/include/efi> LLD_LINK=<lld-link>' >&2; exit 2)
	$(PYTHON) scripts/check_nonboot_vm.py --qemu "$(QEMU)" --ovmf-code "$(OVMF_DIR)/OVMF_CODE.fd" --ovmf-vars "$(OVMF_DIR)/OVMF_VARS.fd" --efi-include "$(EFI_INCLUDE)" --lld "$(LLD_LINK)"

recovery-probe:
	$(PYTHON) scripts/check_recovery_probe.py

nonboot-hid:
	$(PYTHON) scripts/check_nonboot_hid.py
