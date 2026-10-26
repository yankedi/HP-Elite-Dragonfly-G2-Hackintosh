/* Allow Linux fsck.hfsplus to check a regular raw HFS+ image without loop/sudo.
 * Only disk-size ioctls for regular files are supplied. All others pass through.
 * Build: cc -shared -fPIC -O2 hfs_regular_ioctl.c -ldl -o hfs_regular_ioctl.so
 * Use: LD_PRELOAD=/absolute/path/hfs_regular_ioctl.so fsck.hfsplus -f -n image
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <linux/fs.h>
#include <stdarg.h>
#include <stdint.h>
#include <sys/ioctl.h>
#include <sys/stat.h>

int ioctl(int fd, unsigned long request, ...) {
    va_list args;
    void *arg;
    struct stat st;
    va_start(args, request);
    arg = va_arg(args, void *);
    va_end(args);
    if (arg && fstat(fd, &st) == 0 && S_ISREG(st.st_mode)) {
        if (request == BLKSSZGET || request == BLKBSZGET) {
            *(int *)arg = 512;
            return 0;
        }
        if (request == BLKGETSIZE) {
            *(unsigned long *)arg = st.st_size / 512;
            return 0;
        }
        if (request == BLKGETSIZE64) {
            *(uint64_t *)arg = st.st_size;
            return 0;
        }
    }
    int (*real_ioctl)(int, unsigned long, ...) = dlsym(RTLD_NEXT, "ioctl");
    return real_ioctl(fd, request, arg);
}
