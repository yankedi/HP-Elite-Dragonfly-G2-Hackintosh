#include "fault_record_v2.hpp"
#include <cstdint>
#include <cstdio>
#include <cstring>
using namespace Ga37FaultV2;
static uint64_t m(Field f) { return fieldBit(f); }
static FaultRecord canonical(bool derived) {
    FaultRecord r{};
    r.presence = m(Field::RawFault)|m(Field::RawData0)|m(Field::RawData1)|
        m(Field::Sequence)|m(Field::MonotonicNs)|m(Field::BootId)|m(Field::HangId)|
        m(Field::CallerId)|m(Field::ResetEpoch)|m(Field::ExclusionToken)|
        m(Field::ResetClearPhase)|m(Field::Provenance);
    r.unknown = m(Field::ContextIdentity)|m(Field::PML4)|m(Field::RingHead)|
        m(Field::Engine)|m(Field::AllocationGeneration);
    r.captureFlags = ExplicitReadEnable|RawPreserved;
    r.validity = TupleValidity|MetadataValid;
    r.status = RecordStatus::Complete; r.readAttempts = 3;
    r.readSafetySummary = EvidenceStatus::Pass; r.coherenceSummary = EvidenceStatus::Pass;
    r.sequence=1; r.monotonicNs=2; r.bootId=3; r.hangId=4; r.callerId=5;
    r.resetEpoch=6; r.exclusionToken=7;
    r.rawFault = 0x1f000U | (0xa5U << 3) | 7U;
    r.rawData0 = 0x89abcdefU; r.rawData1 = 0x1fbU;
    r.resetClearPhase=ResetClearPhase::Stable; r.provenanceKind=ProvenanceKind::Synthetic;
    for (auto &x:r.readSafety) x=uint32_t(EvidenceStatus::Pass);
    for (auto &x:r.coherence) x=uint32_t(EvidenceStatus::Pass);
    if (derived) {
        r.presence |= m(Field::DerivedVA); r.validity |= DerivedVAValid; r.derivedFlags=1;
        r.derivedAddressSpace=AddressSpace::GGTT; r.derivedEngineV618=31;
        r.derivedEngineV515=7; r.derivedFaultType=3; r.derivedSourceId=0xa5;
        r.derivedPageSize=3; r.derivedVirtualAddress=UINT64_C(0xb89abcdef000);
    }
    return r;
}
static bool allPass(CoherenceEvidence &e) {
    for (auto &x:e.status) x=EvidenceStatus::Pass; return true;
}
int main() {
    CoherenceEvidence evidence{}; allPass(evidence);
    FaultRecord r=canonical(true);
    const uint64_t expected = (uint64_t(r.rawData1 & 0xfU) << 44) | (uint64_t(r.rawData0) << 12);
    DerivedValue d=deriveIfCoherent(r,evidence);
    uint8_t bytes[WireSize]{}; FaultRecord decoded{};
    bool roundtrip=validRecord(r)&&encode(r,bytes,sizeof bytes)&&decode(bytes,sizeof bytes,decoded);
    std::printf("RAW_DERIVED_EQUAL valid=%d derive=%d expected=0x%llx actual=0x%llx roundtrip=%d\n",
        int(validRecord(r)), int(d.available), (unsigned long long)expected,
        (unsigned long long)d.virtualAddress, int(roundtrip && decoded.derivedVirtualAddress==expected &&
            decoded.derivedEngineV618==31 && decoded.derivedEngineV515==7 &&
            decoded.derivedFaultType==3 && decoded.derivedSourceId==0xa5 && decoded.derivedPageSize==3));

    std::printf("UNKNOWN_OPTIONAL valid=%d decoded=%d context=0x%llx pml4=0x%llx ring=0x%llx engine=%u alloc=0x%llx unknown=0x%llx\n",
        int(validRecord(r)), int(roundtrip), (unsigned long long)decoded.contextIdentity,
        (unsigned long long)decoded.pml4, (unsigned long long)decoded.ringHead,
        decoded.engineId, (unsigned long long)decoded.allocationGeneration,
        (unsigned long long)(decoded.unknown & (m(Field::ContextIdentity)|m(Field::PML4)|m(Field::RingHead)|m(Field::Engine)|m(Field::AllocationGeneration))));

    FaultRecord forged=r; forged.derivedVirtualAddress ^= UINT64_C(0x1000);
    std::printf("FORGED_DERIVED_REJECT valid=%d encode=%d\n", int(validRecord(forged)), int(encode(forged,bytes,sizeof bytes)));

    FaultRecord mbz=canonical(false); mbz.rawData1=0x800U;
    FaultRecord mbzOut{}; bool mbzRaw=validRecord(mbz)&&encode(mbz,bytes,sizeof bytes)&&decode(bytes,sizeof bytes,mbzOut);
    DerivedValue denied=deriveIfCoherent(mbzOut,evidence);
    std::printf("MBZ_RAW_RETAINED raw_valid=%d derived_available=%d rawData1=0x%x\n", int(mbzRaw), int(denied.available), mbzOut.rawData1);

    FaultRecord ext=canonical(false); ext.captureFlags|=ExternalCorrelationFlag;
    ext.provenanceKind=ProvenanceKind::ExternalCorrelation; ext.provenanceClaim=0x1234;
    std::printf("PROVENANCE_EXPLICIT_UNTRUSTED valid=%d flag=%d claim=0x%llx\n", int(validRecord(ext)),
        int((ext.captureFlags&ExternalCorrelationFlag)!=0), (unsigned long long)ext.provenanceClaim);
    return (validRecord(r)&&d.available&&roundtrip&&d.virtualAddress==expected&&
            decoded.derivedVirtualAddress==expected&&decoded.contextIdentity==0&&decoded.pml4==0&&
            decoded.ringHead==0&&decoded.engineId==0&&decoded.allocationGeneration==0&&
            !validRecord(forged)&&!encode(forged,bytes,sizeof bytes)&&mbzRaw&&!denied.available&&validRecord(ext))?0:1;
}
