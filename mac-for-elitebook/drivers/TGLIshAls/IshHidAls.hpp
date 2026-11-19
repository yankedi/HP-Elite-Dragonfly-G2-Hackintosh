// SPDX-License-Identifier: BSD-3-Clause
// Clean-room HID Sensor Report Descriptor Parser & ALS Lux Converter

#ifndef TGLISH_HID_ALS_HPP
#define TGLISH_HID_ALS_HPP

#include <stddef.h>
#include <stdint.h>
#include <string.h>

namespace ish {

// HID Sensor Usage IDs (Sensor page 0x20)
static constexpr uint32_t kUsageSensorPage               = 0x20u;
static constexpr uint32_t kUsageSensorAls                = 0x200041u;
static constexpr uint32_t kUsageSensorPropReportIntvl    = 0x20030Eu;
static constexpr uint32_t kUsageSensorPropSensitivityAbs = 0x20030Fu;
static constexpr uint32_t kUsageSensorPropSensitivityPct = 0x200310u;
static constexpr uint32_t kUsageSensorPropSensitivityRel = 0x200311u;
static constexpr uint32_t kUsageSensorPropReportState    = 0x200316u;
static constexpr uint32_t kUsageSensorPropPowerState     = 0x200319u;
static constexpr uint32_t kUsageSensorLightIllum         = 0x2004D1u;

static constexpr uint32_t kUsageSensorDataModMask        = 0xF000u;
static constexpr uint32_t kUsageSensorModSensitivityAbs  = 0x1000u;
static constexpr uint32_t kUsageSensorModSensitivityPct  = 0xE000u;

static constexpr uint32_t kDefaultAlsIntervalMs          = 250u;
static constexpr uint32_t kMaxAlsIntervalMs              = 1000u;
static constexpr uint32_t kDefaultAlsSensitivityRaw      = 1u;
static constexpr uint64_t kDefaultAlsDarkThresholdMLux   = 50000ULL;

inline bool isAlsDarkPermissive(bool sampleValid, uint64_t milliLux,
                                uint64_t thresholdMilliLux = kDefaultAlsDarkThresholdMLux) {
    return sampleValid && (milliLux <= thresholdMilliLux);
}

// HID Sensor Enum Selector Usages
static constexpr uint32_t kUsageSelReportAllEvents     = 0x200841u;
static constexpr uint32_t kUsageSelPowerD0Full         = 0x200851u;

// Sensor Units
static constexpr uint32_t kUnitSensorDefault           = 0x00u;
static constexpr uint32_t kUnitSensorLux               = 0x01u;

// SMC Constants
static constexpr uint32_t kSmcLuxInvalid               = 0xFFFFFFFFu;
static constexpr uint64_t kMaxRepresentableMilliLux    = 262143999ULL;

enum : uint8_t {
    kForceScale    = 1u << 0,
    kForceChan     = 1u << 1,
    kForceLux      = 1u << 2,
    kForceHighGain = 1u << 3,
    kForceTemp     = 1u << 4,
};

enum HidReportKind : uint8_t {
    kHidReportInput   = 0,
    kHidReportOutput  = 1,
    kHidReportFeature = 2,
};

struct HidBitField {
    bool     present     = false;
    uint8_t  reportId    = 0;
    uint32_t bitOffset   = 0;
    uint32_t bitWidth    = 0;
    int32_t  logicalMin  = 0;
    int32_t  logicalMax  = 0;
    uint32_t targetVal   = 0;
    uint32_t unit        = 0;
    uint8_t  unitExpoRaw = 0;
};

struct AlsDescriptorInfo {
    bool        found                = false;
    uint8_t     inputReportId        = 0;
    uint32_t    inputByteLen         = 0;
    uint32_t    illumBitOffset       = 0;
    uint32_t    illumBitWidth        = 0;
    uint32_t    unit                 = 0;
    uint8_t     unitExpoRaw          = 0;
    int32_t     logicalMin           = 0;
    int32_t     logicalMax           = 0;

    uint8_t     featureReportId      = 0;
    uint32_t    featureByteLen       = 0;
    uint32_t    alsCollectionByteOffset = 0;
    uint32_t    alsCollectionByteLen    = 0;
    HidBitField powerState;
    HidBitField reportState;
    HidBitField reportInterval;
    HidBitField sensitivity;
    bool        sensitivityIsPct     = false;
};

inline uint16_t readLe16(const uint8_t *p) {
    return static_cast<uint16_t>(p[0]) | (static_cast<uint16_t>(p[1]) << 8);
}

inline uint32_t readLe32(const uint8_t *p) {
    return static_cast<uint32_t>(p[0]) |
           (static_cast<uint32_t>(p[1]) << 8) |
           (static_cast<uint32_t>(p[2]) << 16) |
           (static_cast<uint32_t>(p[3]) << 24);
}

inline void writeLe16(uint8_t *p, uint16_t v) {
    p[0] = static_cast<uint8_t>(v & 0xFFu);
    p[1] = static_cast<uint8_t>((v >> 8) & 0xFFu);
}

inline void writeLe32(uint8_t *p, uint32_t v) {
    p[0] = static_cast<uint8_t>(v & 0xFFu);
    p[1] = static_cast<uint8_t>((v >> 8) & 0xFFu);
    p[2] = static_cast<uint8_t>((v >> 16) & 0xFFu);
    p[3] = static_cast<uint8_t>((v >> 24) & 0xFFu);
}

inline void writeBe16(uint8_t *p, uint16_t v) {
    p[0] = static_cast<uint8_t>((v >> 8) & 0xFFu);
    p[1] = static_cast<uint8_t>(v & 0xFFu);
}

inline void writeBe32(uint8_t *p, uint32_t v) {
    p[0] = static_cast<uint8_t>((v >> 24) & 0xFFu);
    p[1] = static_cast<uint8_t>((v >> 16) & 0xFFu);
    p[2] = static_cast<uint8_t>((v >> 8) & 0xFFu);
    p[3] = static_cast<uint8_t>(v & 0xFFu);
}

inline bool extractUnsignedBits(const uint8_t *buf, size_t bufLen, uint32_t bitOffset, uint32_t bitWidth, uint32_t &outVal) {
    if (buf == nullptr || bitWidth == 0 || bitWidth > 32u) {
        return false;
    }
    const uint64_t endBit = static_cast<uint64_t>(bitOffset) + static_cast<uint64_t>(bitWidth);
    if (endBit > static_cast<uint64_t>(bufLen) * 8ULL) {
        return false;
    }
    uint64_t acc = 0;
    for (uint32_t b = 0; b < bitWidth; ++b) {
        const uint32_t pos = bitOffset + b;
        if ((buf[pos >> 3] & (1u << (pos & 7u))) != 0u) {
            acc |= (1ULL << b);
        }
    }
    outVal = static_cast<uint32_t>(acc);
    return true;
}

inline bool writeBits(uint8_t *buf, size_t bufLen, uint32_t bitOffset, uint32_t bitWidth, uint32_t val) {
    if (buf == nullptr || bitWidth == 0 || bitWidth > 32u) {
        return false;
    }
    const uint64_t endBit = static_cast<uint64_t>(bitOffset) + static_cast<uint64_t>(bitWidth);
    if (endBit > static_cast<uint64_t>(bufLen) * 8ULL) {
        return false;
    }
    for (uint32_t b = 0; b < bitWidth; ++b) {
        const uint32_t pos = bitOffset + b;
        const uint8_t mask = static_cast<uint8_t>(1u << (pos & 7u));
        if (((val >> b) & 1u) != 0u) {
            buf[pos >> 3] |= mask;
        } else {
            buf[pos >> 3] &= static_cast<uint8_t>(~mask);
        }
    }
    return true;
}

inline int decodeUnitExponent(uint8_t rawExpo) {
    const uint8_t nibble = static_cast<uint8_t>(rawExpo & 0xFu);
    return (nibble & 0x8u) ? (static_cast<int>(nibble) - 16) : static_cast<int>(nibble);
}

inline uint64_t rawToMilliLux(uint32_t raw, uint8_t unitExpoRaw) {
    const int expo = decodeUnitExponent(unitExpoRaw);
    const int scalePow = expo + 3; // lux * 10^3 = milliLux -> exponent + 3 in [-5, +10]
    if (scalePow >= 0) {
        uint64_t val = static_cast<uint64_t>(raw);
        for (int i = 0; i < scalePow; ++i) {
            if (val > UINT64_MAX / 10ULL) {
                return UINT64_MAX;
            }
            val *= 10ULL;
        }
        return val;
    }
    uint64_t denom = 1ULL;
    const int negPow = -scalePow;
    for (int i = 0; i < negPow; ++i) {
        denom *= 10ULL;
    }
    return static_cast<uint64_t>(raw) / denom;
}

inline uint32_t milliLuxToSmcFp1814(uint64_t milliLux) {
    if (milliLux > kMaxRepresentableMilliLux) {
        return kSmcLuxInvalid - 1u;
    }
    uint64_t fixed = (milliLux * 16384ULL) / 1000ULL;
    if (fixed >= static_cast<uint64_t>(kSmcLuxInvalid)) {
        return kSmcLuxInvalid - 1u;
    }
    return static_cast<uint32_t>(fixed);
}

inline bool shouldPostAlsChange(bool wasValid, uint64_t lastPostedMilliLux, bool nowValid, uint64_t newMilliLux) {
    if (!nowValid) {
        return wasValid;
    }
    if (!wasValid) {
        return true;
    }
    const uint64_t diff = (newMilliLux >= lastPostedMilliLux)
        ? (newMilliLux - lastPostedMilliLux)
        : (lastPostedMilliLux - newMilliLux);
    const uint64_t fivePct = lastPostedMilliLux / 20ULL;
    const uint64_t threshold = (fivePct > 500ULL) ? fivePct : 500ULL;
    return diff >= threshold;
}

inline void formatAlv0(uint8_t out[10], uint32_t fixedLux, uint8_t forceBits) {
    if (fixedLux == kSmcLuxInvalid) {
        out[0] = 0;
        return;
    }
    out[0] = 1; // valid
    if ((forceBits & kForceHighGain) == 0u) {
        out[1] = 1; // highGain
    }
    if ((forceBits & kForceChan) == 0u) {
        writeBe16(&out[2], static_cast<uint16_t>(fixedLux >> 14));
    }
    if ((forceBits & kForceLux) == 0u) {
        writeBe32(&out[6], fixedLux);
    }
}

namespace detail {

struct HidGlobalState {
    uint32_t usagePage   = 0;
    int32_t  logicalMin  = 0;
    int32_t  logicalMax  = 0;
    uint32_t unit        = 0;
    uint8_t  unitExpoRaw = 0;
    uint32_t reportSize  = 0;
    uint32_t reportId    = 0;
    uint32_t reportCount = 0;
};

struct HidLocalState {
    static constexpr size_t kMaxUsages = 64;
    uint32_t usages[kMaxUsages] {};
    size_t   usageCount   = 0;
    bool     hasUsageMin  = false;
    bool     hasUsageMax  = false;
    uint32_t usageMin     = 0;
    uint32_t usageMax     = 0;

    void reset() {
        usageCount = 0;
        hasUsageMin = false;
        hasUsageMax = false;
        usageMin = 0;
        usageMax = 0;
    }

    uint32_t resolveFieldUsage(uint32_t fieldIndex) const {
        if (usageCount > 0) {
            if (fieldIndex < usageCount) {
                return usages[fieldIndex];
            }
            if (hasUsageMin && hasUsageMax && usageMax >= usageMin) {
                const uint64_t offset = static_cast<uint64_t>(fieldIndex) - static_cast<uint64_t>(usageCount);
                const uint64_t cand = static_cast<uint64_t>(usageMin) + offset;
                return (cand <= usageMax) ? static_cast<uint32_t>(cand) : usageMax;
            }
            return usages[usageCount - 1];
        }
        if (hasUsageMin && hasUsageMax && usageMax >= usageMin) {
            const uint64_t cand = static_cast<uint64_t>(usageMin) + static_cast<uint64_t>(fieldIndex);
            return (cand <= usageMax) ? static_cast<uint32_t>(cand) : usageMax;
        }
        return 0;
    }

    bool findSelectorOffset(uint32_t targetUsage, uint32_t &outIdx) const {
        for (size_t i = 0; i < usageCount; ++i) {
            if (usages[i] == targetUsage) {
                outIdx = static_cast<uint32_t>(i);
                return true;
            }
        }
        if (hasUsageMin && hasUsageMax && usageMax >= usageMin &&
            targetUsage >= usageMin && targetUsage <= usageMax) {
            outIdx = static_cast<uint32_t>(usageCount) + (targetUsage - usageMin);
            return true;
        }
        return false;
    }
};

struct HidReportOffsetEntry {
    bool          used      = false;
    HidReportKind kind      = kHidReportInput;
    uint8_t       reportId  = 0;
    uint32_t      bitOffset = 0;
};

struct HidReportOffsetTable {
    static constexpr size_t kMaxEntries = 128;
    HidReportOffsetEntry entries[kMaxEntries] {};

    uint32_t *getOrCreate(HidReportKind kind, uint8_t reportId) {
        for (size_t i = 0; i < kMaxEntries; ++i) {
            if (entries[i].used && entries[i].kind == kind && entries[i].reportId == reportId) {
                return &entries[i].bitOffset;
            }
        }
        for (size_t i = 0; i < kMaxEntries; ++i) {
            if (!entries[i].used) {
                entries[i].used = true;
                entries[i].kind = kind;
                entries[i].reportId = reportId;
                entries[i].bitOffset = (reportId > 0) ? 8u : 0u;
                return &entries[i].bitOffset;
            }
        }
        return nullptr;
    }

    uint32_t getBits(HidReportKind kind, uint8_t reportId) const {
        for (size_t i = 0; i < kMaxEntries; ++i) {
            if (entries[i].used && entries[i].kind == kind && entries[i].reportId == reportId) {
                return entries[i].bitOffset;
            }
        }
        return (reportId > 0) ? 8u : 0u;
    }
};

inline int32_t signExtendItem(uint32_t raw, uint8_t dataLen) {
    if (dataLen == 1u) {
        return static_cast<int32_t>(static_cast<int8_t>(raw & 0xFFu));
    }
    if (dataLen == 2u) {
        return static_cast<int32_t>(static_cast<int16_t>(raw & 0xFFFFu));
    }
    if (dataLen == 4u) {
        return static_cast<int32_t>(raw);
    }
    return 0;
}

} // namespace detail

inline bool parseAlsReportDescriptor(const uint8_t *desc, size_t len, AlsDescriptorInfo &out) {
    out = AlsDescriptorInfo{};
    if (desc == nullptr || len == 0) {
        return false;
    }

    static constexpr size_t kMaxGlobalStack = 8;
    static constexpr size_t kMaxCollectionStack = 32;

    detail::HidGlobalState global {};
    detail::HidGlobalState globalStack[kMaxGlobalStack] {};
    size_t globalTop = 0;

    uint32_t collectionUsages[kMaxCollectionStack] {};
    size_t collectionDepth = 0;

    detail::HidLocalState local {};
    detail::HidReportOffsetTable offsets {};

    bool foundIllum = false;
    uint32_t alsDepth = 0; // 1-based depth when inside 0x200041, 0 when outside
    AlsDescriptorInfo candidate {};

    auto inAlsCollection = [&]() -> bool {
        return alsDepth > 0;
    };

    size_t pos = 0;
    while (pos < len) {
        const size_t itemStartPos = pos;
        const uint8_t b0 = desc[pos];
        if (b0 == 0xFEu) {
            // Long item: [0xFE, bDataSize, bLongItemTag, data...]
            if (pos + 3 > len) {
                return false;
            }
            const uint8_t dataLen = desc[pos + 1];
            if (pos + 3 + static_cast<size_t>(dataLen) > len) {
                return false;
            }
            pos += 3 + static_cast<size_t>(dataLen);
            continue;
        }

        const uint8_t sizeCode = b0 & 0x03u;
        const uint8_t dataLen = (sizeCode == 3u) ? 4u : sizeCode;
        const uint8_t itemType = (b0 >> 2) & 0x03u;
        const uint8_t itemTag = (b0 >> 4) & 0x0Fu;

        if (pos + 1 + static_cast<size_t>(dataLen) > len) {
            return false;
        }

        uint32_t uval = 0;
        for (uint8_t i = 0; i < dataLen; ++i) {
            uval |= static_cast<uint32_t>(desc[pos + 1 + i]) << (8u * i);
        }
        const int32_t sval = detail::signExtendItem(uval, dataLen);
        pos += 1 + static_cast<size_t>(dataLen);

        if (itemType == 1u) {
            // Global items
            switch (itemTag) {
                case 0x0u: global.usagePage = uval; break;
                case 0x1u: global.logicalMin = sval; break;
                case 0x2u: global.logicalMax = sval; break;
                case 0x5u: global.unitExpoRaw = static_cast<uint8_t>(uval & 0xFu); break;
                case 0x6u: global.unit = uval; break;
                case 0x7u: global.reportSize = uval; break;
                case 0x8u: global.reportId = uval & 0xFFu; break;
                case 0x9u: global.reportCount = uval; break;
                case 0xAu: // Push
                    if (globalTop < kMaxGlobalStack) {
                        globalStack[globalTop++] = global;
                    }
                    break;
                case 0xBu: // Pop
                    if (globalTop > 0) {
                        global = globalStack[--globalTop];
                    }
                    break;
                default:
                    break;
            }
        } else if (itemType == 2u) {
            // Local items
            uint32_t resolved = uval;
            if (dataLen < 4u) {
                resolved = (global.usagePage << 16) | (uval & 0xFFFFu);
            }
            switch (itemTag) {
                case 0x0u: // Usage
                    if (local.usageCount < detail::HidLocalState::kMaxUsages) {
                        local.usages[local.usageCount++] = resolved;
                    }
                    break;
                case 0x1u: // Usage Minimum
                    local.usageMin = resolved;
                    local.hasUsageMin = true;
                    break;
                case 0x2u: // Usage Maximum
                    local.usageMax = resolved;
                    local.hasUsageMax = true;
                    break;
                default:
                    break;
            }
        } else if (itemType == 0u) {
            // Main items
            if (itemTag == 0xAu) {
                // Collection
                const uint32_t colUsage = (local.usageCount > 0)
                    ? local.usages[local.usageCount - 1]
                    : ((local.hasUsageMin) ? local.usageMin : 0u);
                if (collectionDepth < kMaxCollectionStack) {
                    collectionUsages[collectionDepth] = colUsage;
                    ++collectionDepth;
                    if (alsDepth == 0 && colUsage == kUsageSensorAls && !foundIllum) {
                        alsDepth = static_cast<uint32_t>(collectionDepth);
                        candidate = AlsDescriptorInfo{};
                        candidate.alsCollectionByteOffset = static_cast<uint32_t>(itemStartPos);
                    }
                }
                local.reset();
            } else if (itemTag == 0xCu) {
                // End Collection
                if (collectionDepth > 0) {
                    if (alsDepth == static_cast<uint32_t>(collectionDepth)) {
                        if (!foundIllum) {
                            candidate = AlsDescriptorInfo{};
                        } else if (pos >= candidate.alsCollectionByteOffset) {
                            candidate.alsCollectionByteLen = static_cast<uint32_t>(pos - candidate.alsCollectionByteOffset);
                        }
                        alsDepth = 0;
                    }
                    --collectionDepth;
                }
                local.reset();
            } else if (itemTag == 0x8u || itemTag == 0x9u || itemTag == 0xBu) {
                // Input (0x8), Output (0x9), Feature (0xB)
                const HidReportKind kind = (itemTag == 0x8u)
                    ? kHidReportInput
                    : ((itemTag == 0x9u) ? kHidReportOutput : kHidReportFeature);
                const uint8_t reportId = static_cast<uint8_t>(global.reportId & 0xFFu);
                uint32_t *offsetPtr = offsets.getOrCreate(kind, reportId);
                if (offsetPtr == nullptr) {
                    local.reset();
                    continue;
                }
                const uint32_t startBit = *offsetPtr;
                const uint64_t totalBits = static_cast<uint64_t>(global.reportSize) * static_cast<uint64_t>(global.reportCount);
                *offsetPtr = startBit + static_cast<uint32_t>(totalBits);

                const bool isConstant = (uval & 0x01u) != 0u;
                const bool isVariable = (uval & 0x02u) != 0u;
                if (!isConstant && inAlsCollection() && global.reportSize > 0 && global.reportSize <= 32u && global.reportCount > 0) {
                    if (kind == kHidReportInput && isVariable) {
                        for (uint32_t idx = 0; idx < global.reportCount; ++idx) {
                            const uint32_t u = local.resolveFieldUsage(idx);
                            if (u == kUsageSensorLightIllum && !foundIllum) {
                                candidate.found = true;
                                candidate.inputReportId = reportId;
                                candidate.illumBitOffset = startBit + idx * global.reportSize;
                                candidate.illumBitWidth = global.reportSize;
                                candidate.unit = global.unit;
                                candidate.unitExpoRaw = global.unitExpoRaw;
                                candidate.logicalMin = global.logicalMin;
                                candidate.logicalMax = global.logicalMax;
                                foundIllum = true;
                                break;
                            }
                        }
                    } else if (kind == kHidReportFeature) {
                        const uint32_t parentColUsage = (collectionDepth > 0) ? collectionUsages[collectionDepth - 1] : 0u;

                        auto recordFeatureSelector = [&](HidBitField &dst, uint32_t fieldBitOffset, uint32_t selectorTarget) {
                            uint32_t selIdx = 0;
                            uint32_t computedVal = 0;
                            if (local.findSelectorOffset(selectorTarget, selIdx)) {
                                computedVal = static_cast<uint32_t>(global.logicalMin + static_cast<int32_t>(selIdx));
                            } else {
                                // Direct variable control without Named Array selectors: index 1 is D0 / All Events
                                const int32_t fallback = (global.logicalMin + 1 <= global.logicalMax)
                                    ? (global.logicalMin + 1)
                                    : global.logicalMin;
                                computedVal = static_cast<uint32_t>(fallback);
                            }
                            dst.present = true;
                            dst.reportId = reportId;
                            dst.bitOffset = fieldBitOffset;
                            dst.bitWidth = global.reportSize;
                            dst.logicalMin = global.logicalMin;
                            dst.logicalMax = global.logicalMax;
                            dst.targetVal = computedVal;
                            if (candidate.featureReportId == 0) {
                                candidate.featureReportId = reportId;
                            }
                        };

                        auto recordFeatureProp = [&](HidBitField &dst, uint32_t fieldBitOffset, uint32_t defaultTarget) {
                            dst.present = true;
                            dst.reportId = reportId;
                            dst.bitOffset = fieldBitOffset;
                            dst.bitWidth = global.reportSize;
                            dst.logicalMin = global.logicalMin;
                            dst.logicalMax = global.logicalMax;
                            dst.unit = global.unit;
                            dst.unitExpoRaw = global.unitExpoRaw;
                            dst.targetVal = defaultTarget;
                            if (candidate.featureReportId == 0) {
                                candidate.featureReportId = reportId;
                            }
                        };

                        auto isSensitivityUsage = [&](uint32_t u, bool &isPct) -> bool {
                            if (u == kUsageSensorPropSensitivityAbs) {
                                isPct = false;
                                return true;
                            }
                            if (u == kUsageSensorPropSensitivityPct || u == kUsageSensorPropSensitivityRel) {
                                isPct = true;
                                return true;
                            }
                            if ((u >> 16) == kUsageSensorPage) {
                                const uint32_t mod = u & kUsageSensorDataModMask;
                                const uint32_t base = u & 0x0FFFu;
                                if (base == (kUsageSensorLightIllum & 0x0FFFu) || base == 0u) {
                                    if (mod == kUsageSensorModSensitivityAbs) {
                                        isPct = false;
                                        return true;
                                    }
                                    if (mod == kUsageSensorModSensitivityPct) {
                                        isPct = true;
                                        return true;
                                    }
                                }
                            }
                            return false;
                        };

                        bool colSensPct = false;
                        if (parentColUsage == kUsageSensorPropPowerState && !candidate.powerState.present) {
                            recordFeatureSelector(candidate.powerState, startBit, kUsageSelPowerD0Full);
                        } else if (parentColUsage == kUsageSensorPropReportState && !candidate.reportState.present) {
                            recordFeatureSelector(candidate.reportState, startBit, kUsageSelReportAllEvents);
                        } else if (parentColUsage == kUsageSensorPropReportIntvl && !candidate.reportInterval.present) {
                            recordFeatureProp(candidate.reportInterval, startBit, kDefaultAlsIntervalMs);
                        } else if (isSensitivityUsage(parentColUsage, colSensPct) && !candidate.sensitivity.present) {
                            candidate.sensitivityIsPct = colSensPct;
                            const uint32_t defSens = (colSensPct && decodeUnitExponent(global.unitExpoRaw) == -2) ? 100u : kDefaultAlsSensitivityRaw;
                            recordFeatureProp(candidate.sensitivity, startBit, defSens);
                        } else {
                            for (uint32_t idx = 0; idx < global.reportCount; ++idx) {
                                const uint32_t u = local.resolveFieldUsage(idx);
                                bool fieldSensPct = false;
                                if (u == kUsageSensorPropPowerState && !candidate.powerState.present) {
                                    recordFeatureSelector(candidate.powerState, startBit + idx * global.reportSize, kUsageSelPowerD0Full);
                                } else if (u == kUsageSensorPropReportState && !candidate.reportState.present) {
                                    recordFeatureSelector(candidate.reportState, startBit + idx * global.reportSize, kUsageSelReportAllEvents);
                                } else if (u == kUsageSensorPropReportIntvl && !candidate.reportInterval.present) {
                                    recordFeatureProp(candidate.reportInterval, startBit + idx * global.reportSize, kDefaultAlsIntervalMs);
                                } else if (isSensitivityUsage(u, fieldSensPct) && !candidate.sensitivity.present) {
                                    candidate.sensitivityIsPct = fieldSensPct;
                                    const uint32_t defSens = (fieldSensPct && decodeUnitExponent(global.unitExpoRaw) == -2) ? 100u : kDefaultAlsSensitivityRaw;
                                    recordFeatureProp(candidate.sensitivity, startBit + idx * global.reportSize, defSens);
                                }
                            }
                        }
                    }
                }
                local.reset();
            } else {
                local.reset();
            }
        }
    }

    if (!foundIllum) {
        return false;
    }

    if (candidate.alsCollectionByteLen == 0u && candidate.alsCollectionByteOffset < len) {
        candidate.alsCollectionByteLen = static_cast<uint32_t>(len - candidate.alsCollectionByteOffset);
    }
    candidate.inputByteLen = (offsets.getBits(kHidReportInput, candidate.inputReportId) + 7u) / 8u;
    if (candidate.powerState.present) {
        candidate.featureReportId = candidate.powerState.reportId;
    } else if (candidate.reportState.present) {
        candidate.featureReportId = candidate.reportState.reportId;
    } else if (candidate.reportInterval.present) {
        candidate.featureReportId = candidate.reportInterval.reportId;
    } else if (candidate.sensitivity.present) {
        candidate.featureReportId = candidate.sensitivity.reportId;
    }
    if (candidate.powerState.present || candidate.reportState.present ||
        candidate.reportInterval.present || candidate.sensitivity.present) {
        candidate.featureByteLen = (offsets.getBits(kHidReportFeature, candidate.featureReportId) + 7u) / 8u;
    }

    out = candidate;
    return true;
}

inline uint32_t clampFieldTarget(const HidBitField &f, uint32_t desired) {
    int64_t val = static_cast<int64_t>(desired);
    const int64_t lo = (f.logicalMin > 0) ? static_cast<int64_t>(f.logicalMin) : 1LL;
    if (val < lo) {
        val = lo;
    }
    if (f.logicalMax >= lo && val > static_cast<int64_t>(f.logicalMax)) {
        val = static_cast<int64_t>(f.logicalMax);
    }
    if (f.bitWidth < 32u) {
        const uint64_t mask = (1ULL << f.bitWidth) - 1ULL;
        if (static_cast<uint64_t>(val) > mask) {
            val = static_cast<int64_t>(mask);
        }
    }
    return static_cast<uint32_t>(val);
}

inline bool applyAlsFeatureRmw(const AlsDescriptorInfo &desc, uint8_t *featureBuf, size_t featureLen,
                               uint32_t *outInterval = nullptr, uint32_t *outSensitivity = nullptr) {
    if (!desc.found || featureBuf == nullptr) {
        return false;
    }
    if (desc.featureReportId > 0 && (featureLen == 0 || featureBuf[0] != desc.featureReportId)) {
        return false;
    }
    if (desc.featureByteLen > 0 && featureLen < desc.featureByteLen) {
        return false;
    }
    bool modified = false;
    if (desc.powerState.present && desc.powerState.reportId == desc.featureReportId) {
        if (!writeBits(featureBuf, featureLen, desc.powerState.bitOffset, desc.powerState.bitWidth, desc.powerState.targetVal)) {
            return false;
        }
        modified = true;
    }
    if (desc.reportState.present && desc.reportState.reportId == desc.featureReportId) {
        if (!writeBits(featureBuf, featureLen, desc.reportState.bitOffset, desc.reportState.bitWidth, desc.reportState.targetVal)) {
            return false;
        }
        modified = true;
    }
    if (desc.reportInterval.present && desc.reportInterval.reportId == desc.featureReportId) {
        uint32_t curIntvl = 0;
        if (!extractUnsignedBits(featureBuf, featureLen, desc.reportInterval.bitOffset, desc.reportInterval.bitWidth, curIntvl)) {
            return false;
        }
        uint32_t nextIntvl = curIntvl;
        if (curIntvl == 0u || curIntvl > kMaxAlsIntervalMs) {
            nextIntvl = clampFieldTarget(desc.reportInterval, desc.reportInterval.targetVal);
            if (!writeBits(featureBuf, featureLen, desc.reportInterval.bitOffset, desc.reportInterval.bitWidth, nextIntvl)) {
                return false;
            }
            modified = true;
        }
        if (outInterval != nullptr) {
            *outInterval = nextIntvl;
        }
    }
    if (desc.sensitivity.present && desc.sensitivity.reportId == desc.featureReportId) {
        uint32_t curSens = 0;
        if (!extractUnsignedBits(featureBuf, featureLen, desc.sensitivity.bitOffset, desc.sensitivity.bitWidth, curSens)) {
            return false;
        }
        uint32_t nextSens = curSens;
        const int8_t exp = decodeUnitExponent(desc.sensitivity.unitExpoRaw);
        const uint32_t maxSens = (desc.sensitivityIsPct && exp == -2) ? 1000u : 50u; // <= 10% pct or <= 50 lux abs
        if (curSens > maxSens) {
            nextSens = clampFieldTarget(desc.sensitivity, desc.sensitivity.targetVal);
            if (!writeBits(featureBuf, featureLen, desc.sensitivity.bitOffset, desc.sensitivity.bitWidth, nextSens)) {
                return false;
            }
            modified = true;
        }
        if (outSensitivity != nullptr) {
            *outSensitivity = nextSens;
        }
    }
    return modified || desc.found;
}

inline bool applyAlsFeaturePowerOnlyRmw(const AlsDescriptorInfo &desc, uint8_t *featureBuf, size_t featureLen) {
    if (!desc.found || featureBuf == nullptr) {
        return false;
    }
    if (desc.featureReportId > 0 && (featureLen == 0 || featureBuf[0] != desc.featureReportId)) {
        return false;
    }
    if (desc.featureByteLen > 0 && featureLen < desc.featureByteLen) {
        return false;
    }
    bool modified = false;
    if (desc.powerState.present && desc.powerState.reportId == desc.featureReportId) {
        if (!writeBits(featureBuf, featureLen, desc.powerState.bitOffset, desc.powerState.bitWidth, desc.powerState.targetVal)) {
            return false;
        }
        modified = true;
    }
    if (desc.reportState.present && desc.reportState.reportId == desc.featureReportId) {
        if (!writeBits(featureBuf, featureLen, desc.reportState.bitOffset, desc.reportState.bitWidth, desc.reportState.targetVal)) {
            return false;
        }
        modified = true;
    }
    return modified || desc.found;
}

inline bool verifyAlsFeatureControls(const AlsDescriptorInfo &desc, const uint8_t *featureBuf, size_t featureLen,
                                     uint32_t *outInterval = nullptr, uint32_t *outSensitivity = nullptr,
                                     bool strictTuning = true) {
    if (!desc.found || featureBuf == nullptr) {
        return false;
    }
    if (desc.featureReportId > 0 && (featureLen == 0 || featureBuf[0] != desc.featureReportId)) {
        return false;
    }
    if (desc.powerState.present && desc.powerState.reportId == desc.featureReportId) {
        uint32_t v = 0;
        if (!extractUnsignedBits(featureBuf, featureLen, desc.powerState.bitOffset, desc.powerState.bitWidth, v)) {
            return false;
        }
        if (v != desc.powerState.targetVal) {
            return false;
        }
    }
    if (desc.reportState.present && desc.reportState.reportId == desc.featureReportId) {
        uint32_t v = 0;
        if (!extractUnsignedBits(featureBuf, featureLen, desc.reportState.bitOffset, desc.reportState.bitWidth, v)) {
            return false;
        }
        if (v != desc.reportState.targetVal) {
            return false;
        }
    }
    if (desc.reportInterval.present && desc.reportInterval.reportId == desc.featureReportId) {
        uint32_t v = 0;
        if (!extractUnsignedBits(featureBuf, featureLen, desc.reportInterval.bitOffset, desc.reportInterval.bitWidth, v)) {
            return false;
        }
        if (outInterval != nullptr) {
            *outInterval = v;
        }
        if (strictTuning && (v == 0u || v > kMaxAlsIntervalMs)) {
            return false;
        }
    }
    if (desc.sensitivity.present && desc.sensitivity.reportId == desc.featureReportId) {
        uint32_t v = 0;
        if (!extractUnsignedBits(featureBuf, featureLen, desc.sensitivity.bitOffset, desc.sensitivity.bitWidth, v)) {
            return false;
        }
        if (outSensitivity != nullptr) {
            *outSensitivity = v;
        }
        const int8_t exp = decodeUnitExponent(desc.sensitivity.unitExpoRaw);
        const uint32_t maxSens = (desc.sensitivityIsPct && exp == -2) ? 1000u : 50u;
        if (strictTuning && v > maxSens) {
            return false;
        }
    }
    return true;
}

inline bool decodeAlsInputReport(const AlsDescriptorInfo &desc, const uint8_t *reportBuf, size_t reportLen,
                                 uint32_t &outRaw, uint64_t &outMilliLux, uint32_t &outFixedLux) {
    if (!desc.found || reportBuf == nullptr || reportLen < desc.inputByteLen) {
        return false;
    }
    if (desc.inputReportId > 0 && (reportLen == 0 || reportBuf[0] != desc.inputReportId)) {
        return false;
    }
    if (!extractUnsignedBits(reportBuf, reportLen, desc.illumBitOffset, desc.illumBitWidth, outRaw)) {
        return false;
    }
    // Intentionally do not reject raw > logicalMax (Capella ALS sensors can exceed logicalMax).
    outMilliLux = rawToMilliLux(outRaw, desc.unitExpoRaw);
    outFixedLux = milliLuxToSmcFp1814(outMilliLux);
    return true;
}

} // namespace ish

#endif // TGLISH_HID_ALS_HPP
