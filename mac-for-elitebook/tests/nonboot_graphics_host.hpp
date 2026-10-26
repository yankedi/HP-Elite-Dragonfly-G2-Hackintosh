// Host-only stand-ins. No device files, I/O ports, MMIO, firmware or NVRAM APIs.
#pragma once
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <utility>
#include <vector>

using SInt32 = int32_t;
using thread_call_t = void *;
using thread_call_param_t = void *;
struct KernelPatcher {};
struct DeviceInfo {};
struct PatchSubmodule {
    bool enabled = false, requiresPatchingFramebuffer = false;
    bool requiresMMIORegistersReadAccess = false, requiresMMIORegistersWriteAccess = false;
    virtual void init() {}
    virtual void processKernel(KernelPatcher &, DeviceInfo *) {}
    virtual ~PatchSubmodule() = default;
};
struct BaseDeviceInfo {
    uint32_t cpuModel = 0x8C;
    static BaseDeviceInfo &get() { static BaseDeviceInfo data; return data; }
};
static std::map<std::string, uint32_t> bootNumbers;
static std::set<std::string> bootFlags;
static bool interruptsEnabled = true;
static uint32_t allocations = 0, nvWrites = 0, registryWrites = 0;
static bool PE_parse_boot_argn(const char *name, void *out, size_t length) {
    auto item = bootNumbers.find(name);
    if (item == bootNumbers.end()) return false;
    if (length != sizeof(uint32_t)) std::abort();
    std::memcpy(out, &item->second, length);
    return true;
}
static bool checkKernelArgument(const char *name) { return bootFlags.count(name); }
static bool ml_get_interrupts_enabled() { return interruptsEnabled; }
static void OSDecrementAtomic(volatile SInt32 *value) { *value = *value - 1; }
static thread_call_t thread_call_allocate(void (*)(void *, void *), void *) {
    ++allocations;
    return reinterpret_cast<void *>(uintptr_t{1}); // Never executed or dereferenced.
}
static uint64_t mach_absolute_time() { return 1; }
#define arrsize(value) (sizeof(value) / sizeof((value)[0]))
#define SYSLOG(...) do {} while (false)
#define NVRAM_PREFIX(guid, name) name
#define LILU_VENDOR_GUID "host-test-only"
struct NVStorage {
    static constexpr int OptRaw = 1;
    bool init() { return true; }
    void write(const char *, const uint8_t *, size_t, int) { ++nvWrites; }
    void sync() {}
    void deinit() {}
};
struct IOService {
    std::map<uint32_t, uint32_t> registers;
    std::vector<std::pair<uint32_t, uint32_t>> writes;
    void setProperty(const char *, const void *, size_t) { ++registryWrites; }
};
static uint32_t fakeRead(void *controller, uint32_t address) {
    return static_cast<IOService *>(controller)->registers[address];
}
static void fakeWrite(void *controller, uint32_t address, uint32_t value) {
    auto &io = *static_cast<IOService *>(controller);
    io.writes.emplace_back(address, value);
    io.registers[address] = value;
}
struct ReadSupport { uint32_t (*orgReadRegister32)(void *, uint32_t) = fakeRead; };
struct WriteSupport { void (*orgWriteRegister32)(void *, uint32_t, uint32_t) = fakeWrite; };
