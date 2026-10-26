PYTHON ?= python3

.PHONY: check test config-check tool-check patch-check provenance-check

check: test config-check tool-check patch-check

test:
	$(PYTHON) -m unittest discover -s tests -v

config-check:
	$(PYTHON) -m json.tool configs/25g83-evidence.json >/dev/null
	$(PYTHON) -m json.tool evidence/25g83-system.json >/dev/null
	@echo "config OK"

tool-check:
	$(PYTHON) -m py_compile tools/check-tgl-compat.py
	$(PYTHON) tools/check-tgl-compat.py --help >/dev/null
	@echo "tool OK"

patch-check:
	@test -s patches/nootedgreen-tgl-native.patch
	@echo "patch present"

# Requires the private target binaries under input/; intentionally optional.
provenance-check:
	@sha256sum -c evidence/tahoe-frameworks-SHA256SUMS >/dev/null
	@echo "tahoe framework hashes OK"
