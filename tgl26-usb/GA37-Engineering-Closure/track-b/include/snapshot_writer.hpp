#ifndef GA37_TRACK_B_SNAPSHOT_WRITER_HPP
#define GA37_TRACK_B_SNAPSHOT_WRITER_HPP

#include "recordwire.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace ga37 {

enum class CommitStatus : std::uint8_t {
  NotCommitted = 0,
  VisibleButDurabilityUncertain = 1,
  DurableVerified = 2,
};

enum class ErrorCode : std::uint16_t {
  None = 0,
  AlreadyTerminal,
  InvalidOptions,
  InputTooLarge,
  NullInput,
  MalformedWire,
  SnapshotNotPrefix,
  UnsafeParent,
  LockOpen,
  LockAcquire,
  RunDirectory,
  RevisionDirectory,
  RecoveryEntry,
  RecoveryDigest,
  RecoveryRead,
  SequenceExhausted,
  TemporaryOpen,
  Write,
  FileSync,
  FileClose,
  Publish,
  VerifyOpen,
  VerifyRead,
  VerifyClose,
  RevisionDirectorySync,
  ParentDirectorySync,
  AllocationFailure,
  Internal,
};

// This is intentionally the same result layout used by the GA36 pipeline:
// {int error; size_t transferred}.  Do not add a success-only callback or an
// asynchronous acknowledgement here.  CommitResult below carries the richer
// host-side durability state without changing the callback ABI.
struct WriteResult final {
  int error = 0;
  std::size_t transferred = 0;
};

struct CommitResult final {
  CommitStatus status = CommitStatus::NotCommitted;
  ErrorCode error = ErrorCode::Internal;
  std::uint64_t sequence = 0;
  std::array<std::uint8_t, 32> sha256{};
  bool retained_in_memory = false;

  bool success() const noexcept {
    return status == CommitStatus::DurableVerified &&
           error == ErrorCode::None;
  }
};

using PipelineWriteResult = WriteResult (*)(void *ctx, const void *data,
                                            std::size_t length) noexcept;

enum class FaultStage : std::uint8_t {
  None = 0,
  ParentOpen,
  LockOpen,
  LockAcquire,
  RunDirectory,
  RevisionDirectory,
  RecoveryScan,
  TemporaryOpen,
  Write,
  TemporaryFileSync,
  TemporaryClose,
  Rename,
  VerifyOpen,
  VerifyRead,
  VerifyClose,
  RevisionDirectorySync,
  ParentDirectorySync,
};

// Test-only hooks are inert unless a test asks for them.  They are kept out
// of the wire format and are not a production recovery mechanism.  A positive
// max_write forces short writes, which exercises the same loop as a real
// short write.  crash_before/after are used by the fork/_exit crash tests.
struct FaultInjection final {
  FaultStage fail_stage = FaultStage::None;
  FaultStage crash_before = FaultStage::None;
  FaultStage crash_after = FaultStage::None;
  std::size_t max_write = 0;
  int error_number = 5;  // EIO, without requiring errno in this public header
  bool throw_bad_alloc_after_publish = false;
};

struct WriterOptions final {
  // The caller must supply an existing, user-owned directory.  Every
  // absolute/relative component is opened separately with O_NOFOLLOW; dot,
  // dot-dot, repeated, trailing, and symlink components are rejected.
  std::string parent_directory;
  std::size_t max_bytes = 64U * 1024U * 1024U;
  std::uint32_t max_records = 1U << 20;
  std::uint32_t eintr_budget = 32;
  FaultInjection fault;
};

class SnapshotWriter final {
 public:
  explicit SnapshotWriter(WriterOptions options);
  ~SnapshotWriter();

  SnapshotWriter(const SnapshotWriter &) = delete;
  SnapshotWriter &operator=(const SnapshotWriter &) = delete;

  // Rich host-side operation.  The callback below is the exact GA36 ABI and
  // calls this operation internally.
  CommitResult commit(void *ctx, const void *data,
                      std::size_t length) noexcept;

  // Nominally GA36-shaped bridge entry point.  Its return type is Track B's
  // structurally matching type, not the nominal Capture36 type.  The actual
  // GA36 integration must use callback_adapter<the unchanged GA36
  // WriteResult>; ctx is not interpreted as a wire structure.
  WriteResult write(void *ctx, const void *data,
                    std::size_t length) noexcept;

  static WriteResult callback(void *ctx, const void *data,
                              std::size_t length) noexcept;
  // Convenience only for a structurally compatible host-side callback.  It
  // is not an exact Capture36 function pointer; use callback_adapter above
  // for the real A-executor slot.
  PipelineWriteResult pipeline_callback() noexcept { return &callback; }

  // The actual GA36 header remains owned by the A executor.  When its
  // nominal WriteResult type must be used (C++ function-pointer types are not
  // structurally interchangeable), instantiate this adapter with that
  // unchanged type; it only copies the two GA36 result fields.
  template <typename LegacyWriteResult>
  static LegacyWriteResult callback_adapter(void *ctx, const void *data,
                                            std::size_t length) noexcept {
    const WriteResult result = callback(ctx, data, length);
    return LegacyWriteResult{result.error, result.transferred};
  }

  bool terminal() const noexcept { return terminal_; }
  CommitResult last_commit() const noexcept { return last_commit_; }

  // The A executor serializes callbacks per SnapshotWriter object.  These
  // no-allocation ownership methods let the transaction stage its immutable
  // bytes before rename and turn that staged ownership terminal on ambiguity.
  void stage_owned_input(std::vector<std::uint8_t> &&bytes) noexcept;
  void mark_ambiguous() noexcept;
  void clear_owned_input() noexcept;
  const std::vector<std::uint8_t> &owned_input() const noexcept {
    return ambiguous_bytes_;
  }
  bool has_ambiguous_copy() const noexcept { return !ambiguous_bytes_.empty(); }

 private:
  WriterOptions options_;
  bool terminal_ = false;
  std::vector<std::uint8_t> ambiguous_bytes_;
  CommitResult last_commit_{};
};

}  // namespace ga37

#endif  // GA37_TRACK_B_SNAPSHOT_WRITER_HPP
