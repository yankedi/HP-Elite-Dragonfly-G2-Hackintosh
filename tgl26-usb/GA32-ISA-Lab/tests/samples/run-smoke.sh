#!/usr/bin/env bash
#
# run-smoke.sh - regenerate the IGA CLI smoke-test evidence in this lab.
#
# It only writes:
#   logs/tool-smoke-*.txt           (captured stdout+stderr, commands echoed)
#   tests/samples/generated/        (round-trip .krn binaries and probe inputs)
#
# It does not touch tools/iga/source, tools/mesa-eu/source, or any other
# agent-owned output.  Safe to re-run.

set -uo pipefail   # not -e: several probes are expected to fail non-zero

here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd -- "$here/../.." && pwd)"
iga="${IGA64:-$root/tools/iga/build/IGAExe/iga64}"
samples="$here"
gen="$samples/generated"
logs="$root/logs"

[ -x "$iga" ] || { echo "iga64 not found: $iga (run tools/iga/build.sh first)" >&2; exit 2; }
mkdir -p "$gen" "$logs"

log=""      # current log file, set by logstart
logstart() {
  log="$1"
  : > "$log"
  {
    echo "# IGA CLI smoke capture"
    echo "# binary: $iga"
    "$iga" --help 2>&1 | sed -n '1p'
    echo "# note: each block below echoes the exact command, then its combined"
    echo "#       stdout+stderr, then the exit status in brackets."
  } >> "$log"
  echo "started $log"
}
# C <command...> : log the command, run it, record combined output + exit code
C() {
  {
    echo
    printf '$'
    printf ' %q' "$@"
    printf '\n'
  } >> "$log"
  "$@" >> "$log" 2>&1
  echo "[exit $?]" >> "$log"
}

# 1. CLI help + platform list -------------------------------------------------
logstart "$logs/tool-smoke-iga-help.txt"
C "$iga" -h

logstart "$logs/tool-smoke-iga-platforms.txt"
C "$iga" -h=p

# 2. official IGAJSONv2.md example -------------------------------------------
asm="$samples/iga-jsonv2-example.asm12p72"
fix="$samples/iga-jsonv2-example-fixed.asm12p72"
krn="$gen/iga-jsonv2-example-fixed.krn12p72"
logstart "$logs/tool-smoke-iga-official-jsonv2.txt"
C "$iga" "$asm" -p=12p72 -a -o "$gen/iga-jsonv2-example.krn12p72"
C "$iga" "$fix" -p=12p72 -a -o "$krn"
C "$iga" "$krn" -p=12p72 -d
C "$iga" "$krn" -p=12p72 -d -Xprint-json -Xprint-defs

# 3. i-g-t upstream Gen12 kernel (platform 12p1, Tiger Lake) -----------------
logstart "$logs/tool-smoke-iga-igt-gen12.txt"
C "$iga" "$samples/igt-gen12-gpgpu-fill.asm12p1" -p=12p1 -a -o "$gen/igt-gen12.krn12p1"
C "$iga" "$gen/igt-gen12.krn12p1" -p=12p1 -d -Xprint-pc

# 4. minimal Gen11 kernel -----------------------------------------------------
logstart "$logs/tool-smoke-iga-gen11.txt"
C "$iga" "$samples/gen11-minimal.asm11" -p=11 -a -o "$gen/gen11-minimal.krn11"
C "$iga" "$gen/gen11-minimal.krn11" -p=11 -d

# 5. SWSB + compaction behaviour probes --------------------------------------
sw="$gen/swsb"
mkdir -p "$sw"
printf 'send.gtwy (1|M0) null r112 null:0 0x0 0x02000010 {EOT,A@1}\n' > "$sw/send-A1.asm12p72"
printf 'send.gtwy (1|M0) null r112 null:0 0x0 0x02000010 {EOT,A@0}\n' > "$sw/send-A0.asm12p72"
printf 'send.gtwy (1|M0) null r112 null:0 0x0 0x02000010 {EOT}\n'     > "$sw/send-EOT.asm12p72"
printf 'mov (8|M0) r1.0<1>:ud r2.0<1;1,0>:ud {Compacted}\n'           > "$sw/compact-forced.asm12p1"
printf 'send.ts (16|M0) null r112 null 0x10000000 0x2000010 {Compacted}\n' > "$sw/compact-send.asm12p1"
logstart "$logs/tool-smoke-iga-swsb-compact.txt"
C "$iga" "$sw/send-A1.asm12p72" -a -o "$gen/swsb-send-A1.krn12p72"
C "$iga" "$sw/send-A0.asm12p72" -a -o "$gen/swsb-send-A0.krn12p72"
C "$iga" "$gen/swsb-send-A0.krn12p72" -d
C "$iga" "$sw/send-EOT.asm12p72" -a -o "$gen/swsb-send-EOT.krn12p72"
C "$iga" "$sw/compact-forced.asm12p1" -a -o "$gen/swsb-compact-forced.krn12p1"
C "$iga" "$sw/compact-send.asm12p1" -a -o "$gen/swsb-compact-send.krn12p1"
C "$iga" "$sw/compact-send.asm12p1" -a -o "$gen/swsb-compact-send-warn.krn12p1" -Xwarn-on-compact-fail
C "$iga" "$samples/igt-gen12-gpgpu-fill.asm12p1" -p=12p1 -a -o "$gen/igt-gen12-nocompact.krn12p1" -Xforce-no-compact
C "$iga" "$samples/igt-gen12-gpgpu-fill.asm12p1" -p=12p1 -a -o "$gen/igt-gen12-autocompact.krn12p1" -Xautocompact
C stat -c 'nocompact size=%s' "$gen/igt-gen12-nocompact.krn12p1"
C stat -c 'autocompact size=%s' "$gen/igt-gen12-autocompact.krn12p1"

# 6. unknown / invalid byte behaviour ----------------------------------------
printf '\377\377\377\377\377\377\377\377' > "$gen/junk-ffffffff.bin"
logstart "$logs/tool-smoke-iga-unknown.txt"
C "$iga" "$gen/junk-ffffffff.bin" -p=12p1 -d
C "$iga" "$gen/junk-ffffffff.bin" -p=12p1 -d --output-on-fail
C "$iga" "$gen/junk-ffffffff.bin" -p=11 -d --output-on-fail

echo "done."
