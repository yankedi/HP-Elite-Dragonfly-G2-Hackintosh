/* CPU-only transport tests.  No real DRM node is opened by this executable. */
#define _POSIX_C_SOURCE 200809L

#include <xf86drm.h>

#include "drm-darwin-test.h"
#include "identity.h"
#include "intel_kmd.h"

#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <unistd.h>
#ifdef GA41_GEM_INTEGRATION
#include "gem_cpu_backend.h"
#include "gx_ioctl.h"
#include <i915_drm.h>
static struct cpu_context gem_context = {.lock = PTHREAD_MUTEX_INITIALIZER};
static struct gx_device *gem_device;
static gx_file_id gem_file;
static int local_copy_in(void *ctx, uint64_t address, void *out, size_t n) {
   (void)ctx; memcpy(out, (void *)(uintptr_t)address, n); return 0;
}
static int local_copy_out(void *ctx, const void *in, uint64_t address, size_t n) {
   (void)ctx; memcpy((void *)(uintptr_t)address, in, n); return 0;
}
#endif

struct nm_drm_version_test {
   int32_t version_major, version_minor, version_patchlevel;
   uint32_t pad0;
   uint64_t name_len, name;
   uint64_t date_len, date;
   uint64_t desc_len, desc;
};

struct nm_drm_get_cap_test {
   uint64_t capability, value;
};

struct nm_drm_unique_test {
   uint64_t unique_len, unique;
};

struct nm_drm_pciinfo_test {
   uint16_t domain;
   uint8_t bus, dev, func;
   uint16_t vendor_id, device_id, subvendor_id, subdevice_id;
   uint8_t revision_id;
};

#define NM_DRM_IOCTL_VERSION_TEST \
   _IOWR('d', 0x00, struct nm_drm_version_test)
#define NM_DRM_IOCTL_GET_CAP_TEST \
   _IOWR('d', 0x0c, struct nm_drm_get_cap_test)
#define NM_DRM_IOCTL_GET_UNIQUE_TEST \
   _IOWR('d', 0x01, struct nm_drm_unique_test)
#define NM_DRM_IOCTL_GET_PCIINFO_TEST \
   _IOR('d', 0x15, struct nm_drm_pciinfo_test)

struct fake_node {
   const char *name;
   unsigned minor;
   int char_device;
   int gone;
   struct nm_drm_pciinfo_test pci;
};

static struct fake_node fake_nodes[] = {
   {"card0", 0, 1, 0, {0, 0, 2, 0, 0x8086, 0x9a49, 0x103c, 0x8a2a, 0x01}},
   {"card1", 1, 1, 0, {0, 3, 0, 0, 0x1002, 0x7340, 0x1002, 0x0b00, 0x02}},
   {"card2", 2, 0, 0, {0, 0, 0, 0, 0, 0, 0, 0, 0}},
   {"renderD128", 128, 1, 0, {0, 0, 2, 0, 0x8086, 0x9a49, 0x103c, 0x8a2a, 0x01}},
   {"renderD129", 129, 1, 0, {0, 3, 0, 0, 0x1002, 0x7340, 0x1002, 0x0b00, 0x02}},
};
static struct fake_node replacement =
   {"card0", 0, 1, 0, {0, 0, 2, 0, 0x1002, 0x7340, 0x1002, 0x0b00, 0x02}};
static int swap_path, disappear_on_reopen, malformed_name_opens;

static char fake_directory[PATH_MAX];
static char fake_driver[32] = "nmdrm";
static unsigned version_probes;
static unsigned bad_ioctl_requests;
static int malformed_version;
static unsigned interrupted_ioctls;
static unsigned translated_ioctls;
static int malformed_unique;

static struct fake_node *node_for_fd(int fd)
{
   if (fd == 500) return &replacement;
   int index = fd - 400;
   if (index < 0 || (size_t)index >= sizeof(fake_nodes) / sizeof(fake_nodes[0]))
      return NULL;
   return &fake_nodes[index];
}

static struct fake_node *node_for_path(const char *path)
{
   const char *base = strrchr(path, '/');
   size_t i;
   base = base == NULL ? path : base + 1;
   for (i = 0; i < sizeof(fake_nodes) / sizeof(fake_nodes[0]); i++)
      if (strcmp(base, fake_nodes[i].name) == 0)
         return &fake_nodes[i];
   return NULL;
}

static int fake_open(const char *path, int flags)
{
   struct fake_node *node;
   size_t i;
    (void)flags;
    const char *base = strrchr(path, '/'); base = base ? base + 1 : path;
    if (strcmp(base, "card+0") == 0 || strcmp(base, "card00") == 0)
       malformed_name_opens++;
    if (strcmp(base, "card0") == 0 && swap_path) return 500;
    if (strcmp(base, "card0") == 0 && disappear_on_reopen) fake_nodes[0].gone = 1;
   node = node_for_path(path);
   if (node == NULL) {
      errno = ENOENT;
      return -1;
   }
   for (i = 0; i < sizeof(fake_nodes) / sizeof(fake_nodes[0]); i++)
      if (&fake_nodes[i] == node)
         return 400 + (int)i;
   errno = ENOENT;
   return -1;
}

static int fake_close(int fd)
{
   if (node_for_fd(fd) == NULL) {
      errno = EBADF;
      return -1;
   }
   return 0;
}

static int fake_fstat(int fd, struct stat *st)
{
   struct fake_node *node = node_for_fd(fd);
   if (node == NULL) {
      errno = EBADF;
      return -1;
   }
   memset(st, 0, sizeof(*st));
   st->st_mode = node->char_device ? S_IFCHR : S_IFREG;
    st->st_rdev = makedev(fd == 500 ? 241 : 240, node->minor);
   return 0;
}

static int copy_wire_string(uint64_t pointer, uint64_t capacity, const char *text)
{
   size_t length = strlen(text);
   if (pointer != 0 && capacity != 0)
      memcpy((void *)(uintptr_t)pointer, text,
             capacity < length ? (size_t)capacity : length);
   return (int)length;
}

static int fake_ioctl(int fd, unsigned long request, void *argument)
{
   struct fake_node *node = node_for_fd(fd);
   if (node == NULL) {
      errno = EBADF;
      return -1;
   }
    if (node->gone) {
      errno = ENXIO;
       return -1;
    }
    if (interrupted_ioctls != 0) {
       interrupted_ioctls--;
       errno = EINTR;
       return -1;
    }
#ifdef GA41_GEM_INTEGRATION
    if (gem_device && fd == 400 &&
        (request == 0xc010645bUL || request == 0x80086409UL)) {
       const struct gx_copy_ops copy = {local_copy_in, local_copy_out};
       int ret = gx_user_ioctl(gem_device, gem_file, (uint32_t)request,
                               (uintptr_t)argument, &copy, NULL);
       if (ret) { errno = -ret; return -1; }
       return 0;
    }
#endif
    if (request == NM_DRM_IOCTL_VERSION_TEST) {
       translated_ioctls++;
      struct nm_drm_version_test *version = argument;
      int name_length;
      int date_length;
      int desc_length;
      assert(version->name_len == 0 || version->name_len >= strlen(fake_driver) + 1);
      if (version->name_len == 0 && version->date_len == 0 && version->desc_len == 0)
         version_probes++;
      version->version_major = 0;
      version->version_minor = 1;
      version->version_patchlevel = 0;
      name_length = copy_wire_string(version->name, version->name_len, fake_driver);
      date_length = copy_wire_string(version->date, version->date_len, "20261011");
      desc_length = copy_wire_string(version->desc, version->desc_len,
                                     "NullMoth DRM device nodes");
      version->name_len = (uint64_t)name_length;
      version->date_len = (uint64_t)date_length;
      version->desc_len = (uint64_t)desc_length;
      if (malformed_version && version->name != 0)
         version->name_len = version->name_len + 1;
      return 0;
   }
   if (request == NM_DRM_IOCTL_GET_PCIINFO_TEST) {
      memcpy(argument, &node->pci, sizeof(node->pci));
      return 0;
   }
   if (request == NM_DRM_IOCTL_GET_UNIQUE_TEST) {
      struct nm_drm_unique_test *unique = argument;
      const char *text = "pci:0000:00:02.0";
      size_t length = strlen(text);
      translated_ioctls++;
      if (unique->unique != 0 && unique->unique_len != 0)
         memcpy((void *)(uintptr_t)unique->unique, text,
                unique->unique_len < length ? (size_t)unique->unique_len : length);
      unique->unique_len = malformed_unique ? UINT64_MAX : length;
      return 0;
   }
    if (request == NM_DRM_IOCTL_GET_CAP_TEST) {
       translated_ioctls++;
      struct nm_drm_get_cap_test *cap = argument;
      if (cap->capability == 0x5) {
         cap->value = 0;
         return 0;
      }
      errno = EINVAL;
      return -1;
   }
   bad_ioctl_requests++;
   errno = ENOTTY;
   return -1;
}

static int fake_get_path(int fd, char *path, size_t path_size);

static void test_public_ioctl_bridge(void)
{
   const struct drm_darwin_syscalls calls = {
      fake_open, fake_close, fake_fstat, fake_ioctl, fake_get_path
   };
   struct drm_version version = {0};
   struct drm_get_cap cap = {0};
   char name[32] = {0};
   char date[32] = {0};
   char desc[64] = {0};
   int fd;
   unsigned translated_before;

   assert(drmDarwinSetSyscalls(&calls) == 0);
   fd = fake_open("/tmp/unused/card0", O_RDONLY);
   assert(fd == 400);
   version.name_len = sizeof(name);
   version.name = name;
   version.date_len = sizeof(date);
   version.date = date;
   version.desc_len = sizeof(desc);
   version.desc = desc;
   interrupted_ioctls = 1;
   translated_before = translated_ioctls;
   assert(drmIoctl(fd, DRM_IOCTL_VERSION, &version) == 0);
   assert(strcmp(name, "nmdrm") == 0);
   assert(strcmp(date, "20261011") == 0);
   assert(strcmp(desc, "NullMoth DRM device nodes") == 0);
   assert(translated_ioctls == translated_before + 1);

   {
      char *busid = drmGetBusid(fd);
      assert(busid != NULL && strcmp(busid, "pci:0000:00:02.0") == 0);
      drmFreeBusid(busid);
   }
   malformed_unique = 1;
   errno = 0;
   assert(drmGetBusid(fd) == NULL && errno == EOVERFLOW);
   malformed_unique = 0;

   cap.capability = DRM_CAP_PRIME;
   assert(drmIoctl(fd, DRM_IOCTL_GET_CAP, &cap) == 0 && cap.value == 0);
   assert(translated_ioctls == translated_before + 5);

   {
      struct drm_gem_close close_arg = {0};
      errno = 0;
      assert(drmIoctl(fd, DRM_IOCTL_GEM_CLOSE, &close_arg) == -1 && errno == ENOTTY);
      assert(bad_ioctl_requests == 1);
      bad_ioctl_requests = 0;
   }

   fake_nodes[0].gone = 1;
   errno = 0;
   assert(drmIoctl(fd, DRM_IOCTL_GET_CAP, &cap) == -1 && errno == ENXIO);
   fake_nodes[0].gone = 0;
   assert(fake_close(fd) == 0);
   drmDarwinResetSyscalls();
   puts("PASS public DRM ioctl bridge: BSD request translation, nested pointers, EINTR and hot-unplug");
}

static int fake_get_path(int fd, char *path, size_t path_size)
{
   struct fake_node *node = node_for_fd(fd);
   int written;
   if (node == NULL) {
      errno = EBADF;
      return -1;
   }
   written = snprintf(path, path_size, "%s/%s", fake_directory, node->name);
   if (written < 0 || (size_t)written >= path_size) {
      errno = ENAMETOOLONG;
      return -1;
   }
   return 0;
}

static void make_fake_directory(void)
{
    char template_path[] = "/tmp/opencode/ga41-drm-XXXXXX";
   size_t i;
   int directory = mkdtemp(template_path) != NULL;
   assert(directory);
   assert(snprintf(fake_directory, sizeof(fake_directory), "%s", template_path) > 0);
   for (i = 0; i < sizeof(fake_nodes) / sizeof(fake_nodes[0]); i++) {
      char path[PATH_MAX];
      int fd;
      assert(snprintf(path, sizeof(path), "%s/%s", fake_directory,
                      fake_nodes[i].name) > 0);
      fd = open(path, O_CREAT | O_WRONLY | O_TRUNC, 0600);
      assert(fd >= 0);
      assert(close(fd) == 0);
   }
}

static void remove_fake_directory(void)
{
   size_t i;
   for (i = 0; i < sizeof(fake_nodes) / sizeof(fake_nodes[0]); i++) {
      char path[PATH_MAX];
      assert(snprintf(path, sizeof(path), "%s/%s", fake_directory,
                      fake_nodes[i].name) > 0);
      assert(unlink(path) == 0);
   }
   assert(rmdir(fake_directory) == 0);
}

static void test_discovery_and_lifetime(void)
{
   struct drm_darwin_syscalls syscalls = {
      .open = fake_open,
      .close = fake_close,
      .fstat = fake_fstat,
      .ioctl = fake_ioctl,
      .get_path = fake_get_path,
   };
   drmDevicePtr devices[2] = {0};
   drmDevicePtr device = NULL;
   drmVersionPtr version;
   uint64_t value = 99;
   int fd;
   int count;

   make_fake_directory();
   assert(drmDarwinSetSyscalls(&syscalls) == 0);
   assert(drmDarwinSetDeviceDirectory(fake_directory) == 0);

   count = drmGetDevices2(0, NULL, 0);
   assert(count == 2);
   count = drmGetDevices2(DRM_DEVICE_GET_PCI_REVISION, devices, 2);
   assert(count == 2);
   assert(devices[0] != NULL && devices[1] != NULL);
   assert(devices[0]->available_nodes == ((1 << DRM_NODE_PRIMARY) | (1 << DRM_NODE_RENDER)));
   assert(devices[1]->available_nodes == ((1 << DRM_NODE_PRIMARY) | (1 << DRM_NODE_RENDER)));
   assert(strcmp(devices[0]->nodes[DRM_NODE_PRIMARY],
                 "/tmp/does-not-need-to-be-real") != 0);
   assert(devices[0]->deviceinfo.pci->revision_id == 0x01);
   assert(nmx_pci_personality(devices[0]) == NMX_PERSONALITY_INTEL);
   assert(nmx_pci_personality(devices[1]) == NMX_PERSONALITY_AMD);
   assert(nmx_pci_identity_equal(devices[0], devices[0]) == 1);
   assert(drmDevicesEqual(devices[0], devices[1]) == 0);
   drmFreeDevices(devices, count);

   fd = fake_open("/tmp/unused/card0", O_RDONLY);
   assert(fd >= 0);
   version = drmGetVersion(fd);
   assert(version != NULL);
   assert(strcmp(version->name, "nmdrm") == 0);
   assert(version->name_len == 5 && version->date_len == 8);
   assert(version_probes > 0);
   drmFreeVersion(version);
   malformed_version = 1;
   errno = 0;
   assert(drmGetVersion(fd) == NULL && errno == EOVERFLOW);
   malformed_version = 0;
   assert(drmGetCap(fd, 0x5, &value) == 0 && value == 0);
   assert(drmGetCap(fd, DRM_CAP_SYNCOBJ_TIMELINE, &value) == -EINVAL);
   assert(drmGetNodeTypeFromFd(fd) == DRM_NODE_PRIMARY);
   assert(drmGetDevice2(fd, DRM_DEVICE_GET_PCI_REVISION, &device) == 0);
   assert(device != NULL && device->available_nodes == 5);
   drmFreeDevice(&device);
   assert(fake_close(fd) == 0);

   fd = fake_open("/tmp/unused/renderD129", O_RDONLY);
   assert(drmGetNodeTypeFromFd(fd) == DRM_NODE_RENDER);
   assert(drmGetDevice2(fd, 0, &device) == 0);
   assert(device->businfo.pci->bus == 3);
   assert(device->deviceinfo.pci->revision_id == 0xff);
   drmFreeDevice(&device);
   assert(fake_close(fd) == 0);

   /* An fd whose provider disappeared must not retain stale PCI identity. */
   fd = fake_open("/tmp/unused/card1", O_RDONLY);
   fake_nodes[1].gone = 1;
   assert(drmGetDevice2(fd, 0, &device) == -ENXIO);
   fake_nodes[1].gone = 0;
   assert(fake_close(fd) == 0);

   /* A regular fd and an invalid fd are not DRM identities. */
   fd = fake_open("/tmp/unused/card2", O_RDONLY);
   assert(drmGetDevice2(fd, 0, &device) == -EINVAL);
   assert(drmGetDevice2(-1, 0, &device) == -EINVAL);
   assert(drmGetDevices2(2, NULL, 0) == -EINVAL);
   assert(bad_ioctl_requests == 0);
   assert(drmDarwinSetSyscalls(NULL) == -EINVAL);

   remove_fake_directory();
   drmDarwinResetSyscalls();
   drmDarwinResetDeviceDirectory();
}

static void test_unmodified_mesa_kmd_probe(void)
{
   int fd = 400;
   enum intel_kmd_type type;

   strcpy(fake_driver, "nmdrm");
   type = intel_get_kmd_type(fd);
   assert(type == INTEL_KMD_TYPE_INVALID);
   strcpy(fake_driver, "i915");
   type = intel_get_kmd_type(fd);
   assert(type == INTEL_KMD_TYPE_I915);
   strcpy(fake_driver, "xe");
   type = intel_get_kmd_type(fd);
   assert(type == INTEL_KMD_TYPE_XE);
   strcpy(fake_driver, "nmdrm");
}

static void test_review_regressions(void)
{
   const struct drm_darwin_syscalls calls = {
      fake_open, fake_close, fake_fstat, fake_ioctl, fake_get_path
   };
   make_fake_directory();
   assert(drmDarwinSetSyscalls(&calls) == 0);
   assert(drmDarwinSetDeviceDirectory(fake_directory) == 0);
   drmDevicePtr d = NULL;
   swap_path = 1;
   assert(drmGetDevice2(400, DRM_DEVICE_GET_PCI_REVISION, &d) == -ENODEV && d == NULL);
   swap_path = 0;
   struct nm_drm_pciinfo_test old = fake_nodes[3].pci;
   fake_nodes[3].pci.vendor_id = 0x1002;
   drmDevicePtr devices[2] = {0};
   assert(drmGetDevices2(DRM_DEVICE_GET_PCI_REVISION, devices, 2) == -ENODEV);
   assert(devices[0] == NULL && devices[1] == NULL);
   assert(drmGetDevices2(0, NULL, 0) == -ENODEV); /* Count-only also compares full tuple. */
   fake_nodes[3].pci = old;
   fake_nodes[0].pci.dev = 32;
   assert(drmGetDevice2(400,0,&d) == -ENODEV && d == NULL);
   fake_nodes[0].pci.dev = 2;
   disappear_on_reopen = 1;
   assert(drmGetDevice2(400,0,&d) == -ENXIO && d == NULL);
   disappear_on_reopen = 0; fake_nodes[0].gone = 0;
   const char *bad_names[] = {"card+0", "card00"};
   for (size_t i=0;i<2;i++) {
      char path[PATH_MAX]; assert(snprintf(path,sizeof(path),"%s/%s",fake_directory,bad_names[i]) > 0);
      int fd = open(path,O_CREAT|O_WRONLY,0600); assert(fd >= 0 && close(fd) == 0);
   }
   assert(drmGetDevices2(0,NULL,0) == 2 && malformed_name_opens == 0);
   for (size_t i=0;i<2;i++) {
      char path[PATH_MAX]; assert(snprintf(path,sizeof(path),"%s/%s",fake_directory,bad_names[i]) > 0);
      assert(unlink(path) == 0);
   }
   /* A 6-byte struct with 5 bytes of fields has tail padding. */
   drmPciBusInfo a,b; memset(&a,0x11,sizeof(a)); memset(&b,0x22,sizeof(b));
   a.domain=b.domain=0; a.bus=b.bus=0; a.dev=b.dev=2; a.func=b.func=0;
   drmDevice da={.bustype=DRM_BUS_PCI,.businfo.pci=&a};
   drmDevice db={.bustype=DRM_BUS_PCI,.businfo.pci=&b};
   assert(drmDevicesEqual(&da,&db) == 1 && nmx_pci_identity_equal(&da,&db) == 1);
   remove_fake_directory(); drmDarwinResetSyscalls(); drmDarwinResetDeviceDirectory();
   puts("PASS review regressions: replacement-rdev/full-PCI, conflicting pair/count, dev32, disappearing provider, canonical names, tail padding");
}

#ifdef GA41_GEM_INTEGRATION
static void test_combined_cpu_subset(void)
{
   /* Reuse existing explicit transport fixture, not a second fake device model.
    * Standard public drmIoctl reaches the BSD dispatcher and upstream Intel
    * create/publish seam; only host memfd mapping is exercised. */
   const struct drm_darwin_syscalls calls = {
      fake_open, fake_close, fake_fstat, fake_ioctl, fake_get_path
   };
   assert(drmDarwinSetSyscalls(&calls) == 0);
   assert(gx_device_create(&cpu_ops, &gem_context, &gem_device) == 0);
   int fd = fake_open("/tmp/unused/card0", O_RDWR);
   assert(fd == 400 && gx_open(gem_device, &gem_file) == 0);
   assert(intel_get_kmd_type(fd) == INTEL_KMD_TYPE_INVALID);
   struct drm_i915_gem_create a = {.size = 4097};
   assert(drmIoctl(fd, 0xc010645bUL, &a) == 0 && a.size == 8192 && a.handle);
   struct gx_map_result map;
   assert(gx_map(gem_device, gem_file, a.handle, getpid(), 0, a.size, 1, &map) == 0);
   unsigned char *bytes = (void *)(uintptr_t)map.address;
   assert(bytes[0] == 0 && bytes[8191] == 0);
   bytes[0] = 19; bytes[8191] = 97;
   struct drm_gem_close close_arg = {.handle = a.handle};
   assert(drmIoctl(fd, 0x80086409UL, &close_arg) == 0);
   assert(drmIoctl(fd, 0x80086409UL, &close_arg) == -1 && errno == ENOENT);
   assert(gx_close(gem_device, gem_file) == 0 && fake_close(fd) == 0);
   assert(bytes[0] == 19 && bytes[8191] == 97);
   assert(gx_unmap(gem_device, gem_file, map.id) == 0);
   assert(gx_device_destroy(gem_device) == 0);
   gem_device = NULL;
   assert(gem_context.metas == 0 && gem_context.pages == 0 && gem_context.maps == 0);
   drmDarwinResetSyscalls();
   puts("PASS combined drmIoctl -> BSD dispatcher -> upstream create -> CPU memfd map; ANV KMD still rejects nmdrm");
}
#endif

int main(void)
{
    test_public_ioctl_bridge();
    test_discovery_and_lifetime();
    test_review_regressions();
#ifdef GA41_GEM_INTEGRATION
    test_combined_cpu_subset();
#endif
   /* The kmd test is run while the CPU fake transport remains installed. */
   {
      struct drm_darwin_syscalls syscalls = {
         .open = fake_open,
         .close = fake_close,
         .fstat = fake_fstat,
         .ioctl = fake_ioctl,
         .get_path = fake_get_path,
      };
      assert(drmDarwinSetSyscalls(&syscalls) == 0);
      test_unmodified_mesa_kmd_probe();
      drmDarwinResetSyscalls();
   }
   puts("drm-darwin CPU transport tests: PASS");
   return 0;
}
