// Read display identity and the real Screen Recording permission decision.
#include <ApplicationServices/ApplicationServices.h>
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv) {
    CGDirectDisplayID ids[16];
    uint32_t count = 0;
    CGError error = CGGetOnlineDisplayList(16, ids, &count);
    printf("online_error=%d count=%u preflight_screen_capture=%d\n",
           error, count, CGPreflightScreenCaptureAccess());
    for (uint32_t i = 0; i < count; ++i) {
        CGRect bounds = CGDisplayBounds(ids[i]);
        printf("display=%u main=%d active=%d builtin=%d pixels=%zux%zu bounds=%.0fx%.0f\n",
               ids[i], CGDisplayIsMain(ids[i]), CGDisplayIsActive(ids[i]),
               CGDisplayIsBuiltin(ids[i]), CGDisplayPixelsWide(ids[i]),
               CGDisplayPixelsHigh(ids[i]), bounds.size.width, bounds.size.height);
    }
    if (argc == 2 && strcmp(argv[1], "--request") == 0)
        printf("request_screen_capture=%d\n", CGRequestScreenCaptureAccess());
    return error != kCGErrorSuccess;
}
