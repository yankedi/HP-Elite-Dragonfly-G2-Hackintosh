#include "fault_record_v2.hpp"
#include <cstdint>
#include <cstdio>
using namespace Ga37FaultV2;
static FaultRecord r() {
  FaultRecord x{}; auto f=[](Field y){return fieldBit(y);};
  x.presence=f(Field::RawFault)|f(Field::RawData0)|f(Field::RawData1)|f(Field::Sequence)|f(Field::MonotonicNs)|f(Field::BootId)|f(Field::HangId)|f(Field::CallerId)|f(Field::ResetEpoch)|f(Field::ExclusionToken)|f(Field::ResetClearPhase)|f(Field::Provenance);
  x.captureFlags=ExplicitReadEnable|RawPreserved; x.validity=TupleValidity|MetadataValid; x.status=RecordStatus::Complete; x.readAttempts=3;
  x.readSafetySummary=EvidenceStatus::Pass; x.coherenceSummary=EvidenceStatus::Pass; x.sequence=1; x.monotonicNs=2; x.bootId=3; x.hangId=4; x.callerId=5; x.resetEpoch=6; x.exclusionToken=7; x.rawFault=1; x.rawData0=2; x.rawData1=0x800; x.resetClearPhase=ResetClearPhase::Stable; x.provenanceKind=ProvenanceKind::Synthetic;
  for(auto &s:x.readSafety)s=2; for(auto &s:x.coherence)s=2; return x;
}
int main(){auto x=r(); CoherenceEvidence e{};for(auto&s:e.status)s=EvidenceStatus::Pass;auto d=deriveIfCoherent(x,e);std::printf("valid=%d derived_available=%d va=0x%llx rawData1=0x%x\n",int(validRecord(x)),int(d.available),(unsigned long long)d.virtualAddress,x.rawData1);return !(validRecord(x)&&d.available);}
