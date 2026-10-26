#include "recordwire.hpp"

#include <cstring>
#include <utility>

namespace ga37 {
namespace recordwire {
namespace {

constexpr std::uint32_t kThagMagic = 0x47414854U;  // bytes "THAG"
constexpr std::uint32_t kFaultMagic = 0x34464754U; // bytes "TGF4"
constexpr std::size_t kThagV2Size = 0xc2a0U;
constexpr std::size_t kThagV3Size = 0xc2f8U;
constexpr std::size_t kFaultV1Size = 108U;
constexpr std::uint32_t kMaximumThagRecords = 3U;
constexpr std::uint32_t kMaximumFaultRecords = 8U;

std::uint16_t load16(const std::uint8_t *p) noexcept {
  return static_cast<std::uint16_t>(p[0]) |
         static_cast<std::uint16_t>(static_cast<std::uint16_t>(p[1]) << 8U);
}

std::uint32_t load32(const std::uint8_t *p) noexcept {
  return static_cast<std::uint32_t>(p[0]) |
         (static_cast<std::uint32_t>(p[1]) << 8U) |
         (static_cast<std::uint32_t>(p[2]) << 16U) |
         (static_cast<std::uint32_t>(p[3]) << 24U);
}

bool set_error(ParseError *error, ParseError value) noexcept {
  if (error != nullptr) {
    *error = value;
  }
  return false;
}

bool valid_v1_record(const std::uint8_t *bytes) noexcept {
  // These are the GA34 v1 codec's structural checks, expressed as explicit
  // byte loads.  The writer never creates or rewrites a FaultRecord object.
  const std::uint32_t validity = load32(bytes + 8U);
  const std::uint32_t claims = load32(bytes + 12U);
  const std::uint32_t status = load32(bytes + 16U);
  const std::uint32_t attempts = load32(bytes + 20U);
  const std::uint32_t engine = load32(bytes + 24U);
  const std::uint32_t held = load32(bytes + 28U);
  const std::uint32_t ack = load32(bytes + 32U);
  const std::uint64_t sequence =
      static_cast<std::uint64_t>(load32(bytes + 36U)) |
      (static_cast<std::uint64_t>(load32(bytes + 40U)) << 32U);
  const std::uint64_t monotonic =
      static_cast<std::uint64_t>(load32(bytes + 44U)) |
      (static_cast<std::uint64_t>(load32(bytes + 48U)) << 32U);
  const std::uint64_t boot =
      static_cast<std::uint64_t>(load32(bytes + 52U)) |
      (static_cast<std::uint64_t>(load32(bytes + 56U)) << 32U);
  const std::uint64_t hang =
      static_cast<std::uint64_t>(load32(bytes + 60U)) |
      (static_cast<std::uint64_t>(load32(bytes + 64U)) << 32U);
  const std::uint64_t caller =
      static_cast<std::uint64_t>(load32(bytes + 68U)) |
      (static_cast<std::uint64_t>(load32(bytes + 72U)) << 32U);
  const std::uint64_t reset_epoch =
      static_cast<std::uint64_t>(load32(bytes + 76U)) |
      (static_cast<std::uint64_t>(load32(bytes + 80U)) << 32U);
  const std::uint64_t exclusion =
      static_cast<std::uint64_t>(load32(bytes + 84U)) |
      (static_cast<std::uint64_t>(load32(bytes + 88U)) << 32U);
  const std::uint32_t raw_fault = load32(bytes + 92U);
  const std::uint32_t raw_data0 = load32(bytes + 96U);
  const std::uint32_t raw_data1 = load32(bytes + 100U);

  if (claims != 127U || engine != 1U || !(held & 1U) || !(ack & 1U) ||
      sequence == 0 || monotonic == 0 || boot == 0 || hang == 0 ||
      caller == 0 || reset_epoch == 0 || exclusion == 0 || attempts > 3U ||
      (validity & ~31U) != 0 || !(validity & 16U)) {
    return false;
  }
  if (status == 0U) {
    return attempts == 3U && validity == 31U;
  }
  if ((validity & 8U) != 0) {
    return false;
  }
  std::uint32_t completed = attempts;
  switch (status) {
    case 15U:  // FaultReadFailed
      if (attempts != 1U) return false;
      --completed;
      break;
    case 16U:  // Data0ReadFailed
      if (attempts != 2U) return false;
      --completed;
      break;
    case 17U:  // Data1ReadFailed
      if (attempts != 3U) return false;
      --completed;
      break;
    case 12U:  // EpochUnavailable
    case 13U:  // ResetRace
    case 3U:   // PowerUnknown
    case 4U:   // GtForcewakeMissing
    case 5U:   // GtAckMissing
      break;
    default:
      return false;
  }
  if ((validity & 7U) != ((1U << completed) - 1U)) {
    return false;
  }
  if (attempts == 0U && raw_fault != 0U) return false;
  if (attempts < 2U && raw_data0 != 0U) return false;
  if (attempts < 3U && raw_data1 != 0U) return false;
  return true;
}

bool parse_thag(const std::uint8_t *bytes, std::size_t length,
                Snapshot &out, ParseError *error) noexcept {
  const bool v2_extent = length >= kThagV2Size && length % kThagV2Size == 0 &&
                         length / kThagV2Size <= kMaximumThagRecords;
  const bool v3_extent = length >= kThagV3Size && length % kThagV3Size == 0 &&
                         length / kThagV3Size <= kMaximumThagRecords;
  const bool v2 = v2_extent && length / kThagV2Size >= 1U;
  const bool v3 = v3_extent && length / kThagV3Size >= 1U;
  if (v2 == v3) {
    return set_error(error, ParseError::LengthMismatch);
  }

  const std::size_t record_size = v3 ? kThagV3Size : kThagV2Size;
  const std::uint16_t version = v3 ? 3U : 2U;
  const std::size_t count = length / record_size;
  Snapshot parsed;
  parsed.kind = Kind::Thag;
  parsed.version = version;
  parsed.header_size = 0;
  try {
    parsed.records.reserve(count);
    for (std::size_t i = 0; i < count; ++i) {
      const std::uint8_t *record = bytes + i * record_size;
      if (load32(record) != kThagMagic) {
        return set_error(error, ParseError::MixedRecordKind);
      }
      if (load32(record + 4U) != i || load32(record + 12U) > 8U) {
        return set_error(error, ParseError::NonMonotonicIndex);
      }
      if (v3 && (load32(record + kThagV2Size) != 3U ||
                 load32(record + kThagV2Size + 4U) != kThagV3Size)) {
        return set_error(error, ParseError::LengthMismatch);
      }
      parsed.records.push_back(
          {static_cast<std::uint32_t>(i), i * record_size, record_size});
    }
  } catch (...) {
    parsed.records.clear();
    return set_error(error, ParseError::AllocationFailure);
  }
  out = std::move(parsed);
  return true;
}

bool parse_fault_v1(const std::uint8_t *bytes, std::size_t length,
                    Snapshot &out, ParseError *error) noexcept {
  if (length < kFaultV1Size || length % kFaultV1Size != 0 ||
      length / kFaultV1Size > kMaximumFaultRecords) {
    return set_error(error, ParseError::LengthMismatch);
  }
  const std::size_t count = length / kFaultV1Size;
  Snapshot parsed;
  parsed.kind = Kind::Fault108B;
  parsed.version = 1;
  parsed.header_size = 0;
  std::uint64_t previous_sequence = 0;
  try {
    parsed.records.reserve(count);
    for (std::size_t i = 0; i < count; ++i) {
      const std::size_t offset = i * kFaultV1Size;
      const std::uint8_t *record = bytes + offset;
      if (load32(record) != kFaultMagic || load16(record + 4U) != 1U ||
          load16(record + 6U) != kFaultV1Size ||
          load32(record + 104U) != 0U) {
        return set_error(error, ParseError::MixedRecordKind);
      }
      if (!valid_v1_record(record)) {
        return set_error(error, ParseError::LengthMismatch);
      }
      const std::uint64_t sequence =
          static_cast<std::uint64_t>(load32(record + 36U)) |
          (static_cast<std::uint64_t>(load32(record + 40U)) << 32U);
      if (i != 0 && sequence <= previous_sequence) {
        return set_error(error, ParseError::NonMonotonicIndex);
      }
      previous_sequence = sequence;
      parsed.records.push_back(
          {static_cast<std::uint32_t>(i), offset, kFaultV1Size});
    }
  } catch (...) {
    parsed.records.clear();
    return set_error(error, ParseError::AllocationFailure);
  }
  out = std::move(parsed);
  return true;
}

}  // namespace

bool parse(const std::uint8_t *bytes, std::size_t length, Snapshot &out,
           ParseError *error) noexcept {
  if (error != nullptr) {
    *error = ParseError::None;
  }
  if (bytes == nullptr && length != 0) {
    return set_error(error, ParseError::NullInput);
  }
  if (bytes == nullptr || length < 4U) {
    return set_error(error, ParseError::TooShort);
  }
  const std::uint32_t magic = load32(bytes);
  if (magic == kThagMagic) {
    return parse_thag(bytes, length, out, error);
  }
  if (magic == kFaultMagic) {
    return parse_fault_v1(bytes, length, out, error);
  }
  return set_error(error, ParseError::UnknownMagic);
}

bool ReadOnlyHistory::copy_from_history_readonly(const void *history_bytes,
                                                 std::size_t length,
                                                 ReadOnlyHistory &out,
                                                 ParseError *error) noexcept {
  if (history_bytes == nullptr && length != 0) {
    if (error != nullptr) {
      *error = ParseError::NullInput;
    }
    return false;
  }
  const auto *source = static_cast<const std::uint8_t *>(history_bytes);
  Snapshot parsed;
  if (!parse(source, length, parsed, error)) {
    return false;
  }
  try {
    std::vector<std::uint8_t> copy;
    copy.assign(source, source + length);
    out.bytes_ = std::move(copy);
    out.snapshot_ = std::move(parsed);
  } catch (...) {
    if (error != nullptr) {
      *error = ParseError::AllocationFailure;
    }
    return false;
  }
  return true;
}

std::vector<std::uint8_t> ReadOnlyHistory::copy_bytes() const {
  return bytes_;
}

}  // namespace recordwire
}  // namespace ga37
