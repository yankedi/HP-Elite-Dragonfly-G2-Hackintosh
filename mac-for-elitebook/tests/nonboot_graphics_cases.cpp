// Golden register addresses/encodings cross-checked against Intel's Linux v6.18
// intel_display_regs.h, blob 9d71e26a4fa274475a38c7be38995a0ee29486b7.
// Subject functions are extracted verbatim from pinned patched WEG by the runner.
using Map = IGFX::TigerLakeRegisterMap;
static uint64_t checks = 0;
static std::vector<std::string> groups;
static void expect(bool condition, const char *message) {
    ++checks;
    if (!condition) { std::cerr << message << '\n'; std::exit(1); }
}
static void resetEnvironment() {
    bootNumbers.clear(); bootFlags.clear();
    BaseDeviceInfo::get().cpuModel = 0x8C;
    interruptsEnabled = true; allocations = nvWrites = registryWrites = 0;
}
static void testGates() {
    groups.emplace_back("CPU gates and explicit argument precedence");
    KernelPatcher patcher;
    for (uint32_t model : {0x8CU, 0x8DU, 0x7EU, 0xA5U}) {
        resetEnvironment(); BaseDeviceInfo::get().cpuModel = model;
        bootFlags.insert("-igfxtglmap"); Map map;
        map.processKernel(patcher, nullptr);
        expect(map.enabled == (model == 0x8C || model == 0x8D), "CPU gate");
        if (map.enabled) expect(map.features == 0x3F, "default translation mask");
        expect(allocations == 0 && nvWrites == 0, "default gate has no async/NVRAM actions");
    }
    resetEnvironment(); bootFlags.insert("-igfxtglmap"); bootNumbers["igfxtglmap"] = 0;
    Map disabled; disabled.processKernel(patcher, nullptr);
    expect(!disabled.enabled, "explicit zero overrides flag");
    resetEnvironment(); Map absent; absent.processKernel(patcher, nullptr);
    expect(!absent.enabled, "no argument disables mapper");
    for (uint32_t limit : {0U, 1U, 0xAD9U, 0xFFFFU, 0x10000U}) {
        resetEnvironment(); bootNumbers["igfxtglmap"] = 0x3F;
        bootNumbers["igfxtglblmax"] = limit; Map map; map.processKernel(patcher, nullptr);
        expect(map.backlightLevelMax == ((limit && limit <= 0xFFFF) ? limit : 0xFFFF), "backlight argument bound");
    }
}
static void testAddressMap() {
    groups.emplace_back("register golden vectors, disabled features and boundary noninterference");
    Map map; map.features = Map::AllTranslation;
    const std::pair<uint32_t,uint32_t> vectors[] = {
        {0x64040,0x60540}, {0x64044,0x60544}, {0x640F0,0x605F0}, {0x640FC,0x605FC},
        {0x164000,0x164284}, {0x164004,0x164288}, {0x164080,0x16428C}, {0x164084,0x164290},
        {0x6F000,0x60000}, {0x6FFFF,0x60FFF}, {0x7F000,0x70000}, {0x7FFFF,0x70FFF}
    };
    for (auto [input, output] : vectors) {
        expect(map.mapAddress(input, true) == output, "golden write map");
        expect(map.mapAddress(input, false) == output, "golden read map");
    }
    for (uint32_t address : {0x6403CU,0x64048U,0x640ECU,0x64100U,0x164008U,0x164088U,0x6EFFCU,0x70000U,0x7EFFCU,0x80000U})
        expect(map.mapAddress(address, true) == address, "adjacent registers stay untouched");
    map.features = 0;
    for (uint32_t address = 0; address < 0x200000; address += 4)
        expect(map.mapAddress(address, true) == address && map.mapAddress(address, false) == address, "disabled map identity");
    map.features = Map::MapEdpTranscoder | Map::EdpCoreOnly;
    expect(map.mapAddress(0x6F0FC, true) == 0x600FC, "core timing boundary");
    expect(map.mapAddress(0x6F100, true) == 0x6F100, "noncore timing preserved");
    expect(map.mapAddress(0x6F41C, true) == 0x6041C, "core function boundary");
    expect(map.mapAddress(0x6F420, true) == 0x6F420, "noncore function preserved");
    map.features = Map::MapEdpTranscoder | Map::LazyEdpReads;
    expect(map.mapAddress(0x6F400, false) == 0x6F400, "lazy preactivation read");
    expect(map.mapAddress(0x6F400, true) == 0x60400, "lazy write still mapped");
    map.edpActivated = true;
    expect(map.mapAddress(0x6F400, false) == 0x60400, "lazy postactivation read");
}
static void testBitfields() {
    groups.emplace_back("DDI/clock field encodings and DPLL fractional rounding");
    expect(TGLReg::funcCtlToTGL(0) == 0, "disabled zero remains zero");
    for (uint32_t port = 0; port < 8; ++port) {
        uint32_t input = 0x82000002U | (port << 28);
        uint32_t expected = 0x82000002U | ((port + 1) << 27);
        expect(TGLReg::funcCtlToTGL(input) == expected, "Intel DDI select encoding");
        expect(TGLReg::funcCtlToICL(expected) == input, "DDI encoding roundtrip");
    }
    expect(TGLReg::clkSelToTGL(0x20000000) == 0x10000000, "DDI A clock encoding");
    expect(TGLReg::clkSelToICL(0x10000000) == 0x20000000, "DDI A inverse clock encoding");
    for (uint32_t fraction = 0; fraction <= 0x7FFF; ++fraction) {
        uint32_t v = 0xA0000005U | (fraction << 10);
        uint32_t halved = TGLReg::halveFraction(v);
        expect((halved & ~0x01FFFC00U) == (v & ~0x01FFFC00U), "DPLL nonfraction bits preserved");
        uint32_t restored = (TGLReg::doubleFraction(halved) & 0x01FFFC00U) >> 10;
        expect(restored >= fraction && restored - fraction <= 1, "DPLL roundtrip rounding bounded to one LSB");
    }
}
static void testReadWrite(IGFX &igfx) {
    groups.emplace_back("actual read/write callbacks, lazy activation and PLL preservation");
    IOService io; auto &map = igfx.modTigerLakeRegisterMap;
    map.features = Map::AllTranslation | Map::LazyEdpReads;
    io.registers[0x60400] = 0x0A000002;
    io.registers[0x6F400] = 0x11223344;
    expect(map.read(&io, 0x6F400) == 0x11223344, "actual lazy read before write");
    map.write(&io, 0x6F400, 0x82000002);
    expect(map.edpActivated && io.writes.back() == std::make_pair(0x60400U,0x8A000002U), "actual eDP translation activates lazy reads");
    expect(map.read(&io, 0x6F400) == 0x82000002, "actual translated readback");
    map.keepFirmwarePLL = true; size_t writes = io.writes.size();
    map.write(&io, 0x164000, 0x12345678);
    expect(io.writes.size() == writes, "keep firmware PLL suppresses mapped config write");
    map.keepFirmwarePLL = false; map.refIs38400 = 1;
    map.write(&io, 0x164000, 0x80002801);
    expect(io.writes.back() == std::make_pair(0x164284U,0x80001401U), "38.4MHz reference fraction translation");
    expect(map.read(&io, 0x164000) == 0x80002801, "38.4MHz readback");
}
static void testSequence(IGFX &igfx) {
    groups.emplace_back("transcoder-before-link ordering and disable path");
    IOService io; auto &map = igfx.modTigerLakeRegisterMap;
    map = Map{}; map.features = Map::AllTranslation;
    io.registers[0x64000] = 2; // Two lanes: Intel port width encoding.
    map.write(&io, 0x64040, 0x80000300);
    expect(io.writes == std::vector<std::pair<uint32_t,uint32_t>>{
        {0x46140,0x10000000}, {0x60400,0x0A000002}, {0x60540,0x80000300}}, "clock/function writes precede link enable");
    io.writes.clear(); map.write(&io, 0x46140, 0);
    expect(io.writes.back().second == 0x10000000, "active link cannot lose transcoder clock via zero write");
    io.writes.clear(); map.write(&io, 0x64040, 0);
    expect(io.writes == std::vector<std::pair<uint32_t,uint32_t>>{{0x60540,0}}, "disable does not erase function or clock registers");
    expect(nvWrites == 0 && registryWrites == 0, "default translation has no publication side effects");
}
static void testBacklight(IGFX &igfx) {
    groups.emplace_back("PWM monotonicity, clamp, zero-duty powerdown and restore ordering");
    IOService io; auto &map = igfx.modTigerLakeRegisterMap;
    map = Map{}; map.features = Map::ScaleBacklight;
    io.registers[0xC8254] = 1000; io.registers[0xC8258] = 500;
    map.write(&io, 0xC8254, 10000);
    expect(io.registers[0xC8254] == 1000 && map.driverBacklightFreq == 10000, "firmware PWM period retained");
    uint32_t previous = 0;
    for (uint32_t duty = 1; duty <= 0xFFFF; ++duty) {
        map.write(&io, 0xC8258, duty);
        uint32_t out = io.registers[0xC8258];
        expect(out >= previous && out >= 1 && out <= 1000, "positive PWM monotonic and hardware bounded");
        previous = out;
    }
    map.write(&io, 0xC8258, 5000);
    expect(io.registers[0xC8258] == 500 && map.read(&io, 0xC8258) == 5000, "PWM midpoint write/read scale");
    map.write(&io, 0xC8258, 0);
    expect(io.registers[0xC8258] == 0 && map.backlightBlanked, "zero duty actually reaches hardware model for powerdown");
    io.writes.clear(); map.write(&io, 0xC8250, 0x80000000);
    expect(io.writes == std::vector<std::pair<uint32_t,uint32_t>>{{0xC8250,0x80000000},{0xC8258,500}}, "PWM enable then saved duty restore");
    map.backlightLevelMax = 0; map.driverBacklightFreq = 0;
    expect(map.driverDutyMax() == 1, "zero denominator guard");
}
static void testPublication(IGFX &igfx) {
    groups.emplace_back("mock-only NVRAM feature gates and write budget");
    IOService io; auto &map = igfx.modTigerLakeRegisterMap;
    map = Map{}; nvWrites = registryWrites = 0;
    map.features = Map::PublishNVRAM;
    for (int i = 0; i < 15; ++i) map.publish(&io, true);
    expect(nvWrites == 10 && registryWrites == 0, "NVRAM publication budget");
    map.features = Map::PublishRegistry; map.publish(&io, true);
    expect(nvWrites == 10 && registryWrites == 1, "registry-only mode does not write NVRAM");
    interruptsEnabled = false; map.publish(&io, true);
    expect(registryWrites == 1, "publication is suppressed with interrupts disabled");
    interruptsEnabled = true;
}
int main() {
    resetEnvironment(); IGFX igfx; callbackIGFX = &igfx;
    testGates(); resetEnvironment(); testAddressMap(); testBitfields();
    testReadWrite(igfx); testSequence(igfx); testBacklight(igfx); testPublication(igfx);
    std::cout << "{\"case_groups\":" << groups.size() << ",\"assertions\":" << checks << ",\"groups\":[";
    for (size_t i = 0; i < groups.size(); ++i) std::cout << (i ? "," : "") << '"' << groups[i] << '"';
    std::cout << "]}\n";
}
