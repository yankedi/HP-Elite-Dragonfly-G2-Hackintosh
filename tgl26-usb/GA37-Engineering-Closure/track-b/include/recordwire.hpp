#ifndef GA37_TRACK_B_RECORDWIRE_HPP
#define GA37_TRACK_B_RECORDWIRE_HPP

// The writer deliberately treats the GA36 wire payload as bytes.  This small
// parser only decodes fixed-wire validation fields, using explicit
// little-endian loads; it never casts a payload to a C/C++ struct.  THAG v2/v3
// are fixed 0xc2a0/0xc2f8-byte records and the legacy 108BFault v1 is a fixed
// 108-byte TGF4 record.  The format is documented in README.md and kept here
// so the recorder and its tests use the same source-of-truth parser.

#include <cstddef>
#include <cstdint>
#include <vector>

namespace ga37 {
namespace recordwire {

enum class Kind : std::uint8_t {
  Thag = 1,
  Fault108B = 2,
};

enum class ParseError : std::uint8_t {
  None = 0,
  NullInput,
  TooShort,
  UnknownMagic,
  UnsupportedVersion,
  HeaderOutOfRange,
  LengthMismatch,
  RecordCountOutOfRange,
  TruncatedRecordHeader,
  TruncatedRecord,
  EmptyRecord,
  NonMonotonicIndex,
  MixedRecordKind,
  TrailingBytes,
  AllocationFailure,
};

struct RecordSpan {
  std::uint32_t index = 0;
  std::size_t offset = 0;
  std::size_t size = 0;
};

struct Snapshot {
  Kind kind = Kind::Thag;
  std::uint16_t version = 0;
  std::size_t header_size = 0;
  std::vector<RecordSpan> records;
};

// Validate and describe one complete, framed snapshot.  bytes is borrowed;
// the returned spans point into it and are valid only while it is unchanged.
bool parse(const std::uint8_t *bytes, std::size_t length, Snapshot &out,
           ParseError *error = nullptr) noexcept;

// A history copy is intentionally explicit.  It copies the original bytes,
// then parses the copy.  No field is reconstructed from a historical record.
class ReadOnlyHistory final {
 public:
  ReadOnlyHistory() noexcept = default;

  static bool copy_from_history_readonly(const void *history_bytes,
                                         std::size_t length,
                                         ReadOnlyHistory &out,
                                         ParseError *error = nullptr) noexcept;

  const std::uint8_t *data() const noexcept { return bytes_.data(); }
  std::size_t size() const noexcept { return bytes_.size(); }
  const Snapshot &snapshot() const noexcept { return snapshot_; }

  // Useful to the executor when ownership must cross a callback boundary.
  std::vector<std::uint8_t> copy_bytes() const;

 private:
  std::vector<std::uint8_t> bytes_;
  Snapshot snapshot_;
};

}  // namespace recordwire
}  // namespace ga37

#endif  // GA37_TRACK_B_RECORDWIRE_HPP
