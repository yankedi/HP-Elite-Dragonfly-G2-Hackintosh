// SPDX-License-Identifier: MIT
// Strict, offline TGF4 v1/v2 decoder CLI.  It never reads hardware.
#include "dispatch.hpp"

#include <cstdio>
#include <cstdlib>
#include <vector>

int main(int argc, char **argv) {
    if (argc != 2) {
        std::fprintf(stderr, "usage: tgf4decode RECORD\n");
        return 2;
    }
    FILE *file = std::fopen(argv[1], "rb");
    if (!file) return 3;
    if (std::fseek(file, 0, SEEK_END) != 0) { std::fclose(file); return 3; }
    const long size = std::ftell(file);
    if (size < 0 || size > 4096 || std::fseek(file, 0, SEEK_SET) != 0) {
        std::fclose(file); return 3;
    }
    std::vector<uint8_t> bytes(static_cast<size_t>(size));
    if (size && std::fread(bytes.data(), 1, bytes.size(), file) != bytes.size()) {
        std::fclose(file); return 3;
    }
    std::fclose(file);
    Ga37Dispatch::Decoded decoded {};
    if (!Ga37Dispatch::decodeAny(bytes.data(), bytes.size(), decoded)) {
        std::fprintf(stderr, "REJECT invalid-or-unknown-tgf4\n");
        return 1;
    }
    if (decoded.format == Ga37Dispatch::Format::V1)
        std::printf("ACCEPT format=v1 size=%zu sequence=%llu raw_only=1\n", bytes.size(),
                    static_cast<unsigned long long>(decoded.v1.sequence));
    else
        std::printf("ACCEPT format=v2 size=%zu sequence=%llu read_safe_claim=%u "
                    "coherence_claim=%u backend=NONE\n", bytes.size(),
                    static_cast<unsigned long long>(decoded.v2.sequence),
                    unsigned(decoded.v2.readSafetySummary),
                    unsigned(decoded.v2.coherenceSummary));
    return 0;
}
