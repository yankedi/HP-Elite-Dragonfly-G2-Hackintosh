// Hosted CPU-only tests for the freestanding, deliberately unattached header.
#include "kern_tglfault34.hpp"
#include <cstdio>
#include <cstring>
#include <initializer_list>

using namespace TglFault34;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL %s:%d: %s\n", __func__, __LINE__, #c); return false; } } while (0)

static Request approved() {
    Request q;
    q.enabled = q.supportedTgl = q.knownActivePower = q.notResetting = true;
    q.exclusionKnown = q.stableIdentityKnown = q.monotonicTimestampKnown = true;
    q.forcewakeHeldDomains = q.forcewakeAckDomains = DomainGT;
    q.bootId = 17; q.hangId = 1; q.callerId = 29; q.monotonicNs = 1000;
    q.resetEpoch = 3; q.exclusionToken = 41;
    return q;
}

struct Mock {
    uint32_t values[3] = {0x1f000U | (0xa5U << 3) | 7U, 0x89abcdefU, 0x1fbU};
    uint32_t offsets[3] {};
    uint32_t reads = 0, observations = 0;
    int failRead = -1;
    uint32_t changeAt = 0;
    // 1 epoch, 2 token, 3 resetting, 4 callback fail, 5 power, 6 GT, 7 ACK.
    uint32_t changeKind = 0;
    Collector *recursive = nullptr;
    Status recursiveResult = Status::Complete;
    bool wasCapturing = false;
    static bool read(void *ctx, uint32_t offset, uint32_t &value) noexcept {
        Mock &m = *static_cast<Mock *>(ctx);
        const uint32_t n = m.reads++;
        if (n >= 3) return false;
        m.offsets[n] = offset;
        value = m.values[n];
        if (m.recursive) {
            m.wasCapturing = m.recursive->state() == State::Capturing;
            Collector *c = m.recursive; m.recursive = nullptr;
            m.recursiveResult = c->capture(approved(), {ctx, read, observe});
        }
        return int(n) != m.failRead;
    }
    static bool observe(void *ctx, EpochObservation &e) noexcept {
        Mock &m = *static_cast<Mock *>(ctx);
        ++m.observations;
        e.epoch = 3; e.exclusionToken = 41; e.resetting = false;
        e.knownActivePower = true;
        e.forcewakeHeldDomains = e.forcewakeAckDomains = DomainAll;
        if (m.changeAt == m.observations) {
            switch (m.changeKind) {
                case 1: ++e.epoch; break;
                case 2: ++e.exclusionToken; break;
                case 3: e.resetting = true; break;
                case 4: return false;
                case 5: e.knownActivePower = false; break;
                case 6: e.forcewakeHeldDomains = DomainRender; break;
                case 7: e.forcewakeAckDomains = DomainRender; break;
                default: break;
            }
        }
        return true;
    }
    Callbacks callbacks() { return {this, read, observe}; }
};

static bool same(const FaultRecord &a, const FaultRecord &b) {
    return a.validity == b.validity && a.callerClaims == b.callerClaims &&
        a.status == b.status && a.readAttempts == b.readAttempts &&
        a.engineLayout == b.engineLayout && a.forcewakeHeldDomains == b.forcewakeHeldDomains &&
        a.forcewakeAckDomains == b.forcewakeAckDomains && a.sequence == b.sequence &&
        a.monotonicNs == b.monotonicNs && a.bootId == b.bootId && a.hangId == b.hangId &&
        a.callerId == b.callerId && a.resetEpoch == b.resetEpoch &&
        a.exclusionToken == b.exclusionToken && a.rawFault == b.rawFault &&
        a.rawData0 == b.rawData0 && a.rawData1 == b.rawData1;
}

static FaultRecord example() {
    Collector c; Mock m;
    (void)c.capture(approved(), m.callbacks());
    return *c.record(0);
}

static bool roundtrip(const FaultRecord &r) {
    uint8_t b[WireSize] {}; FaultRecord out;
    CHECK(encode(r, b, sizeof b)); CHECK(decode(b, sizeof b, out));
    CHECK(same(r, out));
    return true;
}

static bool default_disabled() {
    Collector c; Mock m;
    CHECK(c.capture(Request{}, m.callbacks()) == Status::Disabled);
    CHECK(c.size() == 0 && c.state() == State::Ready);
    CHECK(m.reads == 0 && m.observations == 0);
    CHECK(c.counters().attempts == 1 && c.counters().refusals == 1);
    CHECK(std::strcmp(BootArgument, "-igfxtglfault34") == 0);
    CHECK(c.record(0) == nullptr && c.record(UINT32_MAX) == nullptr);
    return true;
}

static bool precondition_matrix() {
    for (uint32_t i = 0; i < 18; ++i) {
        Collector c; Mock m; Request q = approved(); Callbacks cb = m.callbacks();
        Status expected = Status::Complete;
        switch (i) {
            case 0: q.enabled = false; expected = Status::Disabled; break;
            case 1: q.supportedTgl = false; expected = Status::UnsupportedTgl; break;
            case 2: q.knownActivePower = false; expected = Status::PowerUnknown; break;
            case 3: q.forcewakeHeldDomains = DomainRender; expected = Status::GtForcewakeMissing; break;
            case 4: q.forcewakeAckDomains = DomainRender; expected = Status::GtAckMissing; break;
            case 5: q.notResetting = false; expected = Status::Resetting; break;
            case 6: q.exclusionKnown = false; expected = Status::ExclusionUnknown; break;
            case 7: q.exclusionToken = 0; expected = Status::ExclusionUnknown; break;
            case 8: q.resetEpoch = 0; expected = Status::ExclusionUnknown; break;
            case 9: q.stableIdentityKnown = false; expected = Status::BadIdentity; break;
            case 10: q.bootId = 0; expected = Status::BadIdentity; break;
            case 11: q.hangId = 0; expected = Status::BadIdentity; break;
            case 12: q.callerId = 0; expected = Status::BadIdentity; break;
            case 13: q.monotonicTimestampKnown = false; expected = Status::BadTimestamp; break;
            case 14: q.monotonicNs = 0; expected = Status::BadTimestamp; break;
            case 15: cb.read = nullptr; expected = Status::MissingCallbacks; break;
            case 16: cb.observe = nullptr; expected = Status::MissingCallbacks; break;
            case 17: q.forcewakeHeldDomains = q.forcewakeAckDomains = DomainMedia;
                expected = Status::GtForcewakeMissing; break;
        }
        CHECK(c.capture(q, cb) == expected);
        CHECK(m.reads == 0 && m.observations == 0 && c.size() == 0);
        CHECK(c.counters().refusals == 1);
    }
    return true;
}

static bool gt_or_all_claims() {
    for (uint32_t domain : {DomainGT, DomainAll}) {
        Collector c; Mock m; Request q = approved();
        q.forcewakeHeldDomains = q.forcewakeAckDomains = domain;
        CHECK(c.capture(q, m.callbacks()) == Status::Complete);
        CHECK(c.record(0)->forcewakeHeldDomains == domain);
        CHECK(roundtrip(*c.record(0)));
    }
    return true;
}

static bool exact_raw_and_masks() {
    Collector c; Mock m;
    CHECK(c.capture(approved(), m.callbacks()) == Status::Complete);
    CHECK(m.reads == 3 && m.observations == 6);
    CHECK(m.offsets[0] == 0xcec4 && m.offsets[1] == 0xceb8 && m.offsets[2] == 0xcebc);
    const FaultRecord &r = *c.record(0);
    CHECK(r.rawFault == m.values[0] && r.rawData0 == m.values[1] && r.rawData1 == m.values[2]);
    CHECK(r.validity == 31 && r.sequence == 1 && r.monotonicNs == 1000);
    DerivedFault d = derive(r);
    CHECK(d.available && d.faultPresent && d.virtualAddress == UINT64_C(0xb89abcdef000));
    CHECK(d.addressSpace == AddressSpace::Ggtt && d.engineIdV618 == 31 && d.engineIdV515 == 7);
    CHECK(d.sourceId == 0xa5 && d.faultType == 3);
    CHECK(d.entryValid && d.entryPresent && d.pageSize == PageSize::GiB1);
    CHECK(roundtrip(r));
    return true;
}

static bool invalid_fault_retained() {
    Collector c; Mock m; m.values[0] &= ~1U;
    CHECK(c.capture(approved(), m.callbacks()) == Status::Complete);
    CHECK(m.reads == 3); // complete snapshot, even if hardware fault-valid is zero
    CHECK(c.record(0)->rawFault == m.values[0]);
    DerivedFault d = derive(*c.record(0));
    CHECK(!d.available && !d.faultPresent && d.virtualAddress == 0);
    CHECK(d.addressSpace == AddressSpace::Unavailable && d.sourceId == 0);
    CHECK(roundtrip(*c.record(0)));
    return true;
}

static bool all_data1_defined_bits() {
    for (uint32_t data1 = 0; data1 <= 0x1ff; ++data1) {
        FaultRecord r = example(); r.rawData0 = 0xffffffff; r.rawData1 = data1;
        DerivedFault d = derive(r);
        CHECK(d.available && d.data1MbzBits == 0);
        CHECK(d.virtualAddress == (uint64_t(data1 & 15U) * UINT64_C(0x100000000000) + UINT64_C(0xffffffff000)));
        CHECK(d.addressSpace == ((data1 & 16U) ? AddressSpace::Ggtt : AddressSpace::Ppgtt));
        CHECK(d.entryValid == bool(data1 & 32U) && d.entryPresent == bool(data1 & 64U));
        CHECK(uint32_t(d.pageSize) == ((data1 / 128U) & 3U));
        CHECK(roundtrip(r));
    }
    return true;
}

static bool data1_mbz_raw_retained() {
    for (uint32_t bit = 9; bit < 32; ++bit) {
        FaultRecord r = example(); r.rawData1 |= 1U << bit;
        CHECK(validRecord(r)); CHECK(roundtrip(r));
        DerivedFault d = derive(r);
        CHECK(!d.available && d.faultPresent && d.data1MbzBits == (1U << bit));
        CHECK(d.virtualAddress == 0 && d.addressSpace == AddressSpace::Unavailable);
    }
    FaultRecord r = example(); r.rawData1 = UINT32_MAX;
    CHECK(derive(r).data1MbzBits == 0xfffffe00 && !derive(r).available);
    return true;
}

static bool va_overflow_and_boundaries() {
    uint64_t out = 123;
    CHECK(checkedFaultPageToVa(0, out) && out == 0);
    CHECK(checkedFaultPageToVa(UINT64_C(0xfffffffff), out) && out == UINT64_C(0xfffffffff000));
    out = 123;
    CHECK(!checkedFaultPageToVa(UINT64_C(0x1000000000), out) && out == 123);
    CHECK(!checkedFaultPageToVa(UINT64_MAX, out) && out == 123);
    FaultRecord r = example(); r.rawData0 = UINT32_MAX; r.rawData1 = 0xf;
    CHECK(derive(r).virtualAddress == UINT64_C(0xfffffffff000));
    r.rawData0 = r.rawData1 = 0;
    CHECK(derive(r).available && derive(r).virtualAddress == 0);
    return true;
}

static bool engine_source_type_exhaustive() {
    FaultRecord r = example();
    for (uint32_t engine = 0; engine < 32; ++engine)
        for (uint32_t source = 0; source < 256; ++source)
            for (uint32_t type = 0; type < 4; ++type) {
                r.rawFault = 0xfffe0800U | (engine << 12) | (source << 3) | (type << 1) | 1U;
                DerivedFault d = derive(r);
                CHECK(d.available && d.engineIdV618 == engine && d.engineIdV515 == (engine & 7U));
                CHECK(d.sourceId == source && d.faultType == type);
            }
    return true;
}

static bool fail_stop_each_register() {
    constexpr Status statuses[] = {Status::FaultReadFailed, Status::Data0ReadFailed, Status::Data1ReadFailed};
    for (int failed = 0; failed < 3; ++failed) {
        Collector c; Mock m; m.failRead = failed;
        CHECK(c.capture(approved(), m.callbacks()) == statuses[failed]);
        CHECK(m.reads == uint32_t(failed + 1) && m.observations == uint32_t(2 * failed + 1));
        const FaultRecord &r = *c.record(0);
        CHECK(r.readAttempts == uint32_t(failed + 1) && r.validity == (16U | ((1U << failed) - 1U)));
        CHECK(r.rawFault == m.values[0]);
        CHECK(r.rawData0 == (failed >= 1 ? m.values[1] : 0));
        CHECK(r.rawData1 == (failed >= 2 ? m.values[2] : 0));
        CHECK(!derive(r).available && validRecord(r) && roundtrip(r));
        CHECK(c.counters().captureFailures == 1 && c.counters().refusals == 0);
    }
    return true;
}

static bool synchronized_epoch_all_boundaries() {
    constexpr Status statuses[] = {Status::Complete, Status::ResetRace, Status::ResetRace,
        Status::ResetRace, Status::EpochUnavailable, Status::PowerUnknown,
        Status::GtForcewakeMissing, Status::GtAckMissing};
    for (uint32_t kind = 1; kind <= 7; ++kind)
        for (uint32_t checkpoint = 1; checkpoint <= 6; ++checkpoint) {
            Collector c; Mock m; m.changeKind = kind; m.changeAt = checkpoint;
            CHECK(c.capture(approved(), m.callbacks()) == statuses[kind]);
            CHECK(m.observations == checkpoint && m.reads == checkpoint / 2);
            const FaultRecord &r = *c.record(0);
            CHECK(r.readAttempts == m.reads && r.validity == (16U | ((1U << m.reads) - 1U)));
            CHECK(!derive(r).available && validRecord(r) && roundtrip(r));
        }
    return true;
}

static bool fixed_eight_preserve_first() {
    Collector c; Request q = approved(); FaultRecord first;
    for (uint32_t i = 0; i < 8; ++i) {
        Mock m; m.values[1] = i; q.hangId = i + 1; q.monotonicNs = 1000 + i;
        CHECK(c.capture(q, m.callbacks()) == Status::Complete);
        CHECK(c.record(i)->sequence == i + 1);
        if (!i) first = *c.record(0);
    }
    CHECK(c.state() == State::Full && c.size() == 8);
    for (uint32_t i = 0; i < 10; ++i) {
        Mock m; ++q.hangId; ++q.monotonicNs;
        CHECK(c.capture(q, m.callbacks()) == Status::BufferFull);
        CHECK(m.reads == 0 && m.observations == 0);
    }
    CHECK(c.counters().full == 10 && c.counters().refusals == 10);
    CHECK(c.size() == 8 && same(first, *c.record(0)) && c.record(8) == nullptr);
    return true;
}

static bool repeated_failures_also_bounded() {
    Collector c; Request q = approved();
    for (uint32_t i = 0; i < 8; ++i) {
        Mock m; m.failRead = 0; q.hangId = i + 1; q.monotonicNs = i + 1;
        CHECK(c.capture(q, m.callbacks()) == Status::FaultReadFailed);
        CHECK(c.record(i)->rawFault == m.values[0]);
    }
    Mock m; ++q.hangId; ++q.monotonicNs;
    CHECK(c.capture(q, m.callbacks()) == Status::BufferFull && m.reads == 0);
    CHECK(c.counters().captureFailures == 8);
    return true;
}

static bool sequence_wrap_refused() {
    Collector c(UINT64_MAX - 1); Request q = approved();
    for (uint32_t i = 0; i < 2; ++i) {
        Mock m; q.hangId += i; q.monotonicNs += i;
        CHECK(c.capture(q, m.callbacks()) == Status::Complete);
        CHECK(c.record(i)->sequence == UINT64_MAX - 1 + i);
        CHECK(roundtrip(*c.record(i)));
    }
    Mock m; ++q.hangId; ++q.monotonicNs;
    CHECK(c.state() == State::SequenceExhausted);
    CHECK(c.capture(q, m.callbacks()) == Status::SequenceOverflow);
    CHECK(m.reads == 0 && m.observations == 0 && c.size() == 2);
    CHECK(c.counters().sequenceOverflow == 1);
    Collector zero(0);
    CHECK(zero.capture(approved(), m.callbacks()) == Status::SequenceOverflow && zero.size() == 0);
    return true;
}

static bool timestamp_monotonicity() {
    for (uint32_t variant = 0; variant < 4; ++variant) {
        Collector c; Mock initial; Request q = approved();
        CHECK(c.capture(q, initial.callbacks()) == Status::Complete);
        ++q.hangId;
        if (variant == 0) q.monotonicNs = 999;
        if (variant == 1) q.monotonicNs = 1000;
        if (variant == 2) q.monotonicTimestampKnown = false;
        if (variant == 3) q.monotonicNs = 0;
        Mock m; CHECK(c.capture(q, m.callbacks()) == Status::BadTimestamp);
        CHECK(c.size() == 1 && m.reads == 0 && m.observations == 0);
    }
    Collector c; Mock m; Request q = approved(); q.monotonicNs = UINT64_MAX;
    CHECK(c.capture(q, m.callbacks()) == Status::Complete);
    Mock next; ++q.hangId; q.monotonicNs = 1;
    CHECK(c.capture(q, next.callbacks()) == Status::BadTimestamp && next.reads == 0);
    return true;
}

static bool identity_stability() {
    for (uint32_t variant = 0; variant < 4; ++variant) {
        Collector c; Mock m; Request q = approved();
        CHECK(c.capture(q, m.callbacks()) == Status::Complete);
        ++q.monotonicNs;
        if (variant == 0) ++q.bootId;
        if (variant == 1) ++q.callerId;
        if (variant == 2) q.hangId = 1;
        if (variant == 3) q.hangId = 0;
        Mock n;
        CHECK(c.capture(q, n.callbacks()) == (variant == 3 ? Status::BadIdentity : Status::IdentityChanged));
        CHECK(n.reads == 0 && n.observations == 0 && c.size() == 1);
    }
    return true;
}

static bool recursive_callback_refused() {
    Collector c; Mock m; m.recursive = &c;
    CHECK(c.capture(approved(), m.callbacks()) == Status::Complete);
    CHECK(m.wasCapturing && m.recursiveResult == Status::Reentrant);
    CHECK(c.size() == 1 && m.reads == 3 && c.counters().attempts == 2);
    CHECK(c.counters().refusals == 1 && c.state() == State::Ready);
    return true;
}

static bool golden_little_endian_codec() {
    FaultRecord r = example(); r.sequence = UINT64_C(0x0102030405060708);
    r.monotonicNs = UINT64_C(0x1112131415161718);
    const uint8_t golden[108] = {
        0x54,0x47,0x46,0x34, 1,0,108,0, 31,0,0,0, 127,0,0,0,
        0,0,0,0, 3,0,0,0, 1,0,0,0, 1,0,0,0, 1,0,0,0,
        8,7,6,5,4,3,2,1, 0x18,0x17,0x16,0x15,0x14,0x13,0x12,0x11,
        17,0,0,0,0,0,0,0, 1,0,0,0,0,0,0,0, 29,0,0,0,0,0,0,0,
        3,0,0,0,0,0,0,0, 41,0,0,0,0,0,0,0,
        0x2f,0xf5,1,0, 0xef,0xcd,0xab,0x89, 0xfb,1,0,0, 0,0,0,0
    };
    uint8_t b[WireSize] {}; CHECK(encode(r, b, sizeof b));
    CHECK(std::memcmp(b, golden, sizeof b) == 0);
    FaultRecord out; CHECK(decode(golden, sizeof golden, out) && same(r, out));
    return true;
}

// Single-threaded, live non-const aliases reproduce review R1/R2. No dangling
// object or unsupported concurrent caller is needed for these mutations.
struct AliasedBackend {
    Request *borrowedRequest = nullptr;
    Callbacks *borrowedCallbacks = nullptr;
    AliasedBackend *replacementContext = nullptr;
    uint64_t epoch = 10, token = 20;
    uint32_t requestMutation = 0; // bit0 epoch, bit1 token, during first read
    uint32_t descriptorMutation = 0; // read null/replace, observe null/replace, context null/replace
    bool descriptorFromReader = false, descriptorsChanged = false;
    bool zeroRequestAtFirstObserver = false;
    uint32_t reads = 0, observations = 0, wrongDispatch = 0;
    bool orderCorrect = true;
    char trace[16] {};
    uint32_t traceSize = 0;
    void event(char c) noexcept { trace[traceSize++] = c; }
    static bool otherRead(void *p, uint32_t, uint32_t &) noexcept {
        ++static_cast<AliasedBackend *>(p)->wrongDispatch;
        return false;
    }
    static bool otherObserve(void *p, EpochObservation &) noexcept {
        ++static_cast<AliasedBackend *>(p)->wrongDispatch;
        return false;
    }
    void mutateDescriptors() noexcept {
        if (!descriptorMutation || descriptorsChanged) return;
        descriptorsChanged = true;
        if (descriptorMutation & 1U) borrowedCallbacks->read = nullptr;
        if (descriptorMutation & 2U) borrowedCallbacks->read = otherRead;
        if (descriptorMutation & 4U) borrowedCallbacks->observe = nullptr;
        if (descriptorMutation & 8U) borrowedCallbacks->observe = otherObserve;
        if (descriptorMutation & 16U) borrowedCallbacks->context = nullptr;
        if (descriptorMutation & 32U) borrowedCallbacks->context = replacementContext;
    }
    static bool read(void *p, uint32_t offset, uint32_t &value) noexcept {
        AliasedBackend &b = *static_cast<AliasedBackend *>(p);
        b.event('R');
        const uint32_t i = b.reads++;
        constexpr uint32_t offsets[] = {0xcec4, 0xceb8, 0xcebc};
        constexpr uint32_t words[] = {0x12345, 0xabcdef01, 0x1f2};
        if (i >= 3 || offset != offsets[i]) { b.orderCorrect = false; return false; }
        value = words[i];
        if (i == 0) {
            if (b.requestMutation & 1U) b.borrowedRequest->resetEpoch = ++b.epoch;
            if (b.requestMutation & 2U) b.borrowedRequest->exclusionToken = ++b.token;
            if (b.descriptorFromReader) b.mutateDescriptors();
        }
        return true;
    }
    static bool observe(void *p, EpochObservation &e) noexcept {
        AliasedBackend &b = *static_cast<AliasedBackend *>(p);
        b.event('O'); ++b.observations;
        if (b.observations == 1) {
            if (b.zeroRequestAtFirstObserver) *b.borrowedRequest = Request{};
            if (!b.descriptorFromReader) b.mutateDescriptors();
        }
        e.epoch = b.epoch; e.exclusionToken = b.token; e.resetting = false;
        e.knownActivePower = true;
        e.forcewakeHeldDomains = e.forcewakeAckDomains = DomainGT;
        return true;
    }
    Callbacks callbacks() noexcept { return {this, read, observe}; }
};

static Request alias_request() {
    Request q = approved(); q.resetEpoch = 10; q.exclusionToken = 20;
    return q;
}

static bool alias_positive_control() {
    Collector c; Request q = alias_request(); AliasedBackend b;
    Callbacks cb = b.callbacks(); b.borrowedRequest = &q; b.borrowedCallbacks = &cb;
    CHECK(c.capture(q, cb) == Status::Complete);
    CHECK(b.reads == 3 && b.observations == 6 && b.orderCorrect);
    CHECK(std::strcmp(b.trace, "OROOROORO") == 0);
    CHECK(c.record(0)->resetEpoch == 10 && c.record(0)->exclusionToken == 20);
    CHECK(q.resetEpoch == 10 && q.exclusionToken == 20);
    CHECK(cb.read == AliasedBackend::read && cb.observe == AliasedBackend::observe && cb.context == &b);
    CHECK(derive(*c.record(0)).available && roundtrip(*c.record(0)));
    std::puts("ALIAS_CONTROL Complete reads=3 observations=6 epoch=10 token=20");
    return true;
}

static bool alias_request_epoch_token_pinned() {
    for (uint32_t mutation = 1; mutation <= 3; ++mutation) {
        Collector c; Request q = alias_request(); AliasedBackend b;
        Callbacks cb = b.callbacks(); b.borrowedRequest = &q; b.requestMutation = mutation;
        CHECK(c.capture(q, cb) == Status::ResetRace);
        CHECK(b.reads == 1 && b.observations == 2 && b.orderCorrect);
        CHECK(std::strcmp(b.trace, "ORO") == 0);
        CHECK(q.resetEpoch == ((mutation & 1U) ? 11U : 10U));
        CHECK(q.exclusionToken == ((mutation & 2U) ? 21U : 20U));
        const FaultRecord &r = *c.record(0);
        CHECK(r.resetEpoch == 10 && r.exclusionToken == 20);
        CHECK(r.validity == (HasMetadata | HasFault) && r.readAttempts == 1);
        CHECK(r.rawFault == 0x12345 && r.rawData0 == 0 && r.rawData1 == 0);
        CHECK(!derive(r).available && roundtrip(r));
    }
    std::puts("R1_FIX ResetRace epoch_only/token_only/both reads=1 observations=2 retained_epoch=10 retained_token=20");
    return true;
}

static bool alias_request_all_fields_snapshot() {
    Collector c; Request q = alias_request(); const Request initial = q;
    AliasedBackend b; b.borrowedRequest = &q; b.zeroRequestAtFirstObserver = true;
    Callbacks cb = b.callbacks();
    CHECK(c.capture(q, cb) == Status::Complete);
    CHECK(!q.enabled && q.resetEpoch == 0 && q.exclusionToken == 0 && q.bootId == 0);
    CHECK(b.reads == 3 && b.observations == 6);
    const FaultRecord &r = *c.record(0);
    CHECK(r.resetEpoch == initial.resetEpoch && r.exclusionToken == initial.exclusionToken);
    CHECK(r.bootId == initial.bootId && r.hangId == initial.hangId && r.callerId == initial.callerId);
    CHECK(r.monotonicNs == initial.monotonicNs && r.callerClaims == RequiredClaims);
    CHECK(r.forcewakeHeldDomains == DomainGT && r.forcewakeAckDomains == DomainGT);
    CHECK(derive(r).available && roundtrip(r));
    return true;
}

static bool alias_callback_read_snapshot() {
    for (uint32_t mutation : {1U, 2U}) {
        Collector c; Request q = alias_request(); AliasedBackend b;
        Callbacks cb = b.callbacks(); b.borrowedCallbacks = &cb; b.descriptorMutation = mutation;
        CHECK(c.capture(q, cb) == Status::Complete);
        CHECK(b.descriptorsChanged && b.reads == 3 && b.observations == 6 && b.wrongDispatch == 0);
        CHECK(cb.read == (mutation == 1 ? nullptr : AliasedBackend::otherRead));
        CHECK(std::strcmp(b.trace, "OROOROORO") == 0);
        CHECK(derive(*c.record(0)).available && roundtrip(*c.record(0)));
    }
    std::puts("R2_FIX observer_mutates_borrowed_read=null/replacement Complete reads=3 observations=6 pinned_dispatch=true");
    return true;
}

static bool alias_callback_observer_context_snapshot() {
    // Mutate each remaining tuple member and whole tuples, from either callback.
    for (bool fromReader : {false, true})
        for (uint32_t mutation : {4U, 8U, 16U, 32U, 21U, 42U}) {
            Collector c; Request q = alias_request(); AliasedBackend b, replacement;
            Callbacks cb = b.callbacks(); b.borrowedCallbacks = &cb;
            b.replacementContext = &replacement; b.descriptorMutation = mutation;
            b.descriptorFromReader = fromReader;
            CHECK(c.capture(q, cb) == Status::Complete);
            CHECK(b.descriptorsChanged && b.reads == 3 && b.observations == 6 && b.wrongDispatch == 0);
            CHECK(replacement.reads == 0 && replacement.observations == 0 && replacement.wrongDispatch == 0);
            CHECK(std::strcmp(b.trace, "OROOROORO") == 0);
            if (mutation & 4U) CHECK(cb.observe == nullptr);
            if (mutation & 8U) CHECK(cb.observe == AliasedBackend::otherObserve);
            if (mutation & 16U) CHECK(cb.context == nullptr);
            if (mutation & 32U) CHECK(cb.context == &replacement);
            CHECK(derive(*c.record(0)).available && roundtrip(*c.record(0)));
        }
    std::puts("R2_TUPLE_FIX observer/context/whole_tuple_mutations=12 original_context_alive=true wrong_dispatch=0");
    return true;
}

static bool codec_lengths_transactional() {
    FaultRecord r = example(), sentinel = r; sentinel.rawData0 = 0x51525354;
    uint8_t b[WireSize + 1] {}; CHECK(encode(r, b, WireSize));
    for (size_t n = 0; n < WireSize; ++n) {
        FaultRecord out = sentinel;
        CHECK(!decode(b, n, out) && same(out, sentinel));
        uint8_t dst[WireSize]; std::memset(dst, 0xa5, sizeof dst);
        CHECK(!encode(r, dst, n));
        for (uint8_t v : dst) CHECK(v == 0xa5);
    }
    FaultRecord out = sentinel;
    CHECK(!decode(b, WireSize + 1, out) && same(out, sentinel));
    CHECK(!decode(nullptr, WireSize, out) && same(out, sentinel));
    CHECK(!encode(r, nullptr, WireSize));
    uint8_t dst[WireSize + 1]; std::memset(dst, 0xa5, sizeof dst);
    CHECK(!encode(r, dst, sizeof dst));
    for (uint8_t v : dst) CHECK(v == 0xa5);
    return true;
}

static bool codec_reject_bad_fields_transactional() {
    const FaultRecord sentinel = example(); uint8_t original[WireSize] {};
    CHECK(encode(sentinel, original, sizeof original));
    // Each mutation is independently invalid; output must stay byte-semantically unchanged.
    const size_t offsets[] = {0,4,5,6,7,8,9,12,13,16,17,20,24,28,32,36,44,52,60,68,76,84,104};
    for (size_t pos : offsets) {
        uint8_t b[WireSize]; std::memcpy(b, original, sizeof b);
        if (pos == 36 || pos == 44 || pos == 52 || pos == 60 || pos == 68 || pos == 76 || pos == 84)
            std::memset(b + pos, 0, 8);
        else if (pos == 28 || pos == 32) b[pos] = 2; // render is not GT
        else b[pos] ^= 0x80;
        FaultRecord out = sentinel;
        CHECK(!decode(b, sizeof b, out) && same(out, sentinel));
    }
    for (uint32_t invalid : {1U, 7U, 8U, 9U, 10U, 11U, 17U, 18U, 19U, 20U, UINT32_MAX}) {
        uint8_t b[WireSize]; std::memcpy(b, original, sizeof b);
        CodecDetail::put(b + 16, invalid, 4);
        FaultRecord out = sentinel;
        CHECK(!decode(b, sizeof b, out) && same(out, sentinel));
    }
    FaultRecord bad = sentinel; bad.status = static_cast<Status>(UINT32_MAX);
    uint8_t dst[WireSize]; std::memset(dst, 0xa5, sizeof dst);
    CHECK(!encode(bad, dst, sizeof dst));
    for (uint8_t v : dst) CHECK(v == 0xa5);
    return true;
}

static bool impossible_validity_combinations() {
    for (uint32_t valid = 0; valid < 64; ++valid)
        for (uint32_t attempts = 0; attempts < 5; ++attempts) {
            FaultRecord r = example(); r.validity = valid; r.readAttempts = attempts;
            CHECK(validRecord(r) == (valid == 31 && attempts == 3));
            if (!validRecord(r)) CHECK(!derive(r).available);
        }
    FaultRecord bad = example(); bad.status = Status::FaultReadFailed;
    bad.validity = HasMetadata; bad.readAttempts = 2;
    CHECK(!validRecord(bad));
    bad.readAttempts = 1; CHECK(!validRecord(bad)); // impossible unattempted DATA0/DATA1
    bad.rawData0 = bad.rawData1 = 0; CHECK(validRecord(bad) && roundtrip(bad));
    return true;
}

static bool deterministic_untrusted_codec_mutations() {
    uint8_t baseline[WireSize]; CHECK(encode(example(), baseline, sizeof baseline));
    uint32_t rng = 0x7351acf9; uint32_t rejected = 0, accepted = 0;
    for (uint32_t iteration = 0; iteration < 20000; ++iteration) {
        uint8_t b[WireSize]; std::memcpy(b, baseline, sizeof b);
        rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5;
        const size_t pos = rng % WireSize;
        b[pos] ^= uint8_t((rng >> 24) | 1U);
        FaultRecord sentinel = example(), out = sentinel;
        if (!decode(b, sizeof b, out)) { ++rejected; CHECK(same(out, sentinel)); }
        else {
            ++accepted; CHECK(validRecord(out));
            uint8_t encoded[WireSize]; CHECK(encode(out, encoded, sizeof encoded));
            CHECK(std::memcmp(b, encoded, sizeof b) == 0);
            DerivedFault d = derive(out);
            if (d.available) CHECK(d.virtualAddress <= UINT64_C(0xfffffffff000));
        }
    }
    CHECK(rejected > 1000 && accepted > 1000);
    return true;
}

static bool saturating_counter() {
    uint64_t n = UINT64_MAX - 1;
    saturateIncrement(n); CHECK(n == UINT64_MAX);
    saturateIncrement(n); CHECK(n == UINT64_MAX);
    return true;
}

struct Test { const char *name; bool (*run)(); };
int main() {
    const Test tests[] = {
        {"B6.default_disabled", default_disabled},
        {"B6.preconditions_18_refusals", precondition_matrix},
        {"B6.GT_minimum_ALL_allowed", gt_or_all_claims},
        {"B6.exact_raw_masks_VA", exact_raw_and_masks},
        {"B6.valid0_retains_raw", invalid_fault_retained},
        {"B6.DATA1_all_512_defined_combinations", all_data1_defined_bits},
        {"B6.DATA1_MBZ_bits9_31", data1_mbz_raw_retained},
        {"B6.va_overflow_boundaries", va_overflow_and_boundaries},
        {"B6.engine_source_type_32768", engine_source_type_exhaustive},
        {"B6.read_failure_failstop_all3", fail_stop_each_register},
        {"B6.reset_power_GT_ACK_42_boundaries", synchronized_epoch_all_boundaries},
        {"B6.buffer8_preserves_first", fixed_eight_preserve_first},
        {"B6.failed_captures_bounded8", repeated_failures_also_bounded},
        {"B6.sequence_wrap", sequence_wrap_refused},
        {"B6.timestamp", timestamp_monotonicity},
        {"B6.identity_stability", identity_stability},
        {"B6.reentrant_mock", recursive_callback_refused},
        {"B6.codec_independent_golden_LE", golden_little_endian_codec},
        {"B6.codec_all_truncations_transactional", codec_lengths_transactional},
        {"B6.codec_versions_enums_impossible_transactional", codec_reject_bad_fields_transactional},
        {"B6.codec_validity_impossible", impossible_validity_combinations},
        {"B6.codec_untrusted_20000_mutations", deterministic_untrusted_codec_mutations},
        {"B6.counter_saturation", saturating_counter},
        {"R1R2.alias_positive_control", alias_positive_control},
        {"R1.alias_request_epoch_token_pinned", alias_request_epoch_token_pinned},
        {"R1.alias_request_all_fields_snapshot", alias_request_all_fields_snapshot},
        {"R2.alias_callback_read_snapshot", alias_callback_read_snapshot},
        {"R2.alias_callback_observer_context_snapshot", alias_callback_observer_context_snapshot}
    };
    uint32_t passed = 0;
    for (const Test &test : tests) {
        if (!test.run()) { std::printf("TEST_FAILED %s\n", test.name); return 1; }
        ++passed; std::printf("PASS %s\n", test.name);
    }
    std::printf("OFFLINE_PASS groups=%u hardware=NONE attachment=NONE whole_kext=NOT_BUILT\n", passed);
    return 0;
}
