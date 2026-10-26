/* CPU-only metadata and newly allocated descriptor observations; no MTLDevice,
 * driver loading, swizzling, compiler request, queue, shader or GPU work.
 * Execution on the target still requires separate user approval.
 */
#include "../metal/runtime-preflight.h"
#include <stdio.h>
int main(void) {
    @autoreleasepool {
        XeMetalObservation o=xe_observe_metal();
        printf("{\"pipeline_size\":%zu,\"attachment_size\":%zu,"
               "\"pipeline_offset\":%td,\"attachment_offset\":%td,"
               "\"pipeline_storage\":%zu,\"attachment_storage\":%zu,"
               "\"pipeline_alignment\":%zu,\"attachment_alignment\":%zu,"
               "\"selector_ok\":%d,\"encoding_ok\":%d,\"storage_ok\":%d,"
               "\"inline_pointer_ok\":%d,\"values_ok\":%d,"
               "\"status\":\"ABI_UNVERIFIED\"}\n",
               o.pipeline_size,o.attachment_size,o.pipeline_offset,o.attachment_offset,
               o.pipeline_storage,o.attachment_storage,o.pipeline_alignment,o.attachment_alignment,
               o.selector_ok,o.encoding_ok,o.storage_ok,o.inline_pointer_ok,o.values_ok);
    }
    return 0;
}
