#!/bin/sh
# Start the existing Recovery sshd with a private, adjacent diagnostic key bundle.
# Runtime state is confined to /tmp. Run explicitly after joining Wi-Fi.
set -eu
umask 077
if [ "$(uname -s)" != Darwin ]; then
    echo 'Run this helper in macOS/Recovery.' >&2
    exit 2
fi
if [ "$#" -ne 0 ]; then
    echo 'Usage: sh /Volumes/*/hpdiag/s' >&2
    exit 2
fi
if [ "$(id -u)" -ne 0 ]; then
    echo 'Run from the Recovery root Terminal.' >&2
    exit 2
fi
here=$(CDPATH= cd "$(dirname "$0")" && pwd)
for file in ssh_host_ed25519_key authorized_keys; do
    if [ ! -s "$here/$file" ]; then
        echo "Missing private diagnostic bundle file: $file" >&2
        exit 1
    fi
done
for tool in /usr/sbin/sshd /usr/libexec/sshd-session /usr/libexec/sshd-auth; do
    if [ ! -x "$tool" ]; then
        echo "Recovery component missing: $tool" >&2
        exit 1
    fi
done
work=$(/usr/bin/mktemp -d /tmp/hp-recovery-ssh.XXXXXX)
/bin/cp "$here/ssh_host_ed25519_key" "$work/host_key"
/bin/cp "$here/authorized_keys" "$work/authorized_keys"
/bin/chmod 600 "$work/host_key" "$work/authorized_keys"
# Standalone config avoids persistent Remote Login settings and system host keys.
# internal-sftp works without a separate sftp-server binary in this BaseSystem.
/bin/cat > "$work/sshd_config" <<EOF
Port 2222
AddressFamily inet
HostKey $work/host_key
PidFile $work/sshd.pid
AuthorizedKeysFile $work/authorized_keys
# mktemp creates a root-only directory; skip the writable /tmp ancestor check.
StrictModes no
PermitRootLogin prohibit-password
AllowUsers root
PubkeyAuthentication yes
AuthenticationMethods publickey
PasswordAuthentication no
KbdInteractiveAuthentication no
UsePAM no
PrintMotd no
Subsystem sftp internal-sftp
LogLevel VERBOSE
EOF
if ! /usr/sbin/sshd -t -f "$work/sshd_config" > "$work/validation.log" 2>&1; then
    /bin/cat "$work/validation.log" >&2
    echo "SSH config validation failed; evidence: $work" >&2
    exit 1
fi
if ! /usr/sbin/sshd -f "$work/sshd_config" -E "$work/sshd.log"; then
    /bin/cat "$work/sshd.log" >&2
    exit 1
fi
# The daemon forks before its child writes PidFile. Recovery exposed this race:
# an immediate check reported failure although the listener accepted SSH.
attempt=0
while [ ! -s "$work/sshd.pid" ] && [ "$attempt" -lt 5 ]; do
    /bin/sleep 1
    attempt=$((attempt+1))
done
if [ ! -s "$work/sshd.pid" ]; then
    /bin/cat "$work/sshd.log" >&2
    echo 'No daemon PID recorded; SSH start is unconfirmed.' >&2
    exit 1
fi
pid=$(/bin/cat "$work/sshd.pid")
case "$pid" in ''|*[!0-9]*) echo 'Invalid daemon PID.' >&2; exit 1;; esac
if ! kill -0 "$pid" 2>/dev/null; then
    /bin/cat "$work/sshd.log" >&2
    exit 1
fi
printf 'SSH daemon running, port 2222; client connection is not yet verified.\n'
printf 'IPv4 addresses (ignore loopback):\n'
/sbin/ifconfig | /usr/bin/awk '$1 == "inet" { print $2 }'
printf 'Private logs: %s\nTo stop this listener: kill %s\n' "$work" "$pid"
