/* GA40 private offline research adapter. Not a Metal plugin or hardware driver. */
#ifndef GA40_NM_BACKEND_H
#define GA40_NM_BACKEND_H
#include <stddef.h>
#include <stdint.h>

typedef struct nm_device nm_device;
typedef uint64_t nm_handle;
enum nm_kind { NM_CPU_MODEL = 1, NM_LAVAPIPE = 2, NM_INTEL_HARDWARE = 3 };
enum nm_result { NM_OK, NM_INVALID, NM_UNSUPPORTED, NM_NOMEM, NM_BUSY,
                 NM_SYNC_FAILED, NM_BAD_STATE, NM_BACKEND_FAILED };
enum nm_cap { NM_CAP_BUFFER = 1, NM_CAP_IMAGE = 2, NM_CAP_TRANSFER = 4,
              NM_CAP_IOSURFACE = 8, NM_CAP_NVIDIA_SASS = 16,
              NM_CAP_INTEL_SUBMIT = 32, NM_CAP_METAL_DEVICE = 64 };
enum nm_fault { NM_FAULT_NONE, NM_FAULT_ALLOCATION, NM_FAULT_SUBMIT,
                NM_FAULT_WAIT };
typedef struct { enum nm_kind kind; uint32_t capabilities; const char *name;
                 int real_gpu; } nm_info;

int nm_open(enum nm_kind kind, uint32_t required, nm_device **out);
int nm_info_get(nm_device *d, nm_info *out);
int nm_close(nm_device *d); /* BUSY until every command/resource is released. */
int nm_fault_once(nm_device *d, enum nm_fault fault); /* Test injection, explicitly named. */
int nm_buffer_create(nm_device *d, size_t size, nm_handle *out);
int nm_image_create(nm_device *d, uint32_t width, uint32_t height, nm_handle *out);
int nm_resource_destroy(nm_device *d, nm_handle resource);
int nm_buffer_write(nm_device *d, nm_handle resource, size_t offset, const void *data, size_t size);
int nm_buffer_read(nm_device *d, nm_handle resource, size_t offset, void *data, size_t size);
int nm_command_create(nm_device *d, nm_handle *out);
int nm_command_fill(nm_device *d, nm_handle command, nm_handle dst, size_t offset, size_t size, uint32_t value);
int nm_command_copy(nm_device *d, nm_handle command, nm_handle src, nm_handle dst, size_t size);
int nm_command_end(nm_device *d, nm_handle command);
int nm_command_submit(nm_device *d, nm_handle command);
int nm_command_wait(nm_device *d, nm_handle command, uint64_t timeout_ns);
int nm_command_destroy(nm_device *d, nm_handle command);
const char *nm_result_string(int result);
#endif
