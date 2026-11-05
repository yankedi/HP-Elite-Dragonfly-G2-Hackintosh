#ifndef HP_REPAIR_POLICY_HPP
#define HP_REPAIR_POLICY_HPP

#include <stdint.h>

// Shared by the kernel hooks and the host-side boundary regression runner.
// TGL's rect-list emitter batches at most this many bytes, including its
// surface/binding/vertex state. Leave headroom in a 4KiB Tahoe pool slot.
namespace HpTglRepair {
// Prefix for the donor's already-sampled CS_CHICKEN1 stack local. An aligned
// single 64-bit x86 store publishes valid bit32 + 32-bit value together. This
// is a last-writer snapshot, NOT a context or per-engine-call association.
inline unsigned existingReadbackPrefix(uint8_t *code, uint64_t state) {
    const uint8_t bytes[] = {
        0x9c,0x50,0x52,0x8b,0x45,0xc4,
        0x48,0xba,0,0,0,0,1,0,0,0,0x48,0x09,0xd0,
        0x48,0xba,0,0,0,0,0,0,0,0,0x48,0x89,0x02,0x5a,0x58,0x9d
    };
    for (unsigned i=0;i<sizeof(bytes);++i) code[i]=bytes[i];
    for (unsigned i=0;i<8;++i) code[21+i]=uint8_t(state>>(8*i));
    return sizeof(bytes);
}
// Execute inside the donor's force-woken engine initialization, before it
// enables/submits contexts. Preserve every register and incoming flags.
// ROW_CHICKEN2 is an engine WA on TGL (not a context-image modification).
// The MCR multicast bit is temporary; restore the complete original selector.
// State: selector-before, row-before, row-after, render-ack, selector-after, calls.
inline unsigned nativeRowPrefix(uint8_t *code, uint64_t state) {
    const uint8_t bytes[] = {
        0x9c,0x51,0x52,
        0x48,0xba,0,0,0,0,0,0,0,0,
        0x8b,0x88,0xdc,0x0f,0,0,0x89,0x0a,
        0x81,0xc9,0,0,0,0x80,0x89,0x88,0xdc,0x0f,0,0,
        0x8b,0x88,0xf4,0xe4,0,0,0x89,0x4a,4,
        0xc7,0x80,0xf4,0xe4,0,0,0,0xc1,0,0xc1,
        0x8b,0x88,0xf4,0xe4,0,0,0x89,0x4a,8,
        0x8b,0x88,0x84,0x0d,0,0,0x89,0x4a,12,
        0x8b,0x0a,0x89,0x88,0xdc,0x0f,0,0,
        0x8b,0x88,0xdc,0x0f,0,0,0x89,0x4a,16,
        0x83,0x42,20,1,0x5a,0x59,0x9d,
    };
    for (unsigned i=0;i<sizeof(bytes);++i) code[i]=bytes[i];
    for (unsigned i=0;i<8;++i) code[5+i]=uint8_t(state>>(8*i));
    return sizeof(bytes);
}

constexpr uint32_t RectChunkBytes = 0xc00;
constexpr uint32_t PageBytes = 0x1000;

// resolve_ccs puts state at pageEnd-align64(0x100+72*rectangles).
// Reserve the whole usable page instead of the donor's two-DWORD probe.
constexpr uint32_t CCSMaxRects = 32;
constexpr uint32_t CCSResumeOffset = 0xfc0;
constexpr uint32_t CCSPageDwords = 0xff8 / 4;
inline uint32_t ccsStateOffset(uint32_t count) {
    return count && count <= CCSMaxRects ? PageBytes - ((0x100+72*count+63)&~63U) : 0;
}
inline bool ccsLayout(uint64_t base, uint64_t commandEnd, uint32_t count) {
    auto state=ccsStateOffset(count);
    return base && !(base&0xfff) && state && commandEnd>=base &&
        commandEnd-base<=state && !(commandEnd&3) &&
        ((commandEnd-base+7)&~7ULL)+12<=state &&
        state+0xb0+72*count<=CCSResumeOffset;
}
inline void ccsFailureGuard(uint8_t (&code)[18], uint64_t cleanup) {
    const uint8_t head[]={0x84,0xc0,0x75,0x0e,0xff,0x25,0,0,0,0};
    for(unsigned i=0;i<sizeof(head);++i) code[i]=head[i];
    for(unsigned i=0;i<8;++i) code[10+i]=uint8_t(cleanup>>(8*i));
}

inline bool validPlane(uint64_t rowBytes, uint32_t elementBytes, uint64_t size) {
    // The legacy TGL instructions divide 32-bit values even though the
    // IOSurface accessors return 64-bit sizes. Reject instead of substituting
    // a divisor of one and silently manufacturing a different image layout.
    return rowBytes && rowBytes <= UINT32_MAX && elementBytes &&
        size && size <= UINT32_MAX && size / rowBytes != 0;
}

inline bool rectRequest(uint32_t dwords, uint64_t base, uint64_t cursor,
                        uint64_t end, uint32_t &requestDwords) {
    if (!dwords || dwords > RectChunkBytes / 4 || !base ||
        (base & (PageBytes - 1)) || cursor < base || cursor > end ||
        (cursor & 3) || end - base < uint64_t(dwords) * 4)
        return false;
    uint32_t pad = uint32_t((0 - cursor) & (PageBytes - 1));
    // Include padding in the request BEFORE the allocator decides whether
    // to roll over. After rollover the padding is recomputed from the new VA.
    requestDwords = dwords + pad / 4;
    return true;
}

inline bool rectResult(uint32_t dwords, uint64_t base, uint64_t cursor,
                       uint64_t end, uint32_t &pad) {
    uint32_t ignored;
    if (!rectRequest(dwords, base, cursor, end, ignored)) return false;
    pad = uint32_t((0 - cursor) & (PageBytes - 1));
    return uint64_t(pad) <= end - cursor &&
         uint64_t(dwords) * 4 <= end - cursor - pad;
}

// Injected before the rect emitter's first command store. Lilu appends the
// original 15 PIC bytes and a continuation jump. Only a null allocation takes
// the donor's stack-canary/epilogue; the hook records a failed blit separately.
inline void rectGuard(uint8_t (&code)[19], uint64_t epilogue) {
    const uint8_t prefix[] = {0x4d,0x85,0xf6,0x75,0x0e,0xff,0x25,0,0,0,0};
    for (unsigned i = 0; i < sizeof(prefix); ++i) code[i] = prefix[i];
    for (unsigned i = 0; i < 8; ++i) code[11+i] = uint8_t(epilogue >> (8*i));
}
}

// Implemented alongside the IOAF and IOSurface hooks in kern_green.cpp.
bool hpTglIOSurfaceLayoutReady();
bool hpTglSurfaceABIReady();
bool hpTglEnableRepair(uint64_t image, uint64_t size, uint64_t rectReturn);

// Stack-owned, per-thread failure scope. A rect-list is void in the donor;
// carry rejected allocations back to submitBlit's boolean result instead of
// returning success after the guarded emitter aborts.
struct HpTglBlitScope {
    void *thread;
    bool failed;
    HpTglBlitScope *next;
};
void hpTglBeginBlit(HpTglBlitScope &scope);
bool hpTglEndBlit(HpTglBlitScope &scope);

struct HpTglCCSScope {
    void *thread;
    void *pool;
    uint64_t base;
    uint32_t count;
    bool committed;
    bool failed;
    HpTglCCSScope *next;
};
bool hpTglCCSPoolReady();
void hpTglCCSArm(uint64_t commitReturn);
bool hpTglCCSBegin(HpTglCCSScope &scope, void *pool, uint32_t count);
bool hpTglCCSEnd(HpTglCCSScope &scope);
void hpTglResolveFailed();

#endif
