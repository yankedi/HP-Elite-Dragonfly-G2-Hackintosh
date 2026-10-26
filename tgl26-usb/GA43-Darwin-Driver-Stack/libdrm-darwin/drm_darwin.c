/*
 * A small, deliberately conservative libdrm subset for NullMoth/NMDRM.
 *
 * The production path uses ordinary Darwin open(2), fstat(2), fcntl(2) and
 * ioctl(2) calls.  The only backend-specific ABI here is the four ioctl
 * structures published by GA40's NMDRM kext.  Tests replace that syscall
 * boundary; they never open a real /dev/dri node or issue an ioctl to a GPU.
 *
 * SPDX-License-Identifier: MIT
 */

#if defined(__APPLE__)
/* F_GETPATH and Darwin major/minor are required by the real fd path. */
#define _DARWIN_C_SOURCE 1
#endif
#define _POSIX_C_SOURCE 200809L

#include <xf86drm.h>

#include "drm-darwin-test.h"

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#if defined(__linux__)
# include <sys/sysmacros.h>
# include <sys/ioctl.h>
#elif defined(__APPLE__) || defined(__FreeBSD__) || defined(__OpenBSD__) || defined(__NetBSD__)
# include <sys/ioctl.h>
#else
# include <sys/ioctl.h>
#endif
#include <unistd.h>

#ifndef PATH_MAX
# define PATH_MAX 1024
#endif
#ifndef O_CLOEXEC
# define O_CLOEXEC 0
#endif

#define NM_DRM_IOCTL_BASE 'd'

/* Keep these wire structures independent of the host libc's drm.h typedefs. */
struct nm_drm_version {
   int32_t version_major;
   int32_t version_minor;
   int32_t version_patchlevel;
   uint32_t pad0;
   uint64_t name_len;
   uint64_t name;
   uint64_t date_len;
   uint64_t date;
   uint64_t desc_len;
   uint64_t desc;
};

struct nm_drm_unique {
   uint64_t unique_len;
   uint64_t unique;
};

struct nm_drm_get_cap {
   uint64_t capability;
   uint64_t value;
};

struct nm_drm_pciinfo {
   uint16_t domain;
   uint8_t bus;
   uint8_t dev;
   uint8_t func;
   uint16_t vendor_id;
   uint16_t device_id;
   uint16_t subvendor_id;
   uint16_t subdevice_id;
   uint8_t revision_id;
};

_Static_assert(sizeof(struct nm_drm_version) == 64, "NMDRM version ABI");
_Static_assert(sizeof(struct nm_drm_unique) == 16, "NMDRM unique ABI");
_Static_assert(sizeof(struct nm_drm_get_cap) == 16, "NMDRM cap ABI");
_Static_assert(sizeof(struct nm_drm_pciinfo) == 16, "NMDRM PCI ABI");
/*
 * DRM's public structs contain user pointers.  The BSD ioctl path receives
 * those pointers through the same 64-bit wire layout as Linux on the only
 * supported target (Darwin x86_64).  Keep this assertion close to the
 * request translation instead of silently relying on a coincidental ABI.
 */
_Static_assert(sizeof(struct drm_version) == sizeof(struct nm_drm_version),
               "DRM version pointer ABI");
_Static_assert(sizeof(struct drm_unique) == sizeof(struct nm_drm_unique),
               "DRM unique pointer ABI");
_Static_assert(sizeof(struct drm_get_cap) == sizeof(struct nm_drm_get_cap),
               "DRM capability ABI");
_Static_assert(offsetof(struct drm_version, name_len) ==
                  offsetof(struct nm_drm_version, name_len) &&
               offsetof(struct drm_version, name) ==
                  offsetof(struct nm_drm_version, name) &&
               offsetof(struct drm_version, date_len) ==
                  offsetof(struct nm_drm_version, date_len) &&
               offsetof(struct drm_version, date) ==
                  offsetof(struct nm_drm_version, date) &&
               offsetof(struct drm_version, desc_len) ==
                  offsetof(struct nm_drm_version, desc_len) &&
               offsetof(struct drm_version, desc) ==
                  offsetof(struct nm_drm_version, desc),
               "DRM version nested pointer offsets");
_Static_assert(offsetof(struct drm_unique, unique_len) ==
                  offsetof(struct nm_drm_unique, unique_len) &&
               offsetof(struct drm_unique, unique) ==
                  offsetof(struct nm_drm_unique, unique),
               "DRM unique nested pointer offsets");

#define NM_DRM_IOCTL_VERSION \
   _IOWR(NM_DRM_IOCTL_BASE, 0x00, struct nm_drm_version)
#define NM_DRM_IOCTL_GET_UNIQUE \
   _IOWR(NM_DRM_IOCTL_BASE, 0x01, struct nm_drm_unique)
#define NM_DRM_IOCTL_GET_CAP \
   _IOWR(NM_DRM_IOCTL_BASE, 0x0c, struct nm_drm_get_cap)
#define NM_DRM_IOCTL_GET_PCIINFO \
   _IOR(NM_DRM_IOCTL_BASE, 0x15, struct nm_drm_pciinfo)

#define NM_DRM_CAP_PRIME 0x5u
#define NM_DRM_MAX_DEVICES 16u
#define NM_DRM_RENDER_MINOR_BASE 128u
#define NM_DRM_MAX_STRING (1024u * 1024u)
#define NM_DRM_DRIVER_NAME "nmdrm"

struct nm_identity {
   struct nm_drm_pciinfo pci;
   char driver[32];
};

struct nm_node {
   int type;
   unsigned number;
   char path[PATH_MAX];
   struct nm_identity identity;
   dev_t rdev;
};

struct drm_darwin_device_list {
   drmDevicePtr *items;
   struct nm_node *identities;
   size_t count;
   size_t capacity;
};

static void free_device_list(struct drm_darwin_device_list *list)
{
   size_t i;
   if (list == NULL)
      return;
   for (i = 0; i < list->count; i++)
      drmFreeDevice(&list->items[i]);
   free(list->items);
   free(list->identities);
   list->items = NULL;
   list->identities = NULL;
   list->count = 0;
   list->capacity = 0;
}

static int real_open(const char *path, int flags)
{
   return open(path, flags);
}

static int real_close(int fd)
{
   return close(fd);
}

static int real_fstat(int fd, struct stat *st)
{
   return fstat(fd, st);
}

static int real_ioctl(int fd, unsigned long request, void *arg)
{
   return ioctl(fd, request, arg);
}

static int real_get_path(int fd, char *path, size_t path_size)
{
#if defined(__APPLE__)
   if (fcntl(fd, F_GETPATH, path) < 0)
      return -1;
   if (strnlen(path, path_size) >= path_size) {
      errno = ENAMETOOLONG;
      return -1;
   }
   return 0;
#elif defined(__linux__)
   char proc_path[64];
   ssize_t length;

   if (snprintf(proc_path, sizeof(proc_path), "/proc/self/fd/%d", fd) < 0)
      return -1;
   length = readlink(proc_path, path, path_size - 1);
   if (length < 0)
      return -1;
   if ((size_t)length >= path_size) {
      errno = ENAMETOOLONG;
      return -1;
   }
   path[length] = '\0';
   return 0;
#else
   (void)fd;
   (void)path;
   (void)path_size;
   errno = ENOTSUP;
   return -1;
#endif
}

static struct drm_darwin_syscalls g_syscalls = {
   .open = real_open,
   .close = real_close,
   .fstat = real_fstat,
   .ioctl = real_ioctl,
   .get_path = real_get_path,
};

static char g_device_directory[PATH_MAX] = "/dev/dri";

int
drmDarwinSetSyscalls(const struct drm_darwin_syscalls *syscalls)
{
   if (syscalls == NULL || syscalls->open == NULL || syscalls->close == NULL ||
       syscalls->fstat == NULL || syscalls->ioctl == NULL ||
       syscalls->get_path == NULL)
      return -EINVAL;

   g_syscalls = *syscalls;
   return 0;
}

void
drmDarwinResetSyscalls(void)
{
   g_syscalls.open = real_open;
   g_syscalls.close = real_close;
   g_syscalls.fstat = real_fstat;
   g_syscalls.ioctl = real_ioctl;
   g_syscalls.get_path = real_get_path;
}

int
drmDarwinSetDeviceDirectory(const char *path)
{
   size_t length;

   if (path == NULL || path[0] == '\0')
      return -EINVAL;
   length = strlen(path);
   if (length >= sizeof(g_device_directory))
      return -ENAMETOOLONG;
   memcpy(g_device_directory, path, length + 1);
   return 0;
}

void
drmDarwinResetDeviceDirectory(void)
{
   strcpy(g_device_directory, "/dev/dri");
}

static int neg_errno(void)
{
   return errno != 0 ? -errno : -EIO;
}

/*
 * ANV is compiled against the Linux DRM request names, while NMDRM's cdev
 * implements the BSD request numbers.  The argument layouts are deliberately
 * not copied here: VERSION and UNIQUE contain nested user pointers, and the
 * kernel must perform the copyin/copyout for those pointers.  Only the command
 * number is translated. Linux write-only requests encode direction as 0x4000,
 * BSD as 0x8000. Translate only exact supported LP64 wire contracts, preserving
 * all argument/nested pointers. Unknown requests pass through for rejection;
 * do not guess arbitrary direction/size bits or advertise GPU capabilities.
 */
static unsigned long native_ioctl_request(unsigned long request)
{
   if (request == DRM_IOCTL_VERSION)
      return NM_DRM_IOCTL_VERSION;
   if (request == DRM_IOCTL_GET_UNIQUE)
      return NM_DRM_IOCTL_GET_UNIQUE;
   if (request == DRM_IOCTL_GET_CAP)
      return NM_DRM_IOCTL_GET_CAP;
   /* Constants also accept clients built from the original Linux UAPI. Some
    * read/write numbers happen to match BSD; write-only ones do not. */
   switch (request) {
   case 0x40086409UL: return 0x80086409UL; /* DRM_IOCTL_GEM_CLOSE */
   case 0x40406469UL: return 0x80406469UL; /* I915_GEM_EXECBUFFER2, not WR */
   default: break;
   }
   return request;
}

static int ioctl_retry(int fd, unsigned long request, void *arg)
{
   int ret;

   do {
      ret = g_syscalls.ioctl(fd, request, arg);
   } while (ret == -1 && (errno == EINTR || errno == EAGAIN));
   return ret;
}

static int valid_wire_length(uint64_t length);
static char *alloc_string(uint64_t length);

static int call_ioctl(int fd, unsigned long request, void *arg)
{
   if (ioctl_retry(fd, request, arg) == 0)
      return 0;
   return neg_errno();
}

static int valid_wire_length(uint64_t length)
{
   return length <= NM_DRM_MAX_STRING && length <= (uint64_t)SIZE_MAX - 1u;
}

static char *alloc_string(uint64_t length)
{
   if (!valid_wire_length(length))
      return NULL;
   return calloc((size_t)length + 1u, 1u);
}

static int wire_string_result(uint64_t length, char *buffer, int *public_length)
{
   if (!valid_wire_length(length) || length > (uint64_t)INT_MAX)
      return -EOVERFLOW;
   /* NMDRM does not copy a trailing NUL.  calloc provided the terminator. */
   buffer[(size_t)length] = '\0';
   *public_length = (int)length;
   return 0;
}

drmVersionPtr
drmGetVersion(int fd)
{
   struct nm_drm_version wire = {0};
   drmVersionPtr result = NULL;
   uint64_t name_capacity;
   uint64_t date_capacity;
   uint64_t desc_capacity;
   int ret;

   if (fd < 0) {
      errno = EINVAL;
      return NULL;
   }

   /* The first call is intentionally a zero-length probe, as NMDRM expects. */
   ret = call_ioctl(fd, NM_DRM_IOCTL_VERSION, &wire);
   if (ret < 0 || !valid_wire_length(wire.name_len) ||
       !valid_wire_length(wire.date_len) || !valid_wire_length(wire.desc_len)) {
      errno = ret < 0 ? -ret : EOVERFLOW;
      return NULL;
   }

   result = calloc(1, sizeof(*result));
   if (result == NULL) {
      errno = ENOMEM;
      return NULL;
   }
   result->name = alloc_string(wire.name_len);
   result->date = alloc_string(wire.date_len);
   result->desc = alloc_string(wire.desc_len);
   if (result->name == NULL || result->date == NULL || result->desc == NULL) {
      drmFreeVersion(result);
      errno = ENOMEM;
      return NULL;
   }

   name_capacity = wire.name_len + 1u;
   date_capacity = wire.date_len + 1u;
   desc_capacity = wire.desc_len + 1u;
   wire.name = (uint64_t)(uintptr_t)result->name;
   wire.date = (uint64_t)(uintptr_t)result->date;
   wire.desc = (uint64_t)(uintptr_t)result->desc;
   /* The probe did not copy strings, so pass the complete capacities. */
   wire.name_len = name_capacity;
   wire.date_len = date_capacity;
   wire.desc_len = desc_capacity;
   ret = call_ioctl(fd, NM_DRM_IOCTL_VERSION, &wire);
   if (ret < 0) {
      drmFreeVersion(result);
      errno = -ret;
      return NULL;
   }

   result->version_major = wire.version_major;
   result->version_minor = wire.version_minor;
   result->version_patchlevel = wire.version_patchlevel;
   if (wire.name_len >= name_capacity || wire.date_len >= date_capacity ||
       wire.desc_len >= desc_capacity) {
      drmFreeVersion(result);
      errno = EOVERFLOW;
      return NULL;
   }
   ret = wire_string_result(wire.name_len, result->name, &result->name_len);
   if (ret == 0)
      ret = wire_string_result(wire.date_len, result->date, &result->date_len);
   if (ret == 0)
      ret = wire_string_result(wire.desc_len, result->desc, &result->desc_len);
   if (ret < 0) {
      drmFreeVersion(result);
      errno = -ret;
      return NULL;
   }

   return result;
}

void
drmFreeVersion(drmVersionPtr version)
{
   if (version == NULL)
      return;
   free(version->name);
   free(version->date);
   free(version->desc);
   free(version);
}

int
drmIoctl(int fd, unsigned long request, void *arg)
{
   return ioctl_retry(fd, native_ioctl_request(request), arg);
}

char *
drmGetBusid(int fd)
{
   struct nm_drm_unique wire = {0};
   char *result;
   uint64_t capacity;

   if (drmIoctl(fd, DRM_IOCTL_GET_UNIQUE, &wire) != 0)
      return NULL;
   if (!valid_wire_length(wire.unique_len)) {
      errno = EOVERFLOW;
      return NULL;
   }

   result = alloc_string(wire.unique_len);
   if (result == NULL) {
      errno = ENOMEM;
      return NULL;
   }
   capacity = wire.unique_len;
   wire.unique = (uint64_t)(uintptr_t)result;
   /* NMDRM reports the full length and copies at most the supplied length. */
   wire.unique_len = capacity;
   if (drmIoctl(fd, DRM_IOCTL_GET_UNIQUE, &wire) != 0) {
      free(result);
      return NULL;
   }
   if (wire.unique_len > capacity) {
      free(result);
      errno = EOVERFLOW;
      return NULL;
   }
   result[wire.unique_len] = '\0';
   return result;
}

void
drmFreeBusid(const char *busid)
{
   free((void *)busid);
}

static int query_pci(int fd, struct nm_drm_pciinfo *pci)
{
   int ret = call_ioctl(fd, NM_DRM_IOCTL_GET_PCIINFO, pci);
   if (ret < 0)
      return ret;

   /* 0xffff is the PCI absent value; zero vendor IDs are not a PCI identity. */
   if (pci->vendor_id == 0 || pci->vendor_id == 0xffff ||
        pci->device_id == 0xffff || pci->dev > 31 || pci->func > 7)
      return -ENODEV;
   return 0;
}

static int query_identity(int fd, struct nm_identity *identity)
{
   drmVersionPtr version;
   int ret;

   memset(identity, 0, sizeof(*identity));
   version = drmGetVersion(fd);
   if (version == NULL)
      return -errno;
   if (version->name == NULL || strcmp(version->name, NM_DRM_DRIVER_NAME) != 0) {
      drmFreeVersion(version);
      return -ENODEV;
   }
   if (snprintf(identity->driver, sizeof(identity->driver), "%s", version->name) < 0) {
      drmFreeVersion(version);
      return -EINVAL;
   }
   drmFreeVersion(version);
   ret = query_pci(fd, &identity->pci);
   return ret;
}

static int parse_decimal(const char *text, unsigned *value)
{
   unsigned long parsed;
   char *end;

    if (text == NULL || text[0] == '\0')
       return -EINVAL;
    for (const char *p = text; *p; p++)
       if (*p < '0' || *p > '9')
          return -EINVAL;
    if (text[0] == '0' && text[1] != '\0')
       return -EINVAL;
   errno = 0;
   parsed = strtoul(text, &end, 10);
   if (errno == ERANGE || end == text || *end != '\0' || parsed > UINT_MAX)
      return -EINVAL;
   *value = (unsigned)parsed;
   return 0;
}

static int parse_node_name(const char *name, int *type, unsigned *number)
{
   if (strncmp(name, "card", 4) == 0) {
      if (parse_decimal(name + 4, number) < 0 || *number >= NM_DRM_RENDER_MINOR_BASE)
         return -EINVAL;
      *type = DRM_NODE_PRIMARY;
      return 0;
   }
   if (strncmp(name, "renderD", 7) == 0) {
      if (parse_decimal(name + 7, number) < 0 ||
          *number < NM_DRM_RENDER_MINOR_BASE ||
          *number >= NM_DRM_RENDER_MINOR_BASE + NM_DRM_MAX_DEVICES)
         return -EINVAL;
      *type = DRM_NODE_RENDER;
      return 0;
   }
   return -EINVAL;
}

static int validate_node_stat(const struct stat *st, int type, unsigned number)
{
   unsigned expected_minor = number;

   if (!S_ISCHR(st->st_mode))
      return -EINVAL;
   if ((unsigned)minor(st->st_rdev) != expected_minor)
      return -ENODEV;
   if (type == DRM_NODE_PRIMARY && number >= NM_DRM_RENDER_MINOR_BASE)
      return -ENODEV;
   if (type == DRM_NODE_RENDER && number < NM_DRM_RENDER_MINOR_BASE)
      return -ENODEV;
   return 0;
}

static int node_from_path(const char *path, struct nm_node *node)
{
   const char *slash;
   const char *base;
   struct stat st;
   int fd;
   int ret;

   if (path == NULL || node == NULL)
      return -EINVAL;
   slash = strrchr(path, '/');
   base = slash == NULL ? path : slash + 1;
   ret = parse_node_name(base, &node->type, &node->number);
   if (ret < 0)
      return ret;
   if (snprintf(node->path, sizeof(node->path), "%s", path) < 0 ||
       strlen(path) >= sizeof(node->path))
      return -ENAMETOOLONG;

   fd = g_syscalls.open(path, O_RDONLY | O_CLOEXEC);
   if (fd < 0)
      return neg_errno();
   ret = g_syscalls.fstat(fd, &st) == 0 ? 0 : neg_errno();
   if (ret == 0)
      ret = validate_node_stat(&st, node->type, node->number);
    if (ret == 0)
       ret = query_identity(fd, &node->identity);
    if (ret == 0)
       node->rdev = st.st_rdev;
   (void)g_syscalls.close(fd);
   return ret;
}

static int pci_bus_equal_wire(const struct nm_drm_pciinfo *a,
                              const struct nm_drm_pciinfo *b)
{
   return a->domain == b->domain && a->bus == b->bus &&
          a->dev == b->dev && a->func == b->func;
}

static int pci_identity_equal_wire(const struct nm_drm_pciinfo *a,
                                    const struct nm_drm_pciinfo *b)
{
   return pci_bus_equal_wire(a, b) &&
          a->vendor_id == b->vendor_id && a->device_id == b->device_id &&
          a->subvendor_id == b->subvendor_id && a->subdevice_id == b->subdevice_id &&
          a->revision_id == b->revision_id;
}

static int pci_bus_equal_public(const drmPciBusInfoPtr a,
                                const struct nm_drm_pciinfo *b)
{
   return a != NULL && b != NULL && a->domain == b->domain &&
          a->bus == b->bus && a->dev == b->dev && a->func == b->func;
}

static drmDevicePtr alloc_device(const struct nm_node *node, uint32_t flags,
                                 int fetch_deviceinfo)
{
   drmDevicePtr device = calloc(1, sizeof(*device));
   if (device == NULL)
      return NULL;

   device->nodes = calloc(DRM_NODE_MAX, sizeof(*device->nodes));
   device->businfo.pci = calloc(1, sizeof(*device->businfo.pci));
   if (device->nodes == NULL || device->businfo.pci == NULL) {
      drmFreeDevice(&device);
      return NULL;
   }
   device->bustype = DRM_BUS_PCI;
   device->available_nodes = 1 << node->type;
   device->nodes[node->type] = strdup(node->path);
   if (device->nodes[node->type] == NULL) {
      drmFreeDevice(&device);
      return NULL;
   }
   device->businfo.pci->domain = node->identity.pci.domain;
   device->businfo.pci->bus = node->identity.pci.bus;
   device->businfo.pci->dev = node->identity.pci.dev;
   device->businfo.pci->func = node->identity.pci.func;

   if (fetch_deviceinfo) {
      device->deviceinfo.pci = calloc(1, sizeof(*device->deviceinfo.pci));
      if (device->deviceinfo.pci == NULL) {
         drmFreeDevice(&device);
         return NULL;
      }
      device->deviceinfo.pci->vendor_id = node->identity.pci.vendor_id;
      device->deviceinfo.pci->device_id = node->identity.pci.device_id;
      device->deviceinfo.pci->subvendor_id = node->identity.pci.subvendor_id;
      device->deviceinfo.pci->subdevice_id = node->identity.pci.subdevice_id;
      device->deviceinfo.pci->revision_id = (flags & DRM_DEVICE_GET_PCI_REVISION) ?
         node->identity.pci.revision_id : 0xff;
   }
   return device;
}

static int add_device(struct drm_darwin_device_list *list,
                      const struct nm_node *node, uint32_t flags,
                      int fetch_deviceinfo)
{
   size_t i;
   drmDevicePtr device;

   for (i = 0; i < list->count; i++) {
       if (list->items[i]->businfo.pci != NULL &&
           pci_bus_equal_public(list->items[i]->businfo.pci, &node->identity.pci)) {
          const struct nm_node *first = &list->identities[i];
          if (!pci_identity_equal_wire(&first->identity.pci, &node->identity.pci) ||
              major(first->rdev) != major(node->rdev) ||
              first->number % NM_DRM_RENDER_MINOR_BASE != node->number % NM_DRM_RENDER_MINOR_BASE)
             return -ENODEV; /* Conflicting/stale pair: never hide disagreement. */
         if ((list->items[i]->available_nodes & (1 << node->type)) == 0) {
            list->items[i]->nodes[node->type] = strdup(node->path);
            if (list->items[i]->nodes[node->type] == NULL)
               return -ENOMEM;
            list->items[i]->available_nodes |= 1 << node->type;
         }
         return 0;
      }
   }

   device = alloc_device(node, flags, fetch_deviceinfo);
   if (device == NULL)
      return -ENOMEM;
   if (list->count == list->capacity) {
      size_t new_capacity = list->capacity == 0 ? 4 : list->capacity * 2;
      drmDevicePtr *new_items = realloc(list->items, new_capacity * sizeof(*new_items));
      if (new_items == NULL) {
         drmFreeDevice(&device);
         return -ENOMEM;
      }
       list->items = new_items;
       struct nm_node *new_identities = realloc(list->identities, new_capacity * sizeof(*new_identities));
       if (new_identities == NULL) {
          drmFreeDevice(&device);
          return -ENOMEM;
       }
       list->identities = new_identities;
      list->capacity = new_capacity;
   }
    list->identities[list->count] = *node;
    list->items[list->count++] = device;
   return 0;
}

static int node_name_compare(const void *a, const void *b)
{
   const char *const *left = a;
   const char *const *right = b;
   return strcmp(*left, *right);
}

static void free_names(char **names, size_t count)
{
   size_t i;
   for (i = 0; i < count; i++)
      free(names[i]);
   free(names);
}

static int collect_node_names(char ***names_out, size_t *count_out)
{
   DIR *directory;
   struct dirent *entry;
   char **names = NULL;
   size_t count = 0;
   size_t capacity = 0;

   directory = opendir(g_device_directory);
   if (directory == NULL)
      return neg_errno();
   while ((entry = readdir(directory)) != NULL) {
      int type;
      unsigned number;
      char **new_names;
      if (parse_node_name(entry->d_name, &type, &number) < 0)
         continue;
      (void)type;
      (void)number;
      if (count == capacity) {
         size_t new_capacity = capacity == 0 ? 8 : capacity * 2;
         new_names = realloc(names, new_capacity * sizeof(*new_names));
         if (new_names == NULL) {
            free_names(names, count);
            closedir(directory);
            return -ENOMEM;
         }
         names = new_names;
         capacity = new_capacity;
      }
      names[count] = strdup(entry->d_name);
      if (names[count] == NULL) {
         free_names(names, count);
         closedir(directory);
         return -ENOMEM;
      }
      count++;
   }
   closedir(directory);
   if (count > 1)
      qsort(names, count, sizeof(*names), node_name_compare);
   *names_out = names;
   *count_out = count;
   return 0;
}

static int enumerate_nodes(uint32_t flags, int fetch_deviceinfo,
                           struct drm_darwin_device_list *list)
{
   char **names = NULL;
   size_t count = 0;
   size_t i;
   int ret;

   ret = collect_node_names(&names, &count);
   if (ret < 0)
      return ret;
   for (i = 0; i < count; i++) {
      struct nm_node node;
      char path[PATH_MAX];
      if (snprintf(path, sizeof(path), "%s/%s", g_device_directory, names[i]) < 0 ||
          strlen(g_device_directory) + 1u + strlen(names[i]) >= sizeof(path))
         continue;
      ret = node_from_path(path, &node);
      if (ret < 0)
         continue; /* ENXIO includes a provider which disappeared mid-scan. */
      ret = add_device(list, &node, flags, fetch_deviceinfo);
      if (ret < 0) {
         free_device_list(list);
         free_names(names, count);
         return ret;
      }
   }
   free_names(names, count);
   return 0;
}

void
drmFreeDevice(drmDevicePtr *device)
{
   int i;
   if (device == NULL || *device == NULL)
      return;
   if ((*device)->nodes != NULL) {
      for (i = 0; i < DRM_NODE_MAX; i++)
         free((*device)->nodes[i]);
      free((*device)->nodes);
   }
   if ((*device)->bustype == DRM_BUS_PCI) {
      free((*device)->businfo.pci);
      free((*device)->deviceinfo.pci);
   }
   free(*device);
   *device = NULL;
}

void
drmFreeDevices(drmDevicePtr devices[], int count)
{
   int i;
   if (devices == NULL || count < 0)
      return;
   for (i = 0; i < count; i++)
      drmFreeDevice(&devices[i]);
}

int
drmDevicesEqual(drmDevicePtr a, drmDevicePtr b)
{
   if (a == NULL || b == NULL || a->bustype != b->bustype)
      return 0;
   if (a->bustype != DRM_BUS_PCI || a->businfo.pci == NULL || b->businfo.pci == NULL)
      return 0;
    return a->businfo.pci->domain == b->businfo.pci->domain &&
           a->businfo.pci->bus == b->businfo.pci->bus &&
           a->businfo.pci->dev == b->businfo.pci->dev &&
           a->businfo.pci->func == b->businfo.pci->func;
}

int
drmGetDevices2(uint32_t flags, drmDevicePtr devices[], int max_devices)
{
   struct drm_darwin_device_list list = {0};
   size_t i;
   int ret;
   int result;

   if ((flags & ~DRM_DEVICE_GET_PCI_REVISION) != 0 || max_devices < 0)
      return -EINVAL;
   if (devices != NULL) {
      for (i = 0; i < (size_t)max_devices; i++)
         devices[i] = NULL;
   }
   ret = enumerate_nodes(flags, devices != NULL, &list);
   if (ret < 0) {
      free_device_list(&list);
      return ret;
   }

   result = (int)list.count;
   if (devices == NULL) {
      for (i = 0; i < list.count; i++)
         drmFreeDevice(&list.items[i]);
   } else {
      size_t copied = list.count < (size_t)max_devices ? list.count : (size_t)max_devices;
      for (i = 0; i < copied; i++)
         devices[i] = list.items[i];
      for (i = copied; i < list.count; i++)
         drmFreeDevice(&list.items[i]);
   }
    free(list.items);
    free(list.identities);
   return devices == NULL ? result : (result < max_devices ? result : max_devices);
}

static int query_fd(struct stat *st, int fd, struct nm_identity *identity)
{
   if (fd < 0)
      return -EINVAL;
   if (g_syscalls.fstat(fd, st) != 0)
      return neg_errno();
   if (!S_ISCHR(st->st_mode))
      return -EINVAL;
   return query_identity(fd, identity);
}

static int device_from_fd_path(int fd, const char *path, uint32_t flags,
                               drmDevicePtr *device)
{
   struct stat st;
   struct nm_identity identity = {0};
   struct nm_node node = {0};
   struct drm_darwin_device_list list = {0};
   size_t i;
   int ret;

   ret = query_fd(&st, fd, &identity);
   if (ret < 0)
      return ret;
   if (path == NULL)
      return -ENOTSUP;
   ret = node_from_path(path, &node);
   if (ret < 0)
      return ret;
    if (node.rdev != st.st_rdev ||
        !pci_identity_equal_wire(&node.identity.pci, &identity.pci))
       return -ENODEV;

   /* Enumerating again folds the card/render pair and verifies live nodes. */
    ret = enumerate_nodes(flags, 1, &list);
   if (ret < 0) {
      free_device_list(&list);
       return ret;
    }
    struct stat live_st;
    struct nm_identity live_identity;
    ret = query_fd(&live_st, fd, &live_identity);
    if (ret < 0 || live_st.st_rdev != st.st_rdev ||
        !pci_identity_equal_wire(&live_identity.pci, &identity.pci)) {
       free_device_list(&list);
       return ret < 0 ? ret : -ENODEV;
    }
   for (i = 0; i < list.count; i++) {
      if (list.items[i]->businfo.pci != NULL &&
           pci_bus_equal_public(list.items[i]->businfo.pci, &identity.pci)) {
          if (!pci_identity_equal_wire(&list.identities[i].identity.pci, &identity.pci) ||
              major(list.identities[i].rdev) != major(st.st_rdev)) {
             free_device_list(&list);
             return -ENODEV;
          }
         *device = list.items[i];
         list.items[i] = NULL;
         for (i = 0; i < list.count; i++)
            drmFreeDevice(&list.items[i]);
          free(list.items);
          free(list.identities);
         return 0;
      }
   }
   for (i = 0; i < list.count; i++)
      drmFreeDevice(&list.items[i]);
    free(list.items);
    free(list.identities);

   /* The node may have been unlinked after the fd was opened. */
   *device = alloc_device(&node, flags, 1);
   return *device == NULL ? -ENOMEM : 0;
}

int
drmGetDevice2(int fd, uint32_t flags, drmDevicePtr *device)
{
   char path[PATH_MAX];
   struct stat st;
   struct nm_identity identity;
   int ret;

   if (device == NULL || (flags & ~DRM_DEVICE_GET_PCI_REVISION) != 0)
      return -EINVAL;
   *device = NULL;
   ret = query_fd(&st, fd, &identity);
   if (ret < 0)
      return ret;
   if (g_syscalls.get_path(fd, path, sizeof(path)) != 0)
      return neg_errno();
   return device_from_fd_path(fd, path, flags, device);
}

int
drmGetDevice(int fd, drmDevicePtr *device)
{
   return drmGetDevice2(fd, DRM_DEVICE_GET_PCI_REVISION, device);
}

int
drmGetNodeTypeFromFd(int fd)
{
   char path[PATH_MAX];
   const char *slash;
   int type;
   unsigned number;
   struct stat st;

   if (g_syscalls.fstat(fd, &st) != 0 || !S_ISCHR(st.st_mode))
      return -EINVAL;
   if (g_syscalls.get_path(fd, path, sizeof(path)) != 0)
      return neg_errno();
   slash = strrchr(path, '/');
   if (parse_node_name(slash == NULL ? path : slash + 1, &type, &number) < 0)
      return -EINVAL;
   return validate_node_stat(&st, type, number) < 0 ? -ENODEV : type;
}

int
drmGetCap(int fd, uint64_t capability, uint64_t *value)
{
   struct nm_drm_get_cap cap;
   int ret;

   if (value == NULL)
      return -EINVAL;
   cap.capability = capability;
   cap.value = 0;
   ret = call_ioctl(fd, NM_DRM_IOCTL_GET_CAP, &cap);
   if (ret < 0)
      return ret;
   *value = cap.value;
   return 0;
}
