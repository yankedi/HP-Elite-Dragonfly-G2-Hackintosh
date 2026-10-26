// Hosted synthetic sample producer; no hardware/backend or OS boot-arg access.
#include "kern_tglfault34.hpp"
#include "kern_tglfault34_boottext.hpp"
#include <cstdio>
#include <cstring>
#include <inttypes.h>
#include <string>

using namespace TglFault34;
namespace BootText = TglFault34BootText;
#define REQUIRE(x) do { if (!(x)) { std::fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x); return false; } } while (0)
static const char *boolean(bool v) { return v ? "true" : "false"; }

static bool test_scanner() {
    struct Case { const char *text; bool expected; };
    const Case cases[] = {
        {"", false}, {"-v keepsyms=1", false}, {"-igfxtglfault34", true},
        {" -igfxtglfault34 ", true}, {"-v\t-igfxtglfault34\nkeepsyms=1", true},
        {"\r\v\f-igfxtglfault34\r", true},
        {"x-igfxtglfault34", false}, {"-igfxtglfault34x", false},
        {"--igfxtglfault34", false}, {"-igfxtglfault340", false},
        {"-igfxtglfault34=1", false}, {"foo=-igfxtglfault34", false},
        {"'-igfxtglfault34'", false}, {"\"-igfxtglfault34\"", false},
        {"-IGFXTGLFAULT34", false}, {"-igfxtglfault34,-v", false},
        {"-igfxtglfault34 -igfxtglfault34", true}
    };
    unsigned count = 0;
    REQUIRE(std::strcmp(BootText::Token, BootArgument) == 0);
    for (const Case &c : cases) {
        REQUIRE(BootText::enabled(c.text, std::strlen(c.text) + 1) == c.expected);
        ++count;
    }
    REQUIRE(!BootText::enabled(nullptr, 1)); ++count;
    REQUIRE(!BootText::enabled(BootArgument, 0)); ++count;
    // Exact token bytes with no terminator in the supplied span.
    REQUIRE(!BootText::enabled(BootArgument, sizeof(BootArgument) - 1)); ++count;
    char boundary[BootText::MaxBytes]; std::memset(boundary, ' ', sizeof boundary);
    std::memcpy(boundary, BootArgument, sizeof(BootArgument) - 1);
    REQUIRE(!BootText::enabled(boundary, sizeof boundary)); ++count;
    boundary[sizeof boundary - 1] = '\0';
    REQUIRE(BootText::enabled(boundary, sizeof boundary)); ++count;
    char over[BootText::MaxBytes + 1] {};
    std::memcpy(over, BootArgument, sizeof(BootArgument));
    REQUIRE(!BootText::enabled(over, sizeof over)); ++count;
    const char embedded[] = "-v\0 -igfxtglfault34";
    REQUIRE(!BootText::enabled(embedded, sizeof embedded)); ++count;
    std::printf("SCANNER_PASS cases=%u max_bytes=%zu exact_whitespace_token_only=true\n", count, BootText::MaxBytes);
    return true;
}

struct SyntheticReader {
    uint32_t words[3];
    int failIndex = -1;
    uint32_t reads = 0, observations = 0;
    bool orderCorrect = true;
    static bool read(void *context, uint32_t offset, uint32_t &value) noexcept {
        auto &s = *static_cast<SyntheticReader *>(context);
        const uint32_t i = s.reads++;
        constexpr uint32_t offsets[] = {0xcec4, 0xceb8, 0xcebc};
        if (i >= 3) { s.orderCorrect = false; return false; }
        if (offset != offsets[i]) { s.orderCorrect = false; return false; }
        value = s.words[i];
        return int(i) != s.failIndex;
    }
    static bool observe(void *context, EpochObservation &e) noexcept {
        ++static_cast<SyntheticReader *>(context)->observations;
        e.epoch = 11; e.exclusionToken = 22; e.resetting = false;
        e.knownActivePower = true;
        e.forcewakeHeldDomains = e.forcewakeAckDomains = DomainGT;
        return true;
    }
    Callbacks callbacks() { return {this, read, observe}; }
};

static Request synthetic_request(uint64_t id) {
    constexpr char input[] = "-v -igfxtglfault34 keepsyms=1";
    Request q;
    q.enabled = BootText::enabled(input, sizeof input);
    q.supportedTgl = q.knownActivePower = q.notResetting = true;
    q.exclusionKnown = q.stableIdentityKnown = q.monotonicTimestampKnown = true;
    q.forcewakeHeldDomains = q.forcewakeAckDomains = DomainGT;
    q.bootId = 100; q.hangId = id; q.callerId = 200; q.monotonicNs = 1000000 + id;
    q.resetEpoch = 11; q.exclusionToken = 22;
    return q; // Every ID/time/power/lock flag is synthetic, not an observation.
}

static bool test_disabled_integration() {
    Request q = synthetic_request(1);
    constexpr char suffix[] = "-igfxtglfault34suffix";
    q.enabled = BootText::enabled(suffix, sizeof suffix);
    Collector c; SyntheticReader s {{1, 2, 3}};
    REQUIRE(c.capture(q, s.callbacks()) == Status::Disabled);
    REQUIRE(c.size() == 0 && s.reads == 0 && s.observations == 0);
    std::puts("SCANNER_COLLECTOR_PASS suffix_request_disabled zero_callbacks=true");
    return true;
}

struct Sample {
    const char *name;
    uint32_t fault, data0, data1;
    int failIndex;
    bool expectedDerived;
    Status expectedStatus;
};

static bool emit_sample(const std::string &directory, const Sample &sample, uint64_t id) {
    Collector c;
    SyntheticReader s {{sample.fault, sample.data0, sample.data1}, sample.failIndex};
    const Request q = synthetic_request(id);
    REQUIRE(c.capture(q, s.callbacks()) == sample.expectedStatus);
    REQUIRE(q.enabled && c.size() == 1 && s.orderCorrect);
    uint8_t bytes[WireSize]; REQUIRE(encode(*c.record(0), bytes, sizeof bytes));
    const std::string base = directory + "/" + sample.name;
    FILE *file = std::fopen((base + ".bin").c_str(), "wbx");
    REQUIRE(file != nullptr);
    const bool written = std::fwrite(bytes, 1, sizeof bytes, file) == sizeof bytes;
    const int closed = std::fclose(file); REQUIRE(written && closed == 0);
    // Decode the actual emitted file, not an independently manufactured record.
    uint8_t readback[WireSize]; file = std::fopen((base + ".bin").c_str(), "rb");
    REQUIRE(file != nullptr);
    const bool read = std::fread(readback, 1, sizeof readback, file) == sizeof readback;
    const int trailing = std::fgetc(file); const bool readError = std::ferror(file) != 0;
    const int readClosed = std::fclose(file);
    REQUIRE(read && trailing == EOF && !readError && readClosed == 0);
    FaultRecord r; REQUIRE(decode(readback, sizeof readback, r));
    uint8_t canonical[WireSize]; REQUIRE(encode(r, canonical, sizeof canonical));
    REQUIRE(std::memcmp(bytes, canonical, sizeof bytes) == 0);
    REQUIRE(std::memcmp(bytes, readback, sizeof bytes) == 0);
    const DerivedFault d = derive(r); REQUIRE(d.available == sample.expectedDerived);
    if (sample.failIndex >= 0) REQUIRE(s.reads == 2 && s.observations == 3 && r.rawData1 == 0);
    else REQUIRE(s.reads == 3 && s.observations == 6);
    file = std::fopen((base + ".json").c_str(), "wx"); REQUIRE(file != nullptr);
    std::fprintf(file,
        "{\n  \"name\": \"%s\",\n  \"input_kind\": \"SYNTHETIC_MOCK_ONLY\",\n"
        "  \"hardware_observation\": false,\n  \"live_locks_proven\": false,\n"
        "  \"request_enabled_via_offline_scanner\": %s,\n"
        "  \"wire_version\": %u,\n  \"wire_bytes\": %zu,\n"
        "  \"capture_status\": %u,\n  \"validity_mask\": %u,\n"
        "  \"read_attempts\": %u,\n  \"epoch_observer_calls\": %u,\n"
        "  \"raw\": {\"fault\": \"0x%08" PRIx32 "\", \"data0\": \"0x%08" PRIx32
        "\", \"data1\": \"0x%08" PRIx32 "\"},\n"
        "  \"synthetic_metadata\": {\"sequence\": %" PRIu64 ", \"boot_id\": %" PRIu64
        ", \"hang_id\": %" PRIu64 ", \"caller_id\": %" PRIu64 ", \"monotonic_ns\": %" PRIu64 "},\n"
        "  \"context_id\": null,\n  \"pml4\": null,\n"
        "  \"context_pml4_status\": \"UNKNOWN: core has no context/page-table access\",\n"
        "  \"decoded_file_roundtrip\": true,\n  \"derived\": {\n"
        "    \"available\": %s,\n    \"fault_present_reported_by_core\": %s,\n"
        "    \"data1_mbz_bits_reported_by_core\": \"0x%08" PRIx32 "\",\n",
        sample.name, boolean(q.enabled), unsigned(WireVersion), WireSize,
        uint32_t(r.status), r.validity, r.readAttempts, s.observations,
        r.rawFault, r.rawData0, r.rawData1, r.sequence, r.bootId, r.hangId, r.callerId,
        r.monotonicNs, boolean(d.available), boolean(d.faultPresent), d.data1MbzBits);
    if (d.available) {
        std::fprintf(file,
            "    \"virtual_address\": \"0x%012" PRIx64 "\",\n"
            "    \"address_space\": \"%s\",\n    \"engine_id_linux_v618\": %u,\n"
            "    \"engine_id_linux_v515\": %u,\n    \"source_id\": %u,\n    \"fault_type\": %u,\n"
            "    \"entry_valid\": %s,\n    \"entry_present\": %s,\n    \"page_size_code\": %u\n",
            d.virtualAddress, d.addressSpace == AddressSpace::Ppgtt ? "PPGTT" : "GGTT",
            d.engineIdV618, d.engineIdV515, d.sourceId, d.faultType,
            boolean(d.entryValid), boolean(d.entryPresent), uint32_t(d.pageSize));
    } else {
        std::fputs("    \"virtual_address\": null,\n    \"address_space\": null,\n"
                   "    \"engine_id_linux_v618\": null,\n    \"engine_id_linux_v515\": null,\n"
                   "    \"source_id\": null,\n    \"fault_type\": null,\n"
                   "    \"entry_valid\": null,\n    \"entry_present\": null,\n    \"page_size_code\": null\n", file);
    }
    std::fputs("  }\n}\n", file);
    const bool jsonError = std::ferror(file) != 0;
    const int jsonClosed = std::fclose(file); REQUIRE(!jsonError && jsonClosed == 0);
    std::printf("SAMPLE_PASS name=%s bytes=%zu status=%u validity=%u derived=%s\n",
                sample.name, WireSize, uint32_t(r.status), r.validity, boolean(d.available));
    return true;
}

int main(int argc, char **argv) {
    if (argc != 2) { std::fprintf(stderr, "usage: %s NEW_OUTPUT_DIRECTORY\n", argv[0]); return 2; }
    if (!test_scanner() || !test_disabled_integration()) return 1;
    const Sample samples[] = {
        {"validPPGTT", 0x3213, 0x12345678, 0xea, -1, true, Status::Complete},
        {"validGGTT", 0x9755, 0xfedcba98, 0x17f, -1, true, Status::Complete},
        {"valid0", 0x3212, 0x12345678, 0xea, -1, false, Status::Complete},
        {"DATA1MBZ", 0x3213, 0x12345678, 0x2ea, -1, false, Status::Complete},
        {"failedread", 0x3213, 0xdeadc0de, 0xea, 1, false, Status::Data0ReadFailed}
    };
    uint64_t id = 1;
    for (const Sample &sample : samples) if (!emit_sample(argv[1], sample, id++)) return 1;
    std::puts("SAMPLE_CORE_PASS samples=5 input=SYNTHETIC context=UNKNOWN pml4=UNKNOWN hardware=NONE attachment=NONE");
    return 0;
}
