// SPDX-License-Identifier: MIT
// Focused hosted tests for the byte-identical GA3.4 core and boot-text helper.
// No hardware, no real reader, no OS boot-text source.
#include "kern_tglfault34.hpp"
#include "kern_tglfault34_boottext.hpp"

#include <cstdio>
#include <cstring>
#include <cstdint>

using namespace TglFault34;
namespace B = TglFault34BootText;

static unsigned checks;

#define CHECK(condition)                                                        \
    do {                                                                        \
        ++checks;                                                               \
        if (!(condition)) {                                                     \
            std::printf("FAIL %s:%d: %s\n", __func__, __LINE__, #condition);    \
            return false;                                                       \
        }                                                                       \
    } while (0)

static Request approved() {
    Request q;
    q.enabled = true;
    q.supportedTgl = true;
    q.knownActivePower = true;
    q.notResetting = true;
    q.exclusionKnown = true;
    q.stableIdentityKnown = true;
    q.monotonicTimestampKnown = true;
    q.forcewakeHeldDomains = DomainGT;
    q.forcewakeAckDomains = DomainGT;
    q.bootId = 17;
    q.hangId = 1;
    q.callerId = 29;
    q.monotonicNs = 1000;
    q.resetEpoch = 3;
    q.exclusionToken = 41;
    return q;
}

struct Mock {
    uint32_t values[3] = {
        0x1f000U | (0xa5U << 3) | 7U,
        0x89abcdefU,
        0x1fbU
    };
    uint32_t offsets[3] {};
    uint32_t reads = 0;
    uint32_t observations = 0;
    int failRead = -1;
    uint32_t changeAt = 0;
    // 1 epoch, 2 token, 3 resetting, 4 callback fail, 5 power,
    // 6 GT held, 7 GT ACK.
    uint32_t changeKind = 0;

    static bool read(void *context, uint32_t offset, uint32_t &value) noexcept {
        Mock &mock = *static_cast<Mock *>(context);
        const uint32_t index = mock.reads++;
        if (index >= 3) return false;
        mock.offsets[index] = offset;
        value = mock.values[index];
        return int(index) != mock.failRead;
    }

    static bool observe(void *context, EpochObservation &epoch) noexcept {
        Mock &mock = *static_cast<Mock *>(context);
        ++mock.observations;
        epoch.epoch = 3;
        epoch.exclusionToken = 41;
        epoch.resetting = false;
        epoch.knownActivePower = true;
        epoch.forcewakeHeldDomains = DomainAll;
        epoch.forcewakeAckDomains = DomainAll;
        if (mock.changeAt == mock.observations) {
            switch (mock.changeKind) {
                case 1: ++epoch.epoch; break;
                case 2: ++epoch.exclusionToken; break;
                case 3: epoch.resetting = true; break;
                case 4: return false;
                case 5: epoch.knownActivePower = false; break;
                case 6: epoch.forcewakeHeldDomains = DomainRender; break;
                case 7: epoch.forcewakeAckDomains = DomainRender; break;
                default: break;
            }
        }
        return true;
    }

    Callbacks callbacks() { return {this, read, observe}; }
};

static bool sameRecord(const FaultRecord &a, const FaultRecord &b) {
    return a.validity == b.validity && a.callerClaims == b.callerClaims &&
           a.status == b.status && a.readAttempts == b.readAttempts &&
           a.engineLayout == b.engineLayout &&
           a.forcewakeHeldDomains == b.forcewakeHeldDomains &&
           a.forcewakeAckDomains == b.forcewakeAckDomains &&
           a.sequence == b.sequence && a.monotonicNs == b.monotonicNs &&
           a.bootId == b.bootId && a.hangId == b.hangId &&
           a.callerId == b.callerId && a.resetEpoch == b.resetEpoch &&
           a.exclusionToken == b.exclusionToken &&
           a.rawFault == b.rawFault && a.rawData0 == b.rawData0 &&
           a.rawData1 == b.rawData1;
}

static bool default_off_without_callbacks() {
    Collector collector;
    Mock mock;
    CHECK(collector.capture(Request {}, mock.callbacks()) == Status::Disabled);
    CHECK(collector.size() == 0);
    CHECK(mock.reads == 0);
    CHECK(mock.observations == 0);
    CHECK(collector.counters().attempts == 1);
    CHECK(collector.counters().refusals == 1);
    CHECK(std::strcmp(BootArgument, "-igfxtglfault34") == 0);
    CHECK(std::strcmp(B::Token, BootArgument) == 0);
    return true;
}

static bool complete_capture_and_derive() {
    Collector collector;
    Mock mock;
    CHECK(collector.capture(approved(), mock.callbacks()) == Status::Complete);
    CHECK(mock.reads == 3);
    CHECK(mock.observations == 6);
    CHECK(mock.offsets[0] == FaultRegister);
    CHECK(mock.offsets[1] == Data0Register);
    CHECK(mock.offsets[2] == Data1Register);
    const FaultRecord &record = *collector.record(0);
    CHECK(record.validity == CompleteValidity);
    CHECK((record.validity & StableEpoch) != 0);
    CHECK(record.readAttempts == 3);
    CHECK(record.rawFault == mock.values[0]);
    CHECK(record.rawData0 == mock.values[1]);
    CHECK(record.rawData1 == mock.values[2]);
    CHECK(record.callerClaims == RequiredClaims);
    const DerivedFault derived = derive(record);
    CHECK(derived.available);
    CHECK(derived.faultPresent);
    CHECK(derived.virtualAddress == UINT64_C(0xb89abcdef000));
    CHECK(derived.addressSpace == AddressSpace::Ggtt);
    CHECK(derived.engineIdV618 == 31);
    CHECK(derived.engineIdV515 == 7);
    CHECK(derived.sourceId == 0xa5);
    CHECK(derived.faultType == 3);
    CHECK(derived.entryValid);
    CHECK(derived.entryPresent);
    CHECK(derived.pageSize == PageSize::GiB1);
    return true;
}

static bool wire_roundtrip_and_reserved_bytes() {
    Collector collector;
    Mock mock;
    CHECK(collector.capture(approved(), mock.callbacks()) == Status::Complete);
    const FaultRecord &record = *collector.record(0);
    uint8_t bytes[WireSize] {};
    CHECK(encode(record, bytes, sizeof bytes));
    CHECK(bytes[0] == 'T' && bytes[1] == 'G' && bytes[2] == 'F' && bytes[3] == '4');
    CHECK(bytes[4] == 1 && bytes[5] == 0);
    CHECK(bytes[6] == WireSize && bytes[7] == 0);
    CHECK(bytes[104] == 0 && bytes[105] == 0 && bytes[106] == 0 && bytes[107] == 0);
    FaultRecord decoded;
    CHECK(decode(bytes, sizeof bytes, decoded));
    CHECK(sameRecord(record, decoded));
    return true;
}

static bool decode_rejects_truncation_and_corruption() {
    Collector collector;
    Mock mock;
    CHECK(collector.capture(approved(), mock.callbacks()) == Status::Complete);
    const FaultRecord &record = *collector.record(0);
    uint8_t valid[WireSize] {};
    CHECK(encode(record, valid, sizeof valid));

    const size_t badLengths[] = {0, 1, 8, 107, 109, 200};
    for (size_t length : badLengths) {
        FaultRecord output {};
        output.sequence = UINT64_C(0xdeadbeef);
        CHECK(!decode(valid, length, output));
        CHECK(output.sequence == UINT64_C(0xdeadbeef));
    }

    struct Mutation { size_t offset; uint8_t value; };
    const Mutation mutations[] = {
        {0, uint8_t('X')},       // magic
        {4, 2},                  // wire version
        {6, 107},                // wire size
        {16, 0xff},              // invalid status enum
        {104, 1},                // reserved must be zero
        {107, 1}                 // reserved must be zero
    };
    for (const Mutation &mutation : mutations) {
        uint8_t bytes[WireSize] {};
        std::memcpy(bytes, valid, sizeof bytes);
        bytes[mutation.offset] = mutation.value;
        FaultRecord output {};
        output.sequence = UINT64_C(0xcafebabe);
        CHECK(!decode(bytes, sizeof bytes, output));
        CHECK(output.sequence == UINT64_C(0xcafebabe));
    }

    uint8_t sink[WireSize];
    std::memset(sink, 0xa5, sizeof sink);
    CHECK(!encode(record, sink, WireSize - 1));
    CHECK(sink[0] == 0xa5);
    FaultRecord invalid = record;
    invalid.readAttempts = 2;
    CHECK(!encode(invalid, sink, sizeof sink));
    CHECK(sink[0] == 0xa5);
    return true;
}

static bool partial_read_stops_immediately() {
    struct Case { int failAt; Status status; uint32_t attempts; uint32_t validity; uint32_t observations; };
    const Case cases[] = {
        {0, Status::FaultReadFailed, 1, HasMetadata, 1},
        {1, Status::Data0ReadFailed, 2, HasMetadata | HasFault, 3},
        {2, Status::Data1ReadFailed, 3, HasMetadata | HasFault | HasData0, 5}
    };
    for (const Case &item : cases) {
        Collector collector;
        Mock mock;
        mock.failRead = item.failAt;
        CHECK(collector.capture(approved(), mock.callbacks()) == item.status);
        CHECK(collector.size() == 1);
        CHECK(mock.observations == item.observations);
        const FaultRecord &record = *collector.record(0);
        CHECK(record.status == item.status);
        CHECK(record.readAttempts == item.attempts);
        CHECK(record.validity == item.validity);
        CHECK((record.validity & StableEpoch) == 0);
        CHECK(collector.counters().captureFailures == 1);
    }
    return true;
}

static bool epoch_power_and_ack_failures() {
    struct Case { uint32_t kind; Status status; uint32_t observations; };
    const Case cases[] = {
        {1, Status::ResetRace, 1},
        {2, Status::ResetRace, 1},
        {3, Status::ResetRace, 1},
        {4, Status::EpochUnavailable, 1},
        {5, Status::PowerUnknown, 1},
        {6, Status::GtForcewakeMissing, 1},
        {7, Status::GtAckMissing, 1}
    };
    for (const Case &item : cases) {
        Collector collector;
        Mock mock;
        mock.changeAt = 1;
        mock.changeKind = item.kind;
        CHECK(collector.capture(approved(), mock.callbacks()) == item.status);
        CHECK(mock.observations == item.observations);
        const FaultRecord &record = *collector.record(0);
        CHECK(record.status == item.status);
        CHECK(record.readAttempts == 0);
        CHECK(record.validity == HasMetadata);
        CHECK((record.validity & StableEpoch) == 0);
    }
    return true;
}

static bool boottext_bounded_scan() {
    CHECK(B::enabled(B::Token, sizeof B::Token));
    CHECK(!B::enabled(B::Token, sizeof B::Token - 1));
    CHECK(!B::enabled(nullptr, 16));
    CHECK(!B::enabled(B::Token, 0));

    char maxSpan[B::MaxBytes] {};
    maxSpan[B::MaxBytes - 1] = '\0';
    std::memcpy(maxSpan, B::Token, sizeof B::Token - 1);
    CHECK(B::enabled(maxSpan, sizeof maxSpan));

    char oversize[B::MaxBytes + 1] {};
    std::memcpy(oversize, B::Token, sizeof B::Token - 1);
    CHECK(!B::enabled(oversize, sizeof oversize));

    const char afterNul[] = "-v\0 -igfxtglfault34";
    const char beforeNul[] = "-igfxtglfault34\0arbitrary suffix";
    CHECK(!B::enabled(afterNul, sizeof afterNul));
    CHECK(B::enabled(beforeNul, sizeof beforeNul));

    char leading[] = "X-igfxtglfault34";
    char trailing[] = "-igfxtglfault34X";
    CHECK(!B::enabled(leading, sizeof leading));
    CHECK(!B::enabled(trailing, sizeof trailing));

    char spaced[] = "\t -igfxtglfault34\r\n";
    CHECK(B::enabled(spaced, sizeof spaced));
    return true;
}

int main() {
    if (!default_off_without_callbacks()) return 1;
    if (!complete_capture_and_derive()) return 1;
    if (!wire_roundtrip_and_reserved_bytes()) return 1;
    if (!decode_rejects_truncation_and_corruption()) return 1;
    if (!partial_read_stops_immediately()) return 1;
    if (!epoch_power_and_ack_failures()) return 1;
    if (!boottext_bounded_scan()) return 1;
    std::printf("CORE_CODEC_PASS checks=%u wire_version=%u wire_size=%zu hardware=NONE\n",
                checks, unsigned(WireVersion), WireSize);
    return 0;
}
