/* Read-only symbol observations; never loads the donor/plugin or creates an
 * LLVM context/compiler/GPU. Target execution requires separate approval.
 * Default is NOLOAD; --open-system-images runs system image initializers.
 */
#include <cstdio>
#include <cstring>
#include <dlfcn.h>

static void quote(const char *s) {
    putchar('"');
    for (const unsigned char *p=(const unsigned char *)(s?s:"");*p;p++) {
        if (*p=='"' || *p=='\\') {putchar('\\');putchar(*p);}
        else if (*p<32) printf("\\u%04x",*p);
        else putchar(*p);
    }
    putchar('"');
}
int main(int argc,char **argv) {
    bool open=argc==2 && !strcmp(argv[1],"--open-system-images");
    if (argc>1 && !open) return 2;
    const char *paths[]={
      "/System/Library/PrivateFrameworks/GPUCompiler.framework/Versions/32023/Libraries/libLLVM.dylib",
      "/System/Library/PrivateFrameworks/MTLCompiler.framework/Versions/Current/MTLCompiler"};
    const char *symbols[]={"LLVMContextCreate","LLVMContextDispose",
      "LLVMCreateMemoryBufferWithMemoryRangeCopy","LLVMParseBitcodeInContext",
      "LLVMDisposeModule","LLVMDisposeMemoryBuffer","LLVMDisposeMessage",
      "LLVMWriteBitcodeToMemoryBuffer","LLVMGetBufferStart","LLVMGetBufferSize",
      "MTLCodeGenServiceBuildRequest","MTLCodeGenServiceCreate",
      "MTLCompilerBuildRequestWithOptions","MTLCompilerBuildRequestWithSerializedBitcode"};
    for(const char *path:paths) {
        dlerror();
        void *h=dlopen(path,RTLD_NOW|RTLD_LOCAL|(open?0:RTLD_NOLOAD));
        printf("{\"path\":");quote(path);
        printf(",\"mode\":\"%s\",\"loaded\":%s,\"error\":",open?"open-system-images":"NOLOAD",h?"true":"false");
        quote(h?"":dlerror());printf(",\"symbols\":[");
        bool first=true;
        if(h) for(const char *name:symbols) {
            void *p=dlsym(h,name);Dl_info info{};
            if(!first) putchar(',');first=false;
            printf("{\"name\":");quote(name);
            printf(",\"present\":%s,\"provider\":",p?"true":"false");
            quote(p && dladdr(p,&info)?info.dli_fname:"");printf("}");
        }
        puts("],\"status\":\"RUNTIME_SYMBOL_OBSERVATION_ONLY\"}");
        if(h)dlclose(h);
    }
    return 0;
}
