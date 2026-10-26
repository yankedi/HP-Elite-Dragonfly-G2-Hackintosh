// GA46: serialization is a byte boundary, not a cross-version C++ ABI shim.
// No legacy LLVM symbol is faked or silently accepted. The old C++ ABI exports
// have been removed: donor binding must fail until a real 3902 provider exists.
#include "../compiler/owned-bitcode.hpp"
#include <cstdlib>
#include <cstring>
#include <pthread.h>

namespace {
pthread_once_t once = PTHREAD_ONCE_INIT;
xe::BitcodeImage *image;
void initialize() {
    // Pinned by existing 25G83 GPUCompiler LC_LOAD_DYLIB evidence. No ambiguous
    // Current/framework/bare-name fallback. Process lifetime keeps image pinned.
    static xe::BitcodeImage llvm(
        "/System/Library/PrivateFrameworks/GPUCompiler.framework/Versions/32023/Libraries/libLLVM.dylib");
    image = &llvm;
}
}
extern "C" __attribute__((visibility("default")))
const char *XEBridgeStatus() {
    return "ABI_UNVERIFIED: current-bitcode roundtrip only; not MTL3902 downgrade";
}
// Project-owned diagnostic ABI: 0 success, 1 unavailable/invalid; malloc buffer
// owned by caller, freed only with XEBridgeFreeBytes. Never accepts Module*.
extern "C" __attribute__((visibility("default")))
int XEBridgeRoundTripCurrentBitcode(const void *bytes, size_t n, void **out, size_t *outSize) {
    if (!out || !outSize) return 1;
    *out = nullptr; *outSize = 0;
    pthread_once(&once, initialize);
    std::vector<uint8_t> data;
    std::string error;
    if (!image || !image->roundTrip(bytes, n, data, error)) return 1;
    void *copy = std::malloc(data.size());
    if (!copy) return 1;
    std::memcpy(copy, data.data(), data.size());
    *out = copy; *outSize = data.size();
    return 0;
}
extern "C" __attribute__((visibility("default")))
void XEBridgeFreeBytes(void *p) { std::free(p); }
