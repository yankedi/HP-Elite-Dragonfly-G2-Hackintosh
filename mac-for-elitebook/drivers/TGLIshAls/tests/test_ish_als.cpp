// SPDX-License-Identifier: BSD-3-Clause
// Clean-room Host ASan/UBSan Unit Tests for TGLIshAls Protocol & HID/ALS Engine

#include "../IshProtocol.hpp"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

static int gTestsRun = 0;
static int gTestsFailed = 0;

#define CHECK(cond) do {                                                     \
    ++gTestsRun;                                                             \
    if (!(cond)) {                                                           \
        std::fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
        ++gTestsFailed;                                                      \
        return;                                                              \
    }                                                                        \
} while (0)

static void appendItem(std::vector<uint8_t> &out, uint8_t prefix, const uint8_t *data, size_t n) {
    out.push_back(prefix);
    for (size_t i = 0; i < n; ++i) {
        out.push_back(data[i]);
    }
}

static void u8item(std::vector<uint8_t> &out, uint8_t tagType, uint8_t v) {
    const uint8_t b[1] = { v };
    appendItem(out, static_cast<uint8_t>(tagType | 0x01u), b, 1);
}

static void u16item(std::vector<uint8_t> &out, uint8_t tagType, uint16_t v) {
    const uint8_t b[2] = { static_cast<uint8_t>(v & 0xFFu), static_cast<uint8_t>((v >> 8) & 0xFFu) };
    appendItem(out, static_cast<uint8_t>(tagType | 0x02u), b, 2);
}

static void u32item(std::vector<uint8_t> &out, uint8_t tagType, uint32_t v) {
    const uint8_t b[4] = {
        static_cast<uint8_t>(v & 0xFFu),
        static_cast<uint8_t>((v >> 8) & 0xFFu),
        static_cast<uint8_t>((v >> 16) & 0xFFu),
        static_cast<uint8_t>((v >> 24) & 0xFFu)
    };
    appendItem(out, static_cast<uint8_t>(tagType | 0x03u), b, 4);
}

static void zitem(std::vector<uint8_t> &out, uint8_t tagType) {
    out.push_back(tagType);
}

// Build a realistic ALS HID report descriptor using Push/Pop, padding bits,
// Usage Min/Max selector range, and Report ID > 0.
static std::vector<uint8_t> buildComplexAlsDescriptor(bool useUsageMinMaxForPower) {
    std::vector<uint8_t> d;
    // Usage Page (Sensor = 0x20)
    u8item(d, 0x04, 0x20);
    // Usage (ALS = 0x41)
    u8item(d, 0x08, 0x41);
    // Collection (Application = 0x01)
    u8item(d, 0xA0, 0x01);
    //   Report ID (3)
    u8item(d, 0x84, 0x03);

    //   Feature report:
    //   1) Padding 4 bits (Constant) to verify constant bit accounting
    u8item(d, 0x74, 4);    // Report Size (4)
    u8item(d, 0x94, 1);    // Report Count (1)
    u8item(d, 0xB0, 0x01); // Feature (Const)

    //   2) Power State (0x0319) inside Logical Collection (bits 12..15)
    u16item(d, 0x08, 0x0319); // Usage (Power State)
    u8item(d, 0xA0, 0x02);    // Collection (Logical)
    u8item(d, 0x14, 1);       //   Logical Minimum (1)
    u8item(d, 0x24, 6);       //   Logical Maximum (6)
    u8item(d, 0x74, 4);       //   Report Size (4)
    u8item(d, 0x94, 1);       //   Report Count (1)
    if (useUsageMinMaxForPower) {
        u16item(d, 0x18, 0x0850); // Usage Minimum (Undefined)
        u16item(d, 0x28, 0x0855); // Usage Maximum (Power Off) -> 0x0851 is index 1 -> target = 1 + 1 = 2
    } else {
        u16item(d, 0x08, 0x0850); // idx 0
        u16item(d, 0x08, 0x0855); // idx 1
        u16item(d, 0x08, 0x0851); // idx 2 -> target = 1 + 2 = 3 (tests non-sequential discrete order)
    }
    u8item(d, 0xB0, 0x00);    //   Feature (Data, Array, Abs)
    zitem(d, 0xC0);           // End Collection

    //   3) Reporting State (0x0316) at bits 16..23
    u16item(d, 0x08, 0x0316);
    u8item(d, 0xA0, 0x02);
    u8item(d, 0x14, 0);       //   Logical Min (0)
    u8item(d, 0x24, 5);       //   Logical Max (5)
    u8item(d, 0x74, 8);       //   Report Size (8)
    u8item(d, 0x94, 1);       //   Report Count (1)
    u16item(d, 0x08, 0x0840); //   idx 0: No Events
    u16item(d, 0x08, 0x0841); //   idx 1: All Events -> target = 1
    u8item(d, 0xB0, 0x00);
    zitem(d, 0xC0);

    //   4) Report Interval (0x030E) at bits 24..55 (32-bit, must be preserved by RMW!)
    u16item(d, 0x08, 0x030E);
    u8item(d, 0x14, 0);
    u32item(d, 0x24, 0x7FFFFFFFu);
    u8item(d, 0x74, 32);
    u8item(d, 0x94, 1);
    u8item(d, 0xB0, 0x02);    // Feature (Data, Var, Abs)

    //   Input report (same Report ID = 3, independent Input bit offset starting at bit 8):
    //   Test Push/Pop preserving Unit Exponent (-2 = 0xE) and Usage Page (0x20)
    u8item(d, 0x54, 0x0E);    // Unit Exponent (-2)
    zitem(d, 0xA4);           // Push!
    u8item(d, 0x04, 0x01);    //   Usage Page (Generic Desktop)
    u8item(d, 0x54, 0x05);    //   Unit Exponent (+5)
    u8item(d, 0x74, 8);       //   Report Size (8)
    u8item(d, 0x94, 1);       //   Report Count (1)
    u8item(d, 0x80, 0x01);    //   Input (Const padding 8 bits at bits 8..15)
    zitem(d, 0xB4);           // Pop! Restores Usage Page 0x20 & Unit Exponent -2!

    //   Illuminance (0x04D1) at bits 16..47 (32-bit, Unit=Lux(1), UnitExpo=-2, LogicalMax=65535)
    u16item(d, 0x08, 0x04D1);
    u8item(d, 0x64, 0x01);    // Unit (1 = Lux)
    u8item(d, 0x14, 0);       // Logical Min (0)
    u16item(d, 0x24, 1000);   // Logical Max (1000) -> test raw > logical_max later!
    u8item(d, 0x74, 32);      // Report Size (32)
    u8item(d, 0x94, 1);       // Report Count (1)
    u8item(d, 0x80, 0x02);    // Input (Data, Var, Abs)

    zitem(d, 0xC0);           // End Collection (ALS)
    return d;
}

static std::vector<uint8_t> buildNonAlsDescriptor(uint16_t sensorUsage) {
    std::vector<uint8_t> d;
    u8item(d, 0x04, 0x20);
    u16item(d, 0x08, sensorUsage);
    u8item(d, 0xA0, 0x01);
    u8item(d, 0x84, 0x01);
    // Usage Min/Max with 96 fields (> 64!) to test non-truncating range handling
    u16item(d, 0x18, 0x0400);
    u16item(d, 0x28, 0x045F);
    u8item(d, 0x74, 8);
    u8item(d, 0x94, 96);
    u8item(d, 0x80, 0x02);
    zitem(d, 0xC0);
    return d;
}

static void testProtocolConstantsAndTxSlicer() {
    CHECK(ish::kRegPimrBxt == 0x0008u);
    CHECK(ish::kRegPisrBxt == 0x000Cu);
    CHECK(ish::kRegFwsts == 0x0034u);
    CHECK(ish::kRegHostComm == 0x0038u);
    CHECK(ish::kRegRst == 0x0044u);
    CHECK(ish::kRegHost2IshDrbl == 0x0048u);
    CHECK(ish::kRegIsh2HostDrbl == 0x0054u);
    CHECK(ish::kRegIsh2HostMsg == 0x0060u);
    CHECK(ish::kRegHost2IshMsg == 0x00E0u);
    CHECK(ish::kRegIshRmp2 == 0x0368u);
    CHECK(ish::kTxQueueCapacity >= 32u);

    ish::IshTransport tr;
    tr.reset(1000ULL);
    std::vector<uint8_t> big(4096u);
    for (size_t i = 0; i < big.size(); ++i) {
        big[i] = static_cast<uint8_t>((i * 131u + 7u) & 0xFFu);
    }
    CHECK(tr.enqueueIshtp(5u, 1u, big.data(), big.size()));
    CHECK(tr.txPendingCount() == 34u); // 33*124 + 4 = 4096

    // Ensure > 4096 B is cleanly rejected without partial fragments
    std::vector<uint8_t> tooBig(4097u, 0xAAu);
    CHECK(!tr.enqueueIshtp(5u, 1u, tooBig.data(), tooBig.size()));
    CHECK(tr.txPendingCount() == 34u);

    std::vector<uint8_t> reassembled;
    for (size_t frag = 0; frag < 34u; ++frag) {
        ish::TxFrame f {};
        CHECK(tr.popTxFrame(f));
        CHECK(f.proto == ish::kProtoIshtp);
        uint8_t fw = 0, host = 0;
        uint16_t flen = 0;
        bool comp = false;
        ish::parseIshtpHdrWord(ish::readLe32(f.data), fw, host, flen, comp);
        CHECK(fw == 5u);
        CHECK(host == 1u);
        CHECK(f.len == 4u + flen);
        CHECK(comp == (frag == 33u));
        reassembled.insert(reassembled.end(), f.data + 4, f.data + 4 + flen);
    }
    CHECK(!tr.hasTxPending());
    CHECK(reassembled == big);
}

static void testHidParserAndLuxMath() {
    // 1) Discrete order + Push/Pop + padding bits + Feature RMW
    {
        auto desc = buildComplexAlsDescriptor(false);
        ish::AlsDescriptorInfo als {};
        CHECK(ish::parseAlsReportDescriptor(desc.data(), desc.size(), als));
        CHECK(als.found);
        CHECK(als.inputReportId == 3u);
        CHECK(als.inputByteLen == 6u);     // 8 (id) + 8 (pad) + 32 (illum) = 48 bits = 6 bytes
        CHECK(als.illumBitOffset == 16u);
        CHECK(als.illumBitWidth == 32u);
        CHECK(als.unit == 1u);
        CHECK(ish::decodeUnitExponent(als.unitExpoRaw) == -2);
        CHECK(als.featureReportId == 3u);
        CHECK(als.featureByteLen == 7u);   // 8 (id) + 4 (pad) + 4 (pwr) + 8 (rpt) + 32 (intvl) = 56 bits = 7 bytes
        CHECK(als.powerState.present);
        CHECK(als.powerState.bitOffset == 12u);
        CHECK(als.powerState.bitWidth == 4u);
        CHECK(als.powerState.targetVal == 3u); // logicalMin=1, idx=2 -> 3
        CHECK(als.reportState.present);
        CHECK(als.reportState.bitOffset == 16u);
        CHECK(als.reportState.bitWidth == 8u);
        CHECK(als.reportState.targetVal == 1u);

        // Feature RMW preserves Report Interval (bytes 3..6) and low nibble padding (byte 1 bits 0..3)
        uint8_t feat[7] = { 0x03u, 0x1Au, 0x00u, 0xE8u, 0x03u, 0x00u, 0x00u };
        CHECK(ish::applyAlsFeatureRmw(als, feat, sizeof(feat)));
        CHECK(ish::verifyAlsFeatureControls(als, feat, sizeof(feat)));
        CHECK((feat[1] & 0x0Fu) == 0x0Au); // low 4 bits padding preserved!
        CHECK((feat[1] >> 4) == 3u);       // Power State D0 written to high nibble!
        CHECK(feat[2] == 1u);              // Reporting State All Events written!
        CHECK(feat[3] == 0xE8u && feat[4] == 0x03u && feat[5] == 0x00u && feat[6] == 0x00u); // Interval preserved!

        // Input report with raw = 50000 > logical_max(1000), expo = -2 -> 500.00 lux = 500000 milliLux
        uint8_t inRpt[6] = { 0x03u, 0x77u, 0x50u, 0xC3u, 0x00u, 0x00u }; // 0x0000C350 = 50000
        uint32_t raw = 0;
        uint64_t mLux = 0;
        uint32_t fLux = 0;
        CHECK(ish::decodeAlsInputReport(als, inRpt, sizeof(inRpt), raw, mLux, fLux));
        CHECK(raw == 50000u);
        CHECK(mLux == 500000ULL);
        CHECK(fLux == static_cast<uint32_t>((500000ULL * 16384ULL) / 1000ULL)); // 500 * 16384 = 8192000
    }

    // 2) Usage Min/Max selector range
    {
        auto desc = buildComplexAlsDescriptor(true);
        ish::AlsDescriptorInfo als {};
        CHECK(ish::parseAlsReportDescriptor(desc.data(), desc.size(), als));
        CHECK(als.powerState.present);
        CHECK(als.powerState.targetVal == 2u); // logicalMin=1 + (0x0851 - 0x0850 = 1) = 2
    }

    // 3) Negative/positive exponents, FP18.14 saturation, invalid sentinel, and AL! force bits
    {
        CHECK(ish::decodeUnitExponent(0x0u) == 0);
        CHECK(ish::decodeUnitExponent(0x7u) == 7);
        CHECK(ish::decodeUnitExponent(0x8u) == -8);
        CHECK(ish::decodeUnitExponent(0xEu) == -2);
        CHECK(ish::decodeUnitExponent(0xFu) == -1);

        CHECK(ish::rawToMilliLux(15u, 0xFu) == 1500ULL);     // 15 * 10^-1 = 1.5 lux = 1500 milliLux
        CHECK(ish::rawToMilliLux(3u, 0x2u) == 300000ULL);    // 3 * 10^2 = 300 lux = 300000 milliLux
        CHECK(ish::rawToMilliLux(123u, 0xCu) == 12ULL);      // 123 * 10^-4 lux = 12.3 milliLux -> 12
        CHECK(ish::milliLuxToSmcFp1814(1500ULL) == 24576u);  // 1.5 * 16384
        CHECK(ish::milliLuxToSmcFp1814(250ULL) == 4096u);    // 0.25 * 16384
        CHECK(ish::milliLuxToSmcFp1814(262143999ULL) == 4294967279u);
        CHECK(ish::milliLuxToSmcFp1814(262144000ULL) == ish::kSmcLuxInvalid - 1u);
        CHECK(ish::milliLuxToSmcFp1814(999999999999ULL) == ish::kSmcLuxInvalid - 1u);

        uint8_t alv[10] {};
        ish::formatAlv0(alv, 24576u, 0u);
        CHECK(alv[0] == 1u && alv[1] == 1u);
        CHECK(alv[2] == 0x00u && alv[3] == 0x01u); // chan0 = 1
        CHECK(alv[6] == 0x00u && alv[7] == 0x00u && alv[8] == 0x60u && alv[9] == 0x00u); // 24576 = 0x6000

        // Force Lux bit (4) + Force Chan bit (2) + Force HighGain (8)
        alv[1] = 0u;
        ish::formatAlv0(alv, 163840u, ish::kForceLux | ish::kForceChan | ish::kForceHighGain);
        CHECK(alv[0] == 1u);
        CHECK(alv[1] == 0u); // highGain preserved
        CHECK(alv[2] == 0x00u && alv[3] == 0x01u); // chan0 preserved
        CHECK(alv[6] == 0x00u && alv[7] == 0x00u && alv[8] == 0x60u && alv[9] == 0x00u); // roomLux preserved

        // Invalid / sleeping sentinel clears valid byte
        ish::formatAlv0(alv, ish::kSmcLuxInvalid, 0u);
        CHECK(alv[0] == 0u);
    }

    // 4) Non-ALS descriptor returns false cleanly
    {
        auto nonAls = buildNonAlsDescriptor(0x0073u); // Accelerometer 3D
        ish::AlsDescriptorInfo als {};
        CHECK(!ish::parseAlsReportDescriptor(nonAls.data(), nonAls.size(), als));
    }

    // 5) Hysteresis rule
    {
        CHECK(ish::shouldPostAlsChange(false, 0ULL, true, 100ULL));
        CHECK(!ish::shouldPostAlsChange(true, 10000ULL, true, 10400ULL)); // < 500
        CHECK(ish::shouldPostAlsChange(true, 10000ULL, true, 10500ULL));  // == 500 == 5%
        CHECK(!ish::shouldPostAlsChange(true, 100000ULL, true, 104000ULL)); // < 5% (5000)
        CHECK(ish::shouldPostAlsChange(true, 100000ULL, true, 105000ULL));  // >= 5%
        CHECK(ish::shouldPostAlsChange(true, 100000ULL, false, 0ULL));
    }
}

// Helper to inject a potentially multi-fragment ISHTP message into IshTransport
static void injectIshtpMessage(ish::IshTransport &tr, uint8_t fwAddr, uint8_t hostAddr,
                               const uint8_t *data, size_t len, uint64_t nowNs,
                               size_t forceMaxFrag = ish::kIshtpMaxFragPayload) {
    size_t off = 0;
    while (off < len) {
        size_t chunk = len - off;
        if (chunk > forceMaxFrag) {
            chunk = forceMaxFrag;
        }
        const bool complete = (off + chunk == len);
        uint8_t frame[128] {};
        ish::writeLe32(frame, ish::makeIshtpHdrWord(fwAddr, hostAddr, static_cast<uint16_t>(chunk), complete));
        std::memcpy(frame + 4, data + off, chunk);
        tr.onRxFrame(ish::makeDrbl(ish::kProtoIshtp, 0u, static_cast<uint16_t>(4u + chunk)),
                     frame, 4u + chunk, nowNs);
        off += chunk;
    }
}

static std::vector<ish::TxFrame> drainTx(ish::IshTransport &tr) {
    std::vector<ish::TxFrame> out;
    ish::TxFrame f {};
    while (tr.popTxFrame(f)) {
        out.push_back(f);
    }
    return out;
}

static std::vector<uint8_t> makeHostifMsg(uint8_t cmd, uint8_t devId, uint8_t status,
                                          const uint8_t *payload, size_t len) {
    std::vector<uint8_t> v(sizeof(ish::HostifMsgHdr) + len);
    ish::HostifMsgHdr hdr { cmd, devId, status, 0u, static_cast<uint16_t>(len) };
    std::memcpy(v.data(), &hdr, sizeof(hdr));
    if (len > 0 && payload != nullptr) {
        std::memcpy(v.data() + sizeof(hdr), payload, len);
    }
    return v;
}

static void injectFwFlowControl(ish::IshTransport &tr, uint8_t fwAddr, uint8_t hostAddr, uint64_t nowNs) {
    ish::HbmClientCmd fc {};
    fc.cmd = ish::kHbmFlowControl;
    fc.fw_addr = fwAddr;
    fc.host_addr = hostAddr;
    injectIshtpMessage(tr, 0u, 0u, reinterpret_cast<const uint8_t *>(&fc), sizeof(fc), nowNs);
}

static std::vector<uint8_t> makeDmEnumPayload(const ish::HidDeviceInfo *devs, uint8_t count) {
    std::vector<uint8_t> buf(1u + static_cast<size_t>(count) * sizeof(ish::HidDeviceInfo));
    buf[0] = count;
    if (count > 0 && devs != nullptr) {
        std::memcpy(buf.data() + 1u, devs, static_cast<size_t>(count) * sizeof(ish::HidDeviceInfo));
    }
    return buf;
}

static void testFullStateMachineMultiSensorAndReports() {
    ish::IshTransport tr;
    uint64_t t = 1000000ULL;
    tr.reset(t);
    tr.startInit(t);
    CHECK(tr.stage() == ish::IshTransport::Stage::ResetWait);

    // 1) MNG_RESET_NOTIFY sent -> reply MNG_RESET_NOTIFY_ACK
    auto tx = drainTx(tr);
    CHECK(tx.size() == 1u && tx[0].proto == ish::kProtoMng && tx[0].mngCmd == ish::kMngResetNotify);
    const uint8_t ackPayload[4] = { 1u, 0u, 0u, 0u };
    tr.onRxFrame(ish::makeDrbl(ish::kProtoMng, ish::kMngResetNotifyAck, 4u), ackPayload, 4u, t);
    CHECK(tr.stage() == ish::IshTransport::Stage::ReadyWait);

    // 2) FWSTS ready -> HBM_HOST_START_REQ + initial MNG_SYNC_FW_CLOCK
    t += 10ULL * ish::IshTransport::kNsPerMs;
    tr.onTick(t, ish::kFwstsReadyMask, false, 1700000000000000ULL, 10000ULL);
    CHECK(tr.stage() == ish::IshTransport::Stage::HbmVersionWait);
    CHECK(tr.clockSyncCount() == 1u);
    tx = drainTx(tr);
    CHECK(tx.size() == 2u);
    CHECK(tx[0].data[4] == ish::kHbmHostStartReq);
    CHECK(tx[1].proto == ish::kProtoMng && tx[1].mngCmd == ish::kMngSyncFwClock && tx[1].len == 20u);

    // 3) HBM_HOST_START_RES -> HBM_HOST_ENUM_REQ
    const uint8_t startRes[4] = { ish::kHbmHostStartRes, 1u, 0u, 1u };
    injectIshtpMessage(tr, 0u, 0u, startRes, sizeof(startRes), t);
    CHECK(tr.stage() == ish::IshTransport::Stage::HbmEnumWait);
    tx = drainTx(tr);
    CHECK(tx.size() == 1u && tx[0].data[4] == ish::kHbmHostEnumReq);

    // 4) HBM_HOST_ENUM_RES with bits 2 (non-HID), 7 (HID), 13 (System State) + Client 14 DSM Init
    ish::HbmEnumRes enumRes {};
    enumRes.cmd = ish::kHbmHostEnumRes;
    enumRes.valid_bits[2 >> 3]  |= static_cast<uint8_t>(1u << (2u & 7u));
    enumRes.valid_bits[7 >> 3]  |= static_cast<uint8_t>(1u << (7u & 7u));
    enumRes.valid_bits[13 >> 3] |= static_cast<uint8_t>(1u << (13u & 7u));
    injectIshtpMessage(tr, 0u, 0u, reinterpret_cast<const uint8_t *>(&enumRes), sizeof(enumRes), t);
    CHECK(tr.stage() == ish::IshTransport::Stage::HbmPropsLoop);
    tx = drainTx(tr);
    CHECK(tx.size() == 2u);
    CHECK(tx[0].data[4] == ish::kHbmHostClientPropsReq && tx[0].data[5] == 2u);
    {
        uint8_t dfw = 0, dhost = 0;
        uint16_t dlen = 0;
        bool dcomp = false;
        ish::parseIshtpHdrWord(ish::readLe32(tx[1].data), dfw, dhost, dlen, dcomp);
        CHECK(dfw == ish::kDsmProxyFwAddr && dhost == 0u && dlen == 12u && dcomp);
        CHECK(ish::readLe32(tx[1].data + 4) == ish::kDsmCmdInit);
        CHECK(ish::readLe32(tx[1].data + 8) == 0u);
        CHECK(ish::readLe32(tx[1].data + 12) == ish::kDsmDefaultSupportedMask);
    }

    // Client 2 is not HID
    ish::HbmPropsRes propsNonHid {};
    propsNonHid.cmd = ish::kHbmHostClientPropsRes;
    propsNonHid.addr = 2u;
    propsNonHid.status = 0u;
    propsNonHid.props.guid[0] = 0xAAu;
    injectIshtpMessage(tr, 0u, 0u, reinterpret_cast<const uint8_t *>(&propsNonHid), sizeof(propsNonHid), t);
    tx = drainTx(tr);
    CHECK(tx.size() == 1u && tx[0].data[4] == ish::kHbmHostClientPropsReq && tx[0].data[5] == 7u);

    // Client 7 IS HID; continue enumerating remaining HBM clients (13) before connecting!
    ish::HbmPropsRes propsHid {};
    propsHid.cmd = ish::kHbmHostClientPropsRes;
    propsHid.addr = 7u;
    propsHid.status = 0u;
    std::memcpy(propsHid.props.guid, ish::kIshHidClientGuid, 16u);
    ish::writeLe32(reinterpret_cast<uint8_t *>(&propsHid.props.max_msg_length), 4096u);
    injectIshtpMessage(tr, 0u, 0u, reinterpret_cast<const uint8_t *>(&propsHid), sizeof(propsHid), t);
    CHECK(tr.stage() == ish::IshTransport::Stage::HbmPropsLoop);
    tx = drainTx(tr);
    CHECK(tx.size() == 1u && tx[0].data[4] == ish::kHbmHostClientPropsReq && tx[0].data[5] == 13u);

    // Client 13 properties response -> full HBM enumeration complete, now connect to HID client 7
    ish::HbmPropsRes propsSysState {};
    propsSysState.cmd = ish::kHbmHostClientPropsRes;
    propsSysState.addr = 13u;
    propsSysState.status = 0u;
    propsSysState.props.guid[0] = 0x13u;
    injectIshtpMessage(tr, 0u, 0u, reinterpret_cast<const uint8_t *>(&propsSysState), sizeof(propsSysState), t);
    CHECK(tr.stage() == ish::IshTransport::Stage::HidConnectWait);
    tx = drainTx(tr);
    CHECK(tx.size() == 1u && tx[0].data[4] == ish::kHbmClientConnectReq && tx[0].data[5] == 7u && tx[0].data[6] == 1u);

    // 5) CLIENT_CONNECT_RES -> initial RX flow credit sent, DM_ENUM_DEVICES held until FW grants 0x08 TX credit!
    const uint8_t connRes[4] = { ish::kHbmClientConnectRes, 7u, 1u, 0u };
    injectIshtpMessage(tr, 0u, 0u, connRes, sizeof(connRes), t);
    CHECK(tr.stage() == ish::IshTransport::Stage::HidEnumWait);
    CHECK(tr.flowCreditsSent() == 1u);
    CHECK(tr.hidTxCredits() == 0u);
    CHECK(tr.hidTxPending());
    tx = drainTx(tr);
    CHECK(tx.size() == 1u);
    CHECK(tx[0].data[4] == ish::kHbmFlowControl);

    // Now FW grants TX flow credit (0x08) -> DM_ENUM_DEVICES immediately flushes!
    injectFwFlowControl(tr, 7u, 1u, t);
    CHECK(!tr.hidTxPending());
    CHECK(tr.hidTxCredits() == 0u);
    tx = drainTx(tr);
    CHECK(tx.size() == 1u && tx[0].data[4] == ish::kHostifDmEnumDevices);
    CHECK(ish::readLe16(tx[0].data + 4 + 4) == 0u);

    // 6) DM_ENUM_DEVICES response with 1-byte count prefix (10) + manager-assigned device_id=0x0f (ALS at index 7, dev_id=17)
    ish::HidDeviceInfo devs[10] {};
    for (int i = 0; i < 10; ++i) {
        devs[i].dev_id = static_cast<uint32_t>(10 + i);
    }
    auto dmPayload = makeDmEnumPayload(devs, 10u);
    CHECK(dmPayload.size() == 91u);
    auto enumRsp = makeHostifMsg(ish::kHostifDmEnumDevices | ish::kHostifIsResponse, 0x0Fu, 0u,
                                 dmPayload.data(), dmPayload.size());
    injectFwFlowControl(tr, 7u, 1u, t); // pre-grant 1 TX credit from FW
    injectIshtpMessage(tr, 7u, 1u, enumRsp.data(), enumRsp.size(), t);
    CHECK(tr.stage() == ish::IshTransport::Stage::HidDescHidWait);
    CHECK(tr.hidDevCount() == 10u);
    CHECK(tr.flowCreditsSent() == 2u);
    tx = drainTx(tr);
    CHECK(tx.size() == 2u && tx[0].data[4] == ish::kHbmFlowControl);

    // Skip devices 0..6 (device 0 returns error on GET_HID_DESCRIPTOR, 1..6 return non-ALS report desc)
    for (int i = 0; i < 7; ++i) {
        const uint8_t devId = static_cast<uint8_t>(10 + i);
        if (i == 0) {
            injectFwFlowControl(tr, 7u, 1u, t);
            auto hidErr = makeHostifMsg(ish::kHostifGetHidDescriptor | ish::kHostifIsResponse, devId, 1u, nullptr, 0u);
            injectIshtpMessage(tr, 7u, 1u, hidErr.data(), hidErr.size(), t);
            drainTx(tr);
            continue;
        }
        injectFwFlowControl(tr, 7u, 1u, t);
        const uint8_t hidDescBytes[9] = { 9, 0x21, 0x11, 0x01, 0, 1, 0x22, 20, 0 };
        auto hidRsp = makeHostifMsg(ish::kHostifGetHidDescriptor | ish::kHostifIsResponse, devId, 0u, hidDescBytes, sizeof(hidDescBytes));
        injectIshtpMessage(tr, 7u, 1u, hidRsp.data(), hidRsp.size(), t);
        drainTx(tr);
        injectFwFlowControl(tr, 7u, 1u, t);
        auto nonAls = buildNonAlsDescriptor(0x0073u);
        auto rptRsp = makeHostifMsg(ish::kHostifGetReportDescriptor | ish::kHostifIsResponse, devId, 0u, nonAls.data(), nonAls.size());
        injectIshtpMessage(tr, 7u, 1u, rptRsp.data(), rptRsp.size(), t);
        drainTx(tr);
    }

    // Device 7 (devId=17) is ALS; split its report descriptor across multiple 40-byte fragments
    // AND interleave a SYSTEM_STATE_SUBSCRIBE (fw_addr=13, cmd=1) mid-transfer!
    {
        const uint8_t alsDev = 17u;
        injectFwFlowControl(tr, 7u, 1u, t);
        const uint8_t hidDescBytes[9] = { 9, 0x21, 0x11, 0x01, 0, 1, 0x22, 100, 0 };
        auto hidRsp = makeHostifMsg(ish::kHostifGetHidDescriptor | ish::kHostifIsResponse, alsDev, 0u, hidDescBytes, sizeof(hidDescBytes));
        injectIshtpMessage(tr, 7u, 1u, hidRsp.data(), hidRsp.size(), t);
        drainTx(tr);

        auto alsRptDesc = buildComplexAlsDescriptor(true);
        auto rptRsp = makeHostifMsg(ish::kHostifGetReportDescriptor | ish::kHostifIsResponse, alsDev, 0u,
                                    alsRptDesc.data(), alsRptDesc.size());
        const uint32_t fcBefore = tr.flowCreditsSent();

        // First fragment (incomplete!)
        uint8_t f0[44] {};
        ish::writeLe32(f0, ish::makeIshtpHdrWord(7u, 1u, 40u, false));
        std::memcpy(f0 + 4, rptRsp.data(), 40u);
        tr.onRxFrame(ish::makeDrbl(ish::kProtoIshtp, 0u, 44u), f0, 44u, t);
        CHECK(tr.flowCreditsSent() == fcBefore); // MUST NOT send credit on incomplete fragment!
        CHECK(tr.stage() == ish::IshTransport::Stage::HidDescRptWait);

        // Interleave System State SUBSCRIBE on fw_addr=13, host_addr=0
        ish::SysStateSubscribe sub {};
        ish::writeLe32(reinterpret_cast<uint8_t *>(&sub.cmd), ish::kSysStateSubscribeCmd);
        ish::writeLe32(reinterpret_cast<uint8_t *>(&sub.states), ish::kSysStateAllSupported);
        injectIshtpMessage(tr, ish::kSysStateFwAddr, 0u, reinterpret_cast<const uint8_t *>(&sub), sizeof(sub), t);
        CHECK(tr.sysStateCount() == 1u);
        CHECK(tr.sysStateSubscribed());
        CHECK((tr.fixedClientsSeen() & (1u << ish::kSysStateFwAddr)) != 0u);
        tx = drainTx(tr);
        CHECK(tx.size() == 1u);
        uint8_t sfw = 0, shost = 0;
        uint16_t slen = 0;
        bool scomp = false;
        ish::parseIshtpHdrWord(ish::readLe32(tx[0].data), sfw, shost, slen, scomp);
        CHECK(sfw == 13u && shost == 0u && slen == 16u && scomp);
        CHECK(ish::readLe32(tx[0].data + 4) == ish::kSysStateStatusCmd);
        CHECK(ish::readLe32(tx[0].data + 8) == 0u);
        CHECK(ish::readLe32(tx[0].data + 12) == ish::kSysStateAllSupported);
        CHECK(ish::readLe32(tx[0].data + 16) == 0u);

        // Remaining fragment(s) of ALS report descriptor -> ALS found, continue enumerating remaining devices 8 & 9!
        injectIshtpMessage(tr, 7u, 1u, rptRsp.data() + 40u, rptRsp.size() - 40u, t, 40u);
        CHECK(tr.flowCreditsSent() == fcBefore + 1u); // Exactly 1 credit on complete message!
        CHECK(tr.alsDevId() == alsDev);
        CHECK(tr.alsDesc().found);
        CHECK(tr.stage() == ish::IshTransport::Stage::HidDescHidWait);
        tx = drainTx(tr);
        CHECK(tx.size() == 1u); // Pending GET_HID_DESCRIPTOR held because FW hasn't sent 0x08 yet!
        CHECK(tx[0].data[4] == ish::kHbmFlowControl);

        // Device 8 (devId=18, non-ALS)
        injectFwFlowControl(tr, 7u, 1u, t);
        tx = drainTx(tr);
        CHECK(tx.size() == 1u && tx[0].data[4] == ish::kHostifGetHidDescriptor && tx[0].data[5] == 18u);
        injectFwFlowControl(tr, 7u, 1u, t);
        auto hid8Rsp = makeHostifMsg(ish::kHostifGetHidDescriptor | ish::kHostifIsResponse, 18u, 0u, hidDescBytes, sizeof(hidDescBytes));
        injectIshtpMessage(tr, 7u, 1u, hid8Rsp.data(), hid8Rsp.size(), t);
        drainTx(tr);
        injectFwFlowControl(tr, 7u, 1u, t);
        auto nonAls8 = buildNonAlsDescriptor(0x0073u);
        auto rpt8Rsp = makeHostifMsg(ish::kHostifGetReportDescriptor | ish::kHostifIsResponse, 18u, 0u, nonAls8.data(), nonAls8.size());
        injectIshtpMessage(tr, 7u, 1u, rpt8Rsp.data(), rpt8Rsp.size(), t);
        drainTx(tr);

        // Device 9 (devId=19, non-ALS) -> once complete, enters AlsFeatGet and holds GET_FEATURE_REPORT until FW 0x08!
        injectFwFlowControl(tr, 7u, 1u, t);
        auto hid9Rsp = makeHostifMsg(ish::kHostifGetHidDescriptor | ish::kHostifIsResponse, 19u, 0u, hidDescBytes, sizeof(hidDescBytes));
        injectIshtpMessage(tr, 7u, 1u, hid9Rsp.data(), hid9Rsp.size(), t);
        drainTx(tr);
        auto nonAls9 = buildNonAlsDescriptor(0x0073u);
        auto rpt9Rsp = makeHostifMsg(ish::kHostifGetReportDescriptor | ish::kHostifIsResponse, 19u, 0u, nonAls9.data(), nonAls9.size());
        injectIshtpMessage(tr, 7u, 1u, rpt9Rsp.data(), rpt9Rsp.size(), t);
        CHECK(tr.stage() == ish::IshTransport::Stage::AlsFeatGet);
        CHECK(tr.hidTxPending()); // Held because FW hasn't sent 0x08 yet!
        tx = drainTx(tr);
        CHECK(tx.size() == 1u && tx[0].data[4] == ish::kHbmFlowControl);

        injectFwFlowControl(tr, 7u, 1u, t);
        CHECK(!tr.hidTxPending());
        tx = drainTx(tr);
        CHECK(tx.size() == 1u && tx[0].data[4] == ish::kHostifGetFeatureReport);
        CHECK(ish::readLe16(tx[0].data + 4 + 4) == 1u && tx[0].data[4 + 6] == 0x03u);
    }

    // 7) Feature RMW -> Set -> Verify -> Prime -> Streaming
    {
        injectFwFlowControl(tr, 7u, 1u, t);
        uint8_t feat[7] = { 0x03u, 0x05u, 0x00u, 0x10u, 0x27u, 0x00u, 0x00u };
        auto fgRsp = makeHostifMsg(ish::kHostifGetFeatureReport | ish::kHostifIsResponse, 17u, 0u, feat, sizeof(feat));
        injectIshtpMessage(tr, 7u, 1u, fgRsp.data(), fgRsp.size(), t);
        CHECK(tr.stage() == ish::IshTransport::Stage::AlsFeatSet);
        tx = drainTx(tr);
        CHECK(tx.size() == 2u);
        // Check payload written in SET_FEATURE_REPORT: byte 4.. are HostifMsgHdr (6B), then feat[7]
        CHECK(ish::readLe16(tx[1].data + 4 + 4) == sizeof(feat));
        const uint8_t *sentFeat = tx[1].data + 4 + sizeof(ish::HostifMsgHdr);
        CHECK(sentFeat[0] == 0x03u);
        CHECK((sentFeat[1] & 0x0Fu) == 0x05u);
        CHECK((sentFeat[1] >> 4) == 2u); // D0
        CHECK(sentFeat[2] == 1u);        // All Events
        CHECK(ish::readLe32(sentFeat + 3u) == ish::kDefaultAlsIntervalMs); // 10000ms tuned -> 250ms
        CHECK(tr.alsIntervalMs() == ish::kDefaultAlsIntervalMs);

        injectFwFlowControl(tr, 7u, 1u, t);
        auto fsRsp = makeHostifMsg(ish::kHostifSetFeatureReport | ish::kHostifIsResponse, 17u, 0u, nullptr, 0u);
        injectIshtpMessage(tr, 7u, 1u, fsRsp.data(), fsRsp.size(), t);
        CHECK(tr.stage() == ish::IshTransport::Stage::AlsFeatVerify);
        tx = drainTx(tr);
        CHECK(tx.size() == 2u && tx[1].data[4] == ish::kHostifGetFeatureReport);
        CHECK(ish::readLe16(tx[1].data + 4 + 4) == 1u && tx[1].data[4 + 6] == 0x03u);

        injectFwFlowControl(tr, 7u, 1u, t);
        uint8_t verifiedFeat[7] = { 0x03u, 0x25u, 0x01u, 0xFAu, 0x00u, 0x00u, 0x00u };
        auto fvRsp = makeHostifMsg(ish::kHostifGetFeatureReport | ish::kHostifIsResponse, 17u, 0u, verifiedFeat, sizeof(verifiedFeat));
        injectIshtpMessage(tr, 7u, 1u, fvRsp.data(), fvRsp.size(), t);
        CHECK(tr.alsControlsVerified());
        CHECK(tr.stage() == ish::IshTransport::Stage::AlsPrimeInput);
        tx = drainTx(tr);
        CHECK(tx.size() == 2u && tx[1].data[4] == ish::kHostifGetInputReport);
        CHECK(ish::readLe16(tx[1].data + 4 + 4) == 1u && tx[1].data[4 + 6] == 0x03u);

        uint8_t primeIn[6] = { 0x03u, 0x00u, 0xE8u, 0x03u, 0x00u, 0x00u }; // raw = 1000 -> 10.00 lux = 10000 milliLux
        auto giRsp = makeHostifMsg(ish::kHostifGetInputReport | ish::kHostifIsResponse, 17u, 0u, primeIn, sizeof(primeIn));
        injectIshtpMessage(tr, 7u, 1u, giRsp.data(), giRsp.size(), t);
        CHECK(tr.stage() == ish::IshTransport::Stage::Streaming);
        CHECK(tr.consumeSampleUpdated());
        CHECK(tr.milliLux() == 10000ULL);
        drainTx(tr);
    }

    // 8) Asynchronous PUBLISH_INPUT_REPORT (5)
    {
        uint8_t pubIn[6] = { 0x03u, 0x00u, 0x88u, 0x13u, 0x00u, 0x00u }; // 5000 -> 50000 milliLux
        auto pubMsg = makeHostifMsg(ish::kHostifPublishInputReport, 17u, 0u, pubIn, sizeof(pubIn));
        injectIshtpMessage(tr, 7u, 1u, pubMsg.data(), pubMsg.size(), t);
        CHECK(tr.consumeSampleUpdated());
        CHECK(tr.milliLux() == 50000ULL);
        drainTx(tr);
    }

    // 9) PUBLISH_INPUT_REPORT_LIST (6) with non-ALS (dev=11) + ALS (dev=17), including inner msg.size==0 fallback
    {
        std::vector<uint8_t> listPayload(sizeof(ish::HidReportListHdr));
        // Item 1: dev=11 (non-ALS)
        uint8_t otherIn[4] = { 0x01u, 0xAAu, 0xBBu, 0xCCu };
        auto item1Msg = makeHostifMsg(ish::kHostifPublishInputReport, 11u, 0u, otherIn, sizeof(otherIn));
        uint16_t sz1 = static_cast<uint16_t>(item1Msg.size());
        listPayload.push_back(static_cast<uint8_t>(sz1 & 0xFFu));
        listPayload.push_back(static_cast<uint8_t>((sz1 >> 8) & 0xFFu));
        listPayload.insert(listPayload.end(), item1Msg.begin(), item1Msg.end());

        // Item 2: dev=17 (ALS) raw = 25000 -> 250000 milliLux (with inner msg.size=0 fallback!)
        uint8_t alsIn[6] = { 0x03u, 0x00u, 0xA8u, 0x61u, 0x00u, 0x00u };
        auto item2Msg = makeHostifMsg(ish::kHostifPublishInputReport, 17u, 0u, alsIn, sizeof(alsIn));
        uint16_t sz2 = static_cast<uint16_t>(item2Msg.size()); // 6 + 6 = 12
        ish::writeLe16(&item2Msg[4], 0u); // force inner msg.size == 0 to verify itemSize - 6 fallback
        listPayload.push_back(static_cast<uint8_t>(sz2 & 0xFFu));
        listPayload.push_back(static_cast<uint8_t>((sz2 >> 8) & 0xFFu));
        listPayload.insert(listPayload.end(), item2Msg.begin(), item2Msg.end());

        ish::writeLe16(&listPayload[0], static_cast<uint16_t>(listPayload.size() - sizeof(ish::HidReportListHdr)));
        listPayload[2] = 2u; // num_of_reports
        listPayload[3] = 0u;

        auto listMsg = makeHostifMsg(ish::kHostifPublishInputReportList, 0u, 0u, listPayload.data(), listPayload.size());
        injectIshtpMessage(tr, 7u, 1u, listMsg.data(), listMsg.size(), t);
        CHECK(tr.consumeSampleUpdated());
        CHECK(tr.milliLux() == 250000ULL);
        drainTx(tr);

        // Guard test: malformed itemSize < sizeof(HostifMsgHdr) is safely ignored without ASan OOB
        uint8_t badList[8] = { 4, 0, 1, 0, 3, 0, 5, 17 };
        auto badMsg = makeHostifMsg(ish::kHostifPublishInputReportList, 0u, 0u, badList, sizeof(badList));
        injectIshtpMessage(tr, 7u, 1u, badMsg.data(), badMsg.size(), t);
        CHECK(!tr.consumeSampleUpdated());
        drainTx(tr);
    }

    // 10) Exact 4096 B valid multi-fragment RX reassembly (34 fragments) with concatenated HostIF messages
    {
        uint8_t dummyOther[118] {};
        std::memset(dummyOther, 0x22, sizeof(dummyOther));
        auto padMsg = makeHostifMsg(ish::kHostifPublishInputReport, 12u, 0u, dummyOther, sizeof(dummyOther)); // 6 + 118 = 124 B

        uint8_t alsIn[6] = { 0x03u, 0x00u, 0x10u, 0x27u, 0x00u, 0x00u }; // 10000 -> 100000 milliLux
        auto alsMsg = makeHostifMsg(ish::kHostifPublishInputReport, 17u, 0u, alsIn, sizeof(alsIn)); // 12 B

        std::vector<uint8_t> sdu;
        for (int k = 0; k < 32; ++k) {
            sdu.insert(sdu.end(), padMsg.begin(), padMsg.end()); // 32 * 124 = 3968 B
        }
        std::vector<uint8_t> filler(110u, 0x33u);
        auto fillerMsg = makeHostifMsg(ish::kHostifPublishInputReport, 12u, 0u, filler.data(), filler.size()); // 6 + 110 = 116 B
        sdu.insert(sdu.end(), fillerMsg.begin(), fillerMsg.end());
        sdu.insert(sdu.end(), alsMsg.begin(), alsMsg.end());
        CHECK(sdu.size() == 4096u);

        const uint32_t fcBefore = tr.flowCreditsSent();
        injectIshtpMessage(tr, 7u, 1u, sdu.data(), sdu.size(), t);
        CHECK(tr.flowCreditsSent() == fcBefore + 1u); // Exactly 1 flow credit for complete 4096 B SDU!
        CHECK(tr.consumeSampleUpdated());
        CHECK(tr.milliLux() == 100000ULL);
        drainTx(tr);
    }

    // 11) Streaming 5000ms keepalive when verified + strict hidTxCredits > 0 guard (never wedges hidTxPending at 0 credits)
    CHECK(tr.hidTxCredits() == 0u);
    CHECK(tr.alsControlsVerified());
    t += 1000ULL * ish::IshTransport::kNsPerMs;
    tr.onTick(t, ish::kFwstsReadyMask, false);
    CHECK(!tr.hidTxPending());
    CHECK(drainTx(tr).empty());

    t += 4000ULL * ish::IshTransport::kNsPerMs;
    tr.onTick(t, ish::kFwstsReadyMask, false);
    CHECK(!tr.hidTxPending());
    CHECK(drainTx(tr).empty()); // Not queued while hidTxCredits == 0!

    // Once FW sends 0x08 credit, next tick immediately emits one GET_INPUT_REPORT!
    injectFwFlowControl(tr, 7u, 1u, t);
    CHECK(tr.hidTxCredits() == 1u);
    tr.onTick(t, ish::kFwstsReadyMask, false);
    CHECK(!tr.hidTxPending());
    CHECK(tr.hidTxCredits() == 0u);
    tx = drainTx(tr);
    CHECK(tx.size() == 1u && tx[0].data[4] == ish::kHostifGetInputReport);
}

static void testNoAlsSensorAndTimeouts() {
    // Test timeout in ResetWait (> 1000 ms)
    {
        ish::IshTransport tr;
        uint64_t t = 5000000ULL;
        tr.startInit(t);
        t += 1001ULL * ish::IshTransport::kNsPerMs;
        tr.onTick(t, 0u, false);
        CHECK(tr.stage() == ish::IshTransport::Stage::Failed);
        CHECK(tr.fixedLux() == ish::kSmcLuxInvalid);
    }

    // Test 4096 B RX overflow guard
    {
        ish::IshTransport tr;
        uint64_t t = 1000000ULL;
        tr.startInit(t);
        uint8_t frag[128] {};
        ish::writeLe32(frag, ish::makeIshtpHdrWord(7u, 1u, 124u, false));
        for (int i = 0; i < 34; ++i) {
            tr.onRxFrame(ish::makeDrbl(ish::kProtoIshtp, 0u, 128u), frag, 128u, t);
        }
        CHECK(tr.overflowDrops() >= 1u);
    }

    // Test DM_ENUM_DEVICES missing 1-byte count prefix (9 bytes instead of 1+9) fails cleanly
    {
        ish::IshTransport tr;
        uint64_t t = 1000000ULL;
        tr.startInit(t);
        drainTx(tr);
        const uint8_t ackPayload[4] = { 1u, 0u, 0u, 0u };
        tr.onRxFrame(ish::makeDrbl(ish::kProtoMng, ish::kMngResetNotifyAck, 4u), ackPayload, 4u, t);
        tr.onTick(t, ish::kFwstsReadyMask, false);
        const uint8_t startRes[4] = { ish::kHbmHostStartRes, 1u, 0u, 1u };
        injectIshtpMessage(tr, 0u, 0u, startRes, sizeof(startRes), t);
        ish::HbmEnumRes enumRes {};
        enumRes.cmd = ish::kHbmHostEnumRes;
        enumRes.valid_bits[0] = (1u << 7);
        injectIshtpMessage(tr, 0u, 0u, reinterpret_cast<const uint8_t *>(&enumRes), sizeof(enumRes), t);
        ish::HbmPropsRes propsHid {};
        propsHid.cmd = ish::kHbmHostClientPropsRes;
        propsHid.addr = 7u;
        std::memcpy(propsHid.props.guid, ish::kIshHidClientGuid, 16u);
        ish::writeLe32(reinterpret_cast<uint8_t *>(&propsHid.props.max_msg_length), 4096u);
        injectIshtpMessage(tr, 0u, 0u, reinterpret_cast<const uint8_t *>(&propsHid), sizeof(propsHid), t);
        const uint8_t connRes[4] = { ish::kHbmClientConnectRes, 7u, 1u, 0u };
        injectIshtpMessage(tr, 0u, 0u, connRes, sizeof(connRes), t);
        injectFwFlowControl(tr, 7u, 1u, t);
        ish::HidDeviceInfo dev { 5u, 0u, 0u, 0u };
        auto badEnumRsp = makeHostifMsg(ish::kHostifDmEnumDevices | ish::kHostifIsResponse, 5u, 0u,
                                        reinterpret_cast<const uint8_t *>(&dev), sizeof(dev)); // 9B, missing 1B count!
        injectIshtpMessage(tr, 7u, 1u, badEnumRsp.data(), badEnumRsp.size(), t);
        CHECK(tr.stage() == ish::IshTransport::Stage::Failed);
    }

    // Test NoAlsSensor clean idle when single sensor is non-ALS
    {
        ish::IshTransport tr;
        uint64_t t = 1000000ULL;
        tr.startInit(t);
        drainTx(tr);
        const uint8_t ackPayload[4] = { 1u, 0u, 0u, 0u };
        tr.onRxFrame(ish::makeDrbl(ish::kProtoMng, ish::kMngResetNotifyAck, 4u), ackPayload, 4u, t);
        tr.onTick(t, ish::kFwstsReadyMask, false);
        drainTx(tr);
        const uint8_t startRes[4] = { ish::kHbmHostStartRes, 1u, 0u, 1u };
        injectIshtpMessage(tr, 0u, 0u, startRes, sizeof(startRes), t);
        ish::HbmEnumRes enumRes {};
        enumRes.cmd = ish::kHbmHostEnumRes;
        enumRes.valid_bits[0] = (1u << 7);
        injectIshtpMessage(tr, 0u, 0u, reinterpret_cast<const uint8_t *>(&enumRes), sizeof(enumRes), t);
        ish::HbmPropsRes propsHid {};
        propsHid.cmd = ish::kHbmHostClientPropsRes;
        propsHid.addr = 7u;
        std::memcpy(propsHid.props.guid, ish::kIshHidClientGuid, 16u);
        ish::writeLe32(reinterpret_cast<uint8_t *>(&propsHid.props.max_msg_length), 4096u);
        injectIshtpMessage(tr, 0u, 0u, reinterpret_cast<const uint8_t *>(&propsHid), sizeof(propsHid), t);
        const uint8_t connRes[4] = { ish::kHbmClientConnectRes, 7u, 1u, 0u };
        injectIshtpMessage(tr, 0u, 0u, connRes, sizeof(connRes), t);
        injectFwFlowControl(tr, 7u, 1u, t);
        ish::HidDeviceInfo dev { 5u, 0u, 0u, 0u };
        auto dmPayload = makeDmEnumPayload(&dev, 1u);
        auto enumRsp = makeHostifMsg(ish::kHostifDmEnumDevices | ish::kHostifIsResponse, 5u, 0u,
                                     dmPayload.data(), dmPayload.size());
        injectFwFlowControl(tr, 7u, 1u, t);
        injectIshtpMessage(tr, 7u, 1u, enumRsp.data(), enumRsp.size(), t);
        const uint8_t hidDesc[9] = { 9, 0x21, 0x11, 0x01, 0, 1, 0x22, 20, 0 };
        auto hidRsp = makeHostifMsg(ish::kHostifGetHidDescriptor | ish::kHostifIsResponse, 5u, 0u, hidDesc, sizeof(hidDesc));
        injectFwFlowControl(tr, 7u, 1u, t);
        injectIshtpMessage(tr, 7u, 1u, hidRsp.data(), hidRsp.size(), t);
        auto nonAls = buildNonAlsDescriptor(0x0076u);
        auto rptRsp = makeHostifMsg(ish::kHostifGetReportDescriptor | ish::kHostifIsResponse, 5u, 0u, nonAls.data(), nonAls.size());
        injectIshtpMessage(tr, 7u, 1u, rptRsp.data(), rptRsp.size(), t);
        CHECK(tr.stage() == ish::IshTransport::Stage::NoAlsSensor);
    }
}

static void bringTransportToEnumDone(ish::IshTransport &tr, uint64_t &t) {
    tr.reset(t);
    tr.startInit(t);
    drainTx(tr);
    const uint8_t ackPayload[4] = { 1u, 0u, 0u, 0u };
    tr.onRxFrame(ish::makeDrbl(ish::kProtoMng, ish::kMngResetNotifyAck, 4u), ackPayload, 4u, t);
    t += 10ULL * ish::IshTransport::kNsPerMs;
    tr.onTick(t, ish::kFwstsReadyMask, false, 1700000100000000ULL, 10000ULL);
    drainTx(tr);
    const uint8_t startRes[4] = { ish::kHbmHostStartRes, 1u, 0u, 1u };
    injectIshtpMessage(tr, 0u, 0u, startRes, sizeof(startRes), t);
    drainTx(tr);
    ish::HbmEnumRes enumRes {};
    enumRes.cmd = ish::kHbmHostEnumRes;
    enumRes.valid_bits[7 >> 3] |= static_cast<uint8_t>(1u << (7u & 7u));
    injectIshtpMessage(tr, 0u, 0u, reinterpret_cast<const uint8_t *>(&enumRes), sizeof(enumRes), t);
    drainTx(tr);
}

static void bringTransportToStreaming(ish::IshTransport &tr, uint64_t &t, uint64_t utc0, uint64_t mono0) {
    tr.reset(t);
    tr.startInit(t);
    drainTx(tr);
    const uint8_t ackPayload[4] = { 1u, 0u, 0u, 0u };
    tr.onRxFrame(ish::makeDrbl(ish::kProtoMng, ish::kMngResetNotifyAck, 4u), ackPayload, 4u, t);
    t += 10ULL * ish::IshTransport::kNsPerMs;
    tr.onTick(t, ish::kFwstsReadyMask, false, utc0, mono0);
    const uint8_t startRes[4] = { ish::kHbmHostStartRes, 1u, 0u, 1u };
    injectIshtpMessage(tr, 0u, 0u, startRes, sizeof(startRes), t);
    ish::HbmEnumRes enumRes {};
    enumRes.cmd = ish::kHbmHostEnumRes;
    enumRes.valid_bits[7 >> 3] |= static_cast<uint8_t>(1u << (7u & 7u));
    injectIshtpMessage(tr, 0u, 0u, reinterpret_cast<const uint8_t *>(&enumRes), sizeof(enumRes), t);
    ish::HbmPropsRes propsHid {};
    propsHid.cmd = ish::kHbmHostClientPropsRes;
    propsHid.addr = 7u;
    propsHid.status = 0u;
    std::memcpy(propsHid.props.guid, ish::kIshHidClientGuid, 16u);
    ish::writeLe32(reinterpret_cast<uint8_t *>(&propsHid.props.max_msg_length), 4096u);
    injectIshtpMessage(tr, 0u, 0u, reinterpret_cast<const uint8_t *>(&propsHid), sizeof(propsHid), t);
    const uint8_t connRes[4] = { ish::kHbmClientConnectRes, 7u, 1u, 0u };
    injectIshtpMessage(tr, 0u, 0u, connRes, sizeof(connRes), t);
    injectFwFlowControl(tr, 7u, 1u, t);
    ish::HidDeviceInfo dev { 17u, 0u, 0u, 0u };
    auto dmPayload = makeDmEnumPayload(&dev, 1u);
    auto enumRsp = makeHostifMsg(ish::kHostifDmEnumDevices | ish::kHostifIsResponse, 0x0Fu, 0u,
                                 dmPayload.data(), dmPayload.size());
    injectFwFlowControl(tr, 7u, 1u, t);
    injectIshtpMessage(tr, 7u, 1u, enumRsp.data(), enumRsp.size(), t);
    const uint8_t hidDesc[9] = { 9, 0x21, 0x11, 0x01, 0, 1, 0x22, 100, 0 };
    auto hidRsp = makeHostifMsg(ish::kHostifGetHidDescriptor | ish::kHostifIsResponse, 17u, 0u, hidDesc, sizeof(hidDesc));
    injectFwFlowControl(tr, 7u, 1u, t);
    injectIshtpMessage(tr, 7u, 1u, hidRsp.data(), hidRsp.size(), t);
    auto alsDesc = buildComplexAlsDescriptor(true);
    auto rptRsp = makeHostifMsg(ish::kHostifGetReportDescriptor | ish::kHostifIsResponse, 17u, 0u,
                                alsDesc.data(), alsDesc.size());
    injectFwFlowControl(tr, 7u, 1u, t);
    injectIshtpMessage(tr, 7u, 1u, rptRsp.data(), rptRsp.size(), t);
    uint8_t feat[7] = { 0x03u, 0x25u, 0x01u, 0xC8u, 0x00u, 0x00u, 0x00u };
    auto fgRsp = makeHostifMsg(ish::kHostifGetFeatureReport | ish::kHostifIsResponse, 17u, 0u, feat, sizeof(feat));
    injectFwFlowControl(tr, 7u, 1u, t);
    injectIshtpMessage(tr, 7u, 1u, fgRsp.data(), fgRsp.size(), t);
    auto fsRsp = makeHostifMsg(ish::kHostifSetFeatureReport | ish::kHostifIsResponse, 17u, 0u, nullptr, 0u);
    injectFwFlowControl(tr, 7u, 1u, t);
    injectIshtpMessage(tr, 7u, 1u, fsRsp.data(), fsRsp.size(), t);
    auto fvRsp = makeHostifMsg(ish::kHostifGetFeatureReport | ish::kHostifIsResponse, 17u, 0u, feat, sizeof(feat));
    injectFwFlowControl(tr, 7u, 1u, t);
    injectIshtpMessage(tr, 7u, 1u, fvRsp.data(), fvRsp.size(), t);
    uint8_t primeIn[6] = { 0x03u, 0x00u, 0x10u, 0x00u, 0x00u, 0x00u };
    auto giRsp = makeHostifMsg(ish::kHostifGetInputReport | ish::kHostifIsResponse, 17u, 0u, primeIn, sizeof(primeIn));
    injectIshtpMessage(tr, 7u, 1u, giRsp.data(), giRsp.size(), t);
    drainTx(tr);
}

static void testClockSyncProtocolAnd20sCadence() {
    // Wire layout & doorbell verification matching ISH.sys fcn.14000eed8 and Linux hw-ish.h
    CHECK(ish::makeDrbl(ish::kProtoMng, ish::kMngSyncFwClock, sizeof(ish::MngClockSyncMsg)) == 0x80050C14u);
    CHECK(sizeof(ish::MngClockSyncMsg) == 20u);
    {
        uint8_t raw[20] {};
        const uint64_t utc = 1731990123456789ULL;
        const uint64_t mono = 987654321ULL;
        ish::packMngClockSync(utc, mono, raw);
        uint64_t p = 0, s = 0;
        for (size_t i = 0; i < 8u; ++i) {
            p |= static_cast<uint64_t>(raw[i]) << (i * 8u);
            s |= static_cast<uint64_t>(raw[12u + i]) << (i * 8u);
        }
        CHECK(p == utc);
        CHECK(raw[8] == ish::kClockSourceHostUtcUsec);
        CHECK(raw[9] == ish::kClockSourceHostSysUsec);
        CHECK(raw[10] == 0u && raw[11] == 0u);
        CHECK(s == mono);
    }

    // Immediate post-reset sync + 20 s periodic cadence + suspend/resume gating
    {
        ish::IshTransport tr;
        uint64_t t = 1000000ULL;
        const uint64_t utc0 = 1732000000123456ULL;
        const uint64_t mono0 = 55000ULL;
        bringTransportToStreaming(tr, t, utc0, mono0);
        CHECK(tr.stage() == ish::IshTransport::Stage::Streaming);
        CHECK(tr.clockSyncCount() == 1u);
        CHECK(tr.alsIntervalMs() == 200u);
        CHECK(tr.isAlsDarkPermissive());

        // At +19.9 s: NO periodic sync yet
        const uint64_t tJustBefore = t + 19900ULL * ish::IshTransport::kNsPerMs;
        tr.onTick(tJustBefore, ish::kFwstsReadyMask, false, utc0 + 19900000ULL, mono0 + 19900000ULL);
        CHECK(tr.clockSyncCount() == 1u);
        for (const auto &f : drainTx(tr)) {
            CHECK(!(f.proto == ish::kProtoMng && f.mngCmd == ish::kMngSyncFwClock));
        }

        // At +20.0 s: second MNG_SYNC_FW_CLOCK emits!
        const uint64_t tAt20s = t + 20000ULL * ish::IshTransport::kNsPerMs;
        tr.onTick(tAt20s, ish::kFwstsReadyMask, false, utc0 + 20000000ULL, mono0 + 20000000ULL);
        CHECK(tr.clockSyncCount() == 2u);
        auto tx = drainTx(tr);
        bool sawSync20 = false;
        uint64_t p20 = 0, s20 = 0;
        for (const auto &f : tx) {
            if (f.proto == ish::kProtoMng && f.mngCmd == ish::kMngSyncFwClock) {
                sawSync20 = (f.len == 20u &&
                             f.data[8] == ish::kClockSourceHostUtcUsec &&
                             f.data[9] == ish::kClockSourceHostSysUsec);
                for (size_t i = 0; i < 8u; ++i) {
                    p20 |= static_cast<uint64_t>(f.data[i]) << (i * 8u);
                    s20 |= static_cast<uint64_t>(f.data[12u + i]) << (i * 8u);
                }
            }
        }
        CHECK(sawSync20);
        CHECK(p20 == utc0 + 20000000ULL && s20 == mono0 + 20000000ULL);

        // At +40.0 s: third MNG_SYNC_FW_CLOCK emits!
        const uint64_t tAt40s = tAt20s + 20000ULL * ish::IshTransport::kNsPerMs;
        tr.onTick(tAt40s, ish::kFwstsReadyMask, false, utc0 + 40000000ULL, mono0 + 40000000ULL);
        CHECK(tr.clockSyncCount() == 3u);
        drainTx(tr);

        // Host suspended at +65 s: clock sync MUST NOT fire while suspended
        tr.setHostPowerState(false, false, tAt40s + 1000ULL, utc0 + 41000000ULL, mono0 + 41000000ULL);
        drainTx(tr);
        tr.onTick(tAt40s + 25000ULL * ish::IshTransport::kNsPerMs, ish::kFwstsReadyMask, false,
                  utc0 + 65000000ULL, mono0 + 65000000ULL);
        CHECK(tr.clockSyncCount() == 3u);

        // Resume triggers immediate clock sync + SYSTEM_STATE_STATUS!
        tr.setHostPowerState(true, true, tAt40s + 26000ULL * ish::IshTransport::kNsPerMs,
                             utc0 + 66000000ULL, mono0 + 66000000ULL);
        CHECK(tr.clockSyncCount() == 4u);
        tx = drainTx(tr);
        bool sawSyncResume = false;
        bool sawStateResume = false;
        for (const auto &f : tx) {
            if (f.proto == ish::kProtoMng && f.mngCmd == ish::kMngSyncFwClock) {
                sawSyncResume = true;
            }
            if (f.proto == ish::kProtoIshtp && f.len >= 20u && (f.data[0] & 0xFFu) == ish::kSysStateFwAddr) {
                sawStateResume = true;
            }
        }
        CHECK(sawSyncResume && sawStateResume);
    }

    // -tglnoclock kill switch disables clock sync completely
    {
        ish::IshTransport tr;
        uint64_t t = 1000000ULL;
        tr.setClockSyncEnabled(false);
        CHECK(!tr.clockSyncEnabled());
        bringTransportToStreaming(tr, t, 1732000000000000ULL, 10000ULL);
        CHECK(tr.clockSyncCount() == 0u);
        t += 25000ULL * ish::IshTransport::kNsPerMs;
        tr.onTick(t, ish::kFwstsReadyMask, false, 1732025000000000ULL, 25010000ULL);
        CHECK(tr.clockSyncCount() == 0u);
        tr.setHostPowerState(false, false, t, 0, 0);
        tr.setHostPowerState(true, true, t + 1000ULL, 1732025001000000ULL, 25011000ULL);
        CHECK(tr.clockSyncCount() == 0u);
    }
}

static void testFixedClient13SystemStateTransitions() {
    ish::IshTransport tr;
    uint64_t t = 1000000ULL;
    bringTransportToEnumDone(tr, t);

    // 1) Subscribe arrives with bit 0+1 supported
    ish::SysStateSubscribe sub {};
    ish::writeLe32(reinterpret_cast<uint8_t *>(&sub.cmd), ish::kSysStateSubscribeCmd);
    ish::writeLe32(reinterpret_cast<uint8_t *>(&sub.states), ish::kSysStateAllSupported);
    injectIshtpMessage(tr, ish::kSysStateFwAddr, 0u, reinterpret_cast<const uint8_t *>(&sub), sizeof(sub), t);
    CHECK(tr.sysStateSubscribed());
    CHECK(tr.sysStateSupported() == ish::kSysStateAllSupported);
    CHECK(tr.sysStateStatus() == 0u);
    CHECK(tr.sysStateCount() == 1u);
    auto tx = drainTx(tr);
    CHECK(tx.size() == 1u);
    CHECK(ish::readLe32(tx[0].data + 4) == ish::kSysStateStatusCmd);
    CHECK(ish::readLe32(tx[0].data + 12) == ish::kSysStateAllSupported);
    CHECK(ish::readLe32(tx[0].data + 16) == 0u);

    // 2) Display OFF while awake -> CONNECTED_STANDBY_STATE_BIT (0x01)
    CHECK(tr.setHostPowerState(true, false, t));
    CHECK(tr.sysStateStatus() == ish::kSysStateConnectedStandbyBit);
    CHECK(tr.sysStateCount() == 2u);
    tx = drainTx(tr);
    CHECK(tx.size() == 1u);
    CHECK(ish::readLe32(tx[0].data + 4) == ish::kSysStateStatusCmd);
    CHECK(ish::readLe32(tx[0].data + 16) == ish::kSysStateConnectedStandbyBit);

    // 3) Display ON -> cleared (0x00)
    CHECK(tr.setHostPowerState(true, true, t));
    CHECK(tr.sysStateStatus() == 0u);
    tx = drainTx(tr);
    CHECK(tx.size() == 1u && ish::readLe32(tx[0].data + 16) == 0u);

    // 4) Host sleep -> SUSPEND | CONNECTED_STANDBY (0x03)
    CHECK(tr.setHostPowerState(false, false, t));
    CHECK(tr.sysStateStatus() == (ish::kSysStateConnectedStandbyBit | ish::kSysStateSuspendBit));
    tx = drainTx(tr);
    CHECK(tx.size() == 1u && ish::readLe32(tx[0].data + 16) == 0x03u);

    // 5) Incoming STATE_CHANGE_REQ (cmd=4) queues deferred HIDW Func 1 (argLen=4 zero bytes) + sends status!
    ish::SysStateChangeReq req {};
    ish::writeLe32(reinterpret_cast<uint8_t *>(&req.cmd), ish::kSysStateStateChangeReq);
    ish::writeLe32(reinterpret_cast<uint8_t *>(&req.cmd_status), 0u);
    ish::writeLe32(reinterpret_cast<uint8_t *>(&req.requested_states), ish::kSysStateConnectedStandbyBit);
    ish::writeLe32(reinterpret_cast<uint8_t *>(&req.states_status), 0u);
    injectIshtpMessage(tr, ish::kSysStateFwAddr, 0u, reinterpret_cast<const uint8_t *>(&req), sizeof(req), t);
    tx = drainTx(tr);
    CHECK(tx.size() == 1u && ish::readLe32(tx[0].data + 4) == ish::kSysStateStatusCmd);
    ish::DsmWorkItem dsm {};
    CHECK(tr.popPendingDsm(dsm));
    CHECK(dsm.valid && dsm.funcIndex == 1u && dsm.argLen == 4u);
    CHECK(dsm.args[0] == 0u && dsm.args[1] == 0u && dsm.args[2] == 0u && dsm.args[3] == 0u);
}

static void testFixedClient14DsmProxy() {
    // 1) Verify ACPI mixed-endian UUID {1730E71D-E5DD-4A34-BE57-4D76B6A2FE37}
    const uint8_t expectedGuid[16] = {
        0x1Du, 0xE7u, 0x30u, 0x17u, 0xDDu, 0xE5u, 0x34u, 0x4Au,
        0xBEu, 0x57u, 0x4Du, 0x76u, 0xB6u, 0xA2u, 0xFEu, 0x37u
    };
    CHECK(std::memcmp(ish::kIshDsmGuidBytes, expectedGuid, 16u) == 0);

    // 2) Verify -tglnodsm skips DsmInitMsg on HbmEnumRes
    {
        ish::IshTransport trNoDsm;
        uint64_t t = 1000000ULL;
        trNoDsm.setDsmConfig(false, 0u);
        CHECK(!trNoDsm.dsmEnabled() && trNoDsm.dsmSupportedMask() == 0u);
        trNoDsm.reset(t);
        trNoDsm.startInit(t);
        drainTx(trNoDsm);
        const uint8_t ackPayload[4] = { 1u, 0u, 0u, 0u };
        trNoDsm.onRxFrame(ish::makeDrbl(ish::kProtoMng, ish::kMngResetNotifyAck, 4u), ackPayload, 4u, t);
        t += 10ULL * ish::IshTransport::kNsPerMs;
        trNoDsm.onTick(t, ish::kFwstsReadyMask, false);
        drainTx(trNoDsm);
        const uint8_t startRes[4] = { ish::kHbmHostStartRes, 1u, 0u, 1u };
        injectIshtpMessage(trNoDsm, 0u, 0u, startRes, sizeof(startRes), t);
        drainTx(trNoDsm);
        ish::HbmEnumRes enumRes {};
        enumRes.cmd = ish::kHbmHostEnumRes;
        enumRes.valid_bits[7 >> 3] |= static_cast<uint8_t>(1u << (7u & 7u));
        injectIshtpMessage(trNoDsm, 0u, 0u, reinterpret_cast<const uint8_t *>(&enumRes), sizeof(enumRes), t);
        auto tx = drainTx(trNoDsm);
        CHECK(tx.size() == 1u && tx[0].data[4] == ish::kHbmHostClientPropsReq);
    }

    // 3) Valid Client 14 sub_cmd=4 (Func 2, 1B) and sub_cmd=2 (Func 3, 9B) + malformed guards + queue cap
    ish::IshTransport tr;
    uint64_t t = 1000000ULL;
    bringTransportToEnumDone(tr, t);

    // sub_cmd=4 -> Func 2, argLen=1
    uint8_t reqF2[13] {};
    ish::writeLe32(reqF2 + 0u, ish::kDsmCmdExec);
    ish::writeLe32(reqF2 + 4u, 0u);
    ish::writeLe32(reqF2 + 8u, ish::kDsmSubFunc2);
    reqF2[12] = 0x02u;
    injectIshtpMessage(tr, ish::kDsmProxyFwAddr, 0u, reqF2, sizeof(reqF2), t);
    CHECK(tr.dsmProxyCount() == 1u);
    CHECK((tr.fixedClientsSeen() & (1u << ish::kDsmProxyFwAddr)) != 0u);
    ish::DsmWorkItem item {};
    CHECK(tr.popPendingDsm(item));
    CHECK(item.valid && item.funcIndex == 2u && item.subCmd == ish::kDsmSubFunc2);
    CHECK(item.argLen == 1u && item.args[0] == 0x02u);

    // sub_cmd=2, 9B payload -> Func 3
    uint8_t reqF3[21] {};
    ish::writeLe32(reqF3 + 0u, ish::kDsmCmdExec);
    ish::writeLe32(reqF3 + 4u, 0u);
    ish::writeLe32(reqF3 + 8u, ish::kDsmSubFunc3);
    for (uint8_t i = 0; i < 9u; ++i) {
        reqF3[12u + i] = static_cast<uint8_t>(0xA0u + i);
    }
    injectIshtpMessage(tr, ish::kDsmProxyFwAddr, 0u, reqF3, sizeof(reqF3), t);
    CHECK(tr.dsmProxyCount() == 2u);
    CHECK(tr.popPendingDsm(item));
    CHECK(item.valid && item.funcIndex == 3u && item.argLen == 9u && item.args[0] == 0xA0u && item.args[8] == 0xA8u);

    // Reject truncated / bad status / unknown sub_cmd cleanly without queueing
    uint8_t badShort[12] {};
    ish::writeLe32(badShort + 0u, ish::kDsmCmdExec);
    ish::writeLe32(badShort + 8u, ish::kDsmSubFunc2);
    injectIshtpMessage(tr, ish::kDsmProxyFwAddr, 0u, badShort, sizeof(badShort), t);
    uint8_t badShortF3[20] {};
    ish::writeLe32(badShortF3 + 0u, ish::kDsmCmdExec);
    ish::writeLe32(badShortF3 + 8u, ish::kDsmSubFunc3);
    injectIshtpMessage(tr, ish::kDsmProxyFwAddr, 0u, badShortF3, sizeof(badShortF3), t);
    uint8_t badStatus[13] {};
    ish::writeLe32(badStatus + 0u, ish::kDsmCmdExec);
    ish::writeLe32(badStatus + 4u, 1u);
    ish::writeLe32(badStatus + 8u, ish::kDsmSubFunc2);
    injectIshtpMessage(tr, ish::kDsmProxyFwAddr, 0u, badStatus, sizeof(badStatus), t);
    uint8_t badSubCmd[16] {};
    ish::writeLe32(badSubCmd + 0u, ish::kDsmCmdExec);
    ish::writeLe32(badSubCmd + 8u, 99u);
    injectIshtpMessage(tr, ish::kDsmProxyFwAddr, 0u, badSubCmd, sizeof(badSubCmd), t);
    CHECK(!tr.popPendingDsm(item));
    CHECK(tr.dsmProxyCount() == 2u);

    // Queue overflow beyond kMaxPendingDsm (8) safely counts dsmDropped()
    for (size_t i = 0; i < ish::kMaxPendingDsm + 3u; ++i) {
        reqF2[12] = static_cast<uint8_t>(i & 0xFFu);
        injectIshtpMessage(tr, ish::kDsmProxyFwAddr, 0u, reqF2, sizeof(reqF2), t);
    }
    CHECK(tr.dsmDropped() == 3u);
    size_t drained = 0;
    while (tr.popPendingDsm(item)) {
        ++drained;
    }
    CHECK(drained == ish::kMaxPendingDsm);
}

static std::vector<uint8_t> buildTunedAlsDescriptor(bool useModSensitivity) {
    std::vector<uint8_t> d;
    auto push = [&](std::initializer_list<uint8_t> bytes) {
        d.insert(d.end(), bytes.begin(), bytes.end());
    };
    push({ 0x05, 0x20, 0x09, 0x41, 0xA1, 0x01, 0x85, 0x03 });
    // Input Illuminance 32-bit Unit=Lux Expo=-2 (0x0A = 2-byte Local Usage!)
    push({ 0x0A, 0xD1, 0x04, 0x15, 0x00, 0x27, 0xFF, 0xFF, 0x00, 0x00, 0x67, 0xE1, 0x00, 0x00, 0x01, 0x55, 0x0E, 0x75, 0x20, 0x95, 0x01, 0x81, 0x02 });
    // Feature Report ID 3:
    //   Power State (8b, 1..6), Report State (8b, 1..6), Report Interval (16b, 10..60000), Sensitivity (16b, 0..10000, Expo=-2 if mod)
    push({ 0x0A, 0x19, 0x03, 0x15, 0x01, 0x25, 0x06, 0x55, 0x00, 0x75, 0x08, 0x95, 0x01, 0xB1, 0x02 });
    push({ 0x0A, 0x16, 0x03, 0x15, 0x01, 0x25, 0x06, 0x75, 0x08, 0x95, 0x01, 0xB1, 0x02 });
    push({ 0x0A, 0x0E, 0x03, 0x15, 0x0A, 0x27, 0x60, 0xEA, 0x00, 0x00, 0x75, 0x10, 0x95, 0x01, 0xB1, 0x02 });
    if (useModSensitivity) {
        // Mod Change Sensitivity Rel Pct (0xE000) | Illuminance (0x04D1) -> 0xE4D1, Expo=-2
        push({ 0x0A, 0xD1, 0xE4, 0x55, 0x0E, 0x15, 0x00, 0x26, 0x10, 0x27, 0x75, 0x10, 0x95, 0x01, 0xB1, 0x02 });
    } else {
        // HID_USAGE_SENSOR_PROP_SENSITIVITY_ABS (0x030F)
        push({ 0x0A, 0x0F, 0x03, 0x55, 0x00, 0x15, 0x00, 0x26, 0x10, 0x27, 0x75, 0x10, 0x95, 0x01, 0xB1, 0x02 });
    }
    push({ 0xC0 });
    return d;
}

static void testAlsSensitivityIntervalAndDarkPermissive() {
    // 1) 0x20030E + 0x20030F parsing & tuning when unset/excessive vs preserving valid values
    {
        auto descBytes = buildTunedAlsDescriptor(false);
        ish::AlsDescriptorInfo als {};
        CHECK(ish::parseAlsReportDescriptor(descBytes.data(), descBytes.size(), als));
        CHECK(als.found);
        CHECK(als.reportInterval.present && als.reportInterval.bitWidth == 16u);
        CHECK(als.sensitivity.present && als.sensitivity.bitWidth == 16u && !als.sensitivityIsPct);
        CHECK(als.featureByteLen == 7u);
        CHECK(als.powerState.present && als.reportState.present);

        // Case A: interval=5000ms (>1000) & sensitivity=5000 (>50) -> tuned to 250ms & 1
        uint8_t featA[7] = { 0x03u, 0x01u, 0x01u, 0x88u, 0x13u, 0x88u, 0x13u };
        uint32_t outIntvl = 0, outSens = 0;
        CHECK(ish::applyAlsFeatureRmw(als, featA, sizeof(featA), &outIntvl, &outSens));
        CHECK(featA[1] == 2u && featA[2] == 2u);
        CHECK(ish::readLe16(featA + 3u) == ish::kDefaultAlsIntervalMs && outIntvl == ish::kDefaultAlsIntervalMs);
        CHECK(ish::readLe16(featA + 5u) == ish::kDefaultAlsSensitivityRaw && outSens == ish::kDefaultAlsSensitivityRaw);
        uint32_t verIntvl = 0, verSens = 0;
        CHECK(ish::verifyAlsFeatureControls(als, featA, sizeof(featA), &verIntvl, &verSens));
        CHECK(verIntvl == ish::kDefaultAlsIntervalMs && verSens == ish::kDefaultAlsSensitivityRaw);

        // Case B: valid interval=100ms & valid sensitivity=5 -> preserved untouched!
        uint8_t featB[7] = { 0x03u, 0x01u, 0x01u, 0x64u, 0x00u, 0x05u, 0x00u };
        outIntvl = 0;
        outSens = 0;
        CHECK(ish::applyAlsFeatureRmw(als, featB, sizeof(featB), &outIntvl, &outSens));
        CHECK(ish::readLe16(featB + 3u) == 100u && outIntvl == 100u);
        CHECK(ish::readLe16(featB + 5u) == 5u && outSens == 5u);
        CHECK(ish::verifyAlsFeatureControls(als, featB, sizeof(featB), &verIntvl, &verSens));
        CHECK(verIntvl == 100u && verSens == 5u);

        // Reject excessive interval / excessive sensitivity in verify, while zero sensitivity is preserved & accepted
        uint8_t featBadIntvl[7] = { 0x03u, 0x02u, 0x02u, 0xD0u, 0x07u, 0x05u, 0x00u }; // 2000ms
        CHECK(!ish::verifyAlsFeatureControls(als, featBadIntvl, sizeof(featBadIntvl)));
        uint8_t featBadSens[7] = { 0x03u, 0x02u, 0x02u, 0xFAu, 0x00u, 0x88u, 0x13u }; // 5000 > 50
        CHECK(!ish::verifyAlsFeatureControls(als, featBadSens, sizeof(featBadSens)));
        uint8_t featZeroSens[7] = { 0x03u, 0x02u, 0x02u, 0xFAu, 0x00u, 0x00u, 0x00u };
        CHECK(ish::applyAlsFeatureRmw(als, featZeroSens, sizeof(featZeroSens), &outIntvl, &outSens));
        CHECK(ish::readLe16(featZeroSens + 5u) == 0u && outSens == 0u);
        verIntvl = 0; verSens = 99;
        CHECK(ish::verifyAlsFeatureControls(als, featZeroSens, sizeof(featZeroSens), &verIntvl, &verSens));
        CHECK(verIntvl == ish::kDefaultAlsIntervalMs && verSens == 0u);

        // Power-only RMW modifies ONLY power & report state, leaving interval/sensitivity untouched
        uint8_t featPwrOnly[7] = { 0x03u, 0x01u, 0x01u, 0x88u, 0x13u, 0x88u, 0x13u };
        CHECK(ish::applyAlsFeaturePowerOnlyRmw(als, featPwrOnly, sizeof(featPwrOnly)));
        CHECK(featPwrOnly[1] == 2u && featPwrOnly[2] == 2u);
        CHECK(ish::readLe16(featPwrOnly + 3u) == 5000u);
        CHECK(ish::readLe16(featPwrOnly + 5u) == 5000u);
    }

    // 2) Modified Usage 0xE4D1 (Rel Pct Exp=-2) preserves 0, tunes excessive (>1000) to 100 (1.00%), and Push/Pop keeps Sensor usage page
    {
        auto descBytes = buildTunedAlsDescriptor(true);
        ish::AlsDescriptorInfo als {};
        CHECK(ish::parseAlsReportDescriptor(descBytes.data(), descBytes.size(), als));
        CHECK(als.sensitivity.present && als.sensitivityIsPct);
        CHECK(ish::decodeUnitExponent(als.sensitivity.unitExpoRaw) == -2);
        uint8_t featZero[7] = { 0x03u, 0x01u, 0x01u, 0x00u, 0x00u, 0x00u, 0x00u };
        uint32_t outIntvl = 0, outSens = 99;
        CHECK(ish::applyAlsFeatureRmw(als, featZero, sizeof(featZero), &outIntvl, &outSens));
        CHECK(outIntvl == ish::kDefaultAlsIntervalMs);
        CHECK(outSens == 0u);
        CHECK(ish::readLe16(featZero + 5u) == 0u);
        CHECK(ish::verifyAlsFeatureControls(als, featZero, sizeof(featZero)));

        uint8_t featExcess[7] = { 0x03u, 0x01u, 0x01u, 0x00u, 0x00u, 0x88u, 0x13u }; // 5000 > 1000
        CHECK(ish::applyAlsFeatureRmw(als, featExcess, sizeof(featExcess), &outIntvl, &outSens));
        CHECK(outSens == 100u);
        CHECK(ish::readLe16(featExcess + 5u) == 100u);
        CHECK(ish::verifyAlsFeatureControls(als, featExcess, sizeof(featExcess)));
    }

    // 3) Clamping when descriptor Logical Maximum < 250ms (e.g., 10..150ms)
    {
        ish::HidBitField f {};
        f.present = true;
        f.bitWidth = 8u;
        f.logicalMin = 10;
        f.logicalMax = 150;
        CHECK(ish::clampFieldTarget(f, 250u) == 150u);
        CHECK(ish::clampFieldTarget(f, 1u) == 10u);
        f.logicalMin = 0;
        f.logicalMax = 1000;
        CHECK(ish::clampFieldTarget(f, 250u) == 250u);
    }

    // 4) Full state machine telemetry verification (FixedClientsSeen + ALSIntervalMs + ALSSensitivity + ALSDarkPermissive)
    {
        ish::IshTransport tr;
        uint64_t t = 1000000ULL;
        bringTransportToStreaming(tr, t, 1732000000000000ULL, 10000ULL);
        CHECK(tr.fixedClientsSeen() == 0u);
        CHECK(tr.isAlsDarkPermissive());
        uint8_t brightIn[6] = { 0x03u, 0x00u, 0x50u, 0xC3u, 0x00u, 0x00u }; // raw 50000 -> 500.00 lux
        auto pub = makeHostifMsg(ish::kHostifPublishInputReport, 17u, 0u, brightIn, sizeof(brightIn));
        injectIshtpMessage(tr, 7u, 1u, pub.data(), pub.size(), t);
        CHECK(tr.milliLux() == 500000ULL);
        CHECK(!tr.isAlsDarkPermissive());

        ish::SysStateSubscribe sub {};
        ish::writeLe32(reinterpret_cast<uint8_t *>(&sub.cmd), ish::kSysStateSubscribeCmd);
        ish::writeLe32(reinterpret_cast<uint8_t *>(&sub.states), ish::kSysStateAllSupported);
        injectIshtpMessage(tr, ish::kSysStateFwAddr, 0u, reinterpret_cast<const uint8_t *>(&sub), sizeof(sub), t);
        uint8_t reqF2[13] {};
        ish::writeLe32(reqF2 + 0u, ish::kDsmCmdExec);
        ish::writeLe32(reqF2 + 8u, ish::kDsmSubFunc2);
        reqF2[12] = 0u;
        injectIshtpMessage(tr, ish::kDsmProxyFwAddr, 0u, reqF2, sizeof(reqF2), t);
        CHECK(tr.fixedClientsSeen() == ((1u << ish::kSysStateFwAddr) | (1u << ish::kDsmProxyFwAddr)));
    }

    // 5) Dark permissive threshold boundary checks
    CHECK(!ish::isAlsDarkPermissive(false, 0ULL));
    CHECK(ish::isAlsDarkPermissive(true, 0ULL));
    CHECK(ish::isAlsDarkPermissive(true, ish::kDefaultAlsDarkThresholdMLux));
    CHECK(!ish::isAlsDarkPermissive(true, ish::kDefaultAlsDarkThresholdMLux + 1ULL));
}

static void bringToAlsFeatGet(ish::IshTransport &tr, uint64_t &t) {
    t = 1000000ULL;
    tr.startInit(t);
    drainTx(tr);

    t += 5ULL * ish::IshTransport::kNsPerMs;
    ish::MngResetPayload ack { 1u, 0u };
    tr.onRxFrame(ish::makeDrbl(ish::kProtoMng, ish::kMngResetNotifyAck, sizeof(ack)),
                 reinterpret_cast<const uint8_t *>(&ack), sizeof(ack), t);
    t += 5ULL * ish::IshTransport::kNsPerMs;
    tr.onTick(t, ish::kFwstsReadyMask, false, 1732000000000000ULL, 10000ULL);
    drainTx(tr);

    const uint8_t hbmVer[4] = { ish::kHbmHostStartRes, 1u, 0u, 1u };
    injectIshtpMessage(tr, 0u, 0u, hbmVer, sizeof(hbmVer), t);
    drainTx(tr);

    uint8_t enumRes[36] {};
    enumRes[0] = ish::kHbmHostEnumRes;
    enumRes[4 + 0] = (1u << 7);
    injectIshtpMessage(tr, 0u, 0u, enumRes, sizeof(enumRes), t);
    drainTx(tr);

    ish::HbmPropsRes propsHid {};
    propsHid.cmd = ish::kHbmHostClientPropsRes;
    propsHid.addr = 7u;
    propsHid.status = 0u;
    std::memcpy(propsHid.props.guid, ish::kIshHidClientGuid, 16u);
    ish::writeLe32(reinterpret_cast<uint8_t *>(&propsHid.props.max_msg_length), 4096u);
    injectIshtpMessage(tr, 0u, 0u, reinterpret_cast<const uint8_t *>(&propsHid), sizeof(propsHid), t);
    drainTx(tr);

    const uint8_t connRes[4] = { ish::kHbmClientConnectRes, 7u, 1u, 0u };
    injectIshtpMessage(tr, 0u, 0u, connRes, sizeof(connRes), t);
    drainTx(tr);

    injectFwFlowControl(tr, 7u, 1u, t);
    drainTx(tr);

    ish::HidDeviceInfo dev {};
    dev.dev_id = 0u;
    auto dmPayload = makeDmEnumPayload(&dev, 1u);
    auto enumRsp = makeHostifMsg(ish::kHostifDmEnumDevices | ish::kHostifIsResponse, 0x0Fu, 0u,
                                 dmPayload.data(), dmPayload.size());
    injectFwFlowControl(tr, 7u, 1u, t);
    injectIshtpMessage(tr, 7u, 1u, enumRsp.data(), enumRsp.size(), t);
    drainTx(tr);

    injectFwFlowControl(tr, 7u, 1u, t);
    const uint8_t hidDescBytes[9] = { 9, 0x21, 0x11, 0x01, 0, 1, 0x22, 100, 0 };
    auto hidRsp = makeHostifMsg(ish::kHostifGetHidDescriptor | ish::kHostifIsResponse, 0u, 0u, hidDescBytes, sizeof(hidDescBytes));
    injectIshtpMessage(tr, 7u, 1u, hidRsp.data(), hidRsp.size(), t);
    drainTx(tr);

    auto alsDesc = buildTunedAlsDescriptor(false);
    auto rptRsp = makeHostifMsg(ish::kHostifGetReportDescriptor | ish::kHostifIsResponse, 0u, 0u,
                                alsDesc.data(), alsDesc.size());
    injectFwFlowControl(tr, 7u, 1u, t);
    injectIshtpMessage(tr, 7u, 1u, rptRsp.data(), rptRsp.size(), t);
    drainTx(tr);
    CHECK(tr.stage() == ish::IshTransport::Stage::AlsFeatGet);
}

static void testFeatureFallbacksAndHdrSize() {
    // A) SET_FEATURE_REPORT failure triggers one power-only retry preserving firmware interval/sensitivity
    {
        ish::IshTransport tr;
        uint64_t t = 0;
        bringToAlsFeatGet(tr, t);

        uint8_t origFeat[7] = { 0x03u, 0x01u, 0x01u, 0xB8u, 0x0Bu, 0x88u, 0x13u }; // 3000ms, 5000
        auto fgRsp = makeHostifMsg(ish::kHostifGetFeatureReport | ish::kHostifIsResponse, 0u, 0u, origFeat, sizeof(origFeat));
        injectFwFlowControl(tr, 7u, 1u, t);
        injectIshtpMessage(tr, 7u, 1u, fgRsp.data(), fgRsp.size(), t);
        CHECK(tr.stage() == ish::IshTransport::Stage::AlsFeatSet);
        CHECK(tr.origFeatLen() == sizeof(origFeat));
        auto tx = drainTx(tr);
        CHECK(tx.size() == 2u && tx[1].data[4] == ish::kHostifSetFeatureReport);
        CHECK(ish::readLe16(tx[1].data + 4 + 4) == sizeof(origFeat));

        // Firmware rejects first SET_FEATURE -> driver retries power-only preserving 3000ms & 5000!
        auto fsErr = makeHostifMsg(ish::kHostifSetFeatureReport | ish::kHostifIsResponse, 0u, 1u, nullptr, 0u);
        injectFwFlowControl(tr, 7u, 1u, t);
        injectIshtpMessage(tr, 7u, 1u, fsErr.data(), fsErr.size(), t);
        CHECK(tr.stage() == ish::IshTransport::Stage::AlsFeatSet);
        tx = drainTx(tr);
        CHECK(tx.size() == 2u && tx[1].data[4] == ish::kHostifSetFeatureReport);
        CHECK(ish::readLe16(tx[1].data + 4 + 4) == sizeof(origFeat));
        const uint8_t *retryFeat = tx[1].data + 4 + sizeof(ish::HostifMsgHdr);
        CHECK(retryFeat[1] == 2u && retryFeat[2] == 2u);
        CHECK(ish::readLe16(retryFeat + 3u) == 3000u);
        CHECK(ish::readLe16(retryFeat + 5u) == 5000u);

        // Retry succeeds!
        auto fsOk = makeHostifMsg(ish::kHostifSetFeatureReport | ish::kHostifIsResponse, 0u, 0u, nullptr, 0u);
        injectFwFlowControl(tr, 7u, 1u, t);
        injectIshtpMessage(tr, 7u, 1u, fsOk.data(), fsOk.size(), t);
        CHECK(tr.stage() == ish::IshTransport::Stage::AlsFeatVerify);
        drainTx(tr);

        uint8_t verFeat[7] = { 0x03u, 0x02u, 0x02u, 0xFAu, 0x00u, 0x00u, 0x00u };
        auto fvRsp = makeHostifMsg(ish::kHostifGetFeatureReport | ish::kHostifIsResponse, 0u, 0u, verFeat, sizeof(verFeat));
        injectFwFlowControl(tr, 7u, 1u, t);
        injectIshtpMessage(tr, 7u, 1u, fvRsp.data(), fvRsp.size(), t);
        CHECK(tr.alsControlsVerified());
        CHECK(tr.stage() == ish::IshTransport::Stage::AlsPrimeInput);
    }

    // B) 4 GET_FEATURE_REPORT empty rejections spaced by kFeatRetryDelayNs alternate hdr.size=1/0/1/0,
    //    then fall back cleanly to AlsPrimeInput -> Streaming while preserving featGet* telemetry!
    {
        ish::IshTransport tr;
        uint64_t t = 0;
        bringToAlsFeatGet(tr, t);

        auto fgErr = makeHostifMsg(ish::kHostifGetFeatureReport | ish::kHostifIsResponse, 0u, 1u, nullptr, 0u);
        for (int attempt = 1; attempt <= 3; ++attempt) {
            injectFwFlowControl(tr, 7u, 1u, t);
            injectIshtpMessage(tr, 7u, 1u, fgErr.data(), fgErr.size(), t);
            drainTx(tr);
            CHECK(tr.stage() == ish::IshTransport::Stage::AlsFeatGet);
            CHECK(tr.featGetAttempts() == static_cast<uint8_t>(attempt));
            t += ish::IshTransport::kFeatRetryDelayNs;
            tr.onTick(t, ish::kFwstsReadyMask, false, 1732000000000000ULL, 10000ULL);
            auto tx = drainTx(tr);
            CHECK(tx.size() == 1u && tx[0].data[4] == ish::kHostifGetFeatureReport);
            const uint16_t expectedWireSize = ((attempt % 2) == 1) ? 0u : 1u;
            CHECK(ish::readLe16(tx[0].data + 4 + 4) == expectedWireSize);
            CHECK(tx[0].data[4 + 6] == 0x03u);
        }

        injectFwFlowControl(tr, 7u, 1u, t);
        injectIshtpMessage(tr, 7u, 1u, fgErr.data(), fgErr.size(), t);
        CHECK(tr.stage() == ish::IshTransport::Stage::AlsPrimeInput);
        CHECK(!tr.alsControlsVerified());
        CHECK(tr.featGetAttempts() == 4u);
        CHECK(tr.featGetStatus() == 1u);
        CHECK(tr.featGetDeclaredSize() == 0u);
        CHECK(tr.lastHostifCmd() == ish::kHostifGetFeatureReport);
        CHECK(tr.lastHostifStatus() == 1u);
        CHECK(std::strcmp(tr.featureError(), "GET_FEATURE_REPORT rejected after retries; polling input directly") == 0);
        auto tx = drainTx(tr);
        CHECK(tx.size() == 2u && tx[1].data[4] == ish::kHostifGetInputReport);
        CHECK(ish::readLe16(tx[1].data + 4 + 4) == 1u);

        uint8_t primeIn[5] = { 0x03u, 0x20u, 0x4Eu, 0x00u, 0x00u }; // raw 20000 -> 200.00 lux
        auto giRsp = makeHostifMsg(ish::kHostifGetInputReport | ish::kHostifIsResponse, 0u, 0u, primeIn, sizeof(primeIn));
        injectIshtpMessage(tr, 7u, 1u, giRsp.data(), giRsp.size(), t);
        CHECK(tr.stage() == ish::IshTransport::Stage::Streaming);
        CHECK(tr.consumeSampleUpdated());
        CHECK(tr.milliLux() == 200000ULL);
        CHECK(tr.lastHostifCmd() == ish::kHostifGetInputReport);
        CHECK(tr.featGetStatus() == 1u);
        CHECK(tr.featGetDeclaredSize() == 0u);
    }

    // C) Timeout during AlsFeatGet falls back to AlsPrimeInput rather than Failed
    {
        ish::IshTransport tr;
        uint64_t t = 0;
        bringToAlsFeatGet(tr, t);
        t += ish::IshTransport::kHidStageTimeoutNs + 1ULL;
        tr.onTick(t, ish::kFwstsReadyMask, false, 1732000000000000ULL, 10000ULL);
        CHECK(tr.stage() == ish::IshTransport::Stage::AlsPrimeInput);
        CHECK(std::strcmp(tr.featureError(), "timeout in AlsFeatGet") == 0);
    }
}

static std::vector<uint8_t> buildHp317AlsDescriptor() {
    // Models HP 8716 Report ID 6: 317-byte Feature report + 31-byte Input report (expo=-3 millilux).
    std::vector<uint8_t> d;
    u8item(d, 0x04, 0x20);     // Usage Page (Sensor)
    u8item(d, 0x08, 0x41);     // Usage (ALS)
    u8item(d, 0xA0, 0x01);     // Collection (Application) -> alsCollectionByteOffset == 4
    u8item(d, 0x84, 0x06);     //   Report ID (6)

    //   Feature report = 1 (ID) + 1 (Power) + 1 (Reporting) + 4 (Interval) + 2 (Sensitivity) + 308 (Table) = 317 bytes
    u16item(d, 0x08, 0x0319);  //   Power State (8b, 1..6)
    u8item(d, 0xA0, 0x02);
    u8item(d, 0x14, 1);
    u8item(d, 0x24, 6);
    u8item(d, 0x54, 0);
    u8item(d, 0x74, 8);
    u8item(d, 0x94, 1);
    u16item(d, 0x08, 0x0850);
    u16item(d, 0x08, 0x0851);
    u8item(d, 0xB0, 0x00);
    zitem(d, 0xC0);

    u16item(d, 0x08, 0x0316);  //   Reporting State (8b, 1..6)
    u8item(d, 0xA0, 0x02);
    u8item(d, 0x14, 1);
    u8item(d, 0x24, 6);
    u8item(d, 0x74, 8);
    u8item(d, 0x94, 1);
    u16item(d, 0x08, 0x0840);
    u16item(d, 0x08, 0x0841);
    u8item(d, 0xB0, 0x00);
    zitem(d, 0xC0);

    u16item(d, 0x08, 0x030E);  //   Report Interval (32b)
    u8item(d, 0x14, 0);
    u32item(d, 0x24, 0x7FFFFFFFu);
    u8item(d, 0x74, 32);
    u8item(d, 0x94, 1);
    u8item(d, 0xB0, 0x02);

    u16item(d, 0x08, 0xE4D1);  //   Rel Sensitivity Pct (16b, Expo=-2)
    u8item(d, 0x54, 0x0E);
    u8item(d, 0x14, 0);
    u16item(d, 0x24, 10000);
    u8item(d, 0x74, 16);
    u8item(d, 0x94, 1);
    u8item(d, 0xB0, 0x02);

    u16item(d, 0x08, 0x0318);  //   Response Curve / custom 308B (16b * 154)
    u8item(d, 0x54, 0x00);
    u8item(d, 0x74, 16);
    u8item(d, 0x94, 154);
    u8item(d, 0xB0, 0x02);

    //   Input report = 1 (ID) + 26 (Padding/other) + 4 (Illum) = 31 bytes
    u8item(d, 0x74, 8);
    u8item(d, 0x94, 26);
    u8item(d, 0x80, 0x01);     //   Const 26 bytes
    u16item(d, 0x08, 0x04D1);  //   Illuminance (32b, Unit=Lux(1), Expo=-3 [0xD])
    u8item(d, 0x64, 0x01);
    u8item(d, 0x54, 0x0D);
    u8item(d, 0x14, 0);
    u32item(d, 0x24, 0x7FFFFFFFu);
    u8item(d, 0x74, 32);
    u8item(d, 0x94, 1);
    u8item(d, 0x80, 0x02);

    zitem(d, 0xC0);            // End Collection (ALS)
    return d;
}

static void bringTo317FeatureGet(ish::IshTransport &tr, const std::vector<uint8_t> &alsDesc, uint64_t &t) {
    t = 1000000ULL;
    tr.startInit(t);
    drainTx(tr);

    t += 5ULL * ish::IshTransport::kNsPerMs;
    ish::MngResetPayload ack { 1u, 0u };
    tr.onRxFrame(ish::makeDrbl(ish::kProtoMng, ish::kMngResetNotifyAck, sizeof(ack)),
                 reinterpret_cast<const uint8_t *>(&ack), sizeof(ack), t);
    t += 5ULL * ish::IshTransport::kNsPerMs;
    tr.onTick(t, ish::kFwstsReadyMask, false, 1732000000000000ULL, 10000ULL);
    drainTx(tr);

    const uint8_t hbmVer[4] = { ish::kHbmHostStartRes, 1u, 0u, 1u };
    injectIshtpMessage(tr, 0u, 0u, hbmVer, sizeof(hbmVer), t);
    drainTx(tr);

    uint8_t enumRes[36] {};
    enumRes[0] = ish::kHbmHostEnumRes;
    enumRes[4 + 0] = (1u << 3);
    injectIshtpMessage(tr, 0u, 0u, enumRes, sizeof(enumRes), t);
    drainTx(tr);

    ish::HbmPropsRes propsHid {};
    propsHid.cmd = ish::kHbmHostClientPropsRes;
    propsHid.addr = 3u;
    propsHid.status = 0u;
    std::memcpy(propsHid.props.guid, ish::kIshHidClientGuid, 16u);
    ish::writeLe32(reinterpret_cast<uint8_t *>(&propsHid.props.max_msg_length), 4096u);
    injectIshtpMessage(tr, 0u, 0u, reinterpret_cast<const uint8_t *>(&propsHid), sizeof(propsHid), t);
    drainTx(tr);

    const uint8_t connRes[4] = { ish::kHbmClientConnectRes, 3u, 1u, 0u };
    injectIshtpMessage(tr, 0u, 0u, connRes, sizeof(connRes), t);
    drainTx(tr);

    injectFwFlowControl(tr, 3u, 1u, t);
    drainTx(tr);

    ish::HidDeviceInfo dev {};
    dev.dev_id = 0u;
    auto dmPayload = makeDmEnumPayload(&dev, 1u);
    auto enumRsp = makeHostifMsg(ish::kHostifDmEnumDevices | ish::kHostifIsResponse, 0x0Fu, 0u,
                                 dmPayload.data(), dmPayload.size());
    injectFwFlowControl(tr, 3u, 1u, t);
    injectIshtpMessage(tr, 3u, 1u, enumRsp.data(), enumRsp.size(), t);
    drainTx(tr);

    injectFwFlowControl(tr, 3u, 1u, t);
    const uint8_t hidDescBytes[9] = { 9, 0x21, 0x11, 0x01, 0, 1, 0x22, static_cast<uint8_t>(alsDesc.size() & 0xFFu), 0 };
    auto hidRsp = makeHostifMsg(ish::kHostifGetHidDescriptor | ish::kHostifIsResponse, 0u, 0u, hidDescBytes, sizeof(hidDescBytes));
    injectIshtpMessage(tr, 3u, 1u, hidRsp.data(), hidRsp.size(), t);
    drainTx(tr);

    auto rptRsp = makeHostifMsg(ish::kHostifGetReportDescriptor | ish::kHostifIsResponse, 0u, 0u,
                                alsDesc.data(), alsDesc.size());
    injectFwFlowControl(tr, 3u, 1u, t);
    injectIshtpMessage(tr, 3u, 1u, rptRsp.data(), rptRsp.size(), t);
    drainTx(tr);
    CHECK(tr.stage() == ish::IshTransport::Stage::AlsFeatGet);
}

static std::vector<uint8_t> reassembleHidFrames(const std::vector<ish::TxFrame> &frames, size_t startIdx) {
    std::vector<uint8_t> sdu;
    for (size_t i = startIdx; i < frames.size(); ++i) {
        uint8_t fw = 0, host = 0;
        uint16_t flen = 0;
        bool comp = false;
        ish::parseIshtpHdrWord(ish::readLe32(frames[i].data), fw, host, flen, comp);
        sdu.insert(sdu.end(), frames[i].data + 4, frames[i].data + 4 + flen);
    }
    return sdu;
}

static void testPhase51Hp317FeatureAndRecovery() {
    auto desc317 = buildHp317AlsDescriptor();
    {
        ish::AlsDescriptorInfo info {};
        CHECK(ish::parseAlsReportDescriptor(desc317.data(), desc317.size(), info));
        CHECK(info.found);
        CHECK(info.featureReportId == 6u && info.featureByteLen == 317u);
        CHECK(info.inputReportId == 6u && info.inputByteLen == 31u);
        CHECK(ish::decodeUnitExponent(info.unitExpoRaw) == -3);
        CHECK(info.alsCollectionByteOffset == 4u);
        CHECK(info.alsCollectionByteLen == desc317.size() - 4u);
    }

    // 1) 317-byte Feature report accepted even with non-zero hdr.status == 1; 323B SET_FEATURE splits across 3 ISHTP frags!
    {
        ish::IshTransport tr;
        uint64_t t = 0;
        bringTo317FeatureGet(tr, desc317, t);
        CHECK(tr.alsDescSliceLen() == desc317.size() - 4u);

        std::vector<uint8_t> origFeat(317u, 0u);
        origFeat[0] = 6u;       // Report ID
        origFeat[1] = 1u;       // Power off/init -> RMW sets 2 (D0)
        origFeat[2] = 1u;       // No events -> RMW sets 2 (All Events)
        ish::writeLe32(&origFeat[3], 5000u); // Interval -> RMW tunes to 250ms
        ish::writeLe16(&origFeat[7], 500u);  // Sensitivity 5.00% <= 10% -> preserved
        origFeat[9] = 0x5Au;    // Curve payload marker must be preserved
        origFeat[316] = 0xA5u;

        auto fgRsp = makeHostifMsg(ish::kHostifGetFeatureReport | ish::kHostifIsResponse, 0u, 1u,
                                   origFeat.data(), origFeat.size());
        injectFwFlowControl(tr, 3u, 1u, t);
        injectIshtpMessage(tr, 3u, 1u, fgRsp.data(), fgRsp.size(), t);
        CHECK(tr.stage() == ish::IshTransport::Stage::AlsFeatSet);
        CHECK(tr.featGetStatus() == 1u);
        CHECK(tr.featGetDeclaredSize() == 317u);
        CHECK(tr.origFeatLen() == 317u);
        CHECK(tr.reqFeatLen() == 317u);

        auto tx = drainTx(tr);
        // tx[0] = RX flow control, tx[1..3] = 3 ISHTP fragments (124 + 124 + 75 = 323B = 6B HostifMsgHdr + 317B!)
        CHECK(tx.size() == 4u);
        CHECK(tx[0].data[4] == ish::kHbmFlowControl);
        auto setSdu = reassembleHidFrames(tx, 1u);
        CHECK(setSdu.size() == 323u);
        CHECK(setSdu[0] == ish::kHostifSetFeatureReport && setSdu[1] == 0u);
        CHECK(ish::readLe16(&setSdu[4]) == 317u);
        CHECK(setSdu[6] == 6u && setSdu[7] == 2u && setSdu[8] == 2u);
        CHECK(ish::readLe32(&setSdu[9]) == ish::kDefaultAlsIntervalMs);
        CHECK(ish::readLe16(&setSdu[13]) == 500u);
        CHECK(setSdu[15] == 0x5Au && setSdu[322] == 0xA5u);

        // Complete SET -> VERIFY (non-zero status still parsed cleanly) -> PRIME -> STREAMING
        auto fsRsp = makeHostifMsg(ish::kHostifSetFeatureReport | ish::kHostifIsResponse, 0u, 0u, nullptr, 0u);
        injectFwFlowControl(tr, 3u, 1u, t);
        injectIshtpMessage(tr, 3u, 1u, fsRsp.data(), fsRsp.size(), t);
        CHECK(tr.stage() == ish::IshTransport::Stage::AlsFeatVerify);
        drainTx(tr);

        std::vector<uint8_t> verFeat(setSdu.begin() + 6u, setSdu.end());
        auto fvRsp = makeHostifMsg(ish::kHostifGetFeatureReport | ish::kHostifIsResponse, 0u, 1u,
                                   verFeat.data(), verFeat.size());
        injectFwFlowControl(tr, 3u, 1u, t);
        injectIshtpMessage(tr, 3u, 1u, fvRsp.data(), fvRsp.size(), t);
        CHECK(tr.alsControlsVerified());
        CHECK(tr.curFeatLen() == 317u);
        CHECK(tr.stage() == ish::IshTransport::Stage::AlsPrimeInput);
        drainTx(tr);

        // Input report 31B -> live transitions 47122 -> 0 -> 500000
        std::vector<uint8_t> inRpt(31u, 0u);
        inRpt[0] = 6u;
        ish::writeLe32(&inRpt[27], 47122u);
        auto giRsp = makeHostifMsg(ish::kHostifGetInputReport | ish::kHostifIsResponse, 0u, 0u, inRpt.data(), inRpt.size());
        injectIshtpMessage(tr, 3u, 1u, giRsp.data(), giRsp.size(), t);
        CHECK(tr.stage() == ish::IshTransport::Stage::Streaming);
        CHECK(tr.consumeSampleUpdated());
        CHECK(tr.milliLux() == 47122ULL);

        ish::writeLe32(&inRpt[27], 0u);
        auto darkPub = makeHostifMsg(ish::kHostifPublishInputReport, 0u, 0u, inRpt.data(), inRpt.size());
        injectIshtpMessage(tr, 3u, 1u, darkPub.data(), darkPub.size(), t);
        CHECK(tr.consumeSampleUpdated());
        CHECK(tr.milliLux() == 0ULL);

        ish::writeLe32(&inRpt[27], 500000u);
        auto brightPub = makeHostifMsg(ish::kHostifPublishInputReport, 0u, 0u, inRpt.data(), inRpt.size());
        injectIshtpMessage(tr, 3u, 1u, brightPub.data(), brightPub.size(), t);
        CHECK(tr.consumeSampleUpdated());
        CHECK(tr.milliLux() == 500000ULL);
    }

    // 2) Retry recovery: Attempt 1 empty rejection -> 300ms tick flips hdr.size=0 -> Attempt 2 succeeds!
    //    AND verify SET_FEATURE non-zero status still runs AlsFeatVerify with strictTuning=false!
    {
        ish::IshTransport tr;
        uint64_t t = 0;
        bringTo317FeatureGet(tr, desc317, t);

        auto fgErr = makeHostifMsg(ish::kHostifGetFeatureReport | ish::kHostifIsResponse, 0u, 2u, nullptr, 0u);
        injectFwFlowControl(tr, 3u, 1u, t);
        injectIshtpMessage(tr, 3u, 1u, fgErr.data(), fgErr.size(), t);
        drainTx(tr);
        CHECK(tr.stage() == ish::IshTransport::Stage::AlsFeatGet);
        CHECK(tr.featUseZeroHdrSize());

        t += ish::IshTransport::kFeatRetryDelayNs;
        tr.onTick(t, ish::kFwstsReadyMask, false, 1732000000000000ULL, 10000ULL);
        auto tx = drainTx(tr);
        CHECK(tx.size() == 1u && tx[0].data[4] == ish::kHostifGetFeatureReport);
        CHECK(ish::readLe16(tx[0].data + 4 + 4) == 0u); // Attempt 2 uses hdr.size=0!
        CHECK(tr.featGetAttempts() == 2u);

        std::vector<uint8_t> origFeat(317u, 0u);
        origFeat[0] = 6u;
        origFeat[1] = 1u;
        origFeat[2] = 1u;
        ish::writeLe32(&origFeat[3], 5000u);
        ish::writeLe16(&origFeat[7], 5000u);
        auto fgOk = makeHostifMsg(ish::kHostifGetFeatureReport | ish::kHostifIsResponse, 0u, 0u,
                                  origFeat.data(), origFeat.size());
        injectFwFlowControl(tr, 3u, 1u, t);
        injectIshtpMessage(tr, 3u, 1u, fgOk.data(), fgOk.size(), t);
        CHECK(tr.stage() == ish::IshTransport::Stage::AlsFeatSet);
        tx = drainTx(tr);
        auto setSdu1 = reassembleHidFrames(tx, 1u);
        CHECK(ish::readLe16(&setSdu1[4]) == 0u); // SET_FEATURE matches Attempt 2 zero hdr.size=0!

        // Simulate SET_FEATURE non-zero status 3 times (tuned -> power-only -> non-zero hdr retry -> fall through to AlsFeatVerify)
        auto fsErr = makeHostifMsg(ish::kHostifSetFeatureReport | ish::kHostifIsResponse, 0u, 1u, nullptr, 0u);
        injectFwFlowControl(tr, 3u, 1u, t);
        injectIshtpMessage(tr, 3u, 1u, fsErr.data(), fsErr.size(), t); // triggers power-only retry
        drainTx(tr);
        injectFwFlowControl(tr, 3u, 1u, t);
        injectIshtpMessage(tr, 3u, 1u, fsErr.data(), fsErr.size(), t); // triggers hdr.size=317 retry
        tx = drainTx(tr);
        auto setSduRetry = reassembleHidFrames(tx, 1u);
        CHECK(ish::readLe16(&setSduRetry[4]) == 317u);

        // 3rd SET_FEATURE error still transitions to AlsFeatVerify!
        injectFwFlowControl(tr, 3u, 1u, t);
        injectIshtpMessage(tr, 3u, 1u, fsErr.data(), fsErr.size(), t);
        CHECK(tr.stage() == ish::IshTransport::Stage::AlsFeatVerify);
        tx = drainTx(tr);
        CHECK(tx.size() == 2u && tx[1].data[4] == ish::kHostifGetFeatureReport);
        CHECK(ish::readLe16(tx[1].data + 4 + 4) == 0u); // Verify GET_FEATURE keeps working zeroHdr mode!

        // FW actually enabled Power=D0 & Reporting=AllEvents (keeping interval=0, sensitivity=5000) -> Verified!
        std::vector<uint8_t> readback(317u, 0u);
        readback[0] = 6u;
        readback[1] = 2u;
        readback[2] = 2u;
        ish::writeLe32(&readback[3], 0u);
        ish::writeLe16(&readback[7], 5000u);
        auto fvRsp = makeHostifMsg(ish::kHostifGetFeatureReport | ish::kHostifIsResponse, 0u, 0u,
                                   readback.data(), readback.size());
        injectFwFlowControl(tr, 3u, 1u, t);
        injectIshtpMessage(tr, 3u, 1u, fvRsp.data(), fvRsp.size(), t);
        CHECK(tr.alsControlsVerified());
        CHECK(tr.featureError()[0] == '\0');
        CHECK(tr.stage() == ish::IshTransport::Stage::AlsPrimeInput);
    }
}

static void testPhase52PimrFlowAndKeepalive() {
    // 1) PIMR bit 11 preservation & PISR bit 8 constant
    CHECK(ish::kPisrHost2IshBusyClrBit == (1u << 8));
    CHECK(ish::computeInitPimr(0x00000800u) == 0x00000801u);
    CHECK(ish::computeInitPimr(0x00000900u) == 0x00000801u);
    CHECK(ish::computeInitPimr(0x00000801u) == 0x00000801u);
    CHECK(ish::computeInitPimr(0x00000100u) == 0x00000001u);

    // 2) rxFlowControlPending_ recovery, counters, keepalive cadence/guards, and needHostReady on MNG_RESET_NOTIFY
    ish::IshTransport tr;
    uint64_t t = 1000000ULL;
    const uint64_t utc0 = 1732000000000000ULL;
    const uint64_t mono0 = 10000ULL;
    bringTransportToStreaming(tr, t, utc0, mono0);
    CHECK(tr.stage() == ish::IshTransport::Stage::Streaming);
    CHECK(tr.alsControlsVerified());
    CHECK(tr.getInputRespCount() == 1u);
    CHECK(tr.publishReportCount() == 0u);
    CHECK(!tr.rxFlowControlPending());
    CHECK(!tr.consumeNeedHostReady());

    // Verify publish report + rxFlowControlPending_ recovery when tx_ is full!
    const uint32_t fcBeforeFull = tr.flowCreditsSent();
    while (tr.txPendingCount() < ish::kTxQueueCapacity) {
        CHECK(tr.enqueueMng(ish::kMngSyncFwClock, nullptr, 0u));
    }
    CHECK(tr.txPendingCount() == ish::kTxQueueCapacity);

    uint8_t pubIn[6] = { 0x03u, 0x00u, 0xE8u, 0x03u, 0x00u, 0x00u };
    auto pubMsg = makeHostifMsg(ish::kHostifPublishInputReport, 17u, 0u, pubIn, sizeof(pubIn));
    injectIshtpMessage(tr, 7u, 1u, pubMsg.data(), pubMsg.size(), t);
    CHECK(tr.publishReportCount() == 1u);
    CHECK(tr.rxFlowControlPending());
    CHECK(tr.flowCreditsSent() == fcBeforeFull);
    CHECK(tr.consumeSampleUpdated());

    // Drain tx_, then onTick() immediately recovers and sends the deferred kHbmFlowControl credit!
    drainTx(tr);
    CHECK(tr.txPendingCount() == 0u);
    tr.onTick(t, ish::kFwstsReadyMask, false, utc0, mono0);
    CHECK(!tr.rxFlowControlPending());
    CHECK(tr.flowCreditsSent() == fcBeforeFull + 1u);
    auto fcTx = drainTx(tr);
    CHECK(fcTx.size() == 1u && fcTx[0].proto == ish::kProtoIshtp && fcTx[0].data[4] == ish::kHbmFlowControl);

    // 3) Streaming keepalive cadence & credit/host2IshBusy guards
    CHECK(tr.hidTxCredits() == 0u);
    tr.onTick(t + 1000ULL * ish::IshTransport::kNsPerMs, ish::kFwstsReadyMask, false, utc0, mono0);
    CHECK(!tr.hidTxPending());
    CHECK(drainTx(tr).empty());

    tr.onTick(t + 4900ULL * ish::IshTransport::kNsPerMs, ish::kFwstsReadyMask, false, utc0, mono0);
    CHECK(!tr.hidTxPending());
    CHECK(drainTx(tr).empty());

    // At +5.0s idle with hidTxCredits == 0 -> NO GET_INPUT_REPORT and hidTxPending remains false
    t += 5000ULL * ish::IshTransport::kNsPerMs;
    tr.onTick(t, ish::kFwstsReadyMask, false, utc0, mono0);
    CHECK(!tr.hidTxPending());
    CHECK(drainTx(tr).empty());

    // Grant 1 credit -> increments hidFlowCtrlRxCount() and hidTxCredits() == 1
    const uint32_t fcRxBefore = tr.hidFlowCtrlRxCount();
    injectFwFlowControl(tr, 7u, 1u, t);
    CHECK(tr.hidFlowCtrlRxCount() == fcRxBefore + 1u);
    CHECK(tr.hidTxCredits() == 1u);

    // Tick with host2IshBusy == true -> STILL does not send
    tr.onTick(t, ish::kFwstsReadyMask, true, utc0, mono0);
    CHECK(tr.hidTxCredits() == 1u);
    CHECK(drainTx(tr).empty());

    // Tick with host2IshBusy == false -> emits 1 GET_INPUT_REPORT cleanly
    tr.onTick(t, ish::kFwstsReadyMask, false, utc0, mono0);
    CHECK(tr.hidTxCredits() == 0u);
    CHECK(!tr.hidTxPending());
    auto keepTx = drainTx(tr);
    CHECK(keepTx.size() == 1u && keepTx[0].data[4] == ish::kHostifGetInputReport);

    // 4) Incoming FW kMngResetNotify sets needHostReady_ (consumed once) and sends MNG_RESET_NOTIFY_ACK
    ish::MngResetPayload rstIn { 7u, 0u };
    tr.onRxFrame(ish::makeDrbl(ish::kProtoMng, ish::kMngResetNotify, sizeof(rstIn)),
                 reinterpret_cast<const uint8_t *>(&rstIn), sizeof(rstIn), t);
    CHECK(tr.consumeNeedHostReady());
    CHECK(!tr.consumeNeedHostReady());
    CHECK(tr.stage() == ish::IshTransport::Stage::ReadyWait);
    auto rstTx = drainTx(tr);
    CHECK(rstTx.size() == 1u && rstTx[0].proto == ish::kProtoMng && rstTx[0].mngCmd == ish::kMngResetNotifyAck);
}

int main() {
    testProtocolConstantsAndTxSlicer();
    testHidParserAndLuxMath();
    testFullStateMachineMultiSensorAndReports();
    testNoAlsSensorAndTimeouts();
    testClockSyncProtocolAnd20sCadence();
    testFixedClient13SystemStateTransitions();
    testFixedClient14DsmProxy();
    testAlsSensitivityIntervalAndDarkPermissive();
    testFeatureFallbacksAndHdrSize();
    testPhase51Hp317FeatureAndRecovery();
    testPhase52PimrFlowAndKeepalive();
    if (gTestsFailed != 0) {
        std::fprintf(stderr, "FAILED %d / %d checks\n", gTestsFailed, gTestsRun);
        return 1;
    }
    std::printf("PASS %d checks\n", gTestsRun);
    return 0;
}
