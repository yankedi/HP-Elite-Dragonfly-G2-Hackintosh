#!/bin/bash
# One-shot, bounded control-plane capture. No Metal calls or GPU workloads.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
if [[ ${1:-} == --check ]]; then
  [[ $(uname -s) == Darwin && $EUID -eq 0 ]] || exit 1
  for tool in /usr/bin/kmutil /usr/sbin/ioreg /usr/bin/log /usr/sbin/nvram /usr/bin/csrutil; do
    [[ -x $tool ]] || exit 1
  done
  echo 'Collector syntax/command preflight only; no first-boot capture or marker created.'
  exit 0
fi
[[ $(uname -s) == Darwin && $EUID -eq 0 ]] || exit 1
umask 027
base=/Users/Shared/GA410-firstboot
marker=/private/var/db/ga410-firstboot-once
if [[ -d $marker ]]; then exit 0; fi
/bin/mkdir "$marker"
/bin/date -u > "$marker/started-utc.txt"
output="$base/$(/bin/date -u +%Y%m%dT%H%M%SZ)-$(/usr/sbin/sysctl -n kern.bootsessionuuid)"
/bin/mkdir -p "$output"
/usr/sbin/chown root:admin "$output"
/bin/chmod 2750 "$output"
# Each command has a wall-time watchdog and a 16MiB output limit. Its actual rc
# is recorded, including timeout/signal/truncation. Expected absence is not PASS.
capture() {
  local name=$1 limit=$2 pid watcher rc
  shift 2
  printf 'START\t%s\tSECONDS=%s\n' "$name" "$SECONDS" >> "$output/progress.tsv"
  ( ulimit -f 16384; exec "$@" ) > "$output/$name.stdout" 2> "$output/$name.stderr" &
  pid=$!
  ( /bin/sleep "$limit"; /bin/kill -TERM "$pid" 2>/dev/null; /bin/sleep 2; /bin/kill -KILL "$pid" 2>/dev/null ) &
  watcher=$!
  set +e
  wait "$pid"
  rc=$?
  /bin/kill "$watcher" 2>/dev/null
  wait "$watcher" 2>/dev/null
  set -e
  printf '%s\t%s\n' "$name" "$rc" >> "$output/returncodes.tsv"
  printf 'END\t%s\trc=%s\tSECONDS=%s\n' "$name" "$rc" "$SECONDS" >> "$output/progress.tsv"
}
capture boot-session 5 /usr/sbin/sysctl kern.bootargs kern.bootsessionuuid kern.boottime
capture nvram 8 /usr/sbin/nvram -xp
capture kernel-buffer-early 10 /sbin/dmesg
capture sip 8 /usr/bin/csrutil status
capture authenticated-root 8 /usr/bin/csrutil authenticated-root status
capture csr-decisions 5 '/Library/Application Support/GA410/csr-readonly-probe'
capture loaded-early 12 /usr/bin/kmutil showloaded --variant-suffix release
capture identity 5 /usr/bin/id
capture version 5 /usr/bin/sw_vers
# Finite, read-only snapshots preserve messages emitted after the early dump.
# R3's kernel log query returned 143 and its early dumps predated the new init.
capture kernel-buffer-watch 75 /bin/bash -c 'for i in {1..30}; do printf "SNAPSHOT %s\n" "$i"; /sbin/dmesg; /bin/sleep 2; done' &
kernel_watch=$!
# R2 panicked during the old 15-second delay. Capture attachment state now.
capture ioreg-accelerator 12 /usr/sbin/ioreg -r -c IOAccelerator -l -w0
capture ioreg-framebuffer 12 /usr/sbin/ioreg -r -c IOFramebuffer -l -w0
capture ioreg-pci 12 /usr/sbin/ioreg -r -c IOPCIDevice -l -w0
capture kernel-buffer-late 10 /sbin/dmesg
capture loaded-late 12 /usr/bin/kmutil showloaded --variant-suffix release
capture kernel-log 20 /usr/bin/log show --last 3m --style syslog --predicate 'process == "kernel" OR process == "kernelmanagerd"'
capture network 8 /sbin/ifconfig -a
capture processes 8 /bin/ps -axo pid,ppid,user,command
capture installed-kc 20 '/Library/Application Support/GA410/recovery-sha256' /Library/KernelCollections/AuxiliaryKernelExtensions.kc
capture crash-list 8 /usr/bin/find /Library/Logs/DiagnosticReports -maxdepth 2 -type f -mmin -30 -print
capture recent-panic-text 12 /bin/bash -c '/usr/bin/find /Library/Logs/DiagnosticReports -maxdepth 2 -type f \( -iname "*panic*" -o -iname "*WindowServer*" \) -mmin -60 -exec /usr/bin/tail -c 262144 {} \;'
wait "$kernel_watch"
printf '%s\n' 'Capture only: inspect rc files; no GPU/Metal result or trusted-loading PASS inferred.' > "$output/README.txt"
/usr/sbin/chown -R root:admin "$output"
/bin/chmod -R g+rX,o-rwx "$output"
/bin/date -u > "$marker/finished-utc.txt"
/bin/sync
