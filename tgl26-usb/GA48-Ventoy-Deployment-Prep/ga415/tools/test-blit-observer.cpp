// CPU shim contract test: transparent forwarding, immutable inputs, strict budgets.
// This does not certify kernel runtime ABI or GPU pixel correctness.
#include <array>
#include <cassert>
#include <cstdarg>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
using mach_vm_address_t = uintptr_t;
static std::vector<std::string> lines;
static void IOLog(const char *format, ...) {
    char buffer[2048]; va_list args; va_start(args, format);
    int size = vsnprintf(buffer, sizeof(buffer), format, args); va_end(args);
    assert(size > 0 && size < static_cast<int>(sizeof(buffer)));
    lines.emplace_back(buffer);
}
#define FunctionCast(wrapper, address) reinterpret_cast<decltype(&wrapper)>(address)
#include "../kernel/ga415_blit_observer.hpp"

static unsigned sourceCalls = 0, fastCalls = 0, threeCalls = 0;
static void *wantContext, *wantParams, *wantRects, *wantWA;
static void source(void *ctx, void *params, void *rects, void *wa) {
    assert(ctx == wantContext && params == wantParams && rects == wantRects && wa == wantWA);
    sourceCalls++;
}
static void fast(void *ctx, void *params, void *rects, void *wa) {
    assert(ctx == wantContext && params == wantParams && rects == wantRects && wa == wantWA);
    fastCalls++;
}
static void three(void *ctx, void *params, void *rects) {
    assert(ctx == wantContext && params == wantParams && rects == wantRects); threeCalls++;
}
static void put(std::array<uint8_t, 0xc0> &p, size_t offset, uint32_t value) {
    memcpy(p.data() + offset, &value, sizeof(value));
}

int main() {
    std::array<uint8_t, 0xc0> params{};
    std::array<uint32_t, 8> rect = {0, 0, 0x44208000U, 0x42c80000U, 0, 0, 0x44208000U, 0x42c80000U};
    struct Vector { uint64_t count, capacity; void *data; } vector = {1, 1, rect.data()};
    static_assert(offsetof(Vector, data) == 0x10);
    int context = 1, wa = 2;
    wantContext = &context; wantWA = &wa; wantParams = params.data(); wantRects = &vector;
    gGa415OrgSourceCopy = reinterpret_cast<uintptr_t>(&source);
    gGa415OrgFastCopy = reinterpret_cast<uintptr_t>(&fast);
    gGa415Org3D = reinterpret_cast<uintptr_t>(&three);
    // Disabled hook preserves forwarding with zero observations.
    ga415ObsSourceCopy(&context, params.data(), &vector, &wa);
    assert(sourceCalls == 1 && lines.empty());
    gGa415ObsEnabled = true;
    put(params, 0x08, 2576); put(params, 0x50, 2816); params[0x54] = 1; params[0xa0] = 4;
    auto copy = params; auto rectCopy = rect;
    for (unsigned i = 0; i < 200; i++) {
        ga415ObsSourceCopy(&context, params.data(), &vector, &wa);
        ga415ObsFastCopy(&context, params.data(), &vector, &wa);
        ga415Obs3D(&context, params.data(), &vector);
    }
    assert(params == copy && rect == rectCopy && vector.count == 1 && vector.data == rect.data());
    assert(sourceCalls == 201 && fastCalls == 200 && threeCalls == 200 && lines.size() == 96);
    assert(lines.front().find("kind=COPY2D cls=P n=1") != std::string::npos);
    assert(lines.front().find("sp=2576 dp=2816 st=0 dt=1") != std::string::npos);
    // Non-probe unaligned then aligned work cannot exceed the other two budgets.
    rect[2] = rect[6] = 0x44000000U;
    put(params, 0x08, 2064); put(params, 0x50, 2048);
    for (unsigned i = 0; i < 100; i++) ga415Obs3D(&context, params.data(), &vector);
    assert(lines.size() == 112);
    put(params, 0x08, 2048);
    for (unsigned i = 0; i < 100; i++) ga415Obs3D(&context, params.data(), &vector);
    assert(lines.size() == 128 && gGa415ObsGeneral == 16 && gGa415ObsUnaligned == 16 && gGa415ObsProbe == 96);
    // Null optional observation inputs still reach the original call exactly once.
    wantParams = nullptr; wantRects = nullptr;
    ga415ObsSourceCopy(&context, nullptr, nullptr, &wa);
    assert(sourceCalls == 202 && lines.size() == 128);
    puts("CPU_OBSERVER_CONTRACT_PASS forwarding=802 max_records=128 mutations=0 kernel_or_GPU_run=0");
}
