/* SPDX-License-Identifier: MIT
 * CPU UAPI marshaling fault injection only. No syncobj or GPU is created. */
#include <xf86drm.h>
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>

static int fail, calls;
static unsigned long expected;
static uint32_t handles[] = {7, 9};
static uint64_t points[] = {UINT64_C(0x123456789abcdef0), 0x100000001};

int drmIoctl(int fd, unsigned long request, void *arg)
{
   assert(fd == 42 && request == expected);
   calls++;
   if (request == DRM_IOCTL_SYNCOBJ_CREATE) {
      struct drm_syncobj_create *a = arg;
      assert(a->flags == DRM_SYNCOBJ_CREATE_SIGNALED && !a->handle);
      a->handle = 99;
   } else if (request == DRM_IOCTL_SYNCOBJ_HANDLE_TO_FD) {
      struct drm_syncobj_handle *a = arg;
      assert(a->handle == 7 && a->fd == -1 && !a->pad && !a->point);
      assert(a->flags == DRM_SYNCOBJ_HANDLE_TO_FD_FLAGS_EXPORT_SYNC_FILE);
      a->fd = 81;
   } else if (request == DRM_IOCTL_SYNCOBJ_FD_TO_HANDLE) {
      struct drm_syncobj_handle *a = arg;
      assert(a->fd == 81 && a->flags == 0 && !a->pad && !a->point && !a->handle);
      a->handle = 44;
   } else if (request == DRM_IOCTL_SYNCOBJ_TIMELINE_WAIT) {
      struct drm_syncobj_timeline_wait *a = arg;
      assert(a->handles == (uintptr_t)handles && a->points == (uintptr_t)points);
      assert(a->count_handles == 2 && a->timeout_nsec == INT64_C(0x123456780001));
      assert(a->flags == DRM_SYNCOBJ_WAIT_FLAGS_WAIT_ALL && !a->pad && !a->deadline_nsec);
      a->first_signaled = 1;
   } else if (request == DRM_IOCTL_SYNCOBJ_TRANSFER) {
      struct drm_syncobj_transfer *a = arg;
      assert(a->src_handle == 7 && a->src_point == points[0]);
      assert(a->dst_handle == 9 && a->dst_point == points[1] && !a->flags && !a->pad);
   } else if (request == DRM_IOCTL_SYNCOBJ_SIGNAL) {
      struct drm_syncobj_array *a = arg;
      assert(a->handles == (uintptr_t)handles && a->count_handles == 2 && !a->pad);
   } else assert(0);
   if (fail) { errno = fail; return -1; }
   return 0;
}

int main(void)
{
   uint32_t handle = 0xaabbccdd, first = 0x11223344;
   int fd = -37;
   expected = DRM_IOCTL_SYNCOBJ_CREATE; fail = EOPNOTSUPP;
   assert(drmSyncobjCreate(42, DRM_SYNCOBJ_CREATE_SIGNALED, &handle) == -EOPNOTSUPP);
   assert(handle == 0xaabbccdd && calls == 1);
   assert(drmSyncobjCreate(42, 0, NULL) == -EINVAL && calls == 1);
   fail = 0;
   assert(!drmSyncobjCreate(42, DRM_SYNCOBJ_CREATE_SIGNALED, &handle) && handle == 99);
   expected = DRM_IOCTL_SYNCOBJ_HANDLE_TO_FD; fail = EBADF;
   assert(drmSyncobjExportSyncFile(42, 7, &fd) == -EBADF && fd == -37);
   fail = 0; assert(!drmSyncobjExportSyncFile(42, 7, &fd) && fd == 81);
   expected = DRM_IOCTL_SYNCOBJ_FD_TO_HANDLE; fail = ENOTTY;
   assert(drmSyncobjFDToHandle(42, 81, &handle) == -ENOTTY && handle == 99);
   fail = 0; assert(!drmSyncobjFDToHandle(42, 81, &handle) && handle == 44);
   expected = DRM_IOCTL_SYNCOBJ_TIMELINE_WAIT; fail = ETIMEDOUT;
   assert(drmSyncobjTimelineWait(42, handles, points, 2, INT64_C(0x123456780001),
       DRM_SYNCOBJ_WAIT_FLAGS_WAIT_ALL, &first) == -ETIMEDOUT && first == 0x11223344);
   fail = 0;
   assert(!drmSyncobjTimelineWait(42, handles, points, 2, INT64_C(0x123456780001),
       DRM_SYNCOBJ_WAIT_FLAGS_WAIT_ALL, &first) && first == 1);
   expected = DRM_IOCTL_SYNCOBJ_TRANSFER;
   assert(!drmSyncobjTransfer(42, 9, points[1], 7, points[0], 0));
   expected = DRM_IOCTL_SYNCOBJ_SIGNAL; fail = EOPNOTSUPP;
   assert(drmSyncobjSignal(42, handles, 2) == -EOPNOTSUPP);
   puts("PASS UAPI error/publication/64-bit pointer-point-timeout contracts; CPU injection only");
   return 0;
}
