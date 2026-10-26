#include "snapshot_writer.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <cerrno>
#include <cinttypes>
#include <cstdio>
#include <cstring>
#include <dirent.h>
#include <fcntl.h>
#include <new>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <utility>

#if defined(__linux__)
#include <sys/syscall.h>
#endif

namespace ga37 {
namespace {

constexpr std::size_t kDigestSize = 32;
constexpr std::size_t kRevisionSequenceDigits = 20;
constexpr std::size_t kRevisionNameSize = 20 + 1 + 64 + 5;
constexpr std::size_t kMaxRunAttempts = 4096;
constexpr std::size_t kMaxKnownRunDirectories = 64;
constexpr char kRunPrefix[] = ".snapshot-run-";

// Small self-contained SHA-256 implementation.  It is used only to bind a
// revision filename to its exact bytes; it has no wire-field interpretation.
class Sha256 final {
 public:
  Sha256() noexcept {
    state_[0] = 0x6a09e667U;
    state_[1] = 0xbb67ae85U;
    state_[2] = 0x3c6ef372U;
    state_[3] = 0xa54ff53aU;
    state_[4] = 0x510e527fU;
    state_[5] = 0x9b05688cU;
    state_[6] = 0x1f83d9abU;
    state_[7] = 0x5be0cd19U;
  }

  void update(const std::uint8_t *data, std::size_t length) noexcept {
    total_bytes_ += length;
    while (length != 0) {
      const std::size_t available = 64U - block_size_;
      const std::size_t take = std::min(available, length);
      std::memcpy(block_.data() + block_size_, data, take);
      block_size_ += take;
      data += take;
      length -= take;
      if (block_size_ == 64U) {
        transform(block_.data());
        block_size_ = 0;
      }
    }
  }

  std::array<std::uint8_t, kDigestSize> final() noexcept {
    const std::uint64_t bit_length = total_bytes_ * 8U;
    block_[block_size_++] = 0x80U;
    if (block_size_ > 56U) {
      while (block_size_ < 64U) {
        block_[block_size_++] = 0;
      }
      transform(block_.data());
      block_size_ = 0;
    }
    while (block_size_ < 56U) {
      block_[block_size_++] = 0;
    }
    for (int shift = 56; shift >= 0; shift -= 8) {
      block_[block_size_++] =
          static_cast<std::uint8_t>((bit_length >> shift) & 0xffU);
    }
    transform(block_.data());
    block_size_ = 0;

    std::array<std::uint8_t, kDigestSize> digest{};
    for (std::size_t i = 0; i < state_.size(); ++i) {
      digest[i * 4U] = static_cast<std::uint8_t>(state_[i] >> 24U);
      digest[i * 4U + 1U] = static_cast<std::uint8_t>(state_[i] >> 16U);
      digest[i * 4U + 2U] = static_cast<std::uint8_t>(state_[i] >> 8U);
      digest[i * 4U + 3U] = static_cast<std::uint8_t>(state_[i]);
    }
    return digest;
  }

 private:
  static constexpr std::array<std::uint32_t, 64> k = {
      0x428a2f98U, 0x71374491U, 0xb5c0fbcfU, 0xe9b5dba5U,
      0x3956c25bU, 0x59f111f1U, 0x923f82a4U, 0xab1c5ed5U,
      0xd807aa98U, 0x12835b01U, 0x243185beU, 0x550c7dc3U,
      0x72be5d74U, 0x80deb1feU, 0x9bdc06a7U, 0xc19bf174U,
      0xe49b69c1U, 0xefbe4786U, 0x0fc19dc6U, 0x240ca1ccU,
      0x2de92c6fU, 0x4a7484aaU, 0x5cb0a9dcU, 0x76f988daU,
      0x983e5152U, 0xa831c66dU, 0xb00327c8U, 0xbf597fc7U,
      0xc6e00bf3U, 0xd5a79147U, 0x06ca6351U, 0x14292967U,
      0x27b70a85U, 0x2e1b2138U, 0x4d2c6dfcU, 0x53380d13U,
      0x650a7354U, 0x766a0abbU, 0x81c2c92eU, 0x92722c85U,
      0xa2bfe8a1U, 0xa81a664bU, 0xc24b8b70U, 0xc76c51a3U,
      0xd192e819U, 0xd6990624U, 0xf40e3585U, 0x106aa070U,
      0x19a4c116U, 0x1e376c08U, 0x2748774cU, 0x34b0bcb5U,
      0x391c0cb3U, 0x4ed8aa4aU, 0x5b9cca4fU, 0x682e6ff3U,
      0x748f82eeU, 0x78a5636fU, 0x84c87814U, 0x8cc70208U,
      0x90befffaU, 0xa4506cebU, 0xbef9a3f7U, 0xc67178f2U};

  static std::uint32_t rotate_right(std::uint32_t x,
                                    std::uint32_t n) noexcept {
    return (x >> n) | (x << (32U - n));
  }

  void transform(const std::uint8_t *block) noexcept {
    std::array<std::uint32_t, 64> words{};
    for (std::size_t i = 0; i < 16; ++i) {
      const std::size_t p = i * 4U;
      words[i] = (static_cast<std::uint32_t>(block[p]) << 24U) |
                 (static_cast<std::uint32_t>(block[p + 1U]) << 16U) |
                 (static_cast<std::uint32_t>(block[p + 2U]) << 8U) |
                 static_cast<std::uint32_t>(block[p + 3U]);
    }
    for (std::size_t i = 16; i < words.size(); ++i) {
      const std::uint32_t s0 = rotate_right(words[i - 15U], 7U) ^
                               rotate_right(words[i - 15U], 18U) ^
                               (words[i - 15U] >> 3U);
      const std::uint32_t s1 = rotate_right(words[i - 2U], 17U) ^
                               rotate_right(words[i - 2U], 19U) ^
                               (words[i - 2U] >> 10U);
      words[i] = words[i - 16U] + s0 + words[i - 7U] + s1;
    }

    std::uint32_t a = state_[0];
    std::uint32_t b = state_[1];
    std::uint32_t c = state_[2];
    std::uint32_t d = state_[3];
    std::uint32_t e = state_[4];
    std::uint32_t f = state_[5];
    std::uint32_t g = state_[6];
    std::uint32_t h = state_[7];
    for (std::size_t i = 0; i < words.size(); ++i) {
      const std::uint32_t s1 = rotate_right(e, 6U) ^ rotate_right(e, 11U) ^
                               rotate_right(e, 25U);
      const std::uint32_t ch = (e & f) ^ ((~e) & g);
      const std::uint32_t temp1 = h + s1 + ch + k[i] + words[i];
      const std::uint32_t s0 = rotate_right(a, 2U) ^ rotate_right(a, 13U) ^
                               rotate_right(a, 22U);
      const std::uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
      const std::uint32_t temp2 = s0 + maj;
      h = g;
      g = f;
      f = e;
      e = d + temp1;
      d = c;
      c = b;
      b = a;
      a = temp1 + temp2;
    }
    state_[0] += a;
    state_[1] += b;
    state_[2] += c;
    state_[3] += d;
    state_[4] += e;
    state_[5] += f;
    state_[6] += g;
    state_[7] += h;
  }

  std::array<std::uint32_t, 8> state_{};
  std::array<std::uint8_t, 64> block_{};
  std::uint64_t total_bytes_ = 0;
  std::size_t block_size_ = 0;
};

std::array<std::uint8_t, kDigestSize> digest_of(
    const std::vector<std::uint8_t> &bytes) noexcept {
  Sha256 sha;
  if (!bytes.empty()) {
    sha.update(bytes.data(), bytes.size());
  }
  return sha.final();
}

bool equal_digest(const std::array<std::uint8_t, kDigestSize> &a,
                  const std::array<std::uint8_t, kDigestSize> &b) noexcept {
  return std::memcmp(a.data(), b.data(), kDigestSize) == 0;
}

char hex_digit(std::uint8_t value) noexcept {
  return value < 10U ? static_cast<char>('0' + value)
                     : static_cast<char>('a' + value - 10U);
}

std::string hex_digest(
    const std::array<std::uint8_t, kDigestSize> &digest) {
  std::string result;
  result.reserve(kDigestSize * 2U);
  for (std::uint8_t value : digest) {
    result.push_back(hex_digit(static_cast<std::uint8_t>(value >> 4U)));
    result.push_back(hex_digit(static_cast<std::uint8_t>(value & 0x0fU)));
  }
  return result;
}

struct Fd final {
  int value = -1;

  Fd() noexcept = default;
  explicit Fd(int fd) noexcept : value(fd) {}
  Fd(const Fd &) = delete;
  Fd &operator=(const Fd &) = delete;
  ~Fd() {
    if (value >= 0) {
      (void)::close(value);
    }
  }

  bool close_checked() noexcept {
    if (value < 0) {
      return true;
    }
    const int fd = value;
    value = -1;
    return ::close(fd) == 0;
  }

  int release() noexcept {
    const int fd = value;
    value = -1;
    return fd;
  }
};

struct Revision final {
  std::uint64_t sequence = 0;
  std::array<std::uint8_t, kDigestSize> digest{};
  std::string name;
};

bool is_user_private_directory(int fd, uid_t uid) noexcept {
  struct stat st {};
  if (::fstat(fd, &st) != 0 || !S_ISDIR(st.st_mode) || st.st_uid != uid) {
    return false;
  }
  return (st.st_mode & 0022U) == 0;
}

bool is_exact_private_directory(int fd, uid_t uid) noexcept {
  struct stat st {};
  return ::fstat(fd, &st) == 0 && S_ISDIR(st.st_mode) && st.st_uid == uid &&
         (st.st_mode & 0777U) == 0700U;
}

bool is_user_regular_file(const struct stat &st, uid_t uid) noexcept {
  return S_ISREG(st.st_mode) && st.st_nlink == 1 && st.st_uid == uid &&
         (st.st_mode & 0077U) == 0;
}

bool parse_hex_byte(char c, std::uint8_t &out) noexcept {
  if (c >= '0' && c <= '9') {
    out = static_cast<std::uint8_t>(c - '0');
    return true;
  }
  if (c >= 'a' && c <= 'f') {
    out = static_cast<std::uint8_t>(c - 'a' + 10);
    return true;
  }
  return false;
}

bool parse_revision_name(const char *name, Revision &out) {
  if (name == nullptr) {
    return false;
  }
  const std::size_t length = std::strlen(name);
  if (length != kRevisionNameSize || name[20] != '-' ||
      std::memcmp(name + 85, ".snap", 5) != 0) {
    return false;
  }
  std::uint64_t sequence = 0;
  for (std::size_t i = 0; i < kRevisionSequenceDigits; ++i) {
    if (name[i] < '0' || name[i] > '9') {
      return false;
    }
    const std::uint64_t digit = static_cast<std::uint64_t>(name[i] - '0');
    if (sequence > (UINT64_MAX - digit) / 10U) {
      return false;
    }
    sequence = sequence * 10U + digit;
  }
  if (sequence == 0) {
    return false;
  }
  std::array<std::uint8_t, kDigestSize> digest{};
  for (std::size_t i = 0; i < kDigestSize; ++i) {
    std::uint8_t high = 0;
    std::uint8_t low = 0;
    if (!parse_hex_byte(name[21U + i * 2U], high) ||
        !parse_hex_byte(name[22U + i * 2U], low)) {
      return false;
    }
    digest[i] = static_cast<std::uint8_t>((high << 4U) | low);
  }
  out.sequence = sequence;
  out.digest = digest;
  out.name.assign(name, length);
  return true;
}

bool same_prefix(const std::vector<std::uint8_t> &old_bytes,
                 const recordwire::Snapshot &old_snapshot,
                 const std::vector<std::uint8_t> &new_bytes,
                 const recordwire::Snapshot &new_snapshot) noexcept {
  if (old_snapshot.kind != new_snapshot.kind ||
      old_snapshot.version != new_snapshot.version ||
      new_snapshot.records.size() < old_snapshot.records.size()) {
    return false;
  }
  for (std::size_t i = 0; i < old_snapshot.records.size(); ++i) {
    const recordwire::RecordSpan &old_record = old_snapshot.records[i];
    const recordwire::RecordSpan &new_record = new_snapshot.records[i];
    if (old_record.index != new_record.index ||
        old_record.size != new_record.size ||
        std::memcmp(old_bytes.data() + old_record.offset,
                    new_bytes.data() + new_record.offset,
                    old_record.size) != 0) {
      return false;
    }
  }
  return true;
}

class Worker final {
 public:
  Worker(SnapshotWriter &owner, const WriterOptions &options) noexcept
      : owner_(owner), options_(options), uid_(::geteuid()) {}
  ~Worker() noexcept;

  CommitResult run(const void *data, std::size_t length) noexcept;

 private:
  bool stage(FaultStage stage, bool before) noexcept {
#if defined(GA37_TEST_FAULTS)
    if ((before && options_.fault.crash_before == stage) ||
        (!before && options_.fault.crash_after == stage)) {
      ::_exit(90 + static_cast<int>(stage));
    }
    if (before && options_.fault.fail_stage == stage) {
      errno = options_.fault.error_number == 0 ? EIO
                                                : options_.fault.error_number;
      return false;
    }
#else
    (void)stage;
    (void)before;
#endif
    return true;
  }

  CommitResult fail(ErrorCode code, CommitStatus status =
                                       CommitStatus::NotCommitted) noexcept {
    CommitResult result;
    result.status = status;
    result.error = code;
    return result;
  }

  CommitResult uncertain(ErrorCode code, std::uint64_t sequence,
                         const std::array<std::uint8_t, kDigestSize> &digest,
                         const std::vector<std::uint8_t> &input) noexcept {
    (void)input;
    owner_.mark_ambiguous();
    const bool retained = owner_.has_ambiguous_copy();
    CommitResult result;
    result.status = CommitStatus::VisibleButDurabilityUncertain;
    result.error = code;
    result.sequence = sequence;
    result.sha256 = digest;
    result.retained_in_memory = retained;
    return result;
  }

  bool open_parent() noexcept;
  bool open_lock() noexcept;
  bool open_revisions() noexcept;
  bool create_run_directory() noexcept;
  bool scan_revisions(std::vector<Revision> &revisions) noexcept;
  bool verify_revision(const Revision &revision, std::vector<std::uint8_t> &bytes,
                       recordwire::Snapshot &snapshot) noexcept;
  bool verify_published_noalloc(
      const Revision &revision, const std::vector<std::uint8_t> &expected,
      std::vector<std::uint8_t> &bytes) noexcept;
  bool read_all(int fd, std::size_t size, std::vector<std::uint8_t> &bytes,
                FaultStage stage) noexcept;
  bool sync_fd(int fd, FaultStage stage) noexcept;
  bool sync_directories() noexcept;
  bool write_all(int fd, const std::vector<std::uint8_t> &bytes) noexcept;
  std::string revision_name(std::uint64_t sequence,
                            const std::array<std::uint8_t, kDigestSize> &digest);

  SnapshotWriter &owner_;
  const WriterOptions &options_;
  uid_t uid_;
  Fd parent_;
  Fd lock_;
  Fd revisions_;
  Fd run_;
  std::string run_name_;
  bool staged_input_ = false;

  bool cleanup_run_directory() noexcept;
  bool run_directory_capacity_available() noexcept;
};

bool open_parent_components(const std::string &path, uid_t uid,
                            int &result_fd) noexcept {
  result_fd = -1;
  if (path.empty() || path.find('\0') != std::string::npos) {
    return false;
  }
  try {
    const bool absolute = path.front() == '/';
    Fd current(::open(absolute ? "/" : ".",
                      O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW));
    if (current.value < 0) {
      return false;
    }
    std::size_t cursor = absolute ? 1U : 0U;
    if (cursor == path.size()) {
      return false;  // root is never an acceptable caller-owned parent
    }
    while (cursor < path.size()) {
      if (path[cursor] == '/') {
        return false;  // reject empty, repeated, or trailing components
      }
      const std::size_t slash = path.find('/', cursor);
      const std::size_t end = slash == std::string::npos ? path.size() : slash;
      const std::string component = path.substr(cursor, end - cursor);
      if (component.empty() || component == "." || component == "..") {
        return false;
      }
      const int next = ::openat(current.value, component.c_str(),
                                O_RDONLY | O_DIRECTORY | O_CLOEXEC |
                                    O_NOFOLLOW);
      if (next < 0) {
        return false;
      }
      if (!current.close_checked()) {
        (void)::close(next);
        return false;
      }
      current.value = next;
      if (slash == std::string::npos) {
        cursor = path.size();
      } else {
        cursor = slash + 1U;
        if (cursor == path.size()) {
          return false;
        }
      }
    }
    if (!is_user_private_directory(current.value, uid)) {
      return false;
    }
    result_fd = current.release();
    return true;
  } catch (...) {
    return false;
  }
}

Worker::~Worker() noexcept {
  // A non-terminal return means rename did not make a visible revision.  The
  // staged vector is then only a pre-publish scratch owner and can be dropped
  // without allocation.  An ambiguous return marks the owner terminal and
  // deliberately keeps those already-owned bytes.
  if (staged_input_ && !owner_.terminal()) {
    owner_.clear_owned_input();
  }
  (void)cleanup_run_directory();
}

bool Worker::open_parent() noexcept {
  if (!stage(FaultStage::ParentOpen, true)) {
    return false;
  }
  int fd = -1;
  if (!open_parent_components(options_.parent_directory, uid_, fd)) {
    return false;
  }
  parent_.value = fd;
  return stage(FaultStage::ParentOpen, false);
}

bool Worker::open_lock() noexcept {
  if (!stage(FaultStage::LockOpen, true)) {
    return false;
  }
  const int fd = ::openat(parent_.value, ".snapshot.lock",
                          O_RDWR | O_CREAT | O_CLOEXEC | O_NOFOLLOW, 0600);
  if (fd < 0) {
    return false;
  }
  struct stat st {};
  if (::fstat(fd, &st) != 0 || !is_user_regular_file(st, uid_) ||
      ::fchmod(fd, 0600) != 0) {
    (void)::close(fd);
    return false;
  }
  lock_.value = fd;
  if (!stage(FaultStage::LockOpen, false)) {
    return false;
  }
  if (!stage(FaultStage::LockAcquire, true) ||
      ::flock(lock_.value, LOCK_EX) != 0) {
    return false;
  }
  return stage(FaultStage::LockAcquire, false);
}

bool Worker::open_revisions() noexcept {
  if (!stage(FaultStage::RevisionDirectory, true)) {
    return false;
  }
  if (::mkdirat(parent_.value, "revisions", 0700) != 0 && errno != EEXIST) {
    return false;
  }
  const int fd = ::openat(parent_.value, "revisions",
                          O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
  if (fd < 0 || !is_exact_private_directory(fd, uid_)) {
    if (fd >= 0) {
      (void)::close(fd);
    }
    return false;
  }
  revisions_.value = fd;
  return stage(FaultStage::RevisionDirectory, false);
}

bool Worker::create_run_directory() noexcept {
  if (!stage(FaultStage::RunDirectory, true)) {
    return false;
  }
  if (!run_directory_capacity_available()) {
    return false;
  }
  static std::atomic<std::uint32_t> counter{0};
  const std::uint32_t initial = counter.fetch_add(1U) + 1U;
  const pid_t pid = ::getpid();
  for (std::size_t attempt = 0; attempt < kMaxRunAttempts; ++attempt) {
    char name[96]{};
    const std::uint32_t suffix = initial + static_cast<std::uint32_t>(attempt);
    const int written = std::snprintf(name, sizeof(name), ".snapshot-run-%ld-%u",
                                      static_cast<long>(pid), suffix);
    if (written <= 0 || static_cast<std::size_t>(written) >= sizeof(name)) {
      return false;
    }
    try {
      run_name_.reserve(static_cast<std::size_t>(written));
    } catch (...) {
      return false;
    }
    if (::mkdirat(parent_.value, name, 0700) == 0) {
      const int fd = ::openat(parent_.value, name,
                              O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
      if (fd < 0 || !is_user_private_directory(fd, uid_) ||
          ::fchmod(fd, 0700) != 0 || !is_exact_private_directory(fd, uid_)) {
        if (fd >= 0) {
          (void)::close(fd);
        }
        (void)::unlinkat(parent_.value, name, AT_REMOVEDIR);
        return false;
      }
      run_name_.assign(name, static_cast<std::size_t>(written));
      run_.value = fd;
      return stage(FaultStage::RunDirectory, false);
    }
    if (errno != EEXIST) {
      return false;
    }
  }
  return false;
}

bool Worker::run_directory_capacity_available() noexcept {
  const int duplicate_fd = ::dup(parent_.value);
  if (duplicate_fd < 0) {
    return false;
  }
  DIR *directory = ::fdopendir(duplicate_fd);
  if (directory == nullptr) {
    (void)::close(duplicate_fd);
    return false;
  }
  std::size_t count = 0;
  bool okay = true;
  while (true) {
    errno = 0;
    struct dirent *entry = ::readdir(directory);
    if (entry == nullptr) {
      okay = errno == 0;
      break;
    }
    if (std::strncmp(entry->d_name, kRunPrefix,
                     sizeof(kRunPrefix) - 1U) != 0) {
      continue;
    }
    const int fd = ::openat(parent_.value, entry->d_name,
                            O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0 || !is_exact_private_directory(fd, uid_)) {
      if (fd >= 0) {
        (void)::close(fd);
      }
      okay = false;
      break;
    }
    (void)::close(fd);
    if (++count >= kMaxKnownRunDirectories) {
      okay = false;
      break;
    }
  }
  (void)::closedir(directory);
  return okay;
}

bool Worker::cleanup_run_directory() noexcept {
  if (run_.value < 0 || run_name_.empty() || parent_.value < 0) {
    return true;
  }
  if (!run_.close_checked()) {
    return false;
  }
  const int raw_directory =
      ::openat(parent_.value, run_name_.c_str(),
               O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
  if (raw_directory < 0 || !is_exact_private_directory(raw_directory, uid_)) {
    if (raw_directory >= 0) {
      (void)::close(raw_directory);
    }
    return false;
  }
  Fd directory(raw_directory);
  const int duplicate_fd = ::dup(directory.value);
  if (duplicate_fd < 0) {
    return false;
  }
  DIR *entries = ::fdopendir(duplicate_fd);
  if (entries == nullptr) {
    (void)::close(duplicate_fd);
    return false;
  }
  bool has_temp = false;
  bool safe = true;
  while (true) {
    errno = 0;
    struct dirent *entry = ::readdir(entries);
    if (entry == nullptr) {
      safe = errno == 0;
      break;
    }
    if (std::strcmp(entry->d_name, ".") == 0 ||
        std::strcmp(entry->d_name, "..") == 0) {
      continue;
    }
    if (std::strcmp(entry->d_name, "snapshot.tmp") != 0) {
      safe = false;  // refuse unknown entries; never delete user material
      break;
    }
    struct stat st {};
    if (::fstatat(directory.value, "snapshot.tmp", &st,
                  AT_SYMLINK_NOFOLLOW) != 0 ||
        !is_user_regular_file(st, uid_)) {
      safe = false;
      break;
    }
    has_temp = true;
  }
  (void)::closedir(entries);
  if (!safe) {
    return false;
  }
  if (has_temp && ::unlinkat(directory.value, "snapshot.tmp", 0) != 0) {
    return false;
  }
  if (!directory.close_checked()) {
    return false;
  }
  return ::unlinkat(parent_.value, run_name_.c_str(), AT_REMOVEDIR) == 0;
}

bool Worker::scan_revisions(std::vector<Revision> &revisions) noexcept {
  if (!stage(FaultStage::RecoveryScan, true)) {
    return false;
  }
  const int duplicate_fd = ::dup(revisions_.value);
  if (duplicate_fd < 0) {
    return false;
  }
  DIR *directory = ::fdopendir(duplicate_fd);
  if (directory == nullptr) {
    (void)::close(duplicate_fd);
    return false;
  }
  bool okay = true;
  try {
    while (true) {
      errno = 0;
      struct dirent *entry = ::readdir(directory);
      if (entry == nullptr) {
        if (errno != 0) {
          okay = false;
        }
        break;
      }
      if (std::strcmp(entry->d_name, ".") == 0 ||
          std::strcmp(entry->d_name, "..") == 0) {
        continue;
      }
      Revision revision;
      if (!parse_revision_name(entry->d_name, revision)) {
        okay = false;
        break;
      }
      struct stat st {};
      if (::fstatat(revisions_.value, entry->d_name, &st,
                    AT_SYMLINK_NOFOLLOW) != 0 ||
          !is_user_regular_file(st, uid_)) {
        okay = false;
        break;
      }
      revisions.push_back(std::move(revision));
    }
  } catch (...) {
    okay = false;
  }
  (void)::closedir(directory);
  if (!okay) {
    revisions.clear();
    return false;
  }
  std::sort(revisions.begin(), revisions.end(),
            [](const Revision &a, const Revision &b) {
              return a.sequence < b.sequence;
            });
  for (std::size_t i = 1; i < revisions.size(); ++i) {
    if (revisions[i - 1U].sequence == revisions[i].sequence) {
      revisions.clear();
      return false;
    }
  }
  return stage(FaultStage::RecoveryScan, false);
}

bool Worker::read_all(int fd, std::size_t size,
                      std::vector<std::uint8_t> &bytes,
                      FaultStage fault_stage) noexcept {
  if (size > options_.max_bytes || !stage(fault_stage, true)) {
    return false;
  }
  if (bytes.size() != size) {
    try {
      bytes.resize(size);
    } catch (...) {
      return false;
    }
  }
  std::size_t offset = 0;
  std::uint32_t interrupts = 0;
  while (offset < size) {
    const ssize_t count = ::read(fd, bytes.data() + offset, size - offset);
    if (count > 0) {
      offset += static_cast<std::size_t>(count);
      continue;
    }
    if (count == 0) {
      return false;
    }
    if (errno == EINTR && interrupts++ < options_.eintr_budget) {
      continue;
    }
    return false;
  }
  return stage(fault_stage, false);
}

bool Worker::verify_revision(const Revision &revision,
                             std::vector<std::uint8_t> &bytes,
                             recordwire::Snapshot &snapshot) noexcept {
  if (!stage(FaultStage::VerifyOpen, true)) {
    return false;
  }
  const int fd = ::openat(revisions_.value, revision.name.c_str(),
                          O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
  if (fd < 0) {
    return false;
  }
  if (!stage(FaultStage::VerifyOpen, false)) {
    (void)::close(fd);
    return false;
  }
  Fd file(fd);
  struct stat st {};
  if (::fstat(file.value, &st) != 0 || !is_user_regular_file(st, uid_) ||
      st.st_size < 0) {
    return false;
  }
  const std::size_t size = static_cast<std::size_t>(st.st_size);
  if (!read_all(file.value, size, bytes, FaultStage::VerifyRead)) {
    return false;
  }
  if (!stage(FaultStage::VerifyClose, true) || !file.close_checked() ||
      !stage(FaultStage::VerifyClose, false)) {
    return false;
  }
  const auto digest = digest_of(bytes);
  if (!equal_digest(digest, revision.digest)) {
    return false;
  }
  recordwire::ParseError parse_error = recordwire::ParseError::None;
  if (!recordwire::parse(bytes.data(), bytes.size(), snapshot, &parse_error)) {
    return false;
  }
  return true;
}

bool Worker::verify_published_noalloc(
    const Revision &revision, const std::vector<std::uint8_t> &expected,
    std::vector<std::uint8_t> &bytes) noexcept {
  if (!stage(FaultStage::VerifyOpen, true)) {
    return false;
  }
  const int fd = ::openat(revisions_.value, revision.name.c_str(),
                          O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
  if (fd < 0) {
    return false;
  }
  if (!stage(FaultStage::VerifyOpen, false)) {
    (void)::close(fd);
    return false;
  }
  Fd file(fd);
  struct stat st {};
  if (::fstat(file.value, &st) != 0 || !is_user_regular_file(st, uid_) ||
      st.st_size < 0 || static_cast<std::size_t>(st.st_size) != expected.size()) {
    return false;
  }
  // This is intentionally a separate read loop from read_all(): no
  // allocation-capable vector resize is reachable after rename.
  if (!stage(FaultStage::VerifyRead, true) || bytes.size() != expected.size()) {
    return false;
  }
  std::size_t offset = 0;
  std::uint32_t interrupts = 0;
  while (offset < expected.size()) {
    const ssize_t count =
        ::read(file.value, bytes.data() + offset, expected.size() - offset);
    if (count > 0) {
      offset += static_cast<std::size_t>(count);
      continue;
    }
    if (count < 0 && errno == EINTR && interrupts++ < options_.eintr_budget) {
      continue;
    }
    return false;
  }
  if (!stage(FaultStage::VerifyRead, false)) {
    return false;
  }
  if (!stage(FaultStage::VerifyClose, true) || !file.close_checked() ||
      !stage(FaultStage::VerifyClose, false)) {
    return false;
  }
  const auto digest = digest_of(bytes);
  return equal_digest(digest, revision.digest) && bytes == expected;
}

bool Worker::sync_fd(int fd, FaultStage stage_id) noexcept {
  if (!stage(stage_id, true) || ::fsync(fd) != 0) {
    return false;
  }
  return stage(stage_id, false);
}

bool Worker::sync_directories() noexcept {
  if (!sync_fd(revisions_.value, FaultStage::RevisionDirectorySync)) {
    return false;
  }
  if (!sync_fd(parent_.value, FaultStage::ParentDirectorySync)) {
    return false;
  }
  return true;
}

bool Worker::write_all(int fd,
                       const std::vector<std::uint8_t> &bytes) noexcept {
  if (!stage(FaultStage::Write, true)) {
    return false;
  }
  std::size_t offset = 0;
  std::uint32_t interrupts = 0;
  while (offset < bytes.size()) {
    std::size_t requested = bytes.size() - offset;
#if defined(GA37_TEST_FAULTS)
    if (options_.fault.max_write != 0) {
      requested = std::min(requested, options_.fault.max_write);
    }
#endif
    const ssize_t written =
        ::write(fd, bytes.data() + offset, static_cast<size_t>(requested));
    if (written > 0) {
      offset += static_cast<std::size_t>(written);
      continue;
    }
    if (written < 0 && errno == EINTR && interrupts++ < options_.eintr_budget) {
      continue;
    }
    return false;
  }
  return stage(FaultStage::Write, false);
}

std::string Worker::revision_name(
    std::uint64_t sequence,
    const std::array<std::uint8_t, kDigestSize> &digest) {
  char sequence_text[kRevisionSequenceDigits + 1U]{};
  const int written = std::snprintf(
      sequence_text, sizeof(sequence_text), "%020" PRIu64, sequence);
  if (written != static_cast<int>(kRevisionSequenceDigits)) {
    return std::string();
  }
  std::string result(sequence_text, kRevisionSequenceDigits);
  result.push_back('-');
  result += hex_digest(digest);
  result += ".snap";
  return result;
}

// Linux has a race-free no-replace rename.  Other POSIX hosts use the pinned
// directory fd plus an existence check and then validate the result with
// O_NOFOLLOW; the parent/lock contract makes that fallback deterministic for
// ordinary callers and rejects a pre-existing malicious path.
int rename_noreplace(int old_dirfd, const char *old_name, int new_dirfd,
                     const char *new_name) noexcept {
#if defined(__linux__) && defined(SYS_renameat2)
  const long result = ::syscall(SYS_renameat2, old_dirfd, old_name, new_dirfd,
                                new_name, 1U /* RENAME_NOREPLACE */);
  if (result == 0) {
    return 0;
  }
  if (errno != ENOSYS && errno != EINVAL) {
    return -1;
  }
#endif
  struct stat st {};
  if (::fstatat(new_dirfd, new_name, &st, AT_SYMLINK_NOFOLLOW) == 0) {
    errno = EEXIST;
    return -1;
  }
  if (errno != ENOENT) {
    return -1;
  }
  return ::renameat(old_dirfd, old_name, new_dirfd, new_name);
}

CommitResult Worker::run(const void *data, std::size_t length) noexcept {
  bool published = false;
  std::uint64_t published_sequence = 0;
  std::array<std::uint8_t, kDigestSize> published_digest{};
  try {
    if (length > options_.max_bytes) {
      return fail(ErrorCode::InputTooLarge);
    }
    if (data == nullptr && length != 0) {
      return fail(ErrorCode::NullInput);
    }
    if (options_.parent_directory.empty() || options_.max_bytes == 0 ||
        options_.max_records == 0 || options_.eintr_budget == 0) {
      return fail(ErrorCode::InvalidOptions);
    }

    std::vector<std::uint8_t> input;
    if (length != 0) {
      input.assign(static_cast<const std::uint8_t *>(data),
                   static_cast<const std::uint8_t *>(data) + length);
    }
    recordwire::Snapshot input_snapshot;
    recordwire::ParseError parse_error = recordwire::ParseError::None;
    if (!recordwire::parse(input.data(), input.size(), input_snapshot,
                           &parse_error) ||
        input_snapshot.records.size() > options_.max_records) {
      return fail(ErrorCode::MalformedWire);
    }
    const auto input_digest = digest_of(input);

    if (owner_.terminal()) {
      CommitResult result = fail(ErrorCode::AlreadyTerminal,
                                 CommitStatus::VisibleButDurabilityUncertain);
      result.sha256 = input_digest;
      result.retained_in_memory = owner_.has_ambiguous_copy();
      return result;
    }

    if (!open_parent()) {
      return fail(ErrorCode::UnsafeParent);
    }
    if (!open_lock()) {
      return fail(ErrorCode::LockOpen);
    }
    if (!open_revisions()) {
      return fail(ErrorCode::RevisionDirectory);
    }
    if (!create_run_directory()) {
      return fail(ErrorCode::RunDirectory);
    }

    std::vector<Revision> revisions;
    if (!scan_revisions(revisions)) {
      return fail(ErrorCode::RecoveryEntry);
    }
    std::uint64_t maximum_sequence = 0;
    std::vector<std::uint8_t> latest_bytes;
    recordwire::Snapshot latest_snapshot;
    bool have_latest = false;
    std::uint64_t duplicate_sequence = 0;
    bool duplicate = false;

    for (const Revision &revision : revisions) {
      std::vector<std::uint8_t> bytes;
      recordwire::Snapshot snapshot;
      if (!verify_revision(revision, bytes, snapshot)) {
        return fail(ErrorCode::RecoveryDigest);
      }
      if (revision.digest == input_digest) {
        if (bytes.size() != input.size() ||
            std::memcmp(bytes.data(), input.data(), input.size()) != 0) {
          return fail(ErrorCode::RecoveryDigest);
        }
        duplicate = true;
        duplicate_sequence = revision.sequence;
      }
      if (revision.sequence > maximum_sequence) {
        maximum_sequence = revision.sequence;
        latest_bytes = std::move(bytes);
        latest_snapshot = std::move(snapshot);
        have_latest = true;
      }
    }

    if (duplicate) {
      const Revision *duplicate_revision = nullptr;
      for (const Revision &revision : revisions) {
        if (revision.sequence == duplicate_sequence) {
          duplicate_revision = &revision;
          break;
        }
      }
      if (duplicate_revision == nullptr || !stage(FaultStage::TemporaryOpen, true)) {
        return fail(ErrorCode::RecoveryEntry);
      }
      const int fd = ::openat(revisions_.value, duplicate_revision->name.c_str(),
                              O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
      if (fd < 0) {
        return uncertain(ErrorCode::VerifyOpen, duplicate_sequence,
                         input_digest, input);
      }
      Fd duplicate_file(fd);
      if (!sync_fd(duplicate_file.value, FaultStage::TemporaryFileSync) ||
          !duplicate_file.close_checked() || !sync_directories()) {
        return uncertain(ErrorCode::RevisionDirectorySync, duplicate_sequence,
                         input_digest, input);
      }
      CommitResult result;
      result.status = CommitStatus::DurableVerified;
      result.error = ErrorCode::None;
      result.sequence = duplicate_sequence;
      result.sha256 = input_digest;
      return result;
    }

    if (have_latest && !same_prefix(latest_bytes, latest_snapshot, input,
                                    input_snapshot)) {
      return fail(ErrorCode::SnapshotNotPrefix);
    }
    if (maximum_sequence == UINT64_MAX) {
      return fail(ErrorCode::SequenceExhausted);
    }
    const std::uint64_t sequence = maximum_sequence + 1U;
    Revision published_revision;
    published_revision.sequence = sequence;
    published_revision.digest = input_digest;
    published_revision.name = revision_name(sequence, input_digest);
    if (published_revision.name.empty()) {
      return fail(ErrorCode::SequenceExhausted);
    }

    // All ownership and vector capacity needed after rename is established
    // before publication.  A post-publish exception therefore cannot lose
    // the exact bytes or fall through to NotCommitted.
    std::vector<std::uint8_t> verified_bytes;
    try {
      verified_bytes.resize(input.size());
    } catch (...) {
      return fail(ErrorCode::AllocationFailure);
    }
    owner_.stage_owned_input(std::move(input));
    staged_input_ = true;
    published_sequence = sequence;
    published_digest = input_digest;

    if (!stage(FaultStage::TemporaryOpen, true)) {
      return fail(ErrorCode::TemporaryOpen);
    }
    const int temporary_fd = ::openat(
        run_.value, "snapshot.tmp",
        O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (temporary_fd < 0) {
      return fail(ErrorCode::TemporaryOpen);
    }
    if (!stage(FaultStage::TemporaryOpen, false)) {
      (void)::close(temporary_fd);
      return fail(ErrorCode::TemporaryOpen);
    }
    Fd temporary(temporary_fd);
    struct stat temporary_stat {};
    if (::fstat(temporary.value, &temporary_stat) != 0 ||
        !is_user_regular_file(temporary_stat, uid_) ||
        ::fchmod(temporary.value, 0600) != 0) {
      (void)temporary.close_checked();
      return fail(ErrorCode::TemporaryOpen);
    }
    if (!write_all(temporary.value, owner_.owned_input())) {
      (void)temporary.close_checked();
      return fail(ErrorCode::Write);
    }
    if (!sync_fd(temporary.value, FaultStage::TemporaryFileSync)) {
      (void)temporary.close_checked();
      return fail(ErrorCode::FileSync);
    }
    if (!stage(FaultStage::TemporaryClose, true) ||
        !temporary.close_checked()) {
      return fail(ErrorCode::FileClose);
    }
    if (!stage(FaultStage::TemporaryClose, false)) {
      return fail(ErrorCode::FileClose);
    }

    if (!stage(FaultStage::Rename, true)) {
      return fail(ErrorCode::Publish);
    }
    if (rename_noreplace(run_.value, "snapshot.tmp", revisions_.value,
                         published_revision.name.c_str()) != 0) {
      return fail(ErrorCode::Publish);
    }
    published = true;
    if (!stage(FaultStage::Rename, false)) {
      return uncertain(ErrorCode::Publish, sequence, input_digest,
                       owner_.owned_input());
    }

    // Deliberate test-only exception injection.  This is after the visible
    // rename and must be classified exactly like every other post-publish
    // exception by the handler below.
#if defined(GA37_TEST_FAULTS)
    if (options_.fault.throw_bad_alloc_after_publish) {
      throw std::bad_alloc();
    }
#endif

    // No vector/string/parser operation is performed after rename.  The
    // destination bytes buffer and revision name were prepared above.
    if (!verify_published_noalloc(published_revision, owner_.owned_input(),
                                  verified_bytes)) {
      return uncertain(ErrorCode::VerifyRead, sequence, input_digest,
                       owner_.owned_input());
    }
    if (!sync_directories()) {
      return uncertain(ErrorCode::ParentDirectorySync, sequence, input_digest,
                       owner_.owned_input());
    }

    CommitResult result;
    result.status = CommitStatus::DurableVerified;
    result.error = ErrorCode::None;
    result.sequence = sequence;
    result.sha256 = input_digest;
    return result;
  } catch (...) {
    if (published) {
      // The immutable destination is already visible.  The staged bytes were
      // moved into owner_ before rename, so this path is allocation-free and
      // terminal even for std::bad_alloc.
      return uncertain(ErrorCode::AllocationFailure, published_sequence,
                       published_digest, owner_.owned_input());
    }
    owner_.clear_owned_input();
    return fail(ErrorCode::AllocationFailure);
  }
}

}  // namespace

SnapshotWriter::SnapshotWriter(WriterOptions options)
    : options_(std::move(options)) {}

SnapshotWriter::~SnapshotWriter() = default;

void SnapshotWriter::stage_owned_input(std::vector<std::uint8_t> &&bytes) noexcept {
  ambiguous_bytes_ = std::move(bytes);
}

void SnapshotWriter::mark_ambiguous() noexcept { terminal_ = true; }

void SnapshotWriter::clear_owned_input() noexcept { ambiguous_bytes_.clear(); }

CommitResult SnapshotWriter::commit(void *ctx, const void *data,
                                    std::size_t length) noexcept {
  (void)ctx;
  try {
    Worker worker(*this, options_);
    last_commit_ = worker.run(data, length);
  } catch (...) {
    last_commit_ = CommitResult{};
    last_commit_.error = ErrorCode::AllocationFailure;
  }
  return last_commit_;
}

WriteResult SnapshotWriter::write(void *ctx, const void *data,
                                  std::size_t length) noexcept {
  const CommitResult result = commit(ctx, data, length);
  WriteResult callback_result;
  if (result.success()) {
    callback_result.error = 0;
    callback_result.transferred = length;
  } else {
    callback_result.error = -static_cast<int>(result.error);
    callback_result.transferred = 0;
  }
  return callback_result;
}

WriteResult SnapshotWriter::callback(void *ctx, const void *data,
                                     std::size_t length) noexcept {
  if (ctx == nullptr) {
    WriteResult result;
    result.error = -static_cast<int>(ErrorCode::InvalidOptions);
    result.transferred = 0;
    return result;
  }
  return static_cast<SnapshotWriter *>(ctx)->write(ctx, data, length);
}

}  // namespace ga37
