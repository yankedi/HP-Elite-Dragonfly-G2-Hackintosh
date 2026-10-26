// SPDX-License-Identifier: MIT
// GA37 Track C: bounded, hosted-only TGF4 FaultRecord v2 codec.
// This file has no MMIO reader, kernel entry point, allocation, I/O backend,
// reset or power operation.  A record is data; it is not hardware evidence.
#ifndef GA37_FAULT_RECORD_V2_HPP
#define GA37_FAULT_RECORD_V2_HPP

#include <stddef.h>
#include <stdint.h>

namespace Ga37FaultV2 {

constexpr uint32_t WireMagic = 0x34464754U; // bytes T G F 4
constexpr uint16_t WireVersion = 2;
constexpr uint16_t WireHeaderSize = 16;
constexpr size_t WireSize = 384;
constexpr uint32_t WireHeaderFlags = 0;

enum class EvidenceStatus : uint32_t {
    Unknown = 0,
    Conditional = 1,
    Pass = 2,
    Failed = 3
};

enum class GateDecision : uint32_t {
    Blocked = 0,
    Conditional = 1,
    Failed = 2,
    Pass = 3,
    Invalid = 4,
    Disabled = 5
};

enum class ReadSafetyCondition : uint32_t {
    CorrectBinary = 0,
    CorrectHookABI = 1,
    CorrectGTDomain = 2,
    ObjectLifetime = 3,
    MMIOAddressMapping = 4,
    RuntimePowerHeld = 5,
    GTReferenceHeld = 6,
    SameRequestACK = 7,
    ReadSideEffects = 8,
    ResetClearTeardownExcluded = 9,
    RecoveryUnaffected = 10,
    DefaultDisabled = 11,
    Count = 12,
    // GA36 names retained as aliases; the new gate deliberately decomposes
    // MMIOReadSafe and ResetExcluded rather than collapsing their evidence.
    RuntimePower = RuntimePowerHeld,
    GTReference = GTReferenceHeld,
    ForcewakeReferenceHeld = GTReferenceHeld,
    ForcewakeACKConfirmed = SameRequestACK,
    MMIOReadSafe = ObjectLifetime,
    ResetExcluded = ResetClearTeardownExcluded
};

constexpr uint32_t ReadSafetyConditionCount = 12;

enum class CoherenceCondition : uint32_t {
    Tuple = 0,
    SweepEpoch = 1,
    Latch = 2,
    ABAExcluded = 3,
    Address = 4,
    ContextPML4 = 5,
    Engine = 6,
    AllocationGeneration = 7,
    ResetClearPhase = 8,
    Completeness = 9,
    Count = 10,
    FaultTupleConsistencyEstablished = Tuple
};

constexpr uint32_t CoherenceConditionCount = 10;

enum class RecordStatus : uint32_t {
    Complete = 0,
    Partial = 1,
    Refused = 2
};

enum class EngineLayout : uint32_t {
    LinuxV618FiveBit = 1
};

enum class AddressSpace : uint32_t {
    Unavailable = 0,
    PPGTT = 1,
    GGTT = 2
};

enum class ResetClearPhase : uint32_t {
    Unknown = 0,
    BeforeReset = 1,
    DuringReset = 2,
    AfterClear = 3,
    Stable = 4
};

enum class ProvenanceKind : uint32_t {
    None = 0,
    DirectReaderClaim = 1,
    LegacyReport = 2,
    ExternalCorrelation = 3,
    Synthetic = 4
};

enum CaptureFlag : uint32_t {
    ExplicitReadEnable = 1U << 0,
    RawPreserved = 1U << 1,
    ExternalCorrelationFlag = 1U << 2
};
constexpr uint32_t CaptureFlagsMask =
    ExplicitReadEnable | RawPreserved | ExternalCorrelationFlag;

enum ValidityFlag : uint32_t {
    RawFaultValid = 1U << 0,
    RawData0Valid = 1U << 1,
    RawData1Valid = 1U << 2,
    MetadataValid = 1U << 3,
    DerivedVAValid = 1U << 4
};
constexpr uint32_t ValidityMask =
    RawFaultValid | RawData0Valid | RawData1Valid |
    MetadataValid | DerivedVAValid;

enum class Field : uint32_t {
    RawFault = 0,
    RawData0 = 1,
    RawData1 = 2,
    Sequence = 3,
    MonotonicNs = 4,
    BootId = 5,
    HangId = 6,
    CallerId = 7,
    ResetEpoch = 8,
    ExclusionToken = 9,
    DerivedVA = 10,
    ContextIdentity = 11,
    PML4 = 12,
    RingHead = 13,
    Engine = 14,
    AllocationGeneration = 15,
    ResetClearPhase = 16,
    Provenance = 17,
    SweepEpoch = 18,
    ReadTimestamp0 = 19,
    ReadTimestamp1 = 20,
    ReadTimestamp2 = 21
};

constexpr uint64_t fieldBit(Field field) noexcept {
    return UINT64_C(1) << uint32_t(field);
}
constexpr uint64_t KnownFieldMask = (UINT64_C(1) << 22) - 1;

constexpr uint32_t TupleValidity = RawFaultValid | RawData0Valid | RawData1Valid;

struct ReadSafetyEvidence {
    bool explicitEnable = false;
    EvidenceStatus status[ReadSafetyConditionCount];

    ReadSafetyEvidence() noexcept : explicitEnable(false), status{} {
        // The default-off property is a software fact; every hardware-facing
        // condition remains UNKNOWN until an independent adjudicator supplies it.
        status[uint32_t(ReadSafetyCondition::DefaultDisabled)] = EvidenceStatus::Pass;
    }
};

struct CoherenceEvidence {
    EvidenceStatus status[CoherenceConditionCount];
    CoherenceEvidence() noexcept : status{} {}
};

struct GateResult {
    GateDecision decision = GateDecision::Blocked;
    uint32_t passMask = 0;
    uint32_t unknownMask = 0;
    uint32_t conditionalMask = 0;
    uint32_t failedMask = 0;
    uint32_t invalidMask = 0;
    bool allowed = false;
};

inline bool validEvidence(EvidenceStatus status) noexcept {
    return uint32_t(status) <= uint32_t(EvidenceStatus::Failed);
}

inline GateResult evaluateReadSafety(const ReadSafetyEvidence &evidence) noexcept {
    GateResult result {};
    for (uint32_t i = 0; i < ReadSafetyConditionCount; ++i) {
        const uint32_t bit = 1U << i;
        switch (evidence.status[i]) {
            case EvidenceStatus::Pass: result.passMask |= bit; break;
            case EvidenceStatus::Unknown: result.unknownMask |= bit; break;
            case EvidenceStatus::Conditional: result.conditionalMask |= bit; break;
            case EvidenceStatus::Failed: result.failedMask |= bit; break;
            default: result.invalidMask |= bit; break;
        }
    }
    if (result.invalidMask) result.decision = GateDecision::Invalid;
    else if (result.unknownMask) result.decision = GateDecision::Blocked;
    else if (result.conditionalMask) result.decision = GateDecision::Conditional;
    else if (result.failedMask) result.decision = GateDecision::Failed;
    else if (!evidence.explicitEnable) result.decision = GateDecision::Disabled;
    else {
        result.decision = GateDecision::Pass;
        result.allowed = true;
    }
    // Explicit enable is never implied by a PASS matrix.
    if (!evidence.explicitEnable) result.allowed = false;
    return result;
}

inline GateResult evaluateCoherence(const CoherenceEvidence &evidence) noexcept {
    GateResult result {};
    for (uint32_t i = 0; i < CoherenceConditionCount; ++i) {
        const uint32_t bit = 1U << i;
        switch (evidence.status[i]) {
            case EvidenceStatus::Pass: result.passMask |= bit; break;
            case EvidenceStatus::Unknown: result.unknownMask |= bit; break;
            case EvidenceStatus::Conditional: result.conditionalMask |= bit; break;
            case EvidenceStatus::Failed: result.failedMask |= bit; break;
            default: result.invalidMask |= bit; break;
        }
    }
    if (result.invalidMask) result.decision = GateDecision::Invalid;
    else if (result.unknownMask) result.decision = GateDecision::Blocked;
    else if (result.conditionalMask) result.decision = GateDecision::Conditional;
    else if (result.failedMask) result.decision = GateDecision::Failed;
    else {
        result.decision = GateDecision::Pass;
        result.allowed = true;
    }
    return result;
}

inline const char *readSafetyConditionName(ReadSafetyCondition condition) noexcept {
    switch (condition) {
        case ReadSafetyCondition::CorrectBinary: return "CorrectBinary";
        case ReadSafetyCondition::CorrectHookABI: return "CorrectHookABI";
        case ReadSafetyCondition::CorrectGTDomain: return "CorrectGTDomain";
        case ReadSafetyCondition::ObjectLifetime: return "ObjectLifetime";
        case ReadSafetyCondition::MMIOAddressMapping: return "MMIOAddressMapping";
        case ReadSafetyCondition::RuntimePowerHeld: return "RuntimePowerHeld";
        case ReadSafetyCondition::GTReferenceHeld: return "GTReferenceHeld";
        case ReadSafetyCondition::SameRequestACK: return "SameRequestACK";
        case ReadSafetyCondition::ReadSideEffects: return "ReadSideEffects";
        case ReadSafetyCondition::ResetClearTeardownExcluded:
            return "ResetClearTeardownExcluded";
        case ReadSafetyCondition::RecoveryUnaffected: return "RecoveryUnaffected";
        case ReadSafetyCondition::DefaultDisabled: return "DefaultDisabled";
        default: return "InvalidReadSafetyCondition";
    }
}

inline const char *coherenceConditionName(CoherenceCondition condition) noexcept {
    switch (condition) {
        case CoherenceCondition::Tuple: return "Tuple";
        case CoherenceCondition::SweepEpoch: return "SweepEpoch";
        case CoherenceCondition::Latch: return "Latch";
        case CoherenceCondition::ABAExcluded: return "ABAExcluded";
        case CoherenceCondition::Address: return "Address";
        case CoherenceCondition::ContextPML4: return "ContextPML4";
        case CoherenceCondition::Engine: return "Engine";
        case CoherenceCondition::AllocationGeneration: return "AllocationGeneration";
        case CoherenceCondition::ResetClearPhase: return "ResetClearPhase";
        case CoherenceCondition::Completeness: return "Completeness";
        default: return "InvalidCoherenceCondition";
    }
}

struct FaultRecord {
    uint64_t presence = 0;
    uint64_t unknown = 0;
    uint32_t captureFlags = 0;
    uint32_t validity = 0;
    RecordStatus status = RecordStatus::Refused;
    uint32_t readAttempts = 0;
    EngineLayout engineLayout = EngineLayout::LinuxV618FiveBit;
    EvidenceStatus readSafetySummary = EvidenceStatus::Unknown;
    EvidenceStatus coherenceSummary = EvidenceStatus::Unknown;

    uint64_t sequence = 0;
    uint64_t monotonicNs = 0;
    uint64_t bootId = 0;
    uint64_t hangId = 0;
    uint64_t callerId = 0;
    uint64_t resetEpoch = 0;
    uint64_t exclusionToken = 0;

    // Raw DWORDs are not derived addresses and are never silently converted
    // into context, PML4, engine or allocation identities.
    uint32_t rawFault = 0;
    uint32_t rawData0 = 0;
    uint32_t rawData1 = 0;

    uint32_t derivedFlags = 0;
    AddressSpace derivedAddressSpace = AddressSpace::Unavailable;
    uint32_t derivedEngineV618 = 0;
    uint32_t derivedEngineV515 = 0;
    uint32_t derivedFaultType = 0;
    uint32_t derivedSourceId = 0;
    uint32_t derivedPageSize = 0;
    uint64_t derivedVirtualAddress = 0;

    uint64_t contextIdentity = 0;
    uint64_t pml4 = 0;
    uint64_t ringHead = 0;
    uint32_t engineId = 0;
    uint64_t allocationGeneration = 0;
    ResetClearPhase resetClearPhase = ResetClearPhase::Unknown;
    ProvenanceKind provenanceKind = ProvenanceKind::None;
    uint64_t provenanceClaim = 0;

    uint32_t readSafety[ReadSafetyConditionCount] {};
    uint32_t coherence[CoherenceConditionCount] {};
    uint64_t readTimestamp[3] {};
    uint64_t sweepEpoch = 0;
};

namespace Detail {
inline void put(uint8_t *p, uint64_t value, size_t bytes) noexcept {
    for (size_t i = 0; i < bytes; ++i) p[i] = uint8_t(value >> (i * 8));
}
inline uint64_t get(const uint8_t *p, size_t bytes) noexcept {
    uint64_t value = 0;
    for (size_t i = 0; i < bytes; ++i) value |= uint64_t(p[i]) << (i * 8);
    return value;
}
inline bool zero(const uint8_t *p, size_t bytes) noexcept {
    for (size_t i = 0; i < bytes; ++i) if (p[i] != 0) return false;
    return true;
}
} // namespace Detail

inline bool statusArrayValid(const uint32_t *values, uint32_t count) noexcept {
    for (uint32_t i = 0; i < count; ++i)
        if (values[i] > uint32_t(EvidenceStatus::Failed)) return false;
    return true;
}

inline EvidenceStatus summaryOf(const uint32_t *values, uint32_t count) noexcept {
    bool unknown = false, conditional = false, failed = false;
    for (uint32_t i = 0; i < count; ++i) {
        switch (static_cast<EvidenceStatus>(values[i])) {
            case EvidenceStatus::Pass: break;
            case EvidenceStatus::Unknown: unknown = true; break;
            case EvidenceStatus::Conditional: conditional = true; break;
            case EvidenceStatus::Failed: failed = true; break;
            default: return EvidenceStatus::Failed;
        }
    }
    if (unknown) return EvidenceStatus::Unknown;
    if (conditional) return EvidenceStatus::Conditional;
    if (failed) return EvidenceStatus::Failed;
    return EvidenceStatus::Pass;
}

inline bool fieldKnown(uint64_t presence, uint64_t unknown, Field field) noexcept {
    const uint64_t bit = fieldBit(field);
    return (presence & bit) != 0 && (unknown & bit) == 0;
}

inline bool fieldUnknown(uint64_t presence, uint64_t unknown, Field field) noexcept {
    const uint64_t bit = fieldBit(field);
    return (presence & bit) == 0 && (unknown & bit) != 0;
}

inline bool noValueWhenAbsentOrUnknown(const FaultRecord &r) noexcept {
    const uint64_t p = r.presence;
    const uint64_t u = r.unknown;
    if ((!fieldKnown(p, u, Field::RawFault) && r.rawFault) ||
        (!fieldKnown(p, u, Field::RawData0) && r.rawData0) ||
        (!fieldKnown(p, u, Field::RawData1) && r.rawData1) ||
        (!fieldKnown(p, u, Field::Sequence) && r.sequence) ||
        (!fieldKnown(p, u, Field::MonotonicNs) && r.monotonicNs) ||
        (!fieldKnown(p, u, Field::BootId) && r.bootId) ||
        (!fieldKnown(p, u, Field::HangId) && r.hangId) ||
        (!fieldKnown(p, u, Field::CallerId) && r.callerId) ||
        (!fieldKnown(p, u, Field::ResetEpoch) && r.resetEpoch) ||
        (!fieldKnown(p, u, Field::ExclusionToken) && r.exclusionToken) ||
        (!fieldKnown(p, u, Field::DerivedVA) && r.derivedVirtualAddress) ||
        (!fieldKnown(p, u, Field::ContextIdentity) && r.contextIdentity) ||
        (!fieldKnown(p, u, Field::PML4) && r.pml4) ||
        (!fieldKnown(p, u, Field::RingHead) && r.ringHead) ||
        (!fieldKnown(p, u, Field::Engine) && r.engineId) ||
        (!fieldKnown(p, u, Field::AllocationGeneration) && r.allocationGeneration) ||
        (!fieldKnown(p, u, Field::ResetClearPhase) && uint32_t(r.resetClearPhase)) ||
        (!fieldKnown(p, u, Field::Provenance) &&
         (uint32_t(r.provenanceKind) || r.provenanceClaim)) ||
        (!fieldKnown(p, u, Field::SweepEpoch) && r.sweepEpoch) ||
        (!fieldKnown(p, u, Field::ReadTimestamp0) && r.readTimestamp[0]) ||
        (!fieldKnown(p, u, Field::ReadTimestamp1) && r.readTimestamp[1]) ||
        (!fieldKnown(p, u, Field::ReadTimestamp2) && r.readTimestamp[2])) return false;
    return true;
}

inline bool readSafetyPass(const FaultRecord &r) noexcept {
    if (!(r.captureFlags & ExplicitReadEnable) ||
        !(r.captureFlags & RawPreserved) ||
        r.readSafetySummary != EvidenceStatus::Pass ||
        !statusArrayValid(r.readSafety, ReadSafetyConditionCount)) return false;
    for (uint32_t i = 0; i < ReadSafetyConditionCount; ++i)
        if (r.readSafety[i] != uint32_t(EvidenceStatus::Pass)) return false;
    return true;
}

inline bool coherencePass(const FaultRecord &r) noexcept {
    if (r.coherenceSummary != EvidenceStatus::Pass ||
        !statusArrayValid(r.coherence, CoherenceConditionCount)) return false;
    for (uint32_t i = 0; i < CoherenceConditionCount; ++i)
        if (r.coherence[i] != uint32_t(EvidenceStatus::Pass)) return false;
    return true;
}

// These masks and bounds are the v1/TGL source semantics carried into v2.
// They are applied only when a caller asks for a derived interpretation; raw
// DWORDs remain preservable opaque data even when DATA1 contains MBZ bits.
constexpr uint32_t FaultValidMask = 0x1U;
constexpr uint32_t FaultTypeMask = 0x6U;
constexpr uint32_t FaultSourceMask = 0x7f8U;
constexpr uint32_t FaultEngineMaskV618 = 0x1f000U;
constexpr uint32_t FaultEngineMaskV515 = 0x7000U;
constexpr uint32_t VaHighMask = 0xfU;
constexpr uint32_t GttSelectMask = 0x10U;
constexpr uint32_t Data1MbzMask = 0xfffffe00U;
constexpr uint32_t EntryPageSizeMask = 0x180U;
constexpr uint32_t MaxEngineV618 = 31U;
constexpr uint32_t MaxEngineV515 = 7U;
constexpr uint32_t MaxFaultType = 3U;
constexpr uint32_t MaxSourceId = 255U;
constexpr uint32_t MaxPageSize = 3U;

inline bool checkedPageToVA(uint64_t page, uint64_t &out) noexcept {
    if (page > UINT64_C(0xfffffffff)) return false;
    out = page << 12;
    return true;
}

struct CanonicalDerived {
    AddressSpace addressSpace = AddressSpace::Unavailable;
    uint32_t engineV618 = 0;
    uint32_t engineV515 = 0;
    uint32_t faultType = 0;
    uint32_t sourceId = 0;
    uint32_t pageSize = 0;
    uint64_t virtualAddress = 0;
};

inline bool calculateCanonicalDerived(const FaultRecord &r,
                                      CanonicalDerived &out) noexcept {
    if ((r.validity & TupleValidity) != TupleValidity ||
        !fieldKnown(r.presence, r.unknown, Field::RawFault) ||
        !fieldKnown(r.presence, r.unknown, Field::RawData0) ||
        !fieldKnown(r.presence, r.unknown, Field::RawData1) ||
        !(r.rawFault & FaultValidMask) || (r.rawData1 & Data1MbzMask)) return false;
    const uint64_t page = (uint64_t(r.rawData1 & VaHighMask) << 32) | r.rawData0;
    if (!checkedPageToVA(page, out.virtualAddress)) return false;
    out.addressSpace = (r.rawData1 & GttSelectMask) ? AddressSpace::GGTT : AddressSpace::PPGTT;
    out.engineV618 = (r.rawFault & FaultEngineMaskV618) >> 12;
    out.engineV515 = (r.rawFault & FaultEngineMaskV515) >> 12;
    out.sourceId = (r.rawFault & FaultSourceMask) >> 3;
    out.faultType = (r.rawFault & FaultTypeMask) >> 1;
    out.pageSize = (r.rawData1 & EntryPageSizeMask) >> 7;
    return out.engineV618 <= MaxEngineV618 && out.engineV515 <= MaxEngineV515 &&
        out.faultType <= MaxFaultType && out.sourceId <= MaxSourceId &&
        out.pageSize <= MaxPageSize;
}

inline bool validRecord(const FaultRecord &r) noexcept {
    if ((r.presence & ~KnownFieldMask) || (r.unknown & ~KnownFieldMask) ||
        (r.presence & r.unknown) || (r.captureFlags & ~CaptureFlagsMask) ||
        (r.validity & ~ValidityMask) || !noValueWhenAbsentOrUnknown(r) ||
        !statusArrayValid(r.readSafety, ReadSafetyConditionCount) ||
        !statusArrayValid(r.coherence, CoherenceConditionCount) ||
        !validEvidence(r.readSafetySummary) || !validEvidence(r.coherenceSummary) ||
        r.readSafetySummary != summaryOf(r.readSafety, ReadSafetyConditionCount) ||
        r.coherenceSummary != summaryOf(r.coherence, CoherenceConditionCount) ||
        uint32_t(r.status) > uint32_t(RecordStatus::Refused) ||
        uint32_t(r.engineLayout) != uint32_t(EngineLayout::LinuxV618FiveBit) ||
        r.readAttempts > 3 || r.derivedFlags & ~1U ||
        uint32_t(r.derivedAddressSpace) > uint32_t(AddressSpace::GGTT) ||
        uint32_t(r.resetClearPhase) > uint32_t(ResetClearPhase::Stable) ||
        uint32_t(r.provenanceKind) > uint32_t(ProvenanceKind::Synthetic)) return false;

    if ((fieldKnown(r.presence, r.unknown, Field::ResetClearPhase) &&
         r.resetClearPhase == ResetClearPhase::Unknown) ||
        (fieldKnown(r.presence, r.unknown, Field::Provenance) &&
         r.provenanceKind == ProvenanceKind::None)) return false;

    constexpr uint64_t required = fieldBit(Field::Sequence) |
        fieldBit(Field::MonotonicNs) | fieldBit(Field::BootId) |
        fieldBit(Field::HangId) | fieldBit(Field::CallerId) |
        fieldBit(Field::ResetEpoch) | fieldBit(Field::ExclusionToken);
    if ((r.presence & required) != required || (r.unknown & required) ||
        !r.sequence || !r.monotonicNs || !r.bootId || !r.hangId ||
        !r.callerId || !r.resetEpoch || !r.exclusionToken ||
        !(r.validity & MetadataValid)) return false;

    const uint32_t rawValidity = r.validity & TupleValidity;
    const uint32_t rawPresence =
        (fieldKnown(r.presence, r.unknown, Field::RawFault) ? RawFaultValid : 0U) |
        (fieldKnown(r.presence, r.unknown, Field::RawData0) ? RawData0Valid : 0U) |
        (fieldKnown(r.presence, r.unknown, Field::RawData1) ? RawData1Valid : 0U);
    if (rawValidity != rawPresence) return false;
    if (r.status == RecordStatus::Complete) {
        if (r.readAttempts != 3 || rawValidity != TupleValidity ||
            !readSafetyPass(r)) return false;
    } else if (r.status == RecordStatus::Partial) {
        const uint32_t expected = r.readAttempts == 0 ? 0U : (1U << r.readAttempts) - 1U;
        if (rawValidity != expected || (r.readAttempts && !readSafetyPass(r))) return false;
    } else if (r.readAttempts != 0 || rawValidity != 0 ||
               (r.captureFlags & RawPreserved)) return false;

    if ((r.captureFlags & ExternalCorrelationFlag) &&
        (!fieldKnown(r.presence, r.unknown, Field::Provenance) ||
         r.provenanceKind != ProvenanceKind::ExternalCorrelation ||
         !r.provenanceClaim)) return false;
    if (r.provenanceKind == ProvenanceKind::ExternalCorrelation &&
        (!(r.captureFlags & ExternalCorrelationFlag) ||
         !fieldKnown(r.presence, r.unknown, Field::Provenance) ||
         !r.provenanceClaim)) return false;
    if (r.captureFlags & RawPreserved) {
        if (!rawValidity || !readSafetyPass(r)) return false;
    }
    if (r.derivedFlags & 1U) {
        if (!fieldKnown(r.presence, r.unknown, Field::DerivedVA) ||
            !(r.validity & DerivedVAValid) || rawValidity != TupleValidity ||
            !readSafetyPass(r) || !coherencePass(r)) return false;
        CanonicalDerived canonical {};
        if (!calculateCanonicalDerived(r, canonical) ||
            r.derivedAddressSpace != canonical.addressSpace ||
            r.derivedEngineV618 != canonical.engineV618 ||
            r.derivedEngineV515 != canonical.engineV515 ||
            r.derivedFaultType != canonical.faultType ||
            r.derivedSourceId != canonical.sourceId ||
            r.derivedPageSize != canonical.pageSize ||
            r.derivedVirtualAddress != canonical.virtualAddress) return false;
    } else if (fieldKnown(r.presence, r.unknown, Field::DerivedVA) ||
               (r.validity & DerivedVAValid) || r.derivedVirtualAddress ||
               r.derivedAddressSpace != AddressSpace::Unavailable ||
               r.derivedEngineV618 || r.derivedEngineV515 ||
               r.derivedFaultType || r.derivedSourceId || r.derivedPageSize) return false;

    const bool allReadTimes = fieldKnown(r.presence, r.unknown, Field::ReadTimestamp0) &&
        fieldKnown(r.presence, r.unknown, Field::ReadTimestamp1) &&
        fieldKnown(r.presence, r.unknown, Field::ReadTimestamp2);
    if (allReadTimes && (r.readTimestamp[0] > r.readTimestamp[1] ||
                         r.readTimestamp[1] > r.readTimestamp[2])) return false;
    return true;
}

struct DerivedValue {
    bool available = false;
    uint64_t virtualAddress = 0;
};

// This is deliberately the only derived-VA helper.  It requires an external
// coherence PASS and an independently read-safe record.  It never fills any
// absent context, PML4, ring-head, engine or allocation-generation field.
inline DerivedValue deriveIfCoherent(const FaultRecord &r,
                                     const CoherenceEvidence &evidence) noexcept {
    DerivedValue result {};
    const GateResult gate = evaluateCoherence(evidence);
    if (!validRecord(r) || r.status != RecordStatus::Complete ||
        !readSafetyPass(r) || !coherencePass(r) || !gate.allowed ||
        !(r.rawFault & FaultValidMask)) return result;
    CanonicalDerived canonical {};
    if (!calculateCanonicalDerived(r, canonical)) return DerivedValue {};
    result.virtualAddress = canonical.virtualAddress;
    result.available = true;
    return result;
}

inline bool encode(const FaultRecord &r, uint8_t *out, size_t length) noexcept {
    if (!out || length != WireSize || !validRecord(r)) return false;
    uint8_t b[WireSize] {};
    using Detail::put;
    put(b + 0, WireMagic, 4); put(b + 4, WireVersion, 2);
    put(b + 6, WireHeaderSize, 2); put(b + 8, WireSize, 4);
    put(b + 12, WireHeaderFlags, 4);
    put(b + 16, r.presence, 8); put(b + 24, r.unknown, 8);
    put(b + 32, r.captureFlags, 4); put(b + 36, r.validity, 4);
    put(b + 40, uint32_t(r.status), 4); put(b + 44, r.readAttempts, 4);
    put(b + 48, uint32_t(r.engineLayout), 4);
    put(b + 52, uint32_t(r.readSafetySummary), 4);
    put(b + 56, uint32_t(r.coherenceSummary), 4);
    put(b + 64, r.sequence, 8); put(b + 72, r.monotonicNs, 8);
    put(b + 80, r.bootId, 8); put(b + 88, r.hangId, 8);
    put(b + 96, r.callerId, 8); put(b + 104, r.resetEpoch, 8);
    put(b + 112, r.exclusionToken, 8);
    put(b + 120, r.rawFault, 4); put(b + 124, r.rawData0, 4);
    put(b + 128, r.rawData1, 4);
    put(b + 136, r.derivedFlags, 4); put(b + 140, uint32_t(r.derivedAddressSpace), 4);
    put(b + 144, r.derivedEngineV618, 4); put(b + 148, r.derivedEngineV515, 4);
    put(b + 152, r.derivedFaultType, 4); put(b + 156, r.derivedSourceId, 4);
    put(b + 160, r.derivedPageSize, 4); put(b + 168, r.derivedVirtualAddress, 8);
    put(b + 176, r.contextIdentity, 8); put(b + 184, r.pml4, 8);
    put(b + 192, r.ringHead, 8); put(b + 200, r.engineId, 4);
    put(b + 208, r.allocationGeneration, 8);
    put(b + 216, uint32_t(r.resetClearPhase), 4);
    put(b + 220, uint32_t(r.provenanceKind), 4); put(b + 224, r.provenanceClaim, 8);
    for (uint32_t i = 0; i < ReadSafetyConditionCount; ++i)
        put(b + 232 + i * 4, r.readSafety[i], 4);
    for (uint32_t i = 0; i < CoherenceConditionCount; ++i)
        put(b + 288 + i * 4, r.coherence[i], 4);
    put(b + 328, r.readTimestamp[0], 8); put(b + 336, r.readTimestamp[1], 8);
    put(b + 344, r.readTimestamp[2], 8); put(b + 352, r.sweepEpoch, 8);
    for (size_t i = 0; i < WireSize; ++i) out[i] = b[i];
    return true;
}

inline bool decode(const uint8_t *bytes, size_t length, FaultRecord &out) noexcept {
    if (!bytes || length != WireSize) return false;
    using Detail::get;
    if (get(bytes + 0, 4) != WireMagic || get(bytes + 4, 2) != WireVersion ||
        get(bytes + 6, 2) != WireHeaderSize || get(bytes + 8, 4) != WireSize ||
        get(bytes + 12, 4) != WireHeaderFlags ||
        !Detail::zero(bytes + 60, 4) || !Detail::zero(bytes + 132, 4) ||
        !Detail::zero(bytes + 164, 4) || !Detail::zero(bytes + 204, 4) ||
        !Detail::zero(bytes + 280, 8) || !Detail::zero(bytes + 360, 24)) return false;
    FaultRecord r {};
    r.presence = get(bytes + 16, 8); r.unknown = get(bytes + 24, 8);
    r.captureFlags = uint32_t(get(bytes + 32, 4)); r.validity = uint32_t(get(bytes + 36, 4));
    r.status = static_cast<RecordStatus>(get(bytes + 40, 4));
    r.readAttempts = uint32_t(get(bytes + 44, 4));
    r.engineLayout = static_cast<EngineLayout>(get(bytes + 48, 4));
    r.readSafetySummary = static_cast<EvidenceStatus>(get(bytes + 52, 4));
    r.coherenceSummary = static_cast<EvidenceStatus>(get(bytes + 56, 4));
    r.sequence = get(bytes + 64, 8); r.monotonicNs = get(bytes + 72, 8);
    r.bootId = get(bytes + 80, 8); r.hangId = get(bytes + 88, 8);
    r.callerId = get(bytes + 96, 8); r.resetEpoch = get(bytes + 104, 8);
    r.exclusionToken = get(bytes + 112, 8);
    r.rawFault = uint32_t(get(bytes + 120, 4)); r.rawData0 = uint32_t(get(bytes + 124, 4));
    r.rawData1 = uint32_t(get(bytes + 128, 4));
    r.derivedFlags = uint32_t(get(bytes + 136, 4));
    r.derivedAddressSpace = static_cast<AddressSpace>(get(bytes + 140, 4));
    r.derivedEngineV618 = uint32_t(get(bytes + 144, 4));
    r.derivedEngineV515 = uint32_t(get(bytes + 148, 4));
    r.derivedFaultType = uint32_t(get(bytes + 152, 4));
    r.derivedSourceId = uint32_t(get(bytes + 156, 4));
    r.derivedPageSize = uint32_t(get(bytes + 160, 4));
    r.derivedVirtualAddress = get(bytes + 168, 8);
    r.contextIdentity = get(bytes + 176, 8); r.pml4 = get(bytes + 184, 8);
    r.ringHead = get(bytes + 192, 8); r.engineId = uint32_t(get(bytes + 200, 4));
    r.allocationGeneration = get(bytes + 208, 8);
    r.resetClearPhase = static_cast<ResetClearPhase>(get(bytes + 216, 4));
    r.provenanceKind = static_cast<ProvenanceKind>(get(bytes + 220, 4));
    r.provenanceClaim = get(bytes + 224, 8);
    for (uint32_t i = 0; i < ReadSafetyConditionCount; ++i)
        r.readSafety[i] = uint32_t(get(bytes + 232 + i * 4, 4));
    for (uint32_t i = 0; i < CoherenceConditionCount; ++i)
        r.coherence[i] = uint32_t(get(bytes + 288 + i * 4, 4));
    r.readTimestamp[0] = get(bytes + 328, 8); r.readTimestamp[1] = get(bytes + 336, 8);
    r.readTimestamp[2] = get(bytes + 344, 8); r.sweepEpoch = get(bytes + 352, 8);
    if (!validRecord(r)) return false;
    out = r; // atomic output parameter: no mutation before every check succeeds
    return true;
}

} // namespace Ga37FaultV2
#endif
