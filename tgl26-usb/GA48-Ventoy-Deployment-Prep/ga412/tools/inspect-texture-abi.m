// CPU-only: load the installed user-mode image and inspect Objective-C metadata.
// Does not create a Metal device, resource, command queue, or command buffer.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <dlfcn.h>
#include <stdio.h>

int main(int argc, char **argv) { @autoreleasepool {
    if (argc != 2 && argc != 3) return 2;
    void *image = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!image) { fprintf(stderr, "IMAGE_LOAD_FAILED %s\n", dlerror()); return 2; }
    Class c = objc_getClass("MTLIGAccelTexture");
    if (!c) { fprintf(stderr, "CLASS_MISSING\n"); return 2; }
    NSMutableDictionary *methods = [NSMutableDictionary dictionary];
    for (NSString *name in @[@"getBytes:bytesPerRow:bytesPerImage:fromRegion:mipmapLevel:slice:",
                             @"lockForCPUAccess:readOnly:level:slice:",
                             @"resolveCCS:slice:waitForCompletion:", @"unlockForCPUAccess"]) {
        Method m = class_getInstanceMethod(c, sel_registerName(name.UTF8String));
        methods[name] = m ? @(method_getTypeEncoding(m)) : @"MISSING";
    }
    for (Class current = c; current; current = class_getSuperclass(current)) {
        unsigned count = 0;
        Method *list = class_copyMethodList(current, &count);
        for (unsigned i = 0; i < count; i++) {
            NSString *name = NSStringFromSelector(method_getName(list[i]));
            if ([name containsString:@"CPUAccess"] && !methods[name])
                methods[name] = @(method_getTypeEncoding(list[i]));
        }
        free(list);
    }
    Ivar info = class_getInstanceVariable(c, "m_Info");
    NSMutableDictionary *result = [@{@"class": NSStringFromClass(c), @"instance_size": @(class_getInstanceSize(c)),
        @"info_offset": info ? @(ivar_getOffset(info)) : @(-1),
        @"info_encoding": info ? @(ivar_getTypeEncoding(info)) : @"MISSING",
        @"methods": methods, @"GPU_commands_submitted": @NO} mutableCopy];
    if (argc == 3) {
        void *trace = dlopen(argv[2], RTLD_NOW | RTLD_LOCAL);
        int (*install)(void) = trace ? (int (*)(void))dlsym(trace, "ga412_trace_install") : NULL;
        char *(*manifest)(void) = trace ? (char *(*)(void))dlsym(trace, "ga412_trace_manifest") : NULL;
        if (!install || !manifest || !install()) { fprintf(stderr, "TRACER_ABI_REJECTED\n"); return 2; }
        char *raw = manifest();
        if (!raw) return 2;
        result[@"tracer"] = [NSJSONSerialization JSONObjectWithData:[@(raw) dataUsingEncoding:NSUTF8StringEncoding] options:0 error:nil];
        free(raw);
    }
    NSData *data = [NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];
    if (!data) return 2;
    fwrite(data.bytes, 1, data.length, stdout); putchar('\n');
    return 0;
} }
