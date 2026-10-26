#!/usr/bin/env python3
"""CPU fault injection of the exact added Apple branch; not native os_sync execution."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
patch = (ROOT/'anv/patches/0006-anv-darwin-address-wait.patch').read_text()
added = '\n'.join(s[1:] for s in patch.splitlines() if s.startswith('+') and not s.startswith('+++'))
branch = added.split('#elif defined(__APPLE__) && defined(MESA_INTEL_DARWIN)')[-1]
branch = branch.replace('#include <os/os_sync_wait_on_address.h>', '')
prefix = '''
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <time.h>
#include <errno.h>
#include <assert.h>
#define OS_SYNC_WAIT_ON_ADDRESS_NONE 0
#define OS_SYNC_WAKE_BY_ADDRESS_NONE 0
#define OS_CLOCK_MACH_ABSOLUTE_TIME 32
static int calls, result, injected_errno;
static uint64_t last_ns;
static int os_sync_wait_on_address(void *p, uint64_t value, unsigned size, int flags) {
    assert(p && value == 2 && size == 4 && flags == 0);
    calls++; errno = injected_errno; return result;
}
static int os_sync_wait_on_address_with_timeout(void *p, uint64_t value, unsigned size,
                                               int flags, int clock, uint64_t ns) {
    assert(clock == 32 && ns > 0); last_ns = ns;
    return os_sync_wait_on_address(p, value, size, flags);
}
static int os_sync_wake_by_address_any(void *p, unsigned n, int f) {
    assert(p && n == 4 && f == 0); calls++; errno = injected_errno; return result;
}
static int os_sync_wake_by_address_all(void *p, unsigned n, int f) {
    return os_sync_wake_by_address_any(p, n, f);
}
'''
test = '''
int main(void) {
    uint32_t value = 2;
    result = 7; assert(futex_wait(&value, 2, 0) == 0 && calls == 1);
    result = -1; injected_errno = EINTR;
    assert(futex_wait(&value, 2, 0) == -1 && errno == EINTR);
    struct timespec deadline; assert(!clock_gettime(CLOCK_MONOTONIC, &deadline));
    deadline.tv_sec += 60; result = 4;
    assert(!futex_wait(&value, 2, &deadline) && last_ns > 0 && last_ns <= 60000000000ULL);
    result = -1; injected_errno = ETIMEDOUT;
    assert(futex_wait(&value, 2, &deadline) == -1 && errno == ETIMEDOUT);
    int prior = calls; deadline.tv_nsec = 1000000000;
    assert(futex_wait(&value, 2, &deadline) == -1 && errno == EINVAL && calls == prior);
    deadline.tv_sec = deadline.tv_nsec = 0;
    assert(futex_wait(&value, 2, &deadline) == -1 && errno == ETIMEDOUT && calls == prior);
    value = 9; assert(!futex_wait(&value, 2, &deadline) && calls == prior);
    injected_errno = ENOENT; assert(!futex_wake(&value, 1));
    injected_errno = EINVAL; assert(futex_wake(&value, INT32_MAX) == -1 && errno == EINVAL);
    assert(futex_wake(&value, 2) == -1 && errno == EINVAL);
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='ga43-wait-contract-', dir='/tmp/opencode') as tmp:
    src, exe = Path(tmp)/'contract.c', Path(tmp)/'contract'
    src.write_text(prefix+branch+test)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', str(src), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
print('PASS exact Apple branch CPU fault injection: positive waits normalize, errno/output/deadline preserved; NOT native runtime')
