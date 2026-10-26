// SPDX-License-Identifier: MIT
// Strict TGF4 v1/v2 offline dispatcher.  Unknown versions are rejected.
#ifndef GA37_TGF4_DISPATCH_HPP
#define GA37_TGF4_DISPATCH_HPP

#include "fault_record_v2.hpp"
#include "legacy/kern_tglfault34.hpp"

namespace Ga37Dispatch {

enum class Format : uint32_t { Invalid = 0, V1 = 1, V2 = 2 };

struct Decoded {
    Format format = Format::Invalid;
    TglFault34::FaultRecord v1 {};
    Ga37FaultV2::FaultRecord v2 {};
};

inline uint64_t getLE(const uint8_t *bytes, size_t count) noexcept {
    uint64_t value = 0;
    for (size_t i = 0; i < count; ++i) value |= uint64_t(bytes[i]) << (i * 8);
    return value;
}

inline bool decodeAny(const uint8_t *bytes, size_t length, Decoded &out) noexcept {
    if (!bytes || length < 6 || getLE(bytes, 4) != Ga37FaultV2::WireMagic) return false;
    const uint16_t version = uint16_t(getLE(bytes + 4, 2));
    Decoded temp {};
    if (version == TglFault34::WireVersion) {
        if (!TglFault34::decode(bytes, length, temp.v1)) return false;
        temp.format = Format::V1;
    } else if (version == Ga37FaultV2::WireVersion) {
        if (!Ga37FaultV2::decode(bytes, length, temp.v2)) return false;
        temp.format = Format::V2;
    } else {
        return false;
    }
    out = temp;
    return true;
}

// An old report may be associated with an explicitly supplied opaque external
// reference.  It does not manufacture context, PML4, ring-head, engine or
// allocation-generation fields.  The reference is a provenance CLAIM, not
// self-authentication.
struct LegacyExternalCorrelation {
    TglFault34::FaultRecord report {};
    Ga37FaultV2::FaultRecord v2 {};
    uint64_t externalReference = 0;
};

inline bool makeLegacyExternalV2(const TglFault34::FaultRecord &report,
                                 uint64_t externalReference,
                                 Ga37FaultV2::FaultRecord &out) noexcept {
    if (!externalReference || !TglFault34::validRecord(report)) return false;
    Ga37FaultV2::FaultRecord temp {};
    using namespace Ga37FaultV2;
    temp.presence = fieldBit(Field::Sequence) | fieldBit(Field::MonotonicNs) |
        fieldBit(Field::BootId) | fieldBit(Field::HangId) | fieldBit(Field::CallerId) |
        fieldBit(Field::ResetEpoch) | fieldBit(Field::ExclusionToken) |
        fieldBit(Field::Provenance);
    temp.unknown = fieldBit(Field::RawFault) | fieldBit(Field::RawData0) |
        fieldBit(Field::RawData1) | fieldBit(Field::DerivedVA) |
        fieldBit(Field::ContextIdentity) | fieldBit(Field::PML4) |
        fieldBit(Field::RingHead) | fieldBit(Field::Engine) |
        fieldBit(Field::AllocationGeneration) | fieldBit(Field::ResetClearPhase) |
        fieldBit(Field::SweepEpoch) | fieldBit(Field::ReadTimestamp0) |
        fieldBit(Field::ReadTimestamp1) | fieldBit(Field::ReadTimestamp2);
    temp.captureFlags = ExternalCorrelationFlag;
    temp.validity = MetadataValid;
    temp.status = RecordStatus::Refused;
    temp.engineLayout = EngineLayout::LinuxV618FiveBit;
    temp.readSafetySummary = EvidenceStatus::Unknown;
    temp.coherenceSummary = EvidenceStatus::Unknown;
    temp.sequence = report.sequence;
    temp.monotonicNs = report.monotonicNs;
    temp.bootId = report.bootId;
    temp.hangId = report.hangId;
    temp.callerId = report.callerId;
    temp.resetEpoch = report.resetEpoch;
    temp.exclusionToken = report.exclusionToken;
    temp.provenanceKind = ProvenanceKind::ExternalCorrelation;
    temp.provenanceClaim = externalReference;
    ReadSafetyEvidence readSafety;
    for (uint32_t i = 0; i < ReadSafetyConditionCount; ++i)
        temp.readSafety[i] = uint32_t(readSafety.status[i]);
    for (uint32_t i = 0; i < CoherenceConditionCount; ++i)
        temp.coherence[i] = uint32_t(EvidenceStatus::Unknown);
    if (!validRecord(temp)) return false;
    out = temp;
    return true;
}

inline bool associateLegacyExternal(const TglFault34::FaultRecord &report,
                                    uint64_t externalReference,
                                    LegacyExternalCorrelation &out) noexcept {
    LegacyExternalCorrelation temp {};
    if (!makeLegacyExternalV2(report, externalReference, temp.v2)) return false;
    temp.report = report;
    temp.externalReference = externalReference;
    out = temp;
    return true;
}

} // namespace Ga37Dispatch
#endif
