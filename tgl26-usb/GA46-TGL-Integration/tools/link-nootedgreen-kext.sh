#!/usr/bin/env bash
# Historical GA45 probe emitted a non-kext diagnostic bundle. Do not reuse its
# LLVM21 link semantics or pre-GA46 objects for the verified GA46 target.
echo 'Use make kext KEXT_OUT=logs/kext-UNIQUE_ID (real PR204805 linker and provider audit).' >&2
exit 2
