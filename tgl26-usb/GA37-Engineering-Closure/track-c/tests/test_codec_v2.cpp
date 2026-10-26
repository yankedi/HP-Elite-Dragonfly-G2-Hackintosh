// SPDX-License-Identifier: MIT
// Offline codec, compatibility and strict-validation tests.  No reader exists.
#include "fault_record_v2.hpp"
#include "dispatch.hpp"

#include <cstdio>
#include <cstring>
#include <cstdint>
#include <cstdlib>

using namespace Ga37FaultV2;
static unsigned checks;

#define CHECK(condition)                                                        \
    do {                                                                        \
        ++checks;                                                               \
        if (!(condition)) {                                                     \
            std::printf("FAIL %s:%d: %s\n", __func__, __LINE__, #condition);   \
            return false;                                                       \
        }                                                                       \
    } while (0)

static uint64_t mask(Field field) { return fieldBit(field); }

static FaultRecord completeRecord(bool withDerived = false) {
    FaultRecord r {};
    r.presence = mask(Field::RawFault) | mask(Field::RawData0) | mask(Field::RawData1) |
        mask(Field::Sequence) | mask(Field::MonotonicNs) | mask(Field::BootId) |
        mask(Field::HangId) | mask(Field::CallerId) | mask(Field::ResetEpoch) |
        mask(Field::ExclusionToken) | mask(Field::ContextIdentity) | mask(Field::PML4) |
        mask(Field::RingHead) | mask(Field::Engine) | mask(Field::AllocationGeneration) |
        mask(Field::ResetClearPhase) | mask(Field::Provenance) | mask(Field::SweepEpoch) |
        mask(Field::ReadTimestamp0) | mask(Field::ReadTimestamp1) |
        mask(Field::ReadTimestamp2);
    r.captureFlags = ExplicitReadEnable | RawPreserved;
    r.validity = TupleValidity | MetadataValid;
    r.status = RecordStatus::Complete;
    r.readAttempts = 3;
    r.readSafetySummary = EvidenceStatus::Pass;
    r.coherenceSummary = EvidenceStatus::Pass;
    r.sequence = 7;
    r.monotonicNs = 1000;
    r.bootId = 17;
    r.hangId = 9;
    r.callerId = 29;
    r.resetEpoch = 3;
    r.exclusionToken = 41;
    r.rawFault = 0x1f000U | (0xa5U << 3) | 7U;
    r.rawData0 = 0x89abcdefU;
    r.rawData1 = 0x1fbU;
    r.contextIdentity = 0x1234;
    r.pml4 = 0x5678;
    r.ringHead = 0x9abc;
    r.engineId = 5;
    r.allocationGeneration = 11;
    r.resetClearPhase = ResetClearPhase::Stable;
    r.provenanceKind = ProvenanceKind::Synthetic;
    r.sweepEpoch = 20;
    r.readTimestamp[0] = 100;
    r.readTimestamp[1] = 101;
    r.readTimestamp[2] = 103;
    for (uint32_t i = 0; i < ReadSafetyConditionCount; ++i)
        r.readSafety[i] = uint32_t(EvidenceStatus::Pass);
    for (uint32_t i = 0; i < CoherenceConditionCount; ++i)
        r.coherence[i] = uint32_t(EvidenceStatus::Pass);
    if (withDerived) {
        r.presence |= mask(Field::DerivedVA);
        r.validity |= DerivedVAValid;
        r.derivedFlags = 1;
        r.derivedAddressSpace = AddressSpace::GGTT;
        r.derivedEngineV618 = 31;
        r.derivedEngineV515 = 7;
        r.derivedFaultType = 3;
        r.derivedSourceId = 0xa5;
        r.derivedPageSize = 3;
        r.derivedVirtualAddress = UINT64_C(0xb89abcdef000);
    }
    return r;
}

static bool same(const FaultRecord &a, const FaultRecord &b) {
    return a.presence == b.presence && a.unknown == b.unknown &&
        a.captureFlags == b.captureFlags && a.validity == b.validity &&
        a.status == b.status && a.readAttempts == b.readAttempts &&
        a.engineLayout == b.engineLayout && a.readSafetySummary == b.readSafetySummary &&
        a.coherenceSummary == b.coherenceSummary && a.sequence == b.sequence &&
        a.monotonicNs == b.monotonicNs && a.bootId == b.bootId && a.hangId == b.hangId &&
        a.callerId == b.callerId && a.resetEpoch == b.resetEpoch &&
        a.exclusionToken == b.exclusionToken && a.rawFault == b.rawFault &&
        a.rawData0 == b.rawData0 && a.rawData1 == b.rawData1 &&
        a.derivedFlags == b.derivedFlags && a.derivedAddressSpace == b.derivedAddressSpace &&
        a.derivedEngineV618 == b.derivedEngineV618 &&
        a.derivedEngineV515 == b.derivedEngineV515 &&
        a.derivedFaultType == b.derivedFaultType &&
        a.derivedSourceId == b.derivedSourceId && a.derivedPageSize == b.derivedPageSize &&
        a.derivedVirtualAddress == b.derivedVirtualAddress &&
        a.contextIdentity == b.contextIdentity && a.pml4 == b.pml4 &&
        a.ringHead == b.ringHead && a.engineId == b.engineId &&
        a.allocationGeneration == b.allocationGeneration &&
        a.resetClearPhase == b.resetClearPhase && a.provenanceKind == b.provenanceKind &&
        a.provenanceClaim == b.provenanceClaim && a.sweepEpoch == b.sweepEpoch &&
        a.readTimestamp[0] == b.readTimestamp[0] &&
        a.readTimestamp[1] == b.readTimestamp[1] &&
        a.readTimestamp[2] == b.readTimestamp[2] &&
        std::memcmp(a.readSafety, b.readSafety, sizeof a.readSafety) == 0 &&
        std::memcmp(a.coherence, b.coherence, sizeof a.coherence) == 0;
}

static bool roundtrip_and_layout(const char *samplePath) {
    FaultRecord source = completeRecord(true);
    CHECK(validRecord(source));
    uint8_t bytes[WireSize] {};
    CHECK(encode(source, bytes, sizeof bytes));
    CHECK(bytes[0] == 'T' && bytes[1] == 'G' && bytes[2] == 'F' && bytes[3] == '4');
    CHECK(bytes[4] == 2 && bytes[5] == 0);
    CHECK(bytes[6] == 16 && bytes[7] == 0);
    CHECK(bytes[8] == 0x80 && bytes[9] == 1 && bytes[10] == 0 && bytes[11] == 0);
    CHECK(bytes[120] == uint8_t(source.rawFault) && bytes[121] == uint8_t(source.rawFault >> 8) &&
          bytes[122] == uint8_t(source.rawFault >> 16) && bytes[123] == uint8_t(source.rawFault >> 24));
    CHECK(bytes[124] == 0xef && bytes[125] == 0xcd && bytes[126] == 0xab && bytes[127] == 0x89);
    CHECK(source.derivedEngineV618 == 31 && source.derivedEngineV515 == 7);
    CHECK(source.derivedFaultType == 3 && source.derivedSourceId == 0xa5);
    CHECK(source.derivedPageSize == 3 && source.derivedVirtualAddress == UINT64_C(0xb89abcdef000));
    FaultRecord decoded;
    decoded.sequence = UINT64_C(0xdeadbeef);
    CHECK(decode(bytes, sizeof bytes, decoded));
    CHECK(same(source, decoded));
    if (samplePath) {
        FILE *file = std::fopen(samplePath, "wb");
        CHECK(file != nullptr);
        CHECK(std::fwrite(bytes, 1, sizeof bytes, file) == sizeof bytes);
        CHECK(std::fclose(file) == 0);
    }
    return true;
}

static bool truncation_reserved_enum_unknown_and_atomic_output() {
    FaultRecord source = completeRecord();
    uint8_t valid[WireSize] {};
    CHECK(encode(source, valid, sizeof valid));
    const size_t lengths[] = {0, 1, 15, 383, 385, 4096};
    for (size_t length : lengths) {
        FaultRecord output {};
        output.sequence = UINT64_C(0xfeedface);
        CHECK(!decode(valid, length, output));
        CHECK(output.sequence == UINT64_C(0xfeedface));
    }
    const size_t reservedOffsets[] = {12, 60, 132, 164, 204, 280, 360};
    for (size_t offset : reservedOffsets) {
        uint8_t bad[WireSize];
        std::memcpy(bad, valid, sizeof bad);
        bad[offset] = 1;
        FaultRecord output {};
        output.sequence = 1;
        CHECK(!decode(bad, sizeof bad, output));
        CHECK(output.sequence == 1);
    }
    const size_t enumOffsets[] = {40, 48, 52, 56, 216, 220};
    for (size_t offset : enumOffsets) {
        uint8_t bad[WireSize];
        std::memcpy(bad, valid, sizeof bad);
        bad[offset] = 0xff;
        FaultRecord output {};
        output.sequence = 2;
        CHECK(!decode(bad, sizeof bad, output));
        CHECK(output.sequence == 2);
    }
    const size_t headerAndRangeOffsets[] = {0, 4, 8, 44};
    for (size_t offset : headerAndRangeOffsets) {
        uint8_t bad[WireSize];
        std::memcpy(bad, valid, sizeof bad);
        if (offset == 0) bad[offset] = 'X';
        else if (offset == 4) bad[offset] = 3;
        else if (offset == 8) bad[offset] = 0;
        else bad[offset] = 4; // readAttempts > three
        FaultRecord output {};
        output.sequence = 5;
        CHECK(!decode(bad, sizeof bad, output));
        CHECK(output.sequence == 5);
    }
    {
        uint8_t bad[WireSize];
        std::memcpy(bad, valid, sizeof bad);
        bad[16] = 0; bad[17] = 0; bad[18] = 0x80; // unknown presence bit
        FaultRecord output {};
        output.sequence = 3;
        CHECK(!decode(bad, sizeof bad, output));
        CHECK(output.sequence == 3);
    }
    {
        uint8_t bad[WireSize];
        std::memcpy(bad, valid, sizeof bad);
        bad[24] = 1; // unknown flag without canonical zero/value semantics
        FaultRecord output {};
        output.sequence = 4;
        CHECK(!decode(bad, sizeof bad, output));
        CHECK(output.sequence == 4);
    }
    return true;
}

static bool unknown_values_are_canonical_and_not_invented() {
    FaultRecord source = completeRecord();
    source.presence &= ~(mask(Field::ContextIdentity) | mask(Field::PML4) |
                         mask(Field::Engine) | mask(Field::AllocationGeneration));
    source.unknown |= mask(Field::ContextIdentity) | mask(Field::PML4) |
                      mask(Field::Engine) | mask(Field::AllocationGeneration);
    source.contextIdentity = source.pml4 = source.ringHead = source.allocationGeneration = 0;
    source.engineId = 0;
    source.presence &= ~mask(Field::RingHead);
    source.unknown |= mask(Field::RingHead);
    CHECK(validRecord(source));
    uint8_t bytes[WireSize] {};
    CHECK(encode(source, bytes, sizeof bytes));
    FaultRecord decoded {};
    CHECK(decode(bytes, sizeof bytes, decoded));
    CHECK((decoded.unknown & mask(Field::ContextIdentity)) != 0);
    CHECK(decoded.contextIdentity == 0 && decoded.pml4 == 0 && decoded.engineId == 0);
    CHECK(decoded.ringHead == 0 && decoded.allocationGeneration == 0);
    return true;
}

static bool derived_va_requires_both_gates() {
    FaultRecord source = completeRecord(true);
    CoherenceEvidence unknown;
    DerivedValue denied = deriveIfCoherent(source, unknown);
    CHECK(!denied.available);
    CoherenceEvidence pass;
    for (uint32_t i = 0; i < CoherenceConditionCount; ++i)
        pass.status[i] = EvidenceStatus::Pass;
    CHECK(deriveIfCoherent(source, pass).available);
    source.coherence[uint32_t(CoherenceCondition::Tuple)] = uint32_t(EvidenceStatus::Unknown);
    source.coherenceSummary = EvidenceStatus::Unknown;
    CHECK(!deriveIfCoherent(source, pass).available);
    return true;
}

static bool false_derived_claims_and_ranges_are_rejected() {
    FaultRecord canonical = completeRecord(true);
    uint8_t valid[WireSize] {};
    CHECK(encode(canonical, valid, sizeof valid));

    FaultRecord forged = canonical;
    forged.derivedVirtualAddress ^= UINT64_C(0x1000);
    CHECK(!validRecord(forged));
    CHECK(!encode(forged, valid, sizeof valid));
    FaultRecord orphan = completeRecord(false);
    orphan.presence |= mask(Field::DerivedVA);
    orphan.derivedVirtualAddress = UINT64_C(0xb89abcdef000);
    CHECK(!validRecord(orphan));
    uint8_t bad[WireSize];
    std::memcpy(bad, reinterpret_cast<const uint8_t *>(valid), sizeof bad);
    // Re-encode the canonical value after the expected encode rejection.
    CHECK(encode(canonical, bad, sizeof bad));
    bad[168] ^= 0x01; // false wire derived VA claim
    FaultRecord output = canonical;
    output.sequence = UINT64_C(0xaaaa);
    CHECK(!decode(bad, sizeof bad, output));
    CHECK(output.sequence == UINT64_C(0xaaaa));

    FaultRecord badEngine = canonical; badEngine.derivedEngineV618 = UINT32_MAX;
    FaultRecord badEngine515 = canonical; badEngine515.derivedEngineV515 = UINT32_MAX;
    FaultRecord badType = canonical; badType.derivedFaultType = UINT32_MAX;
    FaultRecord badSource = canonical; badSource.derivedSourceId = UINT32_MAX;
    FaultRecord badPage = canonical; badPage.derivedPageSize = UINT32_MAX;
    CHECK(!validRecord(badEngine)); CHECK(!validRecord(badEngine515));
    CHECK(!validRecord(badType)); CHECK(!validRecord(badSource)); CHECK(!validRecord(badPage));

    FaultRecord mbzRaw = completeRecord(false);
    mbzRaw.rawData1 = 0x800U;
    CHECK(validRecord(mbzRaw)); // raw is retained as untrusted data
    CHECK(encode(mbzRaw, valid, sizeof valid));
    FaultRecord mbzDecoded {};
    CHECK(decode(valid, sizeof valid, mbzDecoded));
    CoherenceEvidence pass;
    for (uint32_t i = 0; i < CoherenceConditionCount; ++i)
        pass.status[i] = EvidenceStatus::Pass;
    CHECK(!deriveIfCoherent(mbzDecoded, pass).available); // DATA1 MBZ blocks derivation
    mbzRaw.presence |= mask(Field::DerivedVA);
    mbzRaw.validity |= DerivedVAValid;
    mbzRaw.derivedFlags = 1;
    CHECK(!validRecord(mbzRaw)); // a derived claim cannot hide MBZ input
    return true;
}

static bool external_correlation_flag_is_bidirectional() {
    FaultRecord record = completeRecord(false);
    record.provenanceKind = ProvenanceKind::ExternalCorrelation;
    record.provenanceClaim = UINT64_C(0x1234);
    CHECK(!validRecord(record));
    record.captureFlags |= ExternalCorrelationFlag;
    CHECK(validRecord(record));
    record.captureFlags &= ~ExternalCorrelationFlag;
    CHECK(!validRecord(record));
    return true;
}

static bool raw_preservation_requires_read_safe_pass() {
    FaultRecord source = completeRecord();
    source.readSafety[uint32_t(ReadSafetyCondition::MMIOAddressMapping)] =
        uint32_t(EvidenceStatus::Unknown);
    source.readSafetySummary = EvidenceStatus::Unknown;
    uint8_t bytes[WireSize] {};
    CHECK(!validRecord(source));
    CHECK(!encode(source, bytes, sizeof bytes));
    source = completeRecord();
    source.derivedAddressSpace = AddressSpace::GGTT;
    CHECK(!validRecord(source)); // no derived-VA claim means no derived metadata
    return true;
}

static bool old_v1_decoder_and_dispatch_compatibility() {
    TglFault34::FaultRecord old {};
    old.validity = TglFault34::CompleteValidity;
    old.callerClaims = TglFault34::RequiredClaims;
    old.status = TglFault34::Status::Complete;
    old.readAttempts = 3;
    old.engineLayout = TglFault34::EngineLayout::LinuxV618FiveBit;
    old.forcewakeHeldDomains = TglFault34::DomainGT;
    old.forcewakeAckDomains = TglFault34::DomainGT;
    old.sequence = 1; old.monotonicNs = 2; old.bootId = 3; old.hangId = 4; old.callerId = 5;
    old.resetEpoch = 6; old.exclusionToken = 7;
    old.rawFault = 1; old.rawData0 = 2; old.rawData1 = 0;
    uint8_t v1[TglFault34::WireSize] {};
    CHECK(TglFault34::encode(old, v1, sizeof v1));
    TglFault34::FaultRecord oldOut {};
    CHECK(TglFault34::decode(v1, sizeof v1, oldOut));
    uint8_t v2[WireSize] {};
    FaultRecord source = completeRecord();
    CHECK(encode(source, v2, sizeof v2));
    oldOut.sequence = UINT64_C(0xabcdef);
    CHECK(!TglFault34::decode(v2, sizeof v2, oldOut));
    CHECK(oldOut.sequence == UINT64_C(0xabcdef));
    Ga37Dispatch::Decoded any {};
    CHECK(Ga37Dispatch::decodeAny(v1, sizeof v1, any));
    CHECK(any.format == Ga37Dispatch::Format::V1 && any.v1.sequence == 1);
    CHECK(Ga37Dispatch::decodeAny(v2, sizeof v2, any));
    CHECK(any.format == Ga37Dispatch::Format::V2 && any.v2.sequence == source.sequence);
    v2[4] = 3;
    any.format = Ga37Dispatch::Format::Invalid;
    CHECK(!Ga37Dispatch::decodeAny(v2, sizeof v2, any));
    CHECK(any.format == Ga37Dispatch::Format::Invalid);
    Ga37Dispatch::LegacyExternalCorrelation correlation {};
    CHECK(Ga37Dispatch::associateLegacyExternal(old, 0x1234, correlation));
    CHECK(correlation.externalReference == 0x1234 && correlation.report.sequence == 1);
    CHECK(Ga37FaultV2::validRecord(correlation.v2));
    CHECK(correlation.v2.status == RecordStatus::Refused);
    CHECK((correlation.v2.unknown & mask(Field::ContextIdentity)) != 0);
    CHECK(correlation.v2.contextIdentity == 0 && correlation.v2.pml4 == 0);
    CHECK((correlation.v2.validity & TupleValidity) == 0);
    uint8_t associated[WireSize] {};
    CHECK(Ga37FaultV2::encode(correlation.v2, associated, sizeof associated));
    const size_t oldLengths[] = {0, 1, 107, 109, 384};
    for (size_t length : oldLengths) {
        TglFault34::FaultRecord unchanged = old;
        unchanged.sequence = UINT64_C(0xabcdef);
        CHECK(!TglFault34::decode(v1, length, unchanged));
        CHECK(unchanged.sequence == UINT64_C(0xabcdef));
    }
    const size_t oldBadOffsets[] = {0, 4, 16, 20, 24, 104};
    for (size_t offset : oldBadOffsets) {
        uint8_t bad[TglFault34::WireSize];
        std::memcpy(bad, v1, sizeof bad);
        bad[offset] = 0xff;
        TglFault34::FaultRecord unchanged = old;
        unchanged.sequence = UINT64_C(0x123456);
        CHECK(!TglFault34::decode(bad, sizeof bad, unchanged));
        CHECK(unchanged.sequence == UINT64_C(0x123456));
    }
    return true;
}

int main(int argc, char **argv) {
    const char *samplePath = argc > 1 ? argv[1] : nullptr;
    if (!roundtrip_and_layout(samplePath)) return 1;
    if (!truncation_reserved_enum_unknown_and_atomic_output()) return 1;
    if (!unknown_values_are_canonical_and_not_invented()) return 1;
    if (!derived_va_requires_both_gates()) return 1;
    if (!false_derived_claims_and_ranges_are_rejected()) return 1;
    if (!external_correlation_flag_is_bidirectional()) return 1;
    if (!raw_preservation_requires_read_safe_pass()) return 1;
    if (!old_v1_decoder_and_dispatch_compatibility()) return 1;
    std::printf("NEGATIVE_AUDIT_REPROS_PASS false-derived/ranges/MBZ/external-flag\n");
    std::printf("CODEC_V2_PASS checks=%u wire_version=%u wire_size=%zu backend=NONE\n",
                checks, unsigned(WireVersion), WireSize);
    return 0;
}
