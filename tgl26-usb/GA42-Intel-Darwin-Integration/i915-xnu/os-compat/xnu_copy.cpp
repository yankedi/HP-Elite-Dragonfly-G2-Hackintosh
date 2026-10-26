/* SPDX-License-Identifier: MIT
 * Unregistered adapter for the explicit copy boundary. Not d_ioctl: XNU's
 * automatic outer copyout cannot report failures back into d_ioctl to rollback
 * a newly created handle. A future registered transport must resolve that
 * integration separately rather than claim this helper fixes it.
 */
#include "gx_ioctl.h"
#include "gx_xnu.h"
#include <sys/systm.h>
static int copy_from(void *, uint64_t address, void *p, size_t n) {
    int err = copyin(static_cast<user_addr_t>(address), p, n);
    return err ? -err : 0;
}
static int copy_to(void *, const void *p, uint64_t address, size_t n) {
    int err = copyout(p, static_cast<user_addr_t>(address), n);
    return err ? -err : 0;
}
extern "C" int gx_xnu_user_ioctl(struct gx_device *d, gx_file_id file,
                                  uint32_t cmd, uint64_t address) {
    const gx_copy_ops ops = {copy_from, copy_to};
    return gx_user_ioctl(d, file, cmd, address, &ops, nullptr);
}
