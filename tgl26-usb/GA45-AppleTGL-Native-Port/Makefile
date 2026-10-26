.PHONY: test objects abi userland probe kext-attempt clean

objects:
	./tools/build-nootedgreen.sh logs/build/objects-current

abi:
	cc -std=c11 -Wall -Wextra -Werror -I src tests/test_xe_abi.c -o logs/build/test_xe_abi
	./logs/build/test_xe_abi

test: abi
	python3 tests/test_tgl_profile.py
	python3 tests/test_compiler_bridge.py

userland:
	./tools/build-darwin-components.sh logs/build/darwin-components-current

probe:
	./tools/build-darwin-probe.sh logs/build/darwin-probe-current

kext-attempt:
	./tools/link-nootedgreen-kext.sh logs/build/objects-current logs/build/kext-link-current

clean:
	@echo "Build outputs are intentionally under logs/ and are not tracked; remove them explicitly if needed."
