#include "kern_tglfault34.hpp"
// Compile-only ABI probe. These exports have no platform integration.
extern "C" uint32_t fault34_offline_capture(TglFault34::Collector *c,
    const TglFault34::Request *q, const TglFault34::Callbacks *cb) noexcept {
    return uint32_t(c->capture(*q, *cb));
}
extern "C" bool fault34_offline_encode(const TglFault34::FaultRecord *r,
    uint8_t *bytes, size_t length) noexcept {
    return TglFault34::encode(*r, bytes, length);
}
extern "C" bool fault34_offline_decode(const uint8_t *bytes, size_t length,
    TglFault34::FaultRecord *r) noexcept {
    return TglFault34::decode(bytes, length, *r);
}
extern "C" uint64_t fault34_offline_derive(const TglFault34::FaultRecord *r) noexcept {
    return TglFault34::derive(*r).virtualAddress;
}
