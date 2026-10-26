/* Read the running kernel's CSR decisions. No NVRAM or kernel memory writes. */
#include <errno.h>
#include <stdint.h>
#include <stdio.h>

extern int csr_get_active_config(uint32_t *config);
extern int csr_check(uint32_t mask);

int main(void)
{
    uint32_t active = 0;
    errno = 0;
    int rc = csr_get_active_config(&active);
    printf("get_active_config rc=%d errno=%d active=0x%08x\n", rc, errno, active);
    if (rc != 0) return 1;
    const struct { uint32_t mask; const char *name; } checks[] = {
        {0, "zero-mask"},
        {0x1, "untrusted-kexts"},
        {0x2, "unrestricted-filesystem"},
        {0x40, "unrestricted-nvram"},
        {0x80, "device-configuration-boot-mode"},
        {0x100, "any-recovery-os"},
        {0x800, "unauthenticated-root"},
    };
    for (unsigned i = 0; i < sizeof(checks) / sizeof(checks[0]); ++i) {
        errno = 0;
        rc = csr_check(checks[i].mask);
        printf("csr_check mask=0x%03x name=%s rc=%d errno=%d\n",
            checks[i].mask, checks[i].name, rc, errno);
    }
    return 0;
}
