/* SPDX-License-Identifier: MIT
 * Standard DRM syncobj request marshaling, not a fence implementation.
 * The native kernel must provide these ioctls; unsupported devices return
 * their real error. Never create CPU handles or report CPU signal completion.
 */
#include <xf86drm.h>
#include <errno.h>
#include <stdint.h>

static int sync_ioctl(int fd, unsigned long request, void *arg)
{
   return drmIoctl(fd, request, arg) == 0 ? 0 : -(errno ? errno : EIO);
}

int drmSyncobjCreate(int fd, uint32_t flags, uint32_t *handle)
{
   if (!handle) return -EINVAL;
   struct drm_syncobj_create arg = { .flags = flags };
   int ret = sync_ioctl(fd, DRM_IOCTL_SYNCOBJ_CREATE, &arg);
   if (!ret) *handle = arg.handle;
   return ret;
}

int drmSyncobjDestroy(int fd, uint32_t handle)
{
   struct drm_syncobj_destroy arg = { .handle = handle };
   return sync_ioctl(fd, DRM_IOCTL_SYNCOBJ_DESTROY, &arg);
}

static int sync_export(int fd, uint32_t handle, uint32_t flags, int *obj_fd)
{
   if (!obj_fd) return -EINVAL;
   struct drm_syncobj_handle arg = { .handle = handle, .flags = flags, .fd = -1 };
   int ret = sync_ioctl(fd, DRM_IOCTL_SYNCOBJ_HANDLE_TO_FD, &arg);
   if (!ret) *obj_fd = arg.fd;
   return ret;
}

int drmSyncobjHandleToFD(int fd, uint32_t handle, int *obj_fd)
{
   return sync_export(fd, handle, 0, obj_fd);
}

int drmSyncobjExportSyncFile(int fd, uint32_t handle, int *sync_file_fd)
{
   return sync_export(fd, handle, DRM_SYNCOBJ_HANDLE_TO_FD_FLAGS_EXPORT_SYNC_FILE, sync_file_fd);
}

int drmSyncobjFDToHandle(int fd, int obj_fd, uint32_t *handle)
{
   if (!handle) return -EINVAL;
   struct drm_syncobj_handle arg = { .fd = obj_fd };
   int ret = sync_ioctl(fd, DRM_IOCTL_SYNCOBJ_FD_TO_HANDLE, &arg);
   if (!ret) *handle = arg.handle;
   return ret;
}

int drmSyncobjImportSyncFile(int fd, uint32_t handle, int sync_file_fd)
{
   struct drm_syncobj_handle arg = {
      .handle = handle, .fd = sync_file_fd,
      .flags = DRM_SYNCOBJ_FD_TO_HANDLE_FLAGS_IMPORT_SYNC_FILE,
   };
   return sync_ioctl(fd, DRM_IOCTL_SYNCOBJ_FD_TO_HANDLE, &arg);
}

int drmSyncobjWait(int fd, uint32_t *handles, unsigned num_handles,
                   int64_t timeout_nsec, unsigned flags, uint32_t *first_signaled)
{
   struct drm_syncobj_wait arg = {
      .handles = (uintptr_t)handles, .count_handles = num_handles,
      .timeout_nsec = timeout_nsec, .flags = flags,
   };
   int ret = sync_ioctl(fd, DRM_IOCTL_SYNCOBJ_WAIT, &arg);
   if (!ret && first_signaled) *first_signaled = arg.first_signaled;
   return ret;
}

static int sync_array(int fd, unsigned long request, const uint32_t *handles, uint32_t count)
{
   struct drm_syncobj_array arg = { .handles = (uintptr_t)handles, .count_handles = count };
   return sync_ioctl(fd, request, &arg);
}

int drmSyncobjReset(int fd, const uint32_t *handles, uint32_t handle_count)
{
   return sync_array(fd, DRM_IOCTL_SYNCOBJ_RESET, handles, handle_count);
}

int drmSyncobjSignal(int fd, const uint32_t *handles, uint32_t handle_count)
{
   return sync_array(fd, DRM_IOCTL_SYNCOBJ_SIGNAL, handles, handle_count);
}

int drmSyncobjTimelineSignal(int fd, const uint32_t *handles, uint64_t *points, uint32_t count)
{
   struct drm_syncobj_timeline_array arg = {
      .handles = (uintptr_t)handles, .points = (uintptr_t)points, .count_handles = count,
   };
   return sync_ioctl(fd, DRM_IOCTL_SYNCOBJ_TIMELINE_SIGNAL, &arg);
}

int drmSyncobjTimelineWait(int fd, uint32_t *handles, uint64_t *points, unsigned count,
                         int64_t timeout_nsec, unsigned flags, uint32_t *first_signaled)
{
   struct drm_syncobj_timeline_wait arg = {
      .handles = (uintptr_t)handles, .points = (uintptr_t)points, .count_handles = count,
      .timeout_nsec = timeout_nsec, .flags = flags,
   };
   int ret = sync_ioctl(fd, DRM_IOCTL_SYNCOBJ_TIMELINE_WAIT, &arg);
   if (!ret && first_signaled) *first_signaled = arg.first_signaled;
   return ret;
}

int drmSyncobjQuery2(int fd, uint32_t *handles, uint64_t *points, uint32_t count, uint32_t flags)
{
   struct drm_syncobj_timeline_array arg = {
      .handles = (uintptr_t)handles, .points = (uintptr_t)points,
      .count_handles = count, .flags = flags,
   };
   return sync_ioctl(fd, DRM_IOCTL_SYNCOBJ_QUERY, &arg);
}

int drmSyncobjQuery(int fd, uint32_t *handles, uint64_t *points, uint32_t count)
{
   return drmSyncobjQuery2(fd, handles, points, count, 0);
}

int drmSyncobjTransfer(int fd, uint32_t dst_handle, uint64_t dst_point,
                       uint32_t src_handle, uint64_t src_point, uint32_t flags)
{
   struct drm_syncobj_transfer arg = {
      .src_handle = src_handle, .dst_handle = dst_handle,
      .src_point = src_point, .dst_point = dst_point, .flags = flags,
   };
   return sync_ioctl(fd, DRM_IOCTL_SYNCOBJ_TRANSFER, &arg);
}
