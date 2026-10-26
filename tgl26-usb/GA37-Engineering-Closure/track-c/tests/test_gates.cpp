// SPDX-License-Identifier: MIT
// Independent READ_SAFE and FAULT_DATA_COHERENT gate tests.
#include "fault_record_v2.hpp"

#include <cstdio>
#include <cstdint>

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

static bool read_safety_is_independent_and_four_valued() {
    ReadSafetyEvidence defaultEvidence;
    const GateResult initial = evaluateReadSafety(defaultEvidence);
    CHECK(!initial.allowed);
    CHECK(initial.decision == GateDecision::Blocked);
    CHECK(initial.unknownMask != 0);
    CHECK(!initial.allowed); // no reader may be attached by default

    ReadSafetyEvidence allPass;
    allPass.explicitEnable = true;
    for (uint32_t i = 0; i < ReadSafetyConditionCount; ++i)
        allPass.status[i] = EvidenceStatus::Pass;
    GateResult pass = evaluateReadSafety(allPass);
    CHECK(pass.allowed && pass.decision == GateDecision::Pass);
    for (uint32_t i = 0; i < ReadSafetyConditionCount; ++i) {
        ReadSafetyEvidence blocked = allPass;
        blocked.status[i] = EvidenceStatus::Unknown;
        CHECK(evaluateReadSafety(blocked).decision == GateDecision::Blocked);
        blocked.status[i] = EvidenceStatus::Conditional;
        CHECK(evaluateReadSafety(blocked).decision == GateDecision::Conditional);
        blocked.status[i] = EvidenceStatus::Failed;
        CHECK(evaluateReadSafety(blocked).decision == GateDecision::Failed);
    }
    ReadSafetyEvidence malformed = allPass;
    malformed.status[0] = static_cast<EvidenceStatus>(0x99);
    CHECK(evaluateReadSafety(malformed).decision == GateDecision::Invalid);
    allPass.explicitEnable = false;
    CHECK(evaluateReadSafety(allPass).decision == GateDecision::Disabled);
    CHECK(!evaluateReadSafety(allPass).allowed);
    return true;
}

static bool coherence_never_substitutes_for_read_safety() {
    CoherenceEvidence allPass;
    for (uint32_t i = 0; i < CoherenceConditionCount; ++i)
        allPass.status[i] = EvidenceStatus::Pass;
    CHECK(evaluateCoherence(allPass).allowed);
    CoherenceEvidence unknown;
    CHECK(evaluateCoherence(unknown).decision == GateDecision::Blocked);
    for (uint32_t i = 0; i < CoherenceConditionCount; ++i) {
        CoherenceEvidence conditional = allPass;
        conditional.status[i] = EvidenceStatus::Conditional;
        CHECK(evaluateCoherence(conditional).decision == GateDecision::Conditional);
        CoherenceEvidence failed = allPass;
        failed.status[i] = EvidenceStatus::Failed;
        CHECK(evaluateCoherence(failed).decision == GateDecision::Failed);
    }
    // A coherence PASS is only a data claim.  It contains no read-safety PASS.
    ReadSafetyEvidence readUnknown;
    CHECK(!evaluateReadSafety(readUnknown).allowed);
    return true;
}

static bool current_project_state_is_blocked() {
    ReadSafetyEvidence current;
    current.explicitEnable = false;
    current.status[uint32_t(ReadSafetyCondition::CorrectBinary)] = EvidenceStatus::Conditional;
    current.status[uint32_t(ReadSafetyCondition::CorrectHookABI)] = EvidenceStatus::Conditional;
    current.status[uint32_t(ReadSafetyCondition::CorrectGTDomain)] = EvidenceStatus::Conditional;
    current.status[uint32_t(ReadSafetyCondition::DefaultDisabled)] = EvidenceStatus::Pass;
    const GateResult read = evaluateReadSafety(current);
    CHECK(!read.allowed && read.decision == GateDecision::Blocked);
    CHECK((read.conditionalMask & (1U << uint32_t(ReadSafetyCondition::CorrectBinary))) != 0);
    CoherenceEvidence coherence;
    CHECK(!evaluateCoherence(coherence).allowed);
    CHECK(evaluateCoherence(coherence).decision == GateDecision::Blocked);
    return true;
}

int main() {
    if (!read_safety_is_independent_and_four_valued()) return 1;
    if (!coherence_never_substitutes_for_read_safety()) return 1;
    if (!current_project_state_is_blocked()) return 1;
    std::printf("GATES_PASS checks=%u read_safety_conditions=%u coherence_conditions=%u "
                "READ_SAFE=BLOCKED FAULT_DATA_COHERENT=UNKNOWN backend=NONE\n",
                checks, ReadSafetyConditionCount, CoherenceConditionCount);
    return 0;
}
