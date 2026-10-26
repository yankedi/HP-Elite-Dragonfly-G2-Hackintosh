// A same-image LLVM C-API byte boundary. No external LLVM/C++ object is accepted.
#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <dlfcn.h>
#include <string>
#include <vector>

namespace xe {
class BitcodeImage {
    void *image_ = nullptr;
    void *owner_ = nullptr;
    template<class T> bool bind(T &out, const char *name) {
        void *p = dlsym(image_, name);
        Dl_info info{};
        if (!p || !dladdr(p, &info) || !info.dli_fbase) return false;
        if (!owner_) owner_ = info.dli_fbase;
        if (owner_ != info.dli_fbase) return false;
        out = reinterpret_cast<T>(p);
        return true;
    }
    void *(*contextCreate_)() = nullptr;
    void (*contextDispose_)(void *) = nullptr;
    void *(*bufferCopy_)(const char *, size_t, const char *) = nullptr;
    int (*parse_)(void *, void *, void **, char **) = nullptr;
    void (*moduleDispose_)(void *) = nullptr;
    void (*bufferDispose_)(void *) = nullptr;
    void (*messageDispose_)(char *) = nullptr;
    void *(*write_)(void *) = nullptr;
    const char *(*start_)(void *) = nullptr;
    size_t (*size_)(void *) = nullptr;
public:
    static constexpr size_t limit = 64u << 20;
    explicit BitcodeImage(const char *installName) {
        // Exact install name only. Shared-cache paths need not exist as files.
        // No bare-name lookup, RTLD_DEFAULT, RTLD_GLOBAL, or image-byte scan.
        image_ = dlopen(installName, RTLD_NOW | RTLD_LOCAL);
        if (!image_) return;
        bool ok = bind(contextCreate_, "LLVMContextCreate") &&
                  bind(contextDispose_, "LLVMContextDispose") &&
                  bind(bufferCopy_, "LLVMCreateMemoryBufferWithMemoryRangeCopy") &&
                  bind(parse_, "LLVMParseBitcodeInContext") &&
                  bind(moduleDispose_, "LLVMDisposeModule") &&
                  bind(bufferDispose_, "LLVMDisposeMemoryBuffer") &&
                  bind(messageDispose_, "LLVMDisposeMessage") &&
                  bind(write_, "LLVMWriteBitcodeToMemoryBuffer") &&
                  bind(start_, "LLVMGetBufferStart") && bind(size_, "LLVMGetBufferSize");
        if (!ok) { dlclose(image_); image_ = nullptr; }
    }
    ~BitcodeImage() { if (image_) dlclose(image_); }
    BitcodeImage(const BitcodeImage &) = delete;
    BitcodeImage &operator=(const BitcodeImage &) = delete;
    bool ready() const { return image_ != nullptr; }

    bool roundTrip(const void *bytes, size_t size, std::vector<uint8_t> &out,
                   std::string &error) const {
        out.clear(); error.clear();
        if (!ready()) { error = "same-image LLVM C API unavailable"; return false; }
        if (!bytes || size < 4 || size > limit) { error = "invalid bitcode extent"; return false; }
        const auto *p = static_cast<const uint8_t *>(bytes);
        const uint8_t raw[] = {'B','C',0xc0,0xde}, wrapper[] = {0xde,0xc0,0x17,0x0b};
        if (memcmp(p, raw, 4) && memcmp(p, wrapper, 4)) { error = "invalid bitcode magic"; return false; }
        // Fresh context for every request; no global LLVM context or mutable
        // module is shared between threads. Objects die before their image.
        struct Request {
            const BitcodeImage &api;
            void *context = nullptr, *input = nullptr, *module = nullptr, *output = nullptr;
            char *message = nullptr;
            ~Request() {
                if (output) api.bufferDispose_(output);
                if (module) api.moduleDispose_(module);
                if (input) api.bufferDispose_(input);
                if (message) api.messageDispose_(message);
                if (context) api.contextDispose_(context);
            }
        } r{*this};
        r.context = contextCreate_();
        if (!r.context) { error = "context allocation failed"; return false; }
        r.input = bufferCopy_(reinterpret_cast<const char *>(p), size, "ga46-owned");
        if (!r.input) { error = "input allocation failed"; return false; }
        if (parse_(r.context, r.input, &r.module, &r.message) || !r.module) {
            error = r.message ? r.message : "bitcode parse failed"; return false;
        }
        r.output = write_(r.module);
        size_t n = r.output ? size_(r.output) : 0;
        const char *data = r.output ? start_(r.output) : nullptr;
        if (!data || !n || n > limit) { error = "invalid serialized extent"; return false; }
        out.assign(data, data + n);
        return true;
    }
};
} // namespace xe
