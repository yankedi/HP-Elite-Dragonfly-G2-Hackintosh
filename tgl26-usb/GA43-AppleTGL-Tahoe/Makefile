PYTHON ?= python3

.PHONY: check test config-check tool-check provenance-check

check: test config-check tool-check

test:
	$(PYTHON) -m unittest discover -s tests -v

config-check:
	$(PYTHON) -m json.tool configs/tgl-9a49-25G83.json >/dev/null
	$(PYTHON) -c "import json; c=json.load(open('configs/tgl-9a49-25G83.json')); assert c['schema_version']==1; assert c['status']=='ANALYSIS_ONLY'; assert c['policy']['deployment_allowed'] is False; assert c['binaries']; print('config OK')"

tool-check:
	$(PYTHON) -m py_compile tools/check-tgl-compat.py
	$(PYTHON) tools/check-tgl-compat.py --help >/dev/null
	@echo "tool OK"

# Requires the pinned inputs/upstream trees; intentionally not part of `check`.
provenance-check:
	@for r in julio-xps13 nootedgreen intel-igpu-tahoe; do \
		(cd inputs/upstream/$$r && sha256sum -c ../../../docs/provenance/$$r-SHA256SUMS >/dev/null) || exit 1; \
		echo "$$r SHA256SUMS OK"; \
	done
