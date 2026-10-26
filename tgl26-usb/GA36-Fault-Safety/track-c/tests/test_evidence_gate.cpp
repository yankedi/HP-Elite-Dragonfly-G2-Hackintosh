// SPDX-License-Identifier: MIT
// Hosted tests for the GA3.6 Track C default-deny evidence gate.
// All capture callbacks are mocks; there is no real MMIO backend.
#include "kern_tglfault34_gate.hpp"

#include <cstdio>
#include <cstring>
#include <cstdint>

using namespace TglFault34;
using namespace TglFault34Gate;

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

struct Tuple {
    uint32_t fault;
    uint32_t data0;
    uint32_t data1;
};

constexpr Tuple TupleA = {
    0x1f000U | (0xa5U << 3) | 7U,
    0x89abcdefU,
    0x1fbU
};
constexpr Tuple TupleB = {
    0x1e000U | (0x33U << 3) | 3U,
    0x01234567U,
    0x001U
};

enum class EventKind : char { Observe = 'O', Read = 'R', Mutate = 'M' };

struct Event {
    EventKind kind;
    uint32_t index;
    uint32_t offset;
    uint32_t value;
};

struct Mock {
    Tuple tuple = TupleA;
    uint32_t offsets[3] {};
    uint32_t reads = 0;
    uint32_t observations = 0;
    uint32_t changeAt = 0;
    // 1 epoch, 2 token, 3 resetting, 4 callback fail, 5 power,
    // 6 GT held, 7 GT ACK.
    uint32_t changeKind = 0;

    // Test-only device mutation model.  It changes the mock device between
    // the core's three reads; it does not add a read to the core.
    bool mutateWithinCapture = false;
    uint32_t faultBefore = 0;
    uint32_t faultAfter = 0;
    uint32_t readValues[3] {};

    // Explicit sub-read event timeline for the within-capture test.
    Event events[16] {};
    uint32_t eventCount = 0;

    static void record(Mock &mock, EventKind kind, uint32_t index,
                       uint32_t offset, uint32_t value) noexcept {
        if (mock.eventCount < sizeof mock.events / sizeof mock.events[0]) {
            mock.events[mock.eventCount++] = {kind, index, offset, value};
        }
    }

    static bool read(void *context, uint32_t offset, uint32_t &value) noexcept {
        Mock &mock = *static_cast<Mock *>(context);
        const uint32_t index = mock.reads++;
        if (index >= 3) return false;
        mock.offsets[index] = offset;
        value = index == 0 ? mock.tuple.fault :
                index == 1 ? mock.tuple.data0 : mock.tuple.data1;
        mock.readValues[index] = value;
        record(mock, EventKind::Read, index, offset, value);
        if (mock.mutateWithinCapture) {
            if (index == 0) {
                mock.faultBefore = value; // CEC4 first sample: A
                mock.tuple = TupleB;      // device mutation before DATA0
                record(mock, EventKind::Mutate, 0, 0, mock.tuple.fault);
            } else if (index == 1) {
                mock.tuple = TupleA;      // device mutation before DATA1
                record(mock, EventKind::Mutate, 1, 0, mock.tuple.fault);
            }
        }
        return true;
    }

    uint32_t peekFault() const noexcept { return tuple.fault; }

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
        record(mock, EventKind::Observe, mock.observations,
               uint32_t(epoch.epoch), uint32_t(epoch.exclusionToken));
        return true;
    }

    Callbacks callbacks() { return {this, read, observe}; }
};

static Evidence allVerified() {
    Evidence evidence;
    evidence.enable = true;
    setAll(evidence, EvidenceStatus::Verified);
    return evidence;
}

static bool default_is_disabled_and_denied() {
    Evidence evidence {};
    const Admission admission = evaluate(evidence);
    CHECK(!admission.allowed);
    CHECK(admission.decision == Decision::Disabled);
    CHECK(admission.blockingMask == AllConditions);
    CHECK(admission.unknownMask == AllConditions);
    CHECK(admission.verifiedMask == 0);
    CHECK(std::strcmp(decisionName(admission.decision), "DISABLED") == 0);
    return true;
}

static bool explicit_enable_and_all_verified_are_both_required() {
    Evidence disabled = allVerified();
    disabled.enable = false;
    const Admission noEnable = evaluate(disabled);
    CHECK(!noEnable.allowed);
    CHECK(noEnable.decision == Decision::Disabled);

    Evidence enabledButUnknown {};
    enabledButUnknown.enable = true;
    const Admission unknown = evaluate(enabledButUnknown);
    CHECK(!unknown.allowed);
    CHECK(unknown.decision == Decision::Unknown);
    CHECK(unknown.blockingMask == AllConditions);

    const Admission allowed = evaluate(allVerified());
    CHECK(allowed.allowed);
    CHECK(allowed.decision == Decision::Allow);
    CHECK(allowed.blockingMask == 0);
    CHECK(allowed.verifiedMask == AllConditions);
    return true;
}

static bool each_nonverified_condition_blocks() {
    const Condition conditions[] = {
        Condition::CorrectBinary,
        Condition::CorrectHookABI,
        Condition::CorrectGTDomain,
        Condition::RuntimePowerHeld,
        Condition::ForcewakeReferenceHeld,
        Condition::ForcewakeACKConfirmed,
        Condition::ResetExcluded,
        Condition::MMIOReadSafe,
        Condition::FaultTupleConsistencyEstablished
    };
    const EvidenceStatus blockers[] = {
        EvidenceStatus::Unknown,
        EvidenceStatus::Conditional,
        EvidenceStatus::Failed
    };
    for (Condition condition : conditions) {
        for (EvidenceStatus blocker : blockers) {
            Evidence evidence = allVerified();
            set(evidence, condition, blocker);
            const Admission admission = evaluate(evidence);
            CHECK(!admission.allowed);
            CHECK((admission.blockingMask & bit(condition)) != 0);
            CHECK((admission.verifiedMask & bit(condition)) == 0);
            switch (blocker) {
                case EvidenceStatus::Unknown:
                    CHECK(admission.decision == Decision::Unknown);
                    CHECK((admission.unknownMask & bit(condition)) != 0);
                    break;
                case EvidenceStatus::Conditional:
                    CHECK(admission.decision == Decision::Conditional);
                    CHECK((admission.conditionalMask & bit(condition)) != 0);
                    break;
                case EvidenceStatus::Failed:
                    CHECK(admission.decision == Decision::Failed);
                    CHECK((admission.failedMask & bit(condition)) != 0);
                    break;
                default:
                    CHECK(false);
                    break;
            }
        }
    }
    return true;
}

static bool only_the_single_all_verified_state_is_admitted() {
    // Exhaustive over four statuses for each of nine conditions.
    uint32_t allowed = 0;
    uint32_t denied = 0;
    for (uint32_t code = 0; code < (uint32_t(1) << 18); ++code) {
        Evidence evidence {};
        evidence.enable = true;
        uint32_t remaining = code;
        bool everyVerified = true;
        for (uint32_t i = 0; i < ConditionCount; ++i) {
            const EvidenceStatus status =
                static_cast<EvidenceStatus>(remaining & 3U);
            remaining >>= 2;
            evidence.status[i] = status;
            if (status != EvidenceStatus::Verified) everyVerified = false;
        }
        const Admission admission = evaluate(evidence);
        if (admission.allowed) {
            ++allowed;
            CHECK(everyVerified);
            CHECK(admission.decision == Decision::Allow);
            CHECK(admission.blockingMask == 0);
        } else {
            ++denied;
            CHECK(!everyVerified);
            CHECK(admission.decision != Decision::Allow);
        }
    }
    CHECK(allowed == 1);
    CHECK(denied == (uint32_t(1) << 18) - 1);
    return true;
}

static bool malformed_status_is_never_truthy() {
    Evidence evidence = allVerified();
    evidence.status[uint32_t(Condition::ResetExcluded)] =
        static_cast<EvidenceStatus>(0x7fffffffU);
    const Admission admission = evaluate(evidence);
    CHECK(!admission.allowed);
    CHECK(admission.decision == Decision::Invalid);
    CHECK((admission.invalidMask & bit(Condition::ResetExcluded)) != 0);
    CHECK((admission.blockingMask & bit(Condition::ResetExcluded)) != 0);
    return true;
}

static bool caller_claims_do_not_satisfy_the_gate() {
    Collector collector;
    Mock mock;
    CHECK(collector.capture(approved(), mock.callbacks()) == Status::Complete);
    const FaultRecord &record = *collector.record(0);
    CHECK(record.callerClaims == RequiredClaims);
    CHECK((record.validity & StableEpoch) != 0);

    Evidence evidence {};
    evidence.enable = true; // even explicitly enabled
    const Admission admission = evaluate(evidence);
    CHECK(!admission.allowed);
    CHECK(admission.decision == Decision::Unknown);
    return true;
}

static bool mock_reset_does_not_self_verify() {
    Collector collector;
    Mock mock;
    mock.changeAt = 1;
    mock.changeKind = 3; // resetting=true on the first observer call
    CHECK(collector.capture(approved(), mock.callbacks()) == Status::ResetRace);
    const FaultRecord &record = *collector.record(0);
    CHECK(record.status == Status::ResetRace);
    CHECK(record.readAttempts == 0);
    CHECK((record.validity & StableEpoch) == 0);

    Evidence evidence = allVerified();
    set(evidence, Condition::ResetExcluded, EvidenceStatus::Unknown);
    CHECK(!evaluate(evidence).allowed);
    set(evidence, Condition::ResetExcluded, EvidenceStatus::Conditional);
    CHECK(!evaluate(evidence).allowed);
    set(evidence, Condition::ResetExcluded, EvidenceStatus::Failed);
    CHECK(!evaluate(evidence).allowed);
    set(evidence, Condition::ResetExcluded, EvidenceStatus::Verified);
    CHECK(evaluate(evidence).allowed);
    return true;
}

static bool mock_ack_timeout_does_not_self_verify() {
    Collector collector;
    Mock mock;
    mock.changeAt = 2;
    mock.changeKind = 7; // GT ACK disappears after the first read
    CHECK(collector.capture(approved(), mock.callbacks()) == Status::GtAckMissing);
    const FaultRecord &record = *collector.record(0);
    CHECK(record.status == Status::GtAckMissing);
    CHECK(record.readAttempts == 1);
    CHECK(mock.observations == 2);
    CHECK((record.validity & StableEpoch) == 0);

    Evidence evidence = allVerified();
    set(evidence, Condition::ForcewakeACKConfirmed, EvidenceStatus::Unknown);
    CHECK(!evaluate(evidence).allowed);
    set(evidence, Condition::ForcewakeACKConfirmed, EvidenceStatus::Conditional);
    CHECK(!evaluate(evidence).allowed);
    set(evidence, Condition::ForcewakeACKConfirmed, EvidenceStatus::Failed);
    CHECK(!evaluate(evidence).allowed);
    set(evidence, Condition::ForcewakeACKConfirmed, EvidenceStatus::Verified);
    CHECK(evaluate(evidence).allowed);
    return true;
}

static bool mock_power_loss_does_not_self_verify() {
    Collector collector;
    Mock mock;
    mock.changeAt = 2;
    mock.changeKind = 5; // active power disappears after the first read
    CHECK(collector.capture(approved(), mock.callbacks()) == Status::PowerUnknown);
    const FaultRecord &record = *collector.record(0);
    CHECK(record.status == Status::PowerUnknown);
    CHECK(record.readAttempts == 1);
    CHECK(mock.observations == 2);
    CHECK((record.validity & StableEpoch) == 0);

    Evidence evidence = allVerified();
    set(evidence, Condition::RuntimePowerHeld, EvidenceStatus::Unknown);
    CHECK(!evaluate(evidence).allowed);
    set(evidence, Condition::RuntimePowerHeld, EvidenceStatus::Conditional);
    CHECK(!evaluate(evidence).allowed);
    set(evidence, Condition::RuntimePowerHeld, EvidenceStatus::Failed);
    CHECK(!evaluate(evidence).allowed);
    set(evidence, Condition::RuntimePowerHeld, EvidenceStatus::Verified);
    CHECK(evaluate(evidence).allowed);
    return true;
}

static bool same_epoch_aba_is_not_tuple_coherence() {
    // Cross-capture A -> B -> A at the same reset epoch/token.  This shows that
    // the epoch is not a unique fault-generation counter: three different
    // Complete samples share it.  By itself this is NOT a torn-tuple proof;
    // the within-capture test below is the deterministic torn-tuple model.
    Collector collector;
    Mock mock;
    Request q = approved();

    mock.tuple = TupleA;
    q.hangId = 1;
    q.monotonicNs = 1000;
    mock.reads = 0;
    mock.observations = 0;
    CHECK(collector.capture(q, mock.callbacks()) == Status::Complete);

    mock.tuple = TupleB;
    q.hangId = 2;
    q.monotonicNs = 2000;
    mock.reads = 0;
    mock.observations = 0;
    CHECK(collector.capture(q, mock.callbacks()) == Status::Complete);

    mock.tuple = TupleA;
    q.hangId = 3;
    q.monotonicNs = 3000;
    mock.reads = 0;
    mock.observations = 0;
    CHECK(collector.capture(q, mock.callbacks()) == Status::Complete);

    CHECK(collector.size() == 3);
    const FaultRecord &first = *collector.record(0);
    const FaultRecord &second = *collector.record(1);
    const FaultRecord &third = *collector.record(2);
    CHECK(first.sequence == 1 && second.sequence == 2 && third.sequence == 3);
    CHECK(first.resetEpoch == 3 && second.resetEpoch == 3 && third.resetEpoch == 3);
    CHECK(first.exclusionToken == 41 && second.exclusionToken == 41 &&
          third.exclusionToken == 41);
    CHECK(first.rawFault == TupleA.fault && second.rawFault == TupleB.fault &&
          third.rawFault == TupleA.fault);
    CHECK(first.rawData0 == TupleA.data0 && second.rawData0 == TupleB.data0 &&
          third.rawData0 == TupleA.data0);
    CHECK((first.validity & StableEpoch) != 0);
    CHECK((second.validity & StableEpoch) != 0);
    CHECK((third.validity & StableEpoch) != 0);
    CHECK(first.callerClaims == RequiredClaims);
    CHECK(second.callerClaims == RequiredClaims);
    CHECK(third.callerClaims == RequiredClaims);

    const DerivedFault derivedFirst = derive(first);
    const DerivedFault derivedSecond = derive(second);
    CHECK(derivedFirst.available && derivedSecond.available);
    CHECK(derivedFirst.virtualAddress != derivedSecond.virtualAddress);

    // StableEpoch and across-capture A/B/A at one epoch do not establish tuple
    // coherence, and they also do not prove a torn tuple by themselves.
    // Admission stays denied until the independent condition is VERIFIED.
    Evidence evidence = allVerified();
    set(evidence, Condition::FaultTupleConsistencyEstablished,
        EvidenceStatus::Unknown);
    Admission admission = evaluate(evidence);
    CHECK(!admission.allowed);
    CHECK(admission.decision == Decision::Unknown);
    CHECK((admission.blockingMask &
           bit(Condition::FaultTupleConsistencyEstablished)) != 0);

    set(evidence, Condition::FaultTupleConsistencyEstablished,
        EvidenceStatus::Conditional);
    admission = evaluate(evidence);
    CHECK(!admission.allowed);
    CHECK(admission.decision == Decision::Conditional);

    set(evidence, Condition::FaultTupleConsistencyEstablished,
        EvidenceStatus::Failed);
    admission = evaluate(evidence);
    CHECK(!admission.allowed);
    CHECK(admission.decision == Decision::Failed);

    set(evidence, Condition::FaultTupleConsistencyEstablished,
        EvidenceStatus::Verified);
    admission = evaluate(evidence);
    CHECK(admission.allowed);
    CHECK(admission.decision == Decision::Allow);
    return true;
}

static bool tupleEqual(const Tuple &a, const Tuple &b) {
    return a.fault == b.fault && a.data0 == b.data0 && a.data1 == b.data1;
}

static Tuple tupleOf(const FaultRecord &record) {
    return {record.rawFault, record.rawData0, record.rawData1};
}

// Test-only helper.  The core still performs exactly three reads; the mock
// changes its device state after read 0 and read 1.
static bool runWithinCaptureMutation(Mock &mock, FaultRecord &record) {
    Collector collector;
    Request q = approved();
    mock.tuple = TupleA;
    mock.mutateWithinCapture = true;
    mock.reads = 0;
    mock.observations = 0;
    mock.eventCount = 0;
    mock.faultBefore = 0;
    mock.faultAfter = 0;
    const Status status = collector.capture(q, mock.callbacks());
    if (status != Status::Complete || collector.size() != 1) return false;
    record = *collector.record(0);
    // Mock-only post-capture CEC4 sample; this is not an extra core read.
    mock.faultAfter = mock.peekFault();
    return true;
}

static bool within_capture_mutation_tears_tuple_in_mock() {
    // Deterministic sub-read timeline inside ONE capture:
    //   O1, R(CEC4)=A, mutate->B, O2, O3, R(CEB8)=B,
    //   mutate->A, O4, O5, R(CEBC)=A, O6.
    // The core sees Complete + StableEpoch, but the raw tuple is mixed:
    // (A.fault, B.data0, A.data1), equal to neither TupleA nor TupleB.
    Mock mock;
    FaultRecord record {};
    CHECK(runWithinCaptureMutation(mock, record));

    CHECK(record.validity == CompleteValidity);
    CHECK((record.validity & StableEpoch) != 0);
    CHECK(record.rawFault == TupleA.fault);
    CHECK(record.rawData0 == TupleB.data0);
    CHECK(record.rawData1 == TupleA.data1);
    const Tuple mixed = tupleOf(record);
    CHECK(!tupleEqual(mixed, TupleA));
    CHECK(!tupleEqual(mixed, TupleB));

    // A mixed tuple can still be derivable; this is not atomic-coherence proof.
    const DerivedFault derived = derive(record);
    CHECK(derived.available);
    CHECK(derived.faultPresent);

    const EventKind expected[] = {
        EventKind::Observe, EventKind::Read, EventKind::Mutate,
        EventKind::Observe, EventKind::Observe, EventKind::Read,
        EventKind::Mutate, EventKind::Observe, EventKind::Observe,
        EventKind::Read, EventKind::Observe
    };
    CHECK(mock.eventCount == sizeof expected / sizeof expected[0]);
    for (uint32_t i = 0; i < mock.eventCount; ++i)
        CHECK(mock.events[i].kind == expected[i]);

    CHECK(mock.events[1].index == 0);
    CHECK(mock.events[1].offset == FaultRegister);
    CHECK(mock.events[1].value == TupleA.fault);
    CHECK(mock.events[2].index == 0);
    CHECK(mock.events[2].value == TupleB.fault);
    CHECK(mock.events[5].index == 1);
    CHECK(mock.events[5].offset == Data0Register);
    CHECK(mock.events[5].value == TupleB.data0);
    CHECK(mock.events[6].index == 1);
    CHECK(mock.events[6].value == TupleA.fault);
    CHECK(mock.events[9].index == 2);
    CHECK(mock.events[9].offset == Data1Register);
    CHECK(mock.events[9].value == TupleA.data1);

    for (uint32_t i = 0; i < mock.eventCount; ++i) {
        if (mock.events[i].kind == EventKind::Observe) {
            CHECK(mock.events[i].offset == 3);
            CHECK(mock.events[i].value == 41);
        }
    }
    CHECK(mock.reads == 3);
    CHECK(mock.faultBefore == TupleA.fault);
    CHECK(mock.faultAfter == TupleA.fault);
    return true;
}

static bool repeated_cec4_same_a_is_not_proof() {
    // Mock-only before/after CEC4 check: both samples are A, while DATA0
    // came from B and DATA1 from A.  A repeated same-CEC4 result is therefore
    // not proof of an atomic tuple or of ABA absence.  No extra core/real read
    // is added; the core still calls read exactly three times.
    Mock mock;
    FaultRecord record {};
    CHECK(runWithinCaptureMutation(mock, record));
    CHECK(mock.faultBefore == TupleA.fault);
    CHECK(mock.faultAfter == TupleA.fault);
    CHECK(mock.readValues[0] == TupleA.fault);
    CHECK(mock.readValues[1] == TupleB.data0);
    CHECK(mock.readValues[2] == TupleA.data1);
    CHECK(record.rawFault == TupleA.fault);
    CHECK(record.rawData0 == TupleB.data0);
    CHECK(record.rawData1 == TupleA.data1);
    CHECK(!tupleEqual(tupleOf(record), TupleA));
    CHECK(!tupleEqual(tupleOf(record), TupleB));
    CHECK((record.validity & StableEpoch) != 0);
    CHECK(mock.reads == 3);
    CHECK(mock.eventCount == 11);
    return true;
}

static bool current_project_assessment_denies() {
    // Snapshot of the GA36 Track C evidence assessment: three CONDITIONAL and
    // six UNKNOWN.  It is deliberately not upgraded by any mock success.
    Evidence evidence {};
    evidence.enable = true;
    set(evidence, Condition::CorrectBinary, EvidenceStatus::Conditional);
    set(evidence, Condition::CorrectHookABI, EvidenceStatus::Conditional);
    set(evidence, Condition::CorrectGTDomain, EvidenceStatus::Conditional);
    const uint32_t conditionalMask =
        bit(Condition::CorrectBinary) | bit(Condition::CorrectHookABI) |
        bit(Condition::CorrectGTDomain);
    const Admission admission = evaluate(evidence);
    CHECK(!admission.allowed);
    CHECK(admission.decision == Decision::Unknown);
    CHECK(admission.blockingMask == AllConditions);
    CHECK(admission.conditionalMask == conditionalMask);
    CHECK(admission.unknownMask == (AllConditions & ~conditionalMask));

    // Even independently VERIFYING tuple consistency alone leaves the other
    // eight conditions blocking admission.
    set(evidence, Condition::FaultTupleConsistencyEstablished,
        EvidenceStatus::Verified);
    const Admission stillBlocked = evaluate(evidence);
    CHECK(!stillBlocked.allowed);
    CHECK((stillBlocked.blockingMask &
           bit(Condition::FaultTupleConsistencyEstablished)) == 0);
    CHECK(stillBlocked.blockingMask ==
          (AllConditions & ~bit(Condition::FaultTupleConsistencyEstablished)));
    return true;
}

static bool names_are_stable_for_receipts() {
    CHECK(std::strcmp(conditionName(Condition::CorrectBinary), "CorrectBinary") == 0);
    CHECK(std::strcmp(conditionName(Condition::FaultTupleConsistencyEstablished),
                       "FaultTupleConsistencyEstablished") == 0);
    CHECK(std::strcmp(statusName(EvidenceStatus::Unknown), "UNKNOWN") == 0);
    CHECK(std::strcmp(statusName(EvidenceStatus::Conditional), "CONDITIONAL") == 0);
    CHECK(std::strcmp(statusName(EvidenceStatus::Verified), "VERIFIED") == 0);
    CHECK(std::strcmp(statusName(EvidenceStatus::Failed), "FAILED") == 0);
    return true;
}

int main() {
    if (!default_is_disabled_and_denied()) return 1;
    if (!explicit_enable_and_all_verified_are_both_required()) return 1;
    if (!each_nonverified_condition_blocks()) return 1;
    if (!only_the_single_all_verified_state_is_admitted()) return 1;
    if (!malformed_status_is_never_truthy()) return 1;
    if (!caller_claims_do_not_satisfy_the_gate()) return 1;
    if (!mock_reset_does_not_self_verify()) return 1;
    if (!mock_ack_timeout_does_not_self_verify()) return 1;
    if (!mock_power_loss_does_not_self_verify()) return 1;
    if (!same_epoch_aba_is_not_tuple_coherence()) return 1;
    if (!within_capture_mutation_tears_tuple_in_mock()) return 1;
    if (!repeated_cec4_same_a_is_not_proof()) return 1;
    if (!current_project_assessment_denies()) return 1;
    if (!names_are_stable_for_receipts()) return 1;
    std::printf("EVIDENCE_GATE_PASS checks=%u conditions=%u exhaustive_states=%u "
                "hardware=NONE backend=NONE\n",
                checks, ConditionCount, uint32_t(1) << 18);
    return 0;
}
