#include "../compiler/owned-bitcode.hpp"
#include <cassert>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <thread>

int main(int argc, char **argv) {
    assert(argc == 4);
    std::ifstream input(argv[2], std::ios::binary);
    std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(input)), {});
    assert(!bytes.empty());
    xe::BitcodeImage api(argv[1]); assert(api.ready());
    std::vector<uint8_t> out; std::string error;
    assert(!api.roundTrip(nullptr, 0, out, error) && out.empty());
    const char garbage[] = "garbage";
    assert(!api.roundTrip(garbage, sizeof garbage, out, error) && out.empty());
    // Valid magic with truncated payload exercises the real LLVM error path.
    assert(!api.roundTrip(bytes.data(), 4, out, error) && out.empty() && !error.empty());
    assert(!api.roundTrip(bytes.data(), xe::BitcodeImage::limit+1, out, error));
    assert(api.roundTrip(bytes.data(), bytes.size(), out, error));
    std::ofstream file(argv[3], std::ios::binary);
    file.write(reinterpret_cast<const char *>(out.data()), out.size()); file.close();
    // Concurrent parses use separate contexts and independent object lifetimes.
    std::vector<std::thread> threads;
    for (int i=0;i<8;i++) threads.emplace_back([&] {
        for (int j=0;j<100;j++) {
            std::vector<uint8_t> a,b;std::string e;
            assert(api.roundTrip(bytes.data(),bytes.size(),a,e));
            assert(api.roundTrip(a.data(),a.size(),b,e));
            assert(a==b);
        }
    });
    for(auto &t:threads)t.join();
    xe::BitcodeImage missing("/nonexistent/ga46-libLLVM.dylib");
    assert(!missing.ready() && !missing.roundTrip(bytes.data(),bytes.size(),out,error));
    puts("Real LLVM: parse error, byte ownership, 1600 concurrent roundtrips PASS");
}
