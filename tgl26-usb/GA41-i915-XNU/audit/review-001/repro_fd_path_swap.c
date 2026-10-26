/*
 * CPU-only regression reproducer for review-001.
 *
 * It supplies the library's test syscall boundary; no DRM node or ioctl is
 * opened on the host.  The original fd reports an Intel PCI function.  The
 * path returned for that fd is reopened as a different character-device
 * major and reports an AMD device with the same BDF.  drmGetDevice2() accepts
 * the replacement and returns the replacement's device metadata.
 */
#define _POSIX_C_SOURCE 200809L

#include "../../libdrm-darwin/drm_darwin.c"

#include <assert.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/sysmacros.h>
#include <unistd.h>

static char directory[PATH_MAX];
static int pair_mode;

static int fake_open(const char *path, int flags)
{
    (void)flags;
    if (strstr(path, "/card0") != NULL) {
        /* Path reopen is alternate in mode 0, original in mode 1. */
        return pair_mode ? 400 : 401;
    }
    if (pair_mode && strstr(path, "/renderD128") != NULL)
        return 402;
    {
        errno = ENOENT;
        return -1;
    }
}

static int fake_close(int fd)
{
    return fd == 400 || fd == 401 || fd == 402 ? 0 : (errno = EBADF, -1);
}

static int fake_fstat(int fd, struct stat *st)
{
    if (fd != 400 && fd != 401 && fd != 402) {
        errno = EBADF;
        return -1;
    }
    memset(st, 0, sizeof(*st));
    st->st_mode = S_IFCHR;
    /* Same minor/name, deliberately different cdev major. */
    st->st_rdev = makedev(fd == 401 ? 241 : 240, fd == 402 ? 128 : 0);
    return 0;
}

static void fill_pci(struct nm_drm_pciinfo *pci, int fd)
{
    memset(pci, 0, sizeof(*pci));
    pci->domain = 0;
    pci->bus = 0;
    pci->dev = 2;
    pci->func = 0;
    pci->vendor_id = fd == 400 ? 0x8086 : 0x1002;
    pci->device_id = fd == 400 ? 0x9a49 : 0x7340;
    pci->subvendor_id = fd == 400 ? 0x103c : 0x1002;
    pci->subdevice_id = fd == 400 ? 0x8a2a : 0x0b00;
    pci->revision_id = fd == 400 ? 1 : 2;
}

static int fake_ioctl(int fd, unsigned long request, void *argument)
{
    if (fd != 400 && fd != 401 && fd != 402) {
        errno = EBADF;
        return -1;
    }
    if (request == NM_DRM_IOCTL_VERSION) {
        struct nm_drm_version *version = argument;
        const char *name = "nmdrm";
        const char *date = "20261021";
        const char *desc = "review-001 CPU transport";
        size_t name_len = strlen(name), date_len = strlen(date), desc_len = strlen(desc);
        if (version->name && version->name_len)
            memcpy((void *)(uintptr_t)version->name, name,
                   version->name_len < name_len ? version->name_len : name_len);
        if (version->date && version->date_len)
            memcpy((void *)(uintptr_t)version->date, date,
                   version->date_len < date_len ? version->date_len : date_len);
        if (version->desc && version->desc_len)
            memcpy((void *)(uintptr_t)version->desc, desc,
                   version->desc_len < desc_len ? version->desc_len : desc_len);
        version->name_len = name_len;
        version->date_len = date_len;
        version->desc_len = desc_len;
        return 0;
    }
    if (request == NM_DRM_IOCTL_GET_PCIINFO) {
        fill_pci(argument, fd);
        return 0;
    }
    errno = ENOTTY;
    return -1;
}

static int fake_get_path(int fd, char *path, size_t path_size)
{
    if (fd != 400) {
        errno = EBADF;
        return -1;
    }
    if (snprintf(path, path_size, "%s/card0", directory) < 0 ||
        strlen(directory) + strlen("/card0") >= path_size) {
        errno = ENAMETOOLONG;
        return -1;
    }
    return 0;
}

int main(void)
{
    static const struct drm_darwin_syscalls calls = {
        fake_open, fake_close, fake_fstat, fake_ioctl, fake_get_path
    };
    char template_path[] = "/tmp/ga41-review-001-XXXXXX";
    drmDevicePtr device = NULL;
    int fd;
    int result;

    assert(mkdtemp(template_path) != NULL);
    assert(snprintf(directory, sizeof(directory), "%s", template_path) > 0);
    {
        char path[PATH_MAX];
        int file;
        assert(snprintf(path, sizeof(path), "%s/card0", directory) > 0);
        file = open(path, O_CREAT | O_WRONLY, 0600);
        assert(file >= 0);
        assert(close(file) == 0);
        assert(snprintf(path, sizeof(path), "%s/renderD128", directory) > 0);
        file = open(path, O_CREAT | O_WRONLY, 0600);
        assert(file >= 0);
        assert(close(file) == 0);
    }
    assert(drmDarwinSetSyscalls(&calls) == 0);
    assert(drmDarwinSetDeviceDirectory(directory) == 0);

    fd = 400; /* Original fd: major 240, Intel metadata. */
    result = drmGetDevice2(fd, DRM_DEVICE_GET_PCI_REVISION, &device);
    assert(result == 0 && device != NULL);
    assert(device->deviceinfo.pci->vendor_id == 0x1002);
    printf("observed success with replacement vendor=0x%04x\n",
           device->deviceinfo.pci->vendor_id);
    drmFreeDevice(&device);

    /* Primary and render nodes share a BDF but disagree on device identity. */
    pair_mode = 1;
    {
        drmDevicePtr pair[1] = {0};
        int count = drmGetDevices2(DRM_DEVICE_GET_PCI_REVISION, pair, 1);
        assert(count == 1 && pair[0] != NULL);
        assert(pair[0]->available_nodes ==
               ((1 << DRM_NODE_PRIMARY) | (1 << DRM_NODE_RENDER)));
        assert(pair[0]->deviceinfo.pci->vendor_id == 0x8086);
        printf("observed same-BDF pair keeps first vendor=0x%04x\n",
               pair[0]->deviceinfo.pci->vendor_id);
        drmFreeDevices(pair, count);
    }

    {
        char path[PATH_MAX];
        assert(snprintf(path, sizeof(path), "%s/card0", directory) > 0);
        assert(unlink(path) == 0);
        assert(snprintf(path, sizeof(path), "%s/renderD128", directory) > 0);
        assert(unlink(path) == 0);
    }
    assert(rmdir(directory) == 0);
    drmDarwinResetSyscalls();
    drmDarwinResetDeviceDirectory();
    return 0;
}
