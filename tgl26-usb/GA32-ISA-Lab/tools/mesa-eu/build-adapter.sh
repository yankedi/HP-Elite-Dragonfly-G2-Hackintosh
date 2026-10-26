#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/adapter"
M=../source
I=(-Istub -Ieu -I"$M/src" -I"$M/src/intel" -I"$M/include" -I"$M/src/util" -I"$M/src/compiler" -I"$M/src/mesa" -DHAVE_PTHREAD -DHAVE_STRUCT_TIMESPEC -DHAVE_TIMESPEC_GET -DUTIL_ARCH_LITTLE_ENDIAN=1 -DUTIL_ARCH_BIG_ENDIAN=0 -include inttypes.h -Wno-everything)
CC=${CC:-clang}
mkdir -p "${OUT:-build}"
O=${OUT:-build}
for f in eu/*.c; do "$CC" -g -O1 ${EXTRA_FLAGS:-} -c "${I[@]}" "$f" -o "$O/$(basename "${f%.c}").o"; done
"$CC" -g -O1 ${EXTRA_FLAGS:-} "${I[@]}" g11to12.c tgl_xlate.c stubs.c dbg.c "$O"/*.o -o "$O/g11to12"
