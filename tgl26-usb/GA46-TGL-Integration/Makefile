.PHONY: check test objects abi userland probe kext kext-attempt clean

CHECK_OUT ?= logs/check-$(shell date -u +%Y%m%dT%H%M%SZ)
check:
	bash tools/check-ga46.sh "$(CHECK_OUT)"

objects:
	./tools/build-nootedgreen.sh logs/build/objects-current

abi:
	cc -std=c11 -Wall -Wextra -Werror -I src tests/test_xe_abi.c -o logs/build/test_xe_abi
	./logs/build/test_xe_abi

test: check

userland:
	./tools/build-darwin-components.sh logs/build/darwin-components-current

probe:
	./tools/build-darwin-probe.sh logs/build/darwin-probe-current

KEXT_OUT ?= logs/kext-$(shell date -u +%Y%m%dT%H%M%SZ)
kext:
	bash tools/build-nootedgreen-kext.sh "$(KEXT_OUT)"

kext-attempt: kext

clean:
	@echo "Build outputs are intentionally under logs/ and are not tracked; remove them explicitly if needed."
