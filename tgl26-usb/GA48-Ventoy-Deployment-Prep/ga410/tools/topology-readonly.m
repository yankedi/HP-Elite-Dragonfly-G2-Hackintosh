// Observe the topology exposed to this Metal client; no GPU workload or writes.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static uint32_t field(const uint8_t *p,size_t off) {
    uint32_t value; memcpy(&value,p+off,4); return value;
}

int main(int argc,char **argv) { @autoreleasepool {
    alarm(20); setbuf(stdout,NULL);
    BOOL expect80=argc==2 && !strcmp(argv[1],"--expect-80eu");
    BOOL raw=argc==2 && !strcmp(argv[1],"--raw");
    if(argc>2 || (argc==2 && !expect80 && !raw)) return 2;
    id<MTLDevice> device=MTLCreateSystemDefaultDevice();
    if (!device) return 1;
    Class cls=object_getClass(device);
    printf("device=%s class=%s registry=%llu\n",device.name.UTF8String,class_getName(cls),device.registryID);
    Ivar info=class_getInstanceVariable(cls,"hwInfo");
    if (!info) { puts("hwInfo unavailable"); return 2; }
    ptrdiff_t offset=ivar_getOffset(info);
    size_t end=class_getInstanceSize(cls);
    for(Class c=cls;c;c=class_getSuperclass(c)) {
        unsigned count=0; Ivar *ivars=class_copyIvarList(c,&count);
        for(unsigned i=0;i<count;++i) {
            ptrdiff_t next=ivar_getOffset(ivars[i]);
            if(next>offset && (size_t)next<end) end=next;
        }
        free(ivars);
    }
    const char *encoding=ivar_getTypeEncoding(info);
    const char *prefix="{IntelHwInfoRec=\"hwCapsInfo\"{_IntelHwCapsInfo=\"fRevisionID\"I\"fRevisionID_PCH\"I\"fDeviceID\"I\"fDeviceID_PCH\"I\"fGpuSku\"I\"fExecutionUnitCount\"I\"fPixelShaderMinThreads\"I\"fPoshShaderMaxThreads\"I\"fVertexShaderMaxThreads\"I\"fHullShaderMaxThreads\"I\"fDomainShaderMaxThreads\"I\"fGeometryShaderMaxThreads\"I\"fPixelShaderMaxThreads\"I\"fPixelShaderMinThreadsReserved\"I\"fMaxPixelShaderDispatchers\"I\"fPixelShaderDispatchers\"I\"fMaxFrequencyInMhz\"I\"fMinFrequencyInMhz\"I\"fNumSubSlices\"I\"fNumSlices\"I\"fL3CacheSizeInKb\"I\"fL3BankCount\"I\"fMaxFillRate\"I\"fMaxEuPerSubSlice\"I";
    if(offset<0 || end<(size_t)offset || end-offset<0x60 || !encoding || strncmp(encoding,prefix,strlen(prefix))) {
        puts("hwInfo ABI mismatch"); return 2;
    }
    printf("hwInfo offset=%td extent=%zu\n",offset,end-offset);
    const uint8_t *p=(const uint8_t*)(__bridge const void*)device+offset;
    printf("fDeviceID=0x%08x fGpuSku=%u fExecutionUnitCount=%u fNumSubSlices=%u fNumSlices=%u fMaxEuPerSubSlice=%u fL3BankCount=%u fPixelShaderDispatchers=%u\n",
           field(p,0x08),field(p,0x10),field(p,0x14),field(p,0x48),field(p,0x4c),field(p,0x5c),field(p,0x54),field(p,0x3c));
    if(raw) for(size_t i=0;i+4<=end-offset && i<0x80;i+=4) {
        printf("hwInfo+0x%03zx = 0x%08x (%u)\n",i,field(p,i),field(p,i));
    }
    if(expect80 && (field(p,0x08)!=0x9a498086 || field(p,0x14)!=80 || field(p,0x48)!=10 ||
                   field(p,0x4c)!=1 || field(p,0x5c)!=8 || field(p,0x54)!=8 || field(p,0x3c)!=5)) {
        puts("EXPECTED_80EU_TOPOLOGY_MISMATCH"); return 1;
    }
    if(expect80) puts("EXPECTED_80EU_TOPOLOGY_OK");
    return 0;
} }
