PYTHON ?= python3
.PHONY: check tests analyze sources native verify

check: tests
	$(PYTHON) -B tools/check_lab.py

tests:
	$(PYTHON) -B -m unittest discover -s track-a/tests -v
	$(PYTHON) -B -m unittest discover -s track-c/tests -v

analyze:
	$(PYTHON) -B tools/catalog_prm_constraints.py
	$(PYTHON) -B track-a/command_stream.py
	$(PYTHON) -B track-a/normalizer.py
	$(PYTHON) -B track-c/correlate.py

sources:
	$(PYTHON) -B tools/audit_fault_sources.py

native:
	./track-b/diagnostic-src/build_core.sh
	$(PYTHON) -B tools/pack_matrix.py --label clang
	$(PYTHON) -B tools/pack_matrix.py --label gcc

verify:
	$(PYTHON) -B tools/archive.py
