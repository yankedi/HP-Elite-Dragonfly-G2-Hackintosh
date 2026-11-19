// SPDX-License-Identifier: BSD-3-Clause
// Clean-room Intel 500-Series ISH MMIO / ISHTP / HBM 1.0 / HID-over-ISHTP Protocol Engine

#ifndef TGLISH_PROTOCOL_HPP
#define TGLISH_PROTOCOL_HPP

#include "IshHidAls.hpp"

namespace ish {

// PCI Identification (Tiger Lake-LP ISH)
static constexpr uint16_t kPciVendorIntel       = 0x8086u;
static constexpr uint16_t kPciDeviceIshTglLp    = 0xA0FCu;
static constexpr uint32_t kPciSubsystemHp8716   = 0x8716103Cu;
static constexpr uint64_t kMinBar0Size          = 0x400ULL;

// BAR0 MMIO Register Offsets
static constexpr uint32_t kRegPimrBxt           = 0x0008u;
static constexpr uint32_t kRegPisrBxt           = 0x000Cu;
static constexpr uint32_t kRegFwsts             = 0x0034u;
static constexpr uint32_t kRegHostComm          = 0x0038u;
static constexpr uint32_t kRegRst               = 0x0044u;
static constexpr uint32_t kRegHost2IshDrbl      = 0x0048u;
static constexpr uint32_t kRegIsh2HostDrbl      = 0x0054u;
static constexpr uint32_t kRegIsh2HostMsg       = 0x0060u; // 128 B inline RX window
static constexpr uint32_t kRegHost2IshMsg       = 0x00E0u; // 128 B inline TX window
static constexpr uint32_t kRegIshRmp2           = 0x0368u;

// Register Bits
static constexpr uint32_t kPimrIntEnBit               = 1u << 0;
static constexpr uint32_t kPimrHost2IshBusyClrMaskBit = 1u << 8;
static constexpr uint32_t kPimrIsh2HostClrMaskBit     = 1u << 11;

static constexpr uint32_t kPisrIsh2HostBit            = 1u << 0;
static constexpr uint32_t kPisrHost2IshBusyClrBit     = 1u << 8;

inline uint32_t computeInitPimr(uint32_t curPimr) {
    // Strictly matches Linux intel-ish-ipc (ipc.c:set_host_ready) & Intel Windows ISH.sys (0x140023be3):
    // Enable ISH2HOST doorbell IRQ (bit 0), disable HOST2ISH busy-clear IRQ (bit 8),
    // and NEVER clear bit 11 (IPC_INT_ISH2HOST_CLR_MASK_BIT) which masks IPC_BUSY_CLR.
    return (curPimr & ~kPimrHost2IshBusyClrMaskBit) | kPimrIntEnBit;
}

static constexpr uint32_t kFwstsIlupBit               = 1u << 0;
static constexpr uint32_t kFwstsIshtpReadyBit         = 1u << 1;
static constexpr uint32_t kFwstsReadyMask             = kFwstsIlupBit | kFwstsIshtpReadyBit;
static constexpr uint32_t kFwstsStateShift            = 12u;
static constexpr uint32_t kFwstsStateMask             = 0xFu << 12;
static constexpr uint32_t kFwstsInDmaMask             = 0x000F0000u;

static constexpr uint32_t kHostCommIlupBit            = 1u << 0;
static constexpr uint32_t kHostCommBusyReadingBit     = 1u << 6;
static constexpr uint32_t kHostCommReadyBit           = 1u << 7;

static constexpr uint32_t kRmp2DmaEnabledBit          = 1u << 0;

static constexpr uint32_t kDrblBusyBit                = 1u << 31;
static constexpr uint32_t kDrblMngCmdShift            = 16u;
static constexpr uint32_t kDrblMngCmdMask             = 0xFu << 16;
static constexpr uint32_t kDrblProtocolShift          = 10u;
static constexpr uint32_t kDrblProtocolMask           = 0xFu << 10;
static constexpr uint32_t kDrblLengthMask             = 0x3FFu;

// IPC Protocols
static constexpr uint8_t kProtoIshtp = 1u;
static constexpr uint8_t kProtoMng   = 3u;

// MNG Commands
static constexpr uint8_t kMngRxCmplEnable     = 0u;
static constexpr uint8_t kMngRxCmplDisable    = 1u;
static constexpr uint8_t kMngRxCmplIndication = 2u;
static constexpr uint8_t kMngResetNotify      = 3u;
static constexpr uint8_t kMngResetNotifyAck   = 4u;
static constexpr uint8_t kMngSyncFwClock      = 5u;

// ISHTP Parameters
static constexpr size_t   kIpcMaxFrameBytes    = 128u;
static constexpr size_t   kIshtpMaxFragPayload = 124u;
static constexpr size_t   kIshtpMaxMsgBytes    = 4096u;
static constexpr size_t   kTxQueueCapacity     = 64u;   // >= 32 slots; holds full 4096 B SDU (34 frags) + ctrl
static constexpr uint8_t  kSysStateFwAddr      = 13u;
static constexpr uint8_t  kDsmProxyFwAddr      = 14u;
static constexpr uint8_t  kHidHostAddr         = 1u;
static constexpr size_t   kMaxHidDevices       = 32u;
static constexpr size_t   kMaxPendingDsm       = 8u;
static constexpr uint64_t kClockSyncPeriodNs   = 20000000000ULL;

// Clock Sync Sources (ISH.sys / Linux hw-ish.h)
static constexpr uint8_t  kClockSourceHostUtcUsec = 0u;
static constexpr uint8_t  kClockSourceHostSysUsec = 1u;

// HBM v1.0 Opcodes
static constexpr uint8_t kHbmRespBit            = 0x80u;
static constexpr uint8_t kHbmHostStartReq       = 0x01u;
static constexpr uint8_t kHbmHostStartRes       = 0x81u;
static constexpr uint8_t kHbmHostStopReq        = 0x02u;
static constexpr uint8_t kHbmHostStopRes        = 0x82u;
static constexpr uint8_t kHbmHostEnumReq        = 0x04u;
static constexpr uint8_t kHbmHostEnumRes        = 0x84u;
static constexpr uint8_t kHbmHostClientPropsReq = 0x05u;
static constexpr uint8_t kHbmHostClientPropsRes = 0x85u;
static constexpr uint8_t kHbmClientConnectReq   = 0x06u;
static constexpr uint8_t kHbmClientConnectRes   = 0x86u;
static constexpr uint8_t kHbmClientDisconnReq   = 0x07u;
static constexpr uint8_t kHbmClientDisconnRes   = 0x87u;
static constexpr uint8_t kHbmFlowControl        = 0x08u;

// System-State Fixed Client (fw_addr = 13, host_addr = 0)
static constexpr uint32_t kSysStateSubscribeCmd      = 1u;
static constexpr uint32_t kSysStateStatusCmd         = 2u;
static constexpr uint32_t kSysStateQuerySubscribers  = 3u;
static constexpr uint32_t kSysStateStateChangeReq    = 4u;
static constexpr uint32_t kSysStateInitQueryCmd      = 5u;
static constexpr uint32_t kSysStateConnectedStandbyBit = (1u << 0);
static constexpr uint32_t kSysStateSuspendBit          = (1u << 1);
static constexpr uint32_t kSysStateAllSupported        =
    kSysStateConnectedStandbyBit | kSysStateSuspendBit;

// ISHD._DSM Proxy Fixed Client (fw_addr = 14, host_addr = 0)
// ACPI GUID {1730E71D-E5DD-4A34-BE57-4D76B6A2FE37} in ACPI mixed-endian byte order
static constexpr uint8_t  kIshDsmGuidBytes[16] = {
    0x1Du, 0xE7u, 0x30u, 0x17u, 0xDDu, 0xE5u, 0x34u, 0x4Au,
    0xBEu, 0x57u, 0x4Du, 0x76u, 0xB6u, 0xA2u, 0xFEu, 0x37u
};
static constexpr uint32_t kDsmCmdInit              = 1u;
static constexpr uint32_t kDsmCmdExec              = 3u;
static constexpr uint32_t kDsmSubFunc3             = 2u;
static constexpr uint32_t kDsmSubFunc2             = 4u;
static constexpr uint32_t kDsmDefaultSupportedMask = 0x03u;

// HID-over-ISHTP HostIF Commands
static constexpr uint8_t kHostifIsResponse             = 0x80u;
static constexpr uint8_t kHostifGetHidDescriptor       = 0u;
static constexpr uint8_t kHostifGetReportDescriptor    = 1u;
static constexpr uint8_t kHostifGetFeatureReport       = 2u;
static constexpr uint8_t kHostifSetFeatureReport       = 3u;
static constexpr uint8_t kHostifGetInputReport         = 4u;
static constexpr uint8_t kHostifPublishInputReport     = 5u;
static constexpr uint8_t kHostifPublishInputReportList = 6u;
static constexpr uint8_t kHostifDmEnumDevices          = 33u;

// HID Client GUID: 33AECD58-B679-4E54-9BD9-A04D34F0C226
static constexpr uint8_t kIshHidClientGuid[16] = {
    0x58u, 0xCDu, 0xAEu, 0x33u, 0x79u, 0xB6u, 0x54u, 0x4Eu,
    0x9Bu, 0xD9u, 0xA0u, 0x4Du, 0x34u, 0xF0u, 0xC2u, 0x26u
};

// Packed Wire Structures
struct __attribute__((packed)) MngResetPayload {
    uint16_t reset_id;
    uint16_t reserved;
};
static_assert(sizeof(MngResetPayload) == 4, "MngResetPayload size");

struct __attribute__((packed)) IshtpMsgHdr {
    uint32_t fw_addr      : 8;
    uint32_t host_addr    : 8;
    uint32_t length       : 9;
    uint32_t reserved     : 6;
    uint32_t msg_complete : 1;
};
static_assert(sizeof(IshtpMsgHdr) == 4, "IshtpMsgHdr size");

struct __attribute__((packed)) HbmStartReq {
    uint8_t cmd;
    uint8_t rsv;
    uint8_t minor;
    uint8_t major;
};
static_assert(sizeof(HbmStartReq) == 4, "HbmStartReq size");

struct __attribute__((packed)) HbmStartRes {
    uint8_t cmd;
    uint8_t supported;
    uint8_t minor;
    uint8_t major;
};
static_assert(sizeof(HbmStartRes) == 4, "HbmStartRes size");

struct __attribute__((packed)) HbmEnumReq {
    uint8_t cmd;
    uint8_t rsv[3];
};
static_assert(sizeof(HbmEnumReq) == 4, "HbmEnumReq size");

struct __attribute__((packed)) HbmEnumRes {
    uint8_t cmd;
    uint8_t rsv[3];
    uint8_t valid_bits[32];
};
static_assert(sizeof(HbmEnumRes) == 36, "HbmEnumRes size");

struct __attribute__((packed)) HbmPropsReq {
    uint8_t cmd;
    uint8_t addr;
    uint8_t rsv[2];
};
static_assert(sizeof(HbmPropsReq) == 4, "HbmPropsReq size");

struct __attribute__((packed)) IshtpClientProps {
    uint8_t  guid[16];
    uint8_t  protocol_version;
    uint8_t  max_connections;
    uint8_t  fixed_address;
    uint8_t  single_recv_buf;
    uint32_t max_msg_length;
    uint8_t  dma_hdr_len;
    uint8_t  reserved[3];
};
static_assert(sizeof(IshtpClientProps) == 28, "IshtpClientProps size");

struct __attribute__((packed)) HbmPropsRes {
    uint8_t          cmd;
    uint8_t          addr;
    uint8_t          status;
    uint8_t          reserved;
    IshtpClientProps props;
};
static_assert(sizeof(HbmPropsRes) == 32, "HbmPropsRes size");

struct __attribute__((packed)) HbmClientCmd {
    uint8_t cmd;
    uint8_t fw_addr;
    uint8_t host_addr;
    uint8_t status_or_rsv;
    uint8_t pad[4];
};
static_assert(sizeof(HbmClientCmd) == 8, "HbmClientCmd size");

struct __attribute__((packed)) MngClockSyncMsg {
    uint64_t primary_host_time;
    uint8_t  ts1_source;
    uint8_t  ts2_source;
    uint16_t reserved;
    uint64_t secondary_host_time;
};
static_assert(sizeof(MngClockSyncMsg) == 20, "MngClockSyncMsg size");

struct __attribute__((packed)) SysStateHeader {
    uint32_t cmd;
    uint32_t cmd_status;
};
static_assert(sizeof(SysStateHeader) == 8, "SysStateHeader size");

struct __attribute__((packed)) SysStateSubscribe {
    uint32_t cmd;
    uint32_t cmd_status;
    uint32_t states;
};
static_assert(sizeof(SysStateSubscribe) == 12, "SysStateSubscribe size");

struct __attribute__((packed)) SysStateStatus {
    uint32_t cmd;
    uint32_t cmd_status;
    uint32_t supported;
    uint32_t status;
};
static_assert(sizeof(SysStateStatus) == 16, "SysStateStatus size");

struct __attribute__((packed)) SysStateChangeReq {
    uint32_t cmd;
    uint32_t cmd_status;
    uint32_t requested_states;
    uint32_t states_status;
};
static_assert(sizeof(SysStateChangeReq) == 16, "SysStateChangeReq size");

struct __attribute__((packed)) DsmInitMsg {
    uint32_t cmd;
    uint32_t status;
    uint32_t supported_mask;
};
static_assert(sizeof(DsmInitMsg) == 12, "DsmInitMsg size");

struct __attribute__((packed)) DsmExecHdr {
    uint32_t cmd;
    uint32_t status;
    uint32_t sub_cmd;
};
static_assert(sizeof(DsmExecHdr) == 12, "DsmExecHdr size");

struct DsmWorkItem {
    bool     valid {false};
    uint8_t  hostAddr {0u};
    uint32_t subCmd {0u};
    uint32_t funcIndex {0u};
    uint8_t  argLen {0u};
    uint8_t  args[16] {};
};

inline void packMngClockSync(uint64_t utcUs, uint64_t monoUs, uint8_t outBuf[sizeof(MngClockSyncMsg)]) {
    const uint64_t p = (utcUs != 0ULL) ? utcUs : monoUs;
    const uint64_t s = monoUs;
    for (size_t i = 0; i < 8u; ++i) {
        outBuf[i] = static_cast<uint8_t>((p >> (i * 8u)) & 0xFFu);
        outBuf[12u + i] = static_cast<uint8_t>((s >> (i * 8u)) & 0xFFu);
    }
    outBuf[8] = kClockSourceHostUtcUsec;
    outBuf[9] = kClockSourceHostSysUsec;
    outBuf[10] = 0u;
    outBuf[11] = 0u;
}

struct __attribute__((packed)) HostifMsgHdr {
    uint8_t  command;
    uint8_t  device_id;
    uint8_t  status;
    uint8_t  flags;
    uint16_t size;
};
static_assert(sizeof(HostifMsgHdr) == 6, "HostifMsgHdr size");

struct __attribute__((packed)) HidDeviceInfo {
    uint32_t dev_id;
    uint8_t  dev_class;
    uint16_t pid;
    uint16_t vid;
};
static_assert(sizeof(HidDeviceInfo) == 9, "HidDeviceInfo size");

struct __attribute__((packed)) HidReportListHdr {
    uint16_t total_size;
    uint8_t  num_of_reports;
    uint8_t  flags;
};
static_assert(sizeof(HidReportListHdr) == 4, "HidReportListHdr size");

struct __attribute__((packed)) HidReportListItem {
    uint16_t     size;
    HostifMsgHdr msg;
};
static_assert(sizeof(HidReportListItem) == 8, "HidReportListItem size");

// Doorbell Helpers
inline uint32_t makeDrbl(uint8_t proto, uint8_t mngCmd, uint16_t len) {
    return kDrblBusyBit |
           ((static_cast<uint32_t>(mngCmd) & 0xFu) << kDrblMngCmdShift) |
           ((static_cast<uint32_t>(proto) & 0xFu) << kDrblProtocolShift) |
           (static_cast<uint32_t>(len) & kDrblLengthMask);
}

inline bool drblBusy(uint32_t drbl) {
    return (drbl & kDrblBusyBit) != 0u;
}

inline uint8_t drblProto(uint32_t drbl) {
    return static_cast<uint8_t>((drbl & kDrblProtocolMask) >> kDrblProtocolShift);
}

inline uint8_t drblMngCmd(uint32_t drbl) {
    return static_cast<uint8_t>((drbl & kDrblMngCmdMask) >> kDrblMngCmdShift);
}

inline uint16_t drblLength(uint32_t drbl) {
    return static_cast<uint16_t>(drbl & kDrblLengthMask);
}

inline uint32_t makeIshtpHdrWord(uint8_t fwAddr, uint8_t hostAddr, uint16_t len, bool complete) {
    return static_cast<uint32_t>(fwAddr) |
           (static_cast<uint32_t>(hostAddr) << 8) |
           ((static_cast<uint32_t>(len) & 0x1FFu) << 16) |
           (complete ? (1u << 31) : 0u);
}

inline void parseIshtpHdrWord(uint32_t word, uint8_t &fwAddr, uint8_t &hostAddr, uint16_t &len, bool &complete) {
    fwAddr   = static_cast<uint8_t>(word & 0xFFu);
    hostAddr = static_cast<uint8_t>((word >> 8) & 0xFFu);
    len      = static_cast<uint16_t>((word >> 16) & 0x1FFu);
    complete = ((word >> 31) & 1u) != 0u;
}

struct TxFrame {
    uint8_t proto  = 0;
    uint8_t mngCmd = 0;
    uint8_t len    = 0;
    uint8_t data[kIpcMaxFrameBytes] {};
};

class TxRing {
public:
    void clear() {
        head_ = 0;
        tail_ = 0;
        count_ = 0;
    }

    size_t count() const { return count_; }
    size_t freeSlots() const { return kTxQueueCapacity - count_; }
    bool empty() const { return count_ == 0u; }

    bool push(const TxFrame &frame) {
        if (count_ >= kTxQueueCapacity) {
            return false;
        }
        ring_[tail_] = frame;
        tail_ = (tail_ + 1u) % kTxQueueCapacity;
        ++count_;
        return true;
    }

    bool pop(TxFrame &out) {
        if (count_ == 0u) {
            return false;
        }
        out = ring_[head_];
        head_ = (head_ + 1u) % kTxQueueCapacity;
        --count_;
        return true;
    }

private:
    TxFrame ring_[kTxQueueCapacity] {};
    size_t  head_  = 0;
    size_t  tail_  = 0;
    size_t  count_ = 0;
};

struct IshtpRxStream {
    bool     active   = false;
    uint8_t  fwAddr   = 0;
    uint8_t  hostAddr = 0;
    size_t   len      = 0;
    uint8_t  buf[kIshtpMaxMsgBytes] {};
};

class IshTransport {
public:
    enum class Stage : uint8_t {
        Idle = 0,
        ResetWait,
        ReadyWait,
        HbmVersionWait,
        HbmEnumWait,
        HbmPropsLoop,
        HidConnectWait,
        HidEnumWait,
        HidDescHidWait,
        HidDescRptWait,
        AlsFeatGet,
        AlsFeatSet,
        AlsFeatVerify,
        AlsPrimeInput,
        Streaming,
        NoAlsSensor,
        Failed,
    };

    static constexpr uint64_t kNsPerMs                = 1000000ULL;
    static constexpr uint64_t kTotalInitBudgetNs      = 15000ULL * kNsPerMs;
    static constexpr uint64_t kResetTimeoutNs         = 1000ULL * kNsPerMs;
    static constexpr uint64_t kReadyTimeoutNs         = 1000ULL * kNsPerMs;
    static constexpr uint64_t kHbmTimeoutNs           = 500ULL * kNsPerMs;
    static constexpr uint64_t kHidStageTimeoutNs      = 1500ULL * kNsPerMs;
    static constexpr uint64_t kStreamingPollNs        = 1000ULL * kNsPerMs;
    static constexpr uint64_t kStreamingKeepaliveNs   = 5000ULL * kNsPerMs;
    static constexpr size_t   kMaxFeatureReportBytes  = 512u;
    static constexpr size_t   kMaxHidTxBytes          = sizeof(HostifMsgHdr) + kMaxFeatureReportBytes;
    static constexpr uint8_t  kMaxFeatGetAttempts     = 4u;
    static constexpr uint64_t kFeatRetryDelayNs       = 300ULL * kNsPerMs;

    void reset(uint64_t nowNs) {
        stage_ = Stage::Idle;
        tx_.clear();
        resetSessionState();
        initStartNs_ = nowNs;
        stageStartNs_ = nowNs;
        lastSampleRxNs_ = nowNs;
        lastHeartbeatTxNs_ = nowNs;
        sampleUpdated_ = false;
        sampleCount_ = 0;
        rawIllum_ = 0;
        milliLux_ = 0;
        lastClockSyncNs_ = 0;
        clockSyncCount_ = 0;
        sysStateSupported_ = kSysStateAllSupported;
        sysStateStatus_ = computeSysStateStatus();
        sysStateCount_ = 0;
        lastSysStateReq_ = 0;
        dsmProxyCount_ = 0;
        dsmDropped_ = 0;
        dsmHead_ = 0;
        dsmTail_ = 0;
        dsmCount_ = 0;
        fixedClientsSeen_ = 0;
        alsIntervalMs_ = 0;
        alsSensitivity_ = 0;
        flowCreditsSent_ = 0;
        overflowDrops_ = 0;
        hidFlowCtrlRxCount_ = 0;
        publishReportCount_ = 0;
        getInputRespCount_ = 0;
        needHostReady_ = false;
        lastHostifCmd_ = 0;
        lastHostifStatus_ = 0;
        lastHostifLen_ = 0;
        memset(errorMsg_, 0, sizeof(errorMsg_));
    }

    void setClockSyncEnabled(bool enabled) {
        clockSyncEnabled_ = enabled;
    }

    void setDsmConfig(bool enabled, uint32_t supportedMask = kDsmDefaultSupportedMask) {
        dsmEnabled_ = enabled;
        dsmSupportedMask_ = enabled ? supportedMask : 0u;
    }

    bool setHostPowerState(bool awake, bool displayOn, uint64_t nowNs, uint64_t utcUs = 0, uint64_t monoUs = 0) {
        const bool wasSuspended = hostSuspended_;
        hostSuspended_ = !awake;
        displayOn_ = displayOn;
        const uint32_t nextStatus = computeSysStateStatus();
        const bool changed = (nextStatus != sysStateStatus_);
        sysStateStatus_ = nextStatus;

        bool sent = false;
        if (stage_ >= Stage::HbmEnumWait && (sysStateSubscribed_ || changed)) {
            sendSysStateStatusMsg(0u);
            sent = true;
        }
        if (wasSuspended && awake && clockSyncEnabled_ && stage_ >= Stage::HbmVersionWait) {
            sendClockSync(utcUs, monoUs, nowNs);
        }
        return sent;
    }

    bool popPendingDsm(DsmWorkItem &out) {
        if (dsmCount_ == 0u) {
            return false;
        }
        out = dsmQueue_[dsmHead_];
        dsmQueue_[dsmHead_] = DsmWorkItem {};
        dsmHead_ = (dsmHead_ + 1u) % kMaxPendingDsm;
        --dsmCount_;
        return true;
    }

    void startInit(uint64_t nowNs) {
        reset(nowNs);
        stage_ = Stage::ResetWait;
        initStartNs_ = nowNs;
        stageStartNs_ = nowNs;
        MngResetPayload rst { 1u, 0u };
        enqueueMng(kMngResetNotify, &rst, sizeof(rst));
    }

    bool enqueueMng(uint8_t cmd, const void *payload, size_t len) {
        if (len > kIpcMaxFrameBytes) {
            return false;
        }
        TxFrame f {};
        f.proto = kProtoMng;
        f.mngCmd = cmd;
        f.len = static_cast<uint8_t>(len);
        if (len > 0 && payload != nullptr) {
            memcpy(f.data, payload, len);
        }
        return tx_.push(f);
    }

    bool enqueueIshtp(uint8_t fwAddr, uint8_t hostAddr, const uint8_t *payload, size_t len) {
        if (len == 0 || len > kIshtpMaxMsgBytes || payload == nullptr) {
            return false;
        }
        const size_t numFrags = (len + kIshtpMaxFragPayload - 1u) / kIshtpMaxFragPayload;
        if (tx_.freeSlots() < numFrags) {
            return false;
        }
        size_t offset = 0;
        while (offset < len) {
            size_t chunk = len - offset;
            if (chunk > kIshtpMaxFragPayload) {
                chunk = kIshtpMaxFragPayload;
            }
            const bool complete = (offset + chunk == len);
            TxFrame f {};
            f.proto = kProtoIshtp;
            f.mngCmd = 0;
            f.len = static_cast<uint8_t>(sizeof(IshtpMsgHdr) + chunk);
            const uint32_t hdrWord = makeIshtpHdrWord(fwAddr, hostAddr, static_cast<uint16_t>(chunk), complete);
            writeLe32(f.data, hdrWord);
            memcpy(&f.data[sizeof(IshtpMsgHdr)], payload + offset, chunk);
            if (!tx_.push(f)) {
                return false;
            }
            offset += chunk;
        }
        return true;
    }

    bool popTxFrame(TxFrame &out) {
        return tx_.pop(out);
    }

    bool hasTxPending() const {
        return !tx_.empty();
    }

    size_t txPendingCount() const {
        return tx_.count();
    }

    void onRxFrame(uint32_t drbl, const uint8_t *payload, size_t payloadBytes, uint64_t nowNs) {
        if (stage_ == Stage::Idle || stage_ == Stage::Failed) {
            return;
        }
        const uint8_t proto = drblProto(drbl);
        const uint8_t mngCmd = drblMngCmd(drbl);
        const uint16_t drblLen = drblLength(drbl);
        const size_t len = (drblLen <= payloadBytes) ? static_cast<size_t>(drblLen) : payloadBytes;

        if (proto == kProtoMng) {
            handleMng(mngCmd, payload, len, nowNs);
            return;
        }
        if (proto == kProtoIshtp) {
            handleIshtpFragment(payload, len, nowNs);
        }
    }

    void onTick(uint64_t nowNs, uint32_t fwsts, bool host2IshBusy, uint64_t utcUs = 0, uint64_t monoUs = 0) {
        if (stage_ == Stage::Idle || stage_ == Stage::Failed || stage_ == Stage::NoAlsSensor) {
            return;
        }

        if (stage_ != Stage::Streaming) {
            if (nowNs >= initStartNs_ && (nowNs - initStartNs_) > kTotalInitBudgetNs) {
                failWith("total init timeout (>15s)");
                return;
            }
            const uint64_t stageLimit = currentStageTimeoutNs();
            if (stageLimit > 0 && nowNs >= stageStartNs_ && (nowNs - stageStartNs_) > stageLimit) {
                if (stage_ == Stage::AlsPrimeInput) {
                    // Transition cleanly to Streaming; fallback heartbeat will retry input read.
                    enterStage(Stage::Streaming, nowNs);
                    lastSampleRxNs_ = nowNs;
                    lastHeartbeatTxNs_ = nowNs;
                } else if (stage_ == Stage::AlsFeatGet ||
                           stage_ == Stage::AlsFeatSet ||
                           stage_ == Stage::AlsFeatVerify) {
                    fallbackToPrimeInput(stageTimeoutName(), nowNs);
                } else {
                    failWith(stageTimeoutName());
                    return;
                }
            }
        }

        if (stage_ == Stage::ReadyWait) {
            if ((fwsts & kFwstsReadyMask) == kFwstsReadyMask && !host2IshBusy) {
                HbmStartReq req { kHbmHostStartReq, 0u, 0u, 1u };
                if (enqueueIshtp(0u, 0u, reinterpret_cast<const uint8_t *>(&req), sizeof(req))) {
                    enterStage(Stage::HbmVersionWait, nowNs);
                    if (clockSyncEnabled_ && !clockSyncSentAfterReset_) {
                        sendClockSync(utcUs, monoUs, nowNs);
                    }
                }
            }
            return;
        }

        if (stage_ >= Stage::HbmVersionWait) {
            maybePeriodicClockSync(nowNs, utcUs, monoUs);
        }

        if (hidConnected_ && rxFlowControlPending_ && tx_.freeSlots() >= 1u) {
            sendFlowControl(hidFwAddr_, kHidHostAddr);
        }

        if (stage_ == Stage::AlsFeatGet && featRetryDueNs_ != 0ULL &&
            nowNs >= featRetryDueNs_ && !hidTxPending_) {
            featRetryDueNs_ = 0ULL;
            ++featGetAttempts_;
            stageStartNs_ = nowNs;
            sendHostifSimple(kHostifGetFeatureReport, alsDevId_, &alsDesc_.featureReportId, 1u, featUseZeroHdrSize_);
        }

        if (stage_ == Stage::Streaming && alsDesc_.found) {
            flushPendingHidTx();
            const uint64_t pollIntervalNs = alsControlsVerified_ ? kStreamingKeepaliveNs : kStreamingPollNs;
            const bool noRecentSample = (nowNs >= lastSampleRxNs_) && ((nowNs - lastSampleRxNs_) >= pollIntervalNs);
            const bool heartbeatDue = (nowNs >= lastHeartbeatTxNs_) && ((nowNs - lastHeartbeatTxNs_) >= pollIntervalNs);
            if (noRecentSample && heartbeatDue && !host2IshBusy &&
                !hidTxPending_ && hidTxCredits_ > 0u && tx_.freeSlots() >= 2u) {
                lastHeartbeatTxNs_ = nowNs;
                sendHostifSimple(kHostifGetInputReport, alsDevId_, &alsDesc_.inputReportId, 1u);
            }
        } else {
            flushPendingHidTx();
        }
    }

    bool consumeSampleUpdated() {
        const bool was = sampleUpdated_;
        sampleUpdated_ = false;
        return was;
    }

    Stage stage() const { return stage_; }
    const char *stageName() const {
        switch (stage_) {
            case Stage::Idle:           return "Idle";
            case Stage::ResetWait:      return "ResetWait";
            case Stage::ReadyWait:      return "ReadyWait";
            case Stage::HbmVersionWait: return "HbmVersionWait";
            case Stage::HbmEnumWait:    return "HbmEnumWait";
            case Stage::HbmPropsLoop:   return "HbmPropsLoop";
            case Stage::HidConnectWait: return "HidConnectWait";
            case Stage::HidEnumWait:    return "HidEnumWait";
            case Stage::HidDescHidWait: return "HidDescHidWait";
            case Stage::HidDescRptWait: return "HidDescRptWait";
            case Stage::AlsFeatGet:     return "AlsFeatGet";
            case Stage::AlsFeatSet:     return "AlsFeatSet";
            case Stage::AlsFeatVerify:  return "AlsFeatVerify";
            case Stage::AlsPrimeInput:  return "AlsPrimeInput";
            case Stage::Streaming:      return "Streaming";
            case Stage::NoAlsSensor:    return "NoALSSensor";
            case Stage::Failed:         return "Failed";
        }
        return "Unknown";
    }

    const char *errorMsg() const { return errorMsg_; }
    uint8_t hidFwAddr() const { return hidFwAddr_; }
    uint32_t hidMaxMsg() const { return hidMaxMsg_; }
    bool hidConnected() const { return hidConnected_; }
    uint32_t hidTxCredits() const { return hidTxCredits_; }
    bool hidTxPending() const { return hidTxPending_; }
    uint8_t alsDevId() const { return alsDevId_; }
    const AlsDescriptorInfo &alsDesc() const { return alsDesc_; }
    bool alsControlsVerified() const { return alsControlsVerified_; }
    uint32_t sampleCount() const { return sampleCount_; }
    uint64_t lastSampleRxNs() const { return lastSampleRxNs_; }
    uint32_t rawIllum() const { return rawIllum_; }
    uint64_t milliLux() const { return milliLux_; }
    uint32_t fixedLux() const { return fixedLux_; }
    uint32_t sysStateCount() const { return sysStateCount_; }
    uint32_t sysStateStatus() const { return sysStateStatus_; }
    uint32_t sysStateSupported() const { return sysStateSupported_; }
    bool     sysStateSubscribed() const { return sysStateSubscribed_; }
    uint32_t clockSyncCount() const { return clockSyncCount_; }
    bool     clockSyncEnabled() const { return clockSyncEnabled_; }
    uint32_t dsmProxyCount() const { return dsmProxyCount_; }
    uint32_t dsmDropped() const { return dsmDropped_; }
    bool     dsmEnabled() const { return dsmEnabled_; }
    uint32_t dsmSupportedMask() const { return dsmSupportedMask_; }
    uint32_t fixedClientsSeen() const { return fixedClientsSeen_; }
    uint32_t alsIntervalMs() const { return alsIntervalMs_; }
    uint32_t alsSensitivity() const { return alsSensitivity_; }
    bool     isAlsDarkPermissive(uint64_t thresholdMilliLux = kDefaultAlsDarkThresholdMLux) const {
        return ish::isAlsDarkPermissive(fixedLux_ != kSmcLuxInvalid, milliLux_, thresholdMilliLux);
    }
    uint32_t flowCreditsSent() const { return flowCreditsSent_; }
    uint32_t overflowDrops() const { return overflowDrops_; }
    bool rxFlowControlPending() const { return rxFlowControlPending_; }
    bool consumeNeedHostReady() {
        const bool v = needHostReady_;
        needHostReady_ = false;
        return v;
    }
    uint32_t hidFlowCtrlRxCount() const { return hidFlowCtrlRxCount_; }
    uint32_t publishReportCount() const { return publishReportCount_; }
    uint32_t getInputRespCount() const { return getInputRespCount_; }
    uint8_t hidDevCount() const { return hidDevCount_; }
    const uint8_t *hidDevListData() const { return hidDevListBuf_; }
    uint16_t hidDevListLen() const { return hidDevListLen_; }
    uint8_t lastHostifCmd() const { return lastHostifCmd_; }
    uint8_t lastHostifStatus() const { return lastHostifStatus_; }
    uint16_t lastHostifLen() const { return lastHostifLen_; }
    const uint8_t *origFeatData() const { return origFeatBuf_; }
    uint16_t origFeatLen() const { return origFeatLen_; }
    const uint8_t *reqFeatData() const { return reqFeatBuf_; }
    uint16_t reqFeatLen() const { return reqFeatLen_; }
    const uint8_t *curFeatData() const { return curFeatBuf_; }
    uint16_t curFeatLen() const { return curFeatLen_; }
    const uint8_t *alsDescSliceData() const { return alsDescSlice_; }
    uint16_t alsDescSliceLen() const { return alsDescSliceLen_; }
    uint8_t featGetStatus() const { return featGetStatus_; }
    uint8_t featGetFlags() const { return featGetFlags_; }
    uint16_t featGetDeclaredSize() const { return featGetDeclaredSize_; }
    uint16_t featGetAvailLen() const { return featGetAvailLen_; }
    const uint8_t *featGetHdr() const { return featGetHdr_; }
    bool featGetHdrValid() const { return featGetHdrValid_; }
    uint8_t featGetAttempts() const { return featGetAttempts_; }
    bool featUseZeroHdrSize() const { return featUseZeroHdrSize_; }
    uint8_t featSetStatus() const { return featSetStatus_; }
    uint8_t featSetFlags() const { return featSetFlags_; }
    uint8_t featVerifyStatus() const { return featVerifyStatus_; }
    bool featVerifySeen() const { return featVerifySeen_; }
    const char *featureError() const { return featureError_; }

private:
    static constexpr size_t kMaxRxStreams = 4u;

    Stage             stage_ = Stage::Idle;
    TxRing            tx_ {};
    IshtpRxStream     rxStreams_[kMaxRxStreams] {};
    uint8_t           validClients_[32] {};
    uint16_t          nextClientQuery_ = 1;
    uint8_t           hidFwAddr_ = 0;
    uint32_t          hidMaxMsg_ = kIshtpMaxMsgBytes;
    bool              hidConnected_ = false;
    uint32_t          hidTxCredits_ = 0;
    bool              hidTxPending_ = false;
    uint8_t           hidTxPendingBuf_[kMaxHidTxBytes] {};
    size_t            hidTxPendingLen_ = 0;
    uint8_t           hidDevCount_ = 0;
    uint8_t           hidDevIds_[kMaxHidDevices] {};
    uint8_t           hidDevListBuf_[kMaxHidDevices * sizeof(HidDeviceInfo)] {};
    uint16_t          hidDevListLen_ = 0;
    uint8_t           descIndex_ = 0;
    uint8_t           alsDevId_ = 0;
    AlsDescriptorInfo alsDesc_ {};
    uint8_t           alsDescSlice_[kMaxFeatureReportBytes] {};
    uint16_t          alsDescSliceLen_ = 0;
    bool              alsControlsVerified_ = false;
    uint32_t          alsIntervalMs_ = 0;
    uint32_t          alsSensitivity_ = 0;
    uint64_t          initStartNs_ = 0;
    uint64_t          stageStartNs_ = 0;
    uint64_t          lastSampleRxNs_ = 0;
    uint64_t          lastHeartbeatTxNs_ = 0;
    bool              sampleUpdated_ = false;
    uint32_t          sampleCount_ = 0;
    uint32_t          rawIllum_ = 0;
    uint64_t          milliLux_ = 0;
    uint32_t          fixedLux_ = kSmcLuxInvalid;
    bool              clockSyncEnabled_ = true;
    bool              clockSyncSentAfterReset_ = false;
    uint64_t          lastClockSyncNs_ = 0;
    uint32_t          clockSyncCount_ = 0;
    bool              hostSuspended_ = false;
    bool              displayOn_ = true;
    bool              sysStateSubscribed_ = false;
    uint32_t          sysStateSupported_ = kSysStateAllSupported;
    uint32_t          sysStateStatus_ = 0;
    uint32_t          sysStateCount_ = 0;
    uint32_t          lastSysStateReq_ = 0;
    bool              dsmEnabled_ = true;
    uint32_t          dsmSupportedMask_ = kDsmDefaultSupportedMask;
    bool              dsmInitSent_ = false;
    DsmWorkItem       dsmQueue_[kMaxPendingDsm] {};
    size_t            dsmHead_ = 0;
    size_t            dsmTail_ = 0;
    size_t            dsmCount_ = 0;
    uint32_t          dsmProxyCount_ = 0;
    uint32_t          dsmDropped_ = 0;
    uint32_t          fixedClientsSeen_ = 0;
    uint32_t          flowCreditsSent_ = 0;
    uint32_t          overflowDrops_ = 0;
    bool              rxFlowControlPending_ = false;
    bool              needHostReady_ = false;
    uint32_t          hidFlowCtrlRxCount_ = 0;
    uint32_t          publishReportCount_ = 0;
    uint32_t          getInputRespCount_ = 0;
    uint8_t           lastHostifCmd_ = 0;
    uint8_t           lastHostifStatus_ = 0;
    uint16_t          lastHostifLen_ = 0;
    uint8_t           origFeatBuf_[kMaxFeatureReportBytes] {};
    uint16_t          origFeatLen_ = 0;
    uint8_t           reqFeatBuf_[kMaxFeatureReportBytes] {};
    uint16_t          reqFeatLen_ = 0;
    uint8_t           curFeatBuf_[kMaxFeatureReportBytes] {};
    uint16_t          curFeatLen_ = 0;
    bool              featRetryPowerOnly_ = false;
    uint8_t           featGetStatus_ = 0;
    uint8_t           featGetFlags_ = 0;
    uint16_t          featGetDeclaredSize_ = 0;
    uint16_t          featGetAvailLen_ = 0;
    uint8_t           featGetHdr_[6] {};
    bool              featGetHdrValid_ = false;
    uint8_t           featGetAttempts_ = 0;
    bool              featUseZeroHdrSize_ = false;
    bool              featSetZeroHdrSize_ = false;
    uint64_t          featRetryDueNs_ = 0;
    uint8_t           featSetStatus_ = 0;
    uint8_t           featSetFlags_ = 0;
    bool              featSetZeroHdrRetry_ = false;
    uint8_t           featVerifyStatus_ = 0;
    bool              featVerifySeen_ = false;
    char              featureError_[96] {};
    char              errorMsg_[96] {};

    void resetSessionState() {
        for (size_t i = 0; i < kMaxRxStreams; ++i) {
            rxStreams_[i].active = false;
            rxStreams_[i].len = 0;
        }
        memset(validClients_, 0, sizeof(validClients_));
        nextClientQuery_ = 1;
        hidFwAddr_ = 0;
        hidMaxMsg_ = kIshtpMaxMsgBytes;
        hidConnected_ = false;
        hidTxCredits_ = 0;
        hidTxPending_ = false;
        hidTxPendingLen_ = 0;
        rxFlowControlPending_ = false;
        hidDevCount_ = 0;
        memset(hidDevIds_, 0, sizeof(hidDevIds_));
        memset(hidDevListBuf_, 0, sizeof(hidDevListBuf_));
        hidDevListLen_ = 0;
        descIndex_ = 0;
        alsDevId_ = 0;
        alsDesc_ = AlsDescriptorInfo{};
        memset(alsDescSlice_, 0, sizeof(alsDescSlice_));
        alsDescSliceLen_ = 0;
        alsControlsVerified_ = false;
        fixedLux_ = kSmcLuxInvalid;
        clockSyncSentAfterReset_ = false;
        dsmInitSent_ = false;
        sysStateSubscribed_ = false;
        origFeatLen_ = 0;
        reqFeatLen_ = 0;
        curFeatLen_ = 0;
        featRetryPowerOnly_ = false;
        featGetStatus_ = 0;
        featGetFlags_ = 0;
        featGetDeclaredSize_ = 0;
        featGetAvailLen_ = 0;
        memset(featGetHdr_, 0, sizeof(featGetHdr_));
        featGetHdrValid_ = false;
        featGetAttempts_ = 0;
        featUseZeroHdrSize_ = false;
        featSetZeroHdrSize_ = false;
        featRetryDueNs_ = 0;
        featSetStatus_ = 0;
        featSetFlags_ = 0;
        featSetZeroHdrRetry_ = false;
        featVerifyStatus_ = 0;
        featVerifySeen_ = false;
        memset(origFeatBuf_, 0, sizeof(origFeatBuf_));
        memset(reqFeatBuf_, 0, sizeof(reqFeatBuf_));
        memset(curFeatBuf_, 0, sizeof(curFeatBuf_));
        memset(featureError_, 0, sizeof(featureError_));
    }

    uint32_t computeSysStateStatus() const {
        return (displayOn_ ? 0u : kSysStateConnectedStandbyBit) |
               (hostSuspended_ ? kSysStateSuspendBit : 0u);
    }

    bool sendClockSync(uint64_t utcUs, uint64_t monoUs, uint64_t nowNs) {
        const uint64_t resolvedMono = (monoUs != 0ULL) ? monoUs : (nowNs / 1000ULL);
        const uint64_t resolvedUtc = (utcUs != 0ULL) ? utcUs : resolvedMono;
        uint8_t msg[sizeof(MngClockSyncMsg)] {};
        packMngClockSync(resolvedUtc, resolvedMono, msg);
        if (!enqueueMng(kMngSyncFwClock, msg, sizeof(msg))) {
            return false;
        }
        clockSyncSentAfterReset_ = true;
        lastClockSyncNs_ = nowNs;
        ++clockSyncCount_;
        return true;
    }

    void maybePeriodicClockSync(uint64_t nowNs, uint64_t utcUs, uint64_t monoUs) {
        if (!clockSyncEnabled_ || hostSuspended_) {
            return;
        }
        if (clockSyncSentAfterReset_ && lastClockSyncNs_ != 0ULL &&
            (nowNs < lastClockSyncNs_ || (nowNs - lastClockSyncNs_) < kClockSyncPeriodNs)) {
            return;
        }
        if (tx_.freeSlots() >= 2u || (stage_ == Stage::Streaming && tx_.freeSlots() >= 1u)) {
            sendClockSync(utcUs, monoUs, nowNs);
        }
    }

    void sendSysStateStatusMsg(uint8_t hostAddr) {
        SysStateStatus rsp {};
        writeLe32(reinterpret_cast<uint8_t *>(&rsp.cmd), kSysStateStatusCmd);
        writeLe32(reinterpret_cast<uint8_t *>(&rsp.cmd_status), 0u);
        writeLe32(reinterpret_cast<uint8_t *>(&rsp.supported), sysStateSupported_);
        writeLe32(reinterpret_cast<uint8_t *>(&rsp.status), sysStateStatus_);
        if (enqueueIshtp(kSysStateFwAddr, hostAddr, reinterpret_cast<const uint8_t *>(&rsp), sizeof(rsp))) {
            ++sysStateCount_;
        }
    }

    void sendDsmInitMsg() {
        DsmInitMsg msg {};
        writeLe32(reinterpret_cast<uint8_t *>(&msg.cmd), kDsmCmdInit);
        writeLe32(reinterpret_cast<uint8_t *>(&msg.status), 0u);
        writeLe32(reinterpret_cast<uint8_t *>(&msg.supported_mask), dsmSupportedMask_);
        if (enqueueIshtp(kDsmProxyFwAddr, 0u, reinterpret_cast<const uint8_t *>(&msg), sizeof(msg))) {
            dsmInitSent_ = true;
        }
    }

    void pushDsmWork(const DsmWorkItem &item) {
        if (dsmCount_ >= kMaxPendingDsm) {
            ++dsmDropped_;
            return;
        }
        dsmQueue_[dsmTail_] = item;
        dsmQueue_[dsmTail_].valid = true;
        dsmTail_ = (dsmTail_ + 1u) % kMaxPendingDsm;
        ++dsmCount_;
        ++dsmProxyCount_;
    }

    void enterStage(Stage s, uint64_t nowNs) {
        stage_ = s;
        stageStartNs_ = nowNs;
    }

    static void copyBoundedStr(char (&dst)[96], const char *msg) {
        size_t i = 0;
        if (msg != nullptr) {
            for (; i + 1 < sizeof(dst) && msg[i] != '\0'; ++i) {
                dst[i] = msg[i];
            }
        }
        dst[i] = '\0';
    }

    static void saveFeatureBytes(uint8_t (&dst)[kMaxFeatureReportBytes], uint16_t &dstLen, const uint8_t *src, size_t len) {
        const size_t n = (len <= sizeof(dst)) ? len : sizeof(dst);
        if (n > 0u && src != nullptr) {
            memcpy(dst, src, n);
        }
        dstLen = static_cast<uint16_t>(n);
    }

    void setFeatureError(const char *msg) {
        copyBoundedStr(featureError_, msg);
    }

    void fallbackToPrimeInput(const char *msg, uint64_t nowNs) {
        setFeatureError(msg);
        alsControlsVerified_ = false;
        sendHostifSimple(kHostifGetInputReport, alsDevId_, &alsDesc_.inputReportId, 1u);
        enterStage(Stage::AlsPrimeInput, nowNs);
    }

    void failWith(const char *msg) {
        stage_ = Stage::Failed;
        fixedLux_ = kSmcLuxInvalid;
        copyBoundedStr(errorMsg_, msg);
    }

    uint64_t currentStageTimeoutNs() const {
        switch (stage_) {
            case Stage::ResetWait:      return kResetTimeoutNs;
            case Stage::ReadyWait:      return kReadyTimeoutNs;
            case Stage::HbmVersionWait:
            case Stage::HbmEnumWait:
            case Stage::HbmPropsLoop:   return kHbmTimeoutNs;
            case Stage::HidConnectWait:
            case Stage::HidEnumWait:
            case Stage::HidDescHidWait:
            case Stage::HidDescRptWait:
            case Stage::AlsFeatGet:
            case Stage::AlsFeatSet:
            case Stage::AlsFeatVerify:
            case Stage::AlsPrimeInput:  return kHidStageTimeoutNs;
            default:                    return 0;
        }
    }

    const char *stageTimeoutName() const {
        switch (stage_) {
            case Stage::ResetWait:      return "timeout in ResetWait";
            case Stage::ReadyWait:      return "timeout in ReadyWait";
            case Stage::HbmVersionWait: return "timeout in HbmVersionWait";
            case Stage::HbmEnumWait:    return "timeout in HbmEnumWait";
            case Stage::HbmPropsLoop:   return "timeout in HbmPropsLoop";
            case Stage::HidConnectWait: return "timeout in HidConnectWait";
            case Stage::HidEnumWait:    return "timeout in HidEnumWait";
            case Stage::HidDescHidWait: return "timeout in HidDescHidWait";
            case Stage::HidDescRptWait: return "timeout in HidDescRptWait";
            case Stage::AlsFeatGet:     return "timeout in AlsFeatGet";
            case Stage::AlsFeatSet:     return "timeout in AlsFeatSet";
            case Stage::AlsFeatVerify:  return "timeout in AlsFeatVerify";
            default:                    return "stage timeout";
        }
    }

    void handleMng(uint8_t mngCmd, const uint8_t *payload, size_t len, uint64_t nowNs) {
        if (mngCmd == kMngResetNotify) {
            MngResetPayload ack { 1u, 0u };
            if (len >= 2u && payload != nullptr) {
                ack.reset_id = readLe16(payload);
            }
            needHostReady_ = true;
            enqueueMng(kMngResetNotifyAck, &ack, sizeof(ack));
            if (stage_ == Stage::ResetWait) {
                enterStage(Stage::ReadyWait, nowNs);
            } else {
                // Firmware-initiated reset mid-session: reset HBM/HID discovery state cleanly
                resetSessionState();
                enterStage(Stage::ReadyWait, nowNs);
            }
        } else if (mngCmd == kMngResetNotifyAck) {
            if (stage_ == Stage::ResetWait) {
                enterStage(Stage::ReadyWait, nowNs);
            }
        }
    }

    IshtpRxStream *findOrAllocStream(uint8_t fwAddr, uint8_t hostAddr) {
        IshtpRxStream *freeSlot = nullptr;
        for (size_t i = 0; i < kMaxRxStreams; ++i) {
            if (rxStreams_[i].active && rxStreams_[i].fwAddr == fwAddr && rxStreams_[i].hostAddr == hostAddr) {
                return &rxStreams_[i];
            }
            if (!rxStreams_[i].active && freeSlot == nullptr) {
                freeSlot = &rxStreams_[i];
            }
        }
        if (freeSlot != nullptr) {
            freeSlot->active = true;
            freeSlot->fwAddr = fwAddr;
            freeSlot->hostAddr = hostAddr;
            freeSlot->len = 0;
        }
        return freeSlot;
    }

    void handleIshtpFragment(const uint8_t *payload, size_t len, uint64_t nowNs) {
        if (payload == nullptr || len < sizeof(IshtpMsgHdr)) {
            return;
        }
        uint8_t fwAddr = 0;
        uint8_t hostAddr = 0;
        uint16_t fragLen = 0;
        bool msgComplete = false;
        parseIshtpHdrWord(readLe32(payload), fwAddr, hostAddr, fragLen, msgComplete);

        if (fragLen == 0u || sizeof(IshtpMsgHdr) + static_cast<size_t>(fragLen) > len) {
            return;
        }

        const uint8_t *fragData = payload + sizeof(IshtpMsgHdr);
        IshtpRxStream *stream = findOrAllocStream(fwAddr, hostAddr);
        if (stream == nullptr) {
            ++overflowDrops_;
            return;
        }

        if (stream->len + static_cast<size_t>(fragLen) > kIshtpMaxMsgBytes) {
            stream->len = 0;
            stream->active = false;
            ++overflowDrops_;
            return;
        }

        memcpy(stream->buf + stream->len, fragData, fragLen);
        stream->len += static_cast<size_t>(fragLen);

        if (!msgComplete) {
            // Never return RX flow credits on intermediate fragments.
            return;
        }

        const size_t assembledLen = stream->len;
        // Return 1 RX flow credit ONLY per complete ISHTP message on connected dynamic HID client.
        if (hidConnected_ && fwAddr == hidFwAddr_ && hostAddr == kHidHostAddr) {
            sendFlowControl(hidFwAddr_, kHidHostAddr);
        }

        // Copy pointers/reset stream before dispatch (fixed buf reused only after dispatch).
        dispatchIshtpSdu(fwAddr, hostAddr, stream->buf, assembledLen, nowNs);
        stream->len = 0;
        stream->active = false;
    }

    void sendFlowControl(uint8_t fwAddr, uint8_t hostAddr) {
        HbmClientCmd fc {};
        fc.cmd = kHbmFlowControl;
        fc.fw_addr = fwAddr;
        fc.host_addr = hostAddr;
        if (enqueueIshtp(0u, 0u, reinterpret_cast<const uint8_t *>(&fc), sizeof(fc))) {
            ++flowCreditsSent_;
            rxFlowControlPending_ = false;
        } else {
            rxFlowControlPending_ = true;
        }
    }

    void dispatchIshtpSdu(uint8_t fwAddr, uint8_t hostAddr, const uint8_t *sdu, size_t len, uint64_t nowNs) {
        if (fwAddr == 0u && hostAddr == 0u) {
            handleHbmMessage(sdu, len, nowNs);
            return;
        }
        if (fwAddr == kSysStateFwAddr) {
            handleSystemStateMessage(hostAddr, sdu, len);
            return;
        }
        if (fwAddr == kDsmProxyFwAddr) {
            handleDsmProxyMessage(hostAddr, sdu, len);
            return;
        }
        if (hidConnected_ && fwAddr == hidFwAddr_ && hostAddr == kHidHostAddr) {
            handleHidSdu(sdu, len, nowNs);
        }
    }

    void handleSystemStateMessage(uint8_t hostAddr, const uint8_t *sdu, size_t len) {
        fixedClientsSeen_ |= (1u << kSysStateFwAddr);
        if (sdu == nullptr || len < sizeof(SysStateHeader)) {
            return;
        }
        const uint32_t cmd = readLe32(sdu);
        const uint32_t cmdStatus = readLe32(sdu + 4u);
        if (cmdStatus != 0u) {
            return;
        }
        if (cmd == kSysStateSubscribeCmd) {
            if (len >= sizeof(SysStateSubscribe)) {
                const uint32_t fwStates = readLe32(sdu + 8u);
                const uint32_t masked = fwStates & kSysStateAllSupported;
                sysStateSupported_ = (masked != 0u) ? masked : kSysStateAllSupported;
            } else {
                sysStateSupported_ = kSysStateAllSupported;
            }
            sysStateSubscribed_ = true;
            sendSysStateStatusMsg(hostAddr);
            return;
        }
        if (cmd == kSysStateStateChangeReq && len >= sizeof(SysStateChangeReq)) {
            const uint32_t reqStates = readLe32(sdu + 8u);
            const uint32_t statesStatus = readLe32(sdu + 12u);
            lastSysStateReq_ = reqStates;
            // Matches ISH.sys fcn.140008ee0 -> 0x14001a9ac -> 0x14001b41d..447:
            // Func 1 with 4 zero bytes {0, 0, 0, 0}.
            if ((reqStates & kSysStateConnectedStandbyBit) != 0u &&
                (statesStatus & kSysStateConnectedStandbyBit) == 0u) {
                DsmWorkItem item {};
                item.valid = true;
                item.hostAddr = hostAddr;
                item.subCmd = 0u;
                item.funcIndex = 1u;
                item.argLen = 4u;
                memset(item.args, 0, 4u);
                pushDsmWork(item);
            }
            sendSysStateStatusMsg(hostAddr);
        }
    }

    void handleDsmProxyMessage(uint8_t hostAddr, const uint8_t *sdu, size_t len) {
        fixedClientsSeen_ |= (1u << kDsmProxyFwAddr);
        if (sdu == nullptr || len < sizeof(DsmExecHdr) || len > kIshtpMaxFragPayload) {
            return;
        }
        const uint32_t cmd = readLe32(sdu);
        const uint32_t status = readLe32(sdu + 4u);
        const uint32_t subCmd = readLe32(sdu + 8u);
        if (cmd != kDsmCmdExec || status != 0u) {
            return;
        }
        // Matches ISH.sys 0x1400097d0 -> 0x14001a894 -> 0x14001b1da..1ff: sub_cmd=4 -> Func 2 (1B).
        if (subCmd == kDsmSubFunc2 && len >= 13u) {
            DsmWorkItem item {};
            item.valid = true;
            item.hostAddr = hostAddr;
            item.subCmd = subCmd;
            item.funcIndex = 2u;
            item.argLen = 1u;
            item.args[0] = sdu[12];
            pushDsmWork(item);
        } else if (subCmd == kDsmSubFunc3 && len >= 21u) {
            DsmWorkItem item {};
            item.valid = true;
            item.hostAddr = hostAddr;
            item.subCmd = subCmd;
            item.funcIndex = 3u;
            item.argLen = 9u;
            memcpy(item.args, sdu + 12u, 9u);
            pushDsmWork(item);
        }
    }

    bool queryNextClientProps(uint64_t nowNs) {
        while (nextClientQuery_ < 256u) {
            const uint16_t addr = nextClientQuery_++;
            if ((validClients_[addr >> 3] & (1u << (addr & 7u))) != 0u) {
                HbmPropsReq req { kHbmHostClientPropsReq, static_cast<uint8_t>(addr), { 0u, 0u } };
                enqueueIshtp(0u, 0u, reinterpret_cast<const uint8_t *>(&req), sizeof(req));
                enterStage(Stage::HbmPropsLoop, nowNs);
                return true;
            }
        }
        return false;
    }

    void handleHbmMessage(const uint8_t *sdu, size_t len, uint64_t nowNs) {
        if (len < 4u) {
            return;
        }
        const uint8_t cmd = sdu[0];

        if (cmd == kHbmHostStartRes && stage_ == Stage::HbmVersionWait) {
            const uint8_t supported = sdu[1];
            if (supported == 0u) {
                failWith("HBM version unsupported");
                return;
            }
            HbmEnumReq req { kHbmHostEnumReq, { 0u, 0u, 0u } };
            enqueueIshtp(0u, 0u, reinterpret_cast<const uint8_t *>(&req), sizeof(req));
            enterStage(Stage::HbmEnumWait, nowNs);
            return;
        }

        if (cmd == kHbmHostEnumRes && stage_ == Stage::HbmEnumWait) {
            if (len < sizeof(HbmEnumRes)) {
                failWith("HBM enum response too short");
                return;
            }
            memcpy(validClients_, sdu + 4, sizeof(validClients_));
            nextClientQuery_ = 1;
            if (!queryNextClientProps(nowNs)) {
                failWith("HBM enum returned zero clients");
                return;
            }
            if (dsmEnabled_ && !dsmInitSent_) {
                sendDsmInitMsg();
            }
            return;
        }

        if (cmd == kHbmHostClientPropsRes && stage_ == Stage::HbmPropsLoop) {
            const uint8_t addr = sdu[1];
            const uint8_t status = sdu[2];
            if (status == 0u && len >= sizeof(HbmPropsRes)) {
                IshtpClientProps props {};
                memcpy(&props, sdu + 4, sizeof(props));
                if (memcmp(props.guid, kIshHidClientGuid, 16u) == 0 && hidFwAddr_ == 0u) {
                    hidFwAddr_ = addr;
                    uint32_t m = readLe32(reinterpret_cast<const uint8_t *>(&props.max_msg_length));
                    if (m < 6u) m = 6u;
                    if (m > kIshtpMaxMsgBytes) m = static_cast<uint32_t>(kIshtpMaxMsgBytes);
                    hidMaxMsg_ = m;
                }
            }
            if (!queryNextClientProps(nowNs)) {
                if (hidFwAddr_ != 0u) {
                    HbmClientCmd conn {};
                    conn.cmd = kHbmClientConnectReq;
                    conn.fw_addr = hidFwAddr_;
                    conn.host_addr = kHidHostAddr;
                    conn.status_or_rsv = 0u;
                    enqueueIshtp(0u, 0u, reinterpret_cast<const uint8_t *>(&conn), 4u);
                    enterStage(Stage::HidConnectWait, nowNs);
                } else {
                    failWith("ISH HID client GUID not found");
                }
            }
            return;
        }

        if (cmd == kHbmFlowControl && len >= 4u) {
            const uint8_t fwAddr = sdu[1];
            const uint8_t hostAddr = sdu[2];
            if (hidConnected_ && fwAddr == hidFwAddr_ && hostAddr == kHidHostAddr) {
                ++hidFlowCtrlRxCount_;
                if (hidTxCredits_ < 255u) {
                    ++hidTxCredits_;
                }
                flushPendingHidTx();
            }
            return;
        }

        if (cmd == kHbmClientConnectRes && stage_ == Stage::HidConnectWait) {
            const uint8_t fwAddr = sdu[1];
            const uint8_t hostAddr = sdu[2];
            const uint8_t status = sdu[3];
            if (fwAddr == hidFwAddr_ && hostAddr == kHidHostAddr && status == 0u) {
                hidConnected_ = true;
                hidTxCredits_ = 0u;
                hidTxPending_ = false;
                hidTxPendingLen_ = 0u;
                // Grant initial RX flow credit upon connect.
                sendFlowControl(hidFwAddr_, kHidHostAddr);
                // Queue HOSTIF_DM_ENUM_DEVICES (held until FW sends 0x08 TX credit).
                sendHostifSimple(kHostifDmEnumDevices, 0u, nullptr, 0u);
                enterStage(Stage::HidEnumWait, nowNs);
            } else {
                failWith("HID client connect failed");
            }
        }
    }

    void flushPendingHidTx() {
        if (!hidConnected_ || !hidTxPending_ || hidTxCredits_ == 0u) {
            return;
        }
        if (enqueueIshtp(hidFwAddr_, kHidHostAddr, hidTxPendingBuf_, hidTxPendingLen_)) {
            --hidTxCredits_;
            hidTxPending_ = false;
            hidTxPendingLen_ = 0u;
        }
    }

    void sendHostifSimple(uint8_t command, uint8_t devId, const uint8_t *payload, size_t payloadLen,
                          bool zeroHdrSize = false) {
        if (sizeof(HostifMsgHdr) + payloadLen > sizeof(hidTxPendingBuf_)) {
            return;
        }
        HostifMsgHdr hdr {};
        hdr.command = command;
        hdr.device_id = devId;
        hdr.status = 0u;
        hdr.flags = 0u;
        const uint16_t wireSize = zeroHdrSize ? 0u : static_cast<uint16_t>(payloadLen);
        writeLe16(reinterpret_cast<uint8_t *>(&hdr.size), wireSize);
        memcpy(hidTxPendingBuf_, &hdr, sizeof(hdr));
        if (payloadLen > 0 && payload != nullptr) {
            memcpy(hidTxPendingBuf_ + sizeof(hdr), payload, payloadLen);
        }
        hidTxPendingLen_ = sizeof(hdr) + payloadLen;
        hidTxPending_ = true;
        flushPendingHidTx();
    }

    void requestNextHidDevice(uint64_t nowNs) {
        if (descIndex_ < hidDevCount_) {
            sendHostifSimple(kHostifGetHidDescriptor, hidDevIds_[descIndex_], nullptr, 0u);
            enterStage(Stage::HidDescHidWait, nowNs);
        } else if (alsDesc_.found) {
            if (alsDesc_.powerState.present || alsDesc_.reportState.present) {
                featGetAttempts_ = 1u;
                featUseZeroHdrSize_ = false;
                featSetZeroHdrSize_ = false;
                featRetryDueNs_ = 0ULL;
                featSetZeroHdrRetry_ = false;
                featRetryPowerOnly_ = false;
                sendHostifSimple(kHostifGetFeatureReport, alsDevId_, &alsDesc_.featureReportId, 1u, false);
                enterStage(Stage::AlsFeatGet, nowNs);
            } else {
                sendHostifSimple(kHostifGetInputReport, alsDevId_, &alsDesc_.inputReportId, 1u);
                enterStage(Stage::AlsPrimeInput, nowNs);
            }
        } else {
            enterStage(Stage::NoAlsSensor, nowNs);
        }
    }

    void handleHidSdu(const uint8_t *sdu, size_t len, uint64_t nowNs) {
        // Walk concatenated HostIF messages inside a single assembled ISHTP SDU.
        size_t offset = 0;
        while (offset + sizeof(HostifMsgHdr) <= len) {
            HostifMsgHdr hdr {};
            memcpy(&hdr, sdu + offset, sizeof(hdr));
            const uint16_t declaredSize = readLe16(reinterpret_cast<const uint8_t *>(&hdr.size));
            const size_t payloadOffset = offset + sizeof(HostifMsgHdr);
            const size_t avail = len - payloadOffset;
            const size_t payloadLen = (static_cast<size_t>(declaredSize) <= avail) ? static_cast<size_t>(declaredSize) : avail;

            dispatchSingleHostif(hdr, sdu + payloadOffset, payloadLen, declaredSize, avail, nowNs);

            if (payloadLen == 0 && declaredSize > avail) {
                break;
            }
            offset = payloadOffset + payloadLen;
        }
    }

    void dispatchSingleHostif(const HostifMsgHdr &hdr, const uint8_t *payload, size_t payloadLen,
                              uint16_t declaredSize, size_t avail, uint64_t nowNs) {
        const uint8_t baseCmd = static_cast<uint8_t>(hdr.command & 0x7Fu);
        const bool isResp = (hdr.command & kHostifIsResponse) != 0u;
        if (isResp && alsDesc_.found && hdr.device_id == alsDevId_) {
            lastHostifCmd_ = baseCmd;
            lastHostifStatus_ = hdr.status;
            lastHostifLen_ = static_cast<uint16_t>(payloadLen);
        }

        if (baseCmd == kHostifDmEnumDevices && isResp && stage_ == Stage::HidEnumWait) {
            if (hdr.status != 0u || payloadLen < 1u + sizeof(HidDeviceInfo)) {
                failWith("DM_ENUM_DEVICES failed or empty");
                return;
            }
            const uint8_t cnt = payload[0];
            if (cnt == 0u || cnt > kMaxHidDevices ||
                1u + static_cast<size_t>(cnt) * sizeof(HidDeviceInfo) > payloadLen) {
                failWith("DM_ENUM_DEVICES invalid count");
                return;
            }
            hidDevCount_ = cnt;
            hidDevListLen_ = static_cast<uint16_t>(static_cast<size_t>(cnt) * sizeof(HidDeviceInfo));
            memcpy(hidDevListBuf_, payload + 1u, hidDevListLen_);
            for (size_t i = 0; i < static_cast<size_t>(cnt); ++i) {
                const uint32_t devId = readLe32(payload + 1u + i * sizeof(HidDeviceInfo));
                hidDevIds_[i] = static_cast<uint8_t>(devId & 0xFFu);
            }
            descIndex_ = 0;
            requestNextHidDevice(nowNs);
            return;
        }

        if (baseCmd == kHostifGetHidDescriptor && isResp && stage_ == Stage::HidDescHidWait) {
            if (descIndex_ < hidDevCount_ && hdr.device_id == hidDevIds_[descIndex_]) {
                if (hdr.status != 0u) {
                    ++descIndex_;
                    requestNextHidDevice(nowNs);
                } else {
                    sendHostifSimple(kHostifGetReportDescriptor, hidDevIds_[descIndex_], nullptr, 0u);
                    enterStage(Stage::HidDescRptWait, nowNs);
                }
            }
            return;
        }

        if (baseCmd == kHostifGetReportDescriptor && isResp && stage_ == Stage::HidDescRptWait) {
            if (descIndex_ < hidDevCount_ && hdr.device_id == hidDevIds_[descIndex_]) {
                AlsDescriptorInfo parsed {};
                if (!alsDesc_.found && hdr.status == 0u && payloadLen > 0 &&
                    parseAlsReportDescriptor(payload, payloadLen, parsed)) {
                    alsDevId_ = hidDevIds_[descIndex_];
                    alsDesc_ = parsed;
                    alsDescSliceLen_ = 0u;
                    if (alsDesc_.alsCollectionByteOffset < payloadLen) {
                        const size_t sliceAvail = payloadLen - static_cast<size_t>(alsDesc_.alsCollectionByteOffset);
                        size_t want = (alsDesc_.alsCollectionByteLen > 0u)
                            ? static_cast<size_t>(alsDesc_.alsCollectionByteLen)
                            : sliceAvail;
                        if (want > sliceAvail) {
                            want = sliceAvail;
                        }
                        saveFeatureBytes(alsDescSlice_, alsDescSliceLen_,
                                         payload + alsDesc_.alsCollectionByteOffset, want);
                    }
                }
                ++descIndex_;
                requestNextHidDevice(nowNs);
            }
            return;
        }

        if (baseCmd == kHostifGetFeatureReport && isResp && hdr.device_id == alsDevId_) {
            const bool idMatches = (alsDesc_.featureReportId == 0u) ||
                                   (payloadLen > 0u && payload[0] == alsDesc_.featureReportId);
            const bool lenMatches = (alsDesc_.featureByteLen > 0u)
                ? (payloadLen >= alsDesc_.featureByteLen)
                : (payloadLen > 0u);
            const bool payloadUsable = idMatches && lenMatches &&
                (hdr.status == 0u || (alsDesc_.featureByteLen > 0u && payloadLen >= alsDesc_.featureByteLen));

            if (stage_ == Stage::AlsFeatGet) {
                featGetStatus_ = hdr.status;
                featGetFlags_ = hdr.flags;
                featGetDeclaredSize_ = declaredSize;
                featGetAvailLen_ = static_cast<uint16_t>(avail);
                memcpy(featGetHdr_, &hdr, sizeof(featGetHdr_));
                featGetHdrValid_ = true;

                if (!payloadUsable) {
                    if (featGetAttempts_ < kMaxFeatGetAttempts) {
                        featUseZeroHdrSize_ = !featUseZeroHdrSize_;
                        featRetryDueNs_ = nowNs + kFeatRetryDelayNs;
                        stageStartNs_ = nowNs;
                        return;
                    }
                    fallbackToPrimeInput("GET_FEATURE_REPORT rejected after retries; polling input directly", nowNs);
                    return;
                }
                featRetryDueNs_ = 0ULL;
                featSetZeroHdrSize_ = featUseZeroHdrSize_;
                saveFeatureBytes(origFeatBuf_, origFeatLen_, payload, payloadLen);
                uint8_t featBuf[kMaxFeatureReportBytes] {};
                const size_t copyLen = (payloadLen <= sizeof(featBuf)) ? payloadLen : sizeof(featBuf);
                memcpy(featBuf, payload, copyLen);
                bool rmwOk = applyAlsFeatureRmw(alsDesc_, featBuf, copyLen, &alsIntervalMs_, &alsSensitivity_);
                if (rmwOk) {
                    featRetryPowerOnly_ = false;
                } else {
                    memcpy(featBuf, payload, copyLen);
                    rmwOk = applyAlsFeaturePowerOnlyRmw(alsDesc_, featBuf, copyLen);
                    if (rmwOk) {
                        featRetryPowerOnly_ = true;
                    }
                }
                if (!rmwOk) {
                    fallbackToPrimeInput("ALS feature RMW failed; polling input directly", nowNs);
                    return;
                }
                saveFeatureBytes(reqFeatBuf_, reqFeatLen_, featBuf, copyLen);
                sendHostifSimple(kHostifSetFeatureReport, alsDevId_, featBuf, copyLen, featSetZeroHdrSize_);
                enterStage(Stage::AlsFeatSet, nowNs);
                return;
            }
            if (stage_ == Stage::AlsFeatVerify) {
                featVerifyStatus_ = hdr.status;
                featVerifySeen_ = true;
                if (payloadUsable) {
                    saveFeatureBytes(curFeatBuf_, curFeatLen_, payload, payloadLen);
                    alsControlsVerified_ = verifyAlsFeatureControls(
                        alsDesc_, payload, payloadLen, &alsIntervalMs_, &alsSensitivity_, !featRetryPowerOnly_);
                    if (!alsControlsVerified_ && !featRetryPowerOnly_) {
                        alsControlsVerified_ = verifyAlsFeatureControls(
                            alsDesc_, payload, payloadLen, &alsIntervalMs_, &alsSensitivity_, false);
                    }
                    if (alsControlsVerified_) {
                        featureError_[0] = '\0';
                    } else if (featureError_[0] == '\0') {
                        setFeatureError("ALS feature verify mismatch");
                    }
                } else if (featureError_[0] == '\0') {
                    setFeatureError("ALS feature verify rejected");
                }
                sendHostifSimple(kHostifGetInputReport, alsDevId_, &alsDesc_.inputReportId, 1u);
                enterStage(Stage::AlsPrimeInput, nowNs);
                return;
            }
        }

        if (baseCmd == kHostifSetFeatureReport && isResp && hdr.device_id == alsDevId_ && stage_ == Stage::AlsFeatSet) {
            featSetStatus_ = hdr.status;
            featSetFlags_ = hdr.flags;
            if (hdr.status != 0u) {
                if (!featRetryPowerOnly_ && origFeatLen_ > 0u) {
                    featRetryPowerOnly_ = true;
                    uint8_t featBuf[kMaxFeatureReportBytes] {};
                    const size_t copyLen = (origFeatLen_ <= sizeof(featBuf)) ? origFeatLen_ : sizeof(featBuf);
                    memcpy(featBuf, origFeatBuf_, copyLen);
                    if (applyAlsFeaturePowerOnlyRmw(alsDesc_, featBuf, copyLen)) {
                        saveFeatureBytes(reqFeatBuf_, reqFeatLen_, featBuf, copyLen);
                        sendHostifSimple(kHostifSetFeatureReport, alsDevId_, featBuf, copyLen, featSetZeroHdrSize_);
                        enterStage(Stage::AlsFeatSet, nowNs);
                        return;
                    }
                }
                if (!featSetZeroHdrRetry_ && reqFeatLen_ > 0u) {
                    featSetZeroHdrRetry_ = true;
                    featSetZeroHdrSize_ = !featSetZeroHdrSize_;
                    sendHostifSimple(kHostifSetFeatureReport, alsDevId_, reqFeatBuf_, reqFeatLen_, featSetZeroHdrSize_);
                    enterStage(Stage::AlsFeatSet, nowNs);
                    return;
                }
                setFeatureError("SET_FEATURE_REPORT non-zero status; verifying readback");
            }
            sendHostifSimple(kHostifGetFeatureReport, alsDevId_, &alsDesc_.featureReportId, 1u, featUseZeroHdrSize_);
            enterStage(Stage::AlsFeatVerify, nowNs);
            return;
        }

        if (baseCmd == kHostifGetInputReport && isResp && hdr.device_id == alsDevId_) {
            if (stage_ == Stage::AlsPrimeInput) {
                enterStage(Stage::Streaming, nowNs);
                lastSampleRxNs_ = nowNs;
                lastHeartbeatTxNs_ = nowNs;
            }
            if (hdr.status == 0u && payloadLen > 0) {
                ++getInputRespCount_;
                processInputReportPayload(hdr.device_id, payload, payloadLen, nowNs);
            }
            return;
        }

        if (baseCmd == kHostifPublishInputReport) {
            if (hdr.status == 0u && payloadLen > 0) {
                if (hdr.device_id == alsDevId_) {
                    ++publishReportCount_;
                }
                processInputReportPayload(hdr.device_id, payload, payloadLen, nowNs);
            }
            return;
        }

        if (baseCmd == kHostifPublishInputReportList) {
            processReportList(payload, payloadLen, nowNs);
        }
    }

    void processInputReportPayload(uint8_t devId, const uint8_t *payload, size_t len, uint64_t nowNs) {
        if (!alsDesc_.found || devId != alsDevId_) {
            return;
        }
        uint32_t raw = 0;
        uint64_t mLux = 0;
        uint32_t fLux = kSmcLuxInvalid;
        if (decodeAlsInputReport(alsDesc_, payload, len, raw, mLux, fLux)) {
            rawIllum_ = raw;
            milliLux_ = mLux;
            fixedLux_ = fLux;
            lastSampleRxNs_ = nowNs;
            ++sampleCount_;
            sampleUpdated_ = true;
        }
    }

    void processReportList(const uint8_t *payload, size_t payloadLen, uint64_t nowNs) {
        if (payload == nullptr || payloadLen < sizeof(HidReportListHdr)) {
            return;
        }
        const uint8_t numReports = payload[2];
        size_t cursor = sizeof(HidReportListHdr);
        for (uint8_t i = 0; i < numReports; ++i) {
            if (cursor + sizeof(HidReportListItem) > payloadLen) {
                break;
            }
            const uint16_t itemSize = readLe16(payload + cursor);
            if (itemSize < sizeof(HostifMsgHdr) ||
                cursor + sizeof(uint16_t) + static_cast<size_t>(itemSize) > payloadLen) {
                break;
            }
            HostifMsgHdr msg {};
            memcpy(&msg, payload + cursor + sizeof(uint16_t), sizeof(HostifMsgHdr));
            uint16_t msgDataLen = readLe16(reinterpret_cast<const uint8_t *>(&msg.size));
            if (msgDataLen == 0u) {
                msgDataLen = static_cast<uint16_t>(itemSize - sizeof(HostifMsgHdr));
            }
            const size_t dataOffset = cursor + sizeof(HidReportListItem);
            if (dataOffset + static_cast<size_t>(msgDataLen) > payloadLen ||
                sizeof(HostifMsgHdr) + static_cast<size_t>(msgDataLen) > static_cast<size_t>(itemSize)) {
                break;
            }
            const uint8_t baseCmd = static_cast<uint8_t>(msg.command & 0x7Fu);
            if ((baseCmd == kHostifPublishInputReport || baseCmd == kHostifGetInputReport) && msg.status == 0u) {
                if (msg.device_id == alsDevId_) {
                    if (baseCmd == kHostifPublishInputReport) {
                        ++publishReportCount_;
                    } else {
                        ++getInputRespCount_;
                    }
                }
                processInputReportPayload(msg.device_id, payload + dataOffset, msgDataLen, nowNs);
            }
            cursor += sizeof(uint16_t) + static_cast<size_t>(itemSize);
        }
    }
};

} // namespace ish

#endif // TGLISH_PROTOCOL_HPP
