#!/usr/bin/env bash
# The historical blanket re-export would mix LLVM3902 and32023 C++ objects.
echo 'ABI_UNVERIFIED: no compatible LLVM3902 provider/request contract; see reports/COMPILER-ABI-RESULT.md' >&2
exit 2
