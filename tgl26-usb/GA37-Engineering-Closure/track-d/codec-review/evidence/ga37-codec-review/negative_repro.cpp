#include "fault_record_v2.hpp"
#include <cstdint>
#include <cstdio>
using namespace Ga37FaultV2;
static FaultRecord rbase() {
    FaultRecord r{}; auto f=[](Field x){return fieldBit(x);};
    r.presence=f(Field::RawFault)|f(Field::RawData0)|f(Field::RawData1)|f(Field::Sequence)|f(Field::MonotonicNs)|f(Field::BootId)|f(Field::HangId)|f(Field::CallerId)|f(Field::ResetEpoch)|f(Field::ExclusionToken)|f(Field::DerivedVA)|f(Field::ResetClearPhase)|f(Field::Provenance);
    r.captureFlags=ExplicitReadEnable|RawPreserved; r.validity=TupleValidity|MetadataValid|DerivedVAValid;
    r.status=RecordStatus::Complete; r.readAttempts=3; r.readSafetySummary=EvidenceStatus::Pass; r.coherenceSummary=EvidenceStatus::Pass;
    r.sequence=1; r.monotonicNs=2; r.bootId=3; r.hangId=4; r.callerId=5; r.resetEpoch=6; r.exclusionToken=7;
    r.rawFault=1; r.rawData0=0x1234; r.rawData1=0; r.derivedFlags=1; r.derivedAddressSpace=AddressSpace::PPGTT; r.derivedVirtualAddress=0xdeadbeef;
    r.resetClearPhase=ResetClearPhase::Stable; r.provenanceKind=ProvenanceKind::Synthetic;
    for (auto &x:r.readSafety) x=uint32_t(EvidenceStatus::Pass); for (auto &x:r.coherence) x=uint32_t(EvidenceStatus::Pass); return r;
}
int main() {
    FaultRecord r=rbase(); uint8_t b[WireSize]{}; FaultRecord out{};
    bool accepted = validRecord(r) && encode(r,b,sizeof b) && decode(b,sizeof b,out);
    std::printf("DERIVED_MISMATCH valid=%d encode=%d decode=%d expected_va=0x%llx accepted_va=0x%llx\n", int(validRecord(r)), int(encode(r,b,sizeof b)), int(decode(b,sizeof b,out)), (unsigned long long)(uint64_t(r.rawData0)<<12), (unsigned long long)out.derivedVirtualAddress);
    FaultRecord range=rbase(); range.derivedEngineV618=UINT32_MAX; range.derivedEngineV515=UINT32_MAX; range.derivedFaultType=UINT32_MAX; range.derivedSourceId=UINT32_MAX; range.derivedPageSize=UINT32_MAX;
    std::printf("DERIVED_RANGE valid=%d\n", int(validRecord(range)));
    FaultRecord ext=rbase(); ext.captureFlags &= ~ExternalCorrelationFlag; ext.provenanceKind=ProvenanceKind::ExternalCorrelation; ext.provenanceClaim=0x55;
    std::printf("EXTERNAL_FLAG_MISMATCH valid=%d\n", int(validRecord(ext)));
    return (accepted && validRecord(range) && validRecord(ext)) ? 0 : 2;
}
