/* GA4.5: read-only compiler/dyld ABI probe.
 * No GPU device, compiler request, shader, private write, or command queue.
 */
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
#include <mach-o/dyld.h>

static void note(const char *tag, const char *value) {
  printf("\"%s\": \"%s\",\n", tag, value ? value : "");
}
int main() {
  const char *want[] = {"GPUCompiler", "MTLCompiler", "libLLVM"};
  for (unsigned i = 0; i < _dyld_image_count(); i++) {
    const char *nm = _dyld_get_image_name(i);
    if (!nm) continue;
    for (unsigned j = 0; j < sizeof(want)/sizeof(want[0]); j++)
      if (strstr(nm, want[j])) printf("image[%u-%u]: %s\n", i, j, nm);
  }
  const char *paths[] = {
    "/System/Library/PrivateFrameworks/GPUCompiler.framework/Versions/32023/Libraries/libLLVM.dylib",
    "/System/Library/PrivateFrameworks/GPUCompiler.framework/Versions/Current/Libraries/libLLVM.dylib",
    "libLLVM.dylib",
    "/System/Library/PrivateFrameworks/MTLCompiler.framework/Versions/Current/MTLCompiler",
    "/System/Library/Extensions/AppleIntelGraphicsShared.bundle/Contents/MacOS/libMTLIGCCompilerPlugin.dylib"
  };
  for (unsigned i = 0; i < sizeof(paths)/sizeof(paths[0]); i++) {
    void *h = dlopen(paths[i], RTLD_NOW | RTLD_NOLOAD);
    printf("path[%u]: %s -> %s\n", i, paths[i], h ? "loaded" : "not-loaded");
    if (!h) h = dlopen(paths[i], RTLD_NOW | RTLD_LOCAL);
    if (h) {
      const char *syms[] = {"MTLCompilerBuildRequestWithSerializedBitcode",
                            "MTLCompilerBuildRequestWithOptions",
                            "getSerializedModule", "MTLCompilerCreate"};
      for (unsigned k = 0; k < sizeof(syms)/sizeof(syms[0]); k++)
        printf("  sym %s: %s\n", syms[k], dlsym(h, syms[k]) ? "present" : "absent");
      dlclose(h);
    }
  }
  note("status", "ABI_PROBE_READ_ONLY");
  return 0;
}
