/*
 * Test-only hooks for the Darwin NMDRM libdrm subset.
 *
 * The public entry points are declared by <xf86drm.h>.  This header is not
 * installed: it lets CPU-only tests replace the small syscall boundary and
 * use a temporary directory instead of /dev/dri.  Production callers must
 * leave the hooks at their defaults.
 */
#ifndef GA41_DRM_DARWIN_TEST_H
#define GA41_DRM_DARWIN_TEST_H

#include <stddef.h>
#include <sys/stat.h>

#ifdef __cplusplus
extern "C" {
#endif

struct drm_darwin_syscalls {
   int (*open)(const char *path, int flags);
   int (*close)(int fd);
   int (*fstat)(int fd, struct stat *st);
   int (*ioctl)(int fd, unsigned long request, void *arg);
   int (*get_path)(int fd, char *path, size_t path_size);
};

/* Return 0 on success, -EINVAL for an incomplete table. */
int drmDarwinSetSyscalls(const struct drm_darwin_syscalls *syscalls);
void drmDarwinResetSyscalls(void);

/* Return 0 on success.  The path is copied by the library. */
int drmDarwinSetDeviceDirectory(const char *path);
void drmDarwinResetDeviceDirectory(void);

#ifdef __cplusplus
}
#endif

#endif /* GA41_DRM_DARWIN_TEST_H */
