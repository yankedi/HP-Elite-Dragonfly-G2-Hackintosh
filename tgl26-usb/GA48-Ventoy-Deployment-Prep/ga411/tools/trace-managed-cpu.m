// Reuse the historical getBytes/resolve observer unchanged, adding lock observation.
// All hooks call the original exactly once; no private resolve is initiated here.
#include "../../ga410/tools/trace-texture-cpu.m"
static IMP originalLock;
static void *lockObserved(id t,SEL s,void *seed,signed char readOnly,unsigned level,unsigned slice) {
    state(t,"lockForCPUAccess-enter");
    void *result=((void *(*)(id,SEL,void*,signed char,unsigned,unsigned))originalLock)(t,s,seed,readOnly,level,slice);
    fprintf(stderr,"CPU_TRACE lockForCPUAccess_result=%p readOnly=%d level=%u slice=%u\n",result,readOnly,level,slice);
    state(t,"lockForCPUAccess-exit");
    return result;
}
__attribute__((constructor)) static void installLockObserver(void) {
    Class c=objc_getClass("MTLIGAccelTexture");
    Method m=class_getInstanceMethod(c,sel_registerName("lockForCPUAccess:readOnly:level:slice:"));
    // Match the captured 16.0.32 ABI; reject an unknown method signature.
    NSMethodSignature *sig=m?[NSMethodSignature signatureWithObjCTypes:method_getTypeEncoding(m)]:nil;
    if (!originalGet || !sig || sig.numberOfArguments!=6 || strcmp(sig.methodReturnType,"^v") ||
        strcmp([sig getArgumentTypeAtIndex:2],"^I") || strcmp([sig getArgumentTypeAtIndex:3],"c") ||
        strcmp([sig getArgumentTypeAtIndex:4],"I") || strcmp([sig getArgumentTypeAtIndex:5],"I")) {
        fprintf(stderr,"CPU_TRACE lock ABI not verified: %s\n",m?method_getTypeEncoding(m):"missing"); return;
    }
    originalLock=method_setImplementation(m,(IMP)lockObserved);
    fprintf(stderr,"CPU_TRACE lock installed ABI=%s\n",method_getTypeEncoding(m));
}
