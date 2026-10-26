#include "fault_record_v2.hpp"
#include <cstdint>
#include <cstdio>
using namespace Ga37FaultV2;
static FaultRecord complete() {
    FaultRecord r{};
    auto m=[](Field f){return fieldBit(f);};
    r.presence=m(Field::RawFault)|m(Field::RawData0)|m(Field::RawData1)|m(Field::Sequence)|m(Field::MonotonicNs)|m(Field::BootId)|m(Field::HangId)|m(Field::CallerId)|m(Field::ResetEpoch)|m(Field::ExclusionToken)|m(Field::DerivedVA)|m(Field::ResetClearPhase)|m(Field::Provenance);
    r.captureFlags=ExplicitReadEnable|RawPreserved;
    r.validity=TupleValidity|MetadataValid|DerivedVAValid;
    r.status=RecordStatus::Complete; r.readAttempts=3;
    r.readSafetySummary=EvidenceStatus::Pass; r.coherenceSummary=EvidenceStatus::Pass;
    r.sequence=1; r.monotonicNs=2; r.bootId=3; r.hangId=4; r.callerId=5; r.resetEpoch=6; r.exclusionToken=7;
    r.rawFault=1; r.rawData0=0x1234; r.rawData1=0;
    r.derivedFlags=1; r.derivedAddressSpace=AddressSpace::PPGTT; r.derivedVirtualAddress=0xdeadbeef;
    r.resetClearPhase=ResetClearPhase::Stable; r.provenanceKind=ProvenanceKind::Synthetic;
    for (auto &x:r.readSafety) x=uint32_t(EvidenceStatus::Pass);
    for (auto &x:r.coherence) x=uint32_t(EvidenceStatus::Pass);
    return r;
}
int main() {
    FaultRecord r=complete();
    std::printf("fake_derived_valid=%d expected_derived=0x%llx stored=0x%llx\n", int(validRecord(r)), (unsigned long long)((uint64_t(r.rawData1&0xf)<<32)|r.rawData0)<<12, (unsigned long long)r.derivedVirtualAddress);
    uint8_t b[WireSize]{}; FaultRecord out{};
    bool enc=encode(r,b,sizeof b), dec=decode(b,sizeof b,out);
    std::printf("fake_derived_encode=%d decode=%d decoded_va=0x%llx\n",int(enc),int(dec),(unsigned long long)out.derivedVirtualAddress);

    FaultRecord p=complete();
    p.captureFlags &= ~ExternalCorrelationFlag;
    p.provenanceKind=ProvenanceKind::ExternalCorrelation;
    p.provenanceClaim=0x55;
    std::printf("ext_without_capture_flag_valid=%d\n",int(validRecord(p)));

    FaultRecord absent=complete();
    absent.presence &= ~(fieldBit(Field::ContextIdentity)|fieldBit(Field::PML4)|fieldBit(Field::Engine)|fieldBit(Field::AllocationGeneration));
    absent.unknown |= fieldBit(Field::ContextIdentity)|fieldBit(Field::PML4)|fieldBit(Field::Engine)|fieldBit(Field::AllocationGeneration);
    absent.contextIdentity=absent.pml4=absent.allocationGeneration=0; absent.engineId=0;
    CoherenceEvidence pass{}; for (auto &x:pass.status) x=EvidenceStatus::Pass;
    DerivedValue dv=deriveIfCoherent(absent,pass);
    std::printf("coherence_pass_without_identity_fields_valid=%d derived=%d\n",int(validRecord(absent)),int(dv.available));
    return (enc&&dec&&validRecord(r)&&validRecord(p)&&validRecord(absent)&&dv.available)?0:1;
}
