// GA46: explicit unsupported boundary until the 25G83 request ABI is proved.
// Returning a guessed status or writing through unknown stack arguments is not
// error propagation. A corrupt compiler process must not resume after a signal.
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <syslog.h>

extern "C" __attribute__((visibility("default")))
const char *XECompilerAdapterStatus() {
    return "ABI_UNVERIFIED: LLVM3902 provider, request/reply/ICB helper ABI required";
}

// Pointer-return contract is present in donor disassembly. Null means that no
// compiler instance was created. Do not invoke the donor with a forged helper.
extern "C" __attribute__((visibility("default")))
void *MTLCompilerCreate(void *) {
    syslog(LOG_ERR, "xe-adapter: %s", XECompilerAdapterStatus());
    return nullptr;
}

[[noreturn]] static void unsupported(const char *entry) {
    syslog(LOG_ERR, "xe-adapter: %s refused: %s", entry, XECompilerAdapterStatus());
    std::abort(); // no handlers, longjmp, guessed error object or leaked LLVM state
}

// Register/stack positions were observed, but semantic arguments and return
// status were not established. Never dereference them or claim compilation.
extern "C" __attribute__((visibility("default")))
long MTLCompilerBuildRequestWithSerializedBitcode(void *, void *, void *, uint32_t,
        const char *, size_t, void *, void *, void *, void *, void *, void *, void *) {
    unsupported("MTLCompilerBuildRequestWithSerializedBitcode");
}
extern "C" __attribute__((visibility("default")))
void MTLCompilerDelete(void *) { unsupported("MTLCompilerDelete foreign instance"); }
extern "C" __attribute__((visibility("default")))
void MTLCompilerReleaseReply(void *) { unsupported("MTLCompilerReleaseReply foreign reply"); }
