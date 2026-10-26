#include "snapshot_writer.hpp"

#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dirent.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <iostream>
#include <string>
#include <utility>
#include <vector>

namespace {

using ga37::CommitStatus;
using ga37::CommitResult;
using ga37::ErrorCode;
using ga37::FaultStage;
using ga37::SnapshotWriter;

struct TestState {
  int passed = 0;
  int failed = 0;

  void check(bool value, const char *what) {
    if (value) {
      ++passed;
      std::cout << "PASS " << what << '\n';
    } else {
      ++failed;
      std::cerr << "FAIL " << what << '\n';
    }
  }
};

void put16_at(std::vector<std::uint8_t> &out, std::size_t offset,
              std::uint16_t value) {
  out[offset] = static_cast<std::uint8_t>(value);
  out[offset + 1U] = static_cast<std::uint8_t>(value >> 8U);
}

void put32_at(std::vector<std::uint8_t> &out, std::size_t offset,
              std::uint32_t value) {
  out[offset] = static_cast<std::uint8_t>(value);
  out[offset + 1U] = static_cast<std::uint8_t>(value >> 8U);
  out[offset + 2U] = static_cast<std::uint8_t>(value >> 16U);
  out[offset + 3U] = static_cast<std::uint8_t>(value >> 24U);
}

void put64_at(std::vector<std::uint8_t> &out, std::size_t offset,
              std::uint64_t value) {
  for (std::size_t i = 0; i < 8U; ++i) {
    out[offset + i] = static_cast<std::uint8_t>(value >> (i * 8U));
  }
}

struct Record {
  std::uint32_t index;
  std::string bytes;
};

struct LegacyWriteResult {
  int error;
  std::size_t transferred;
};

std::vector<std::uint8_t> make_wire(bool fault, std::uint16_t version,
                                    const std::vector<Record> &records) {
  const std::size_t record_size =
      fault ? 108U : (version == 3U ? 0xc2f8U : 0xc2a0U);
  std::vector<std::uint8_t> result(record_size * records.size(), 0);
  for (std::size_t i = 0; i < records.size(); ++i) {
    const Record &record = records[i];
    const std::size_t offset = i * record_size;
    if (fault) {
      put32_at(result, offset, 0x34464754U);  // TGF4 / 108BFault v1
      put16_at(result, offset + 4U, 1U);
      put16_at(result, offset + 6U, 108U);
      put32_at(result, offset + 8U, 31U);
      put32_at(result, offset + 12U, 127U);
      put32_at(result, offset + 16U, 0U);
      put32_at(result, offset + 20U, 3U);
      put32_at(result, offset + 24U, 1U);
      put32_at(result, offset + 28U, 1U);
      put32_at(result, offset + 32U, 1U);
      put64_at(result, offset + 36U, i + 1U);
      put64_at(result, offset + 44U, 100U + i);
      put64_at(result, offset + 52U, 1U);
      put64_at(result, offset + 60U, i + 1U);
      put64_at(result, offset + 68U, 1U);
      put64_at(result, offset + 76U, 1U);
      put64_at(result, offset + 84U, 1U);
      put32_at(result, offset + 92U,
               record.bytes.empty() ? 0U : static_cast<unsigned char>(record.bytes[0]));
    } else {
      put32_at(result, offset, 0x47414854U);  // THAG
      put32_at(result, offset + 4U, record.index);
      put32_at(result, offset + 12U, 1U);
      for (std::size_t j = 0; j < record.bytes.size() && offset + 16U + j < offset + record_size;
           ++j) {
        result[offset + 16U + j] = static_cast<std::uint8_t>(record.bytes[j]);
      }
      if (version == 3U) {
        put32_at(result, offset + 0xc2a0U, 3U);
        put32_at(result, offset + 0xc2a4U, 0xc2f8U);
      }
    }
  }
  return result;
}

std::string make_root() {
  char path[] = "/tmp/ga37-track-b-test-XXXXXX";
  const char *made = ::mkdtemp(path);
  return made == nullptr ? std::string() : std::string(made);
}

std::size_t revision_count(const std::string &root) {
  const std::string path = root + "/revisions";
  DIR *directory = ::opendir(path.c_str());
  if (directory == nullptr) {
    return 0;
  }
  std::size_t count = 0;
  while (struct dirent *entry = ::readdir(directory)) {
    if (std::strcmp(entry->d_name, ".") != 0 &&
        std::strcmp(entry->d_name, "..") != 0) {
      ++count;
    }
  }
  (void)::closedir(directory);
  return count;
}

std::size_t run_directory_count(const std::string &root) {
  DIR *directory = ::opendir(root.c_str());
  if (directory == nullptr) {
    return 0;
  }
  std::size_t count = 0;
  while (struct dirent *entry = ::readdir(directory)) {
    if (std::strncmp(entry->d_name, ".snapshot-run-", 14U) == 0) {
      ++count;
    }
  }
  (void)::closedir(directory);
  return count;
}

std::vector<std::uint8_t> read_revision(const std::string &root) {
  const std::string path = root + "/revisions";
  DIR *directory = ::opendir(path.c_str());
  if (directory == nullptr) {
    return {};
  }
  std::string name;
  while (struct dirent *entry = ::readdir(directory)) {
    if (std::strlen(entry->d_name) == 90U) {
      name = entry->d_name;
      break;
    }
  }
  (void)::closedir(directory);
  if (name.empty()) {
    return {};
  }
  const int fd = ::open((path + "/" + name).c_str(), O_RDONLY | O_CLOEXEC);
  if (fd < 0) {
    return {};
  }
  struct stat st {};
  if (::fstat(fd, &st) != 0 || st.st_size < 0) {
    (void)::close(fd);
    return {};
  }
  std::vector<std::uint8_t> bytes(static_cast<std::size_t>(st.st_size));
  std::size_t offset = 0;
  while (offset < bytes.size()) {
    const ssize_t n = ::read(fd, bytes.data() + offset, bytes.size() - offset);
    if (n <= 0) {
      (void)::close(fd);
      return {};
    }
    offset += static_cast<std::size_t>(n);
  }
  (void)::close(fd);
  return bytes;
}

ga37::WriterOptions options(const std::string &root,
                            ga37::FaultInjection fault = {}) {
  ga37::WriterOptions result;
  result.parent_directory = root;
  result.max_bytes = 1024U * 1024U;
  result.max_records = 32;
  result.eintr_budget = 16;
  result.fault = fault;
  return result;
}

bool is_success(const CommitResult &result) {
  return result.status == CommitStatus::DurableVerified && result.success();
}

bool is_uncertain(const CommitResult &result) {
  return result.status == CommitStatus::VisibleButDurabilityUncertain &&
         !result.success();
}

void test_basic(TestState &state) {
  const std::string root = make_root();
  const auto base = make_wire(false, 2, {{0, "first"}});
  const auto extension = make_wire(false, 2, {{0, "first"}, {1, "second"}});
  const auto changed = make_wire(false, 2, {{0, "changed"}, {1, "second"}});

  SnapshotWriter writer(options(root));
  const CommitResult first = writer.commit(nullptr, base.data(), base.size());
  state.check(is_success(first) && first.sequence == 1U,
              "initial full snapshot is durable");
  const ga37::WriteResult callback_result =
      writer.pipeline_callback()(&writer, base.data(), base.size());
  state.check(callback_result.error == 0 &&
                  callback_result.transferred == base.size() &&
                  writer.last_commit().success(),
              "GA36 callback shape acknowledges only durable commit");
  const LegacyWriteResult legacy_result =
      SnapshotWriter::callback_adapter<LegacyWriteResult>(
          &writer, base.data(), base.size());
  state.check(legacy_result.error == 0 &&
                  legacy_result.transferred == base.size(),
              "nominal GA36 result type adapter preserves exact fields");
  const std::size_t one_revision = revision_count(root);
  const CommitResult duplicate =
      writer.commit(nullptr, base.data(), base.size());
  state.check(is_success(duplicate) && duplicate.sequence == 1U &&
                  duplicate.sha256 == first.sha256 &&
                  revision_count(root) == one_revision,
              "repeated callback is content-idempotent");
  const CommitResult second =
      writer.commit(nullptr, extension.data(), extension.size());
  state.check(is_success(second) && second.sequence == 2U &&
                  revision_count(root) == 2U,
              "prefix extension gets a new immutable revision");
  const CommitResult rejected =
      writer.commit(nullptr, changed.data(), changed.size());
  state.check(rejected.status == CommitStatus::NotCommitted &&
                  rejected.error == ErrorCode::SnapshotNotPrefix &&
                  revision_count(root) == 2U,
              "same index with different bytes is refused");
  state.check(read_revision(root) == base,
              "exact bytes of first committed evidence remain readable");

  ga37::recordwire::ReadOnlyHistory history;
  state.check(ga37::recordwire::ReadOnlyHistory::copy_from_history_readonly(
                  base.data(), base.size(), history) &&
                  history.copy_bytes() == base,
              "history is parser-validated and copied without field casts");
}

void test_parser_rejections(TestState &state) {
  const auto valid = make_wire(false, 3, {{0, "a"}, {1, "b"}});
  ga37::recordwire::Snapshot parsed;
  ga37::recordwire::ParseError error = ga37::recordwire::ParseError::None;
  state.check(!ga37::recordwire::parse(valid.data(), valid.size() - 1U, parsed,
                                       &error),
              "truncated wire is rejected");
  auto mixed = make_wire(false, 2, {{0, "a"}, {1, "b"}});
  put32_at(mixed, 0xc2a0U, 0x34464754U);
  state.check(!ga37::recordwire::parse(mixed.data(), mixed.size(), parsed,
                                       &error),
              "mixed record kind is rejected");
  auto bad_index = make_wire(false, 2, {{1, "a"}});
  state.check(!ga37::recordwire::parse(bad_index.data(), bad_index.size(),
                                       parsed, &error),
              "shifted record index is rejected");
  auto fault = make_wire(true, 1, {{0, "fault"}});
  state.check(ga37::recordwire::parse(fault.data(), fault.size(), parsed,
                                      &error) &&
                  parsed.kind == ga37::recordwire::Kind::Fault108B,
              "108BFault v1 framing is parsed separately");
}

void test_fault_stage(TestState &state, FaultStage stage,
                      CommitStatus expected_status) {
  const std::string root = make_root();
  const auto payload = make_wire(false, 2, {{0, "fault-stage"}});
  ga37::FaultInjection fault;
  fault.fail_stage = stage;
  SnapshotWriter writer(options(root, fault));
  const CommitResult result =
      writer.commit(nullptr, payload.data(), payload.size());
  const bool status_ok = expected_status == CommitStatus::NotCommitted
                             ? result.status == CommitStatus::NotCommitted
                             : is_uncertain(result);
  state.check(status_ok &&
                  (expected_status == CommitStatus::NotCommitted ||
                   writer.terminal()),
              "fault stage has the documented commit classification");
}

void test_old_evidence_preserved(TestState &state) {
  const std::string root = make_root();
  const auto base = make_wire(false, 2, {{0, "old-evidence"}});
  const auto next = make_wire(false, 2, {{0, "old-evidence"}, {1, "new"}});
  SnapshotWriter initial(options(root));
  const CommitResult committed =
      initial.commit(nullptr, base.data(), base.size());
  const std::vector<std::uint8_t> before = read_revision(root);
  ga37::FaultInjection fault;
  fault.fail_stage = FaultStage::RevisionDirectorySync;
  SnapshotWriter failing(options(root, fault));
  const CommitResult result = failing.commit(nullptr, next.data(), next.size());
  state.check(is_success(committed) && is_uncertain(result) &&
                  read_revision(root) == before && revision_count(root) == 2U,
              "post-rename failure preserves previous evidence SHA bytes");
  SnapshotWriter recovery(options(root));
  const CommitResult retry =
      recovery.commit(nullptr, next.data(), next.size());
  state.check(is_success(retry) && retry.sequence == result.sequence,
              "fresh process recovers visible ambiguous revision");
}

void test_symlink_rejection(TestState &state) {
  const std::string root = make_root();
  const auto payload = make_wire(false, 2, {{0, "symlink"}});
  const std::string target = root + "/other";
  const int fd = ::open(target.c_str(), O_CREAT | O_WRONLY | O_CLOEXEC, 0600);
  if (fd >= 0) {
    (void)::close(fd);
  }
  (void)::symlink("other", (root + "/.snapshot.lock").c_str());
  SnapshotWriter writer(options(root));
  const CommitResult result = writer.commit(nullptr, payload.data(), payload.size());
  state.check(result.status == CommitStatus::NotCommitted &&
                  result.error == ErrorCode::LockOpen,
              "pre-existing lock symlink is rejected");
}

void test_prefix_component_symlink_rejection(TestState &state) {
  const std::string outer = make_root();
  const std::string real_prefix = outer + "/prefix-real";
  const std::string parent = real_prefix + "/parent";
  (void)::mkdir(real_prefix.c_str(), 0700);
  (void)::mkdir(parent.c_str(), 0700);
  const std::string link = outer + "/prefix-link";
  (void)::symlink("prefix-real", link.c_str());

  const auto payload = make_wire(false, 2, {{0, "prefix-link"}});
  ga37::WriterOptions writer_options = options(link + "/parent");
  SnapshotWriter writer(writer_options);
  const CommitResult result =
      writer.commit(nullptr, payload.data(), payload.size());
  state.check(result.status == CommitStatus::NotCommitted &&
                  result.error == ErrorCode::UnsafeParent &&
                  revision_count(parent) == 0U,
              "symlinked absolute parent prefix is refused without following target");
}

void test_post_publish_allocation_is_terminal(TestState &state) {
  const std::string root = make_root();
  const auto payload = make_wire(false, 2, {{0, "post-publish-allocation"}});
  ga37::FaultInjection fault;
  fault.throw_bad_alloc_after_publish = true;
  SnapshotWriter failing(options(root, fault));
  const CommitResult result =
      failing.commit(nullptr, payload.data(), payload.size());
  state.check(is_uncertain(result) && failing.terminal() &&
                  result.retained_in_memory && failing.has_ambiguous_copy() &&
                  revision_count(root) == 1U,
              "post-publish bad_alloc is terminal visible uncertainty with retained bytes");

  SnapshotWriter recovery(options(root));
  const CommitResult recovered =
      recovery.commit(nullptr, payload.data(), payload.size());
  state.check(is_success(recovered) && recovered.sequence == 1U,
              "fresh process recovers post-publish allocation ambiguity");
}

void test_run_cleanup_and_bounded_admission(TestState &state) {
  const std::string root = make_root();
  const auto payload = make_wire(false, 2, {{0, "run-cleanup"}});
  const auto next_payload =
      make_wire(false, 2, {{0, "run-cleanup"}, {1, "next"}});
  {
    SnapshotWriter writer(options(root));
    state.check(is_success(writer.commit(nullptr, payload.data(), payload.size())) &&
                    run_directory_count(root) == 0U,
                "successful callback removes its private run directory");
  }

  ga37::FaultInjection fault;
  fault.fail_stage = FaultStage::Write;
  {
    SnapshotWriter writer(options(root, fault));
    const CommitResult result =
        writer.commit(nullptr, next_payload.data(), next_payload.size());
    state.check(result.status == CommitStatus::NotCommitted &&
                    run_directory_count(root) == 0U,
                "pre-publish write failure removes only known temporary state");
  }

  const std::string bounded_root = make_root();
  for (unsigned int i = 0; i < 64U; ++i) {
    const std::string name = bounded_root + "/.snapshot-run-preexisting-" +
                             std::to_string(i);
    (void)::mkdir(name.c_str(), 0700);
  }
  SnapshotWriter bounded(options(bounded_root));
  const CommitResult bounded_result =
      bounded.commit(nullptr, payload.data(), payload.size());
  state.check(bounded_result.status == CommitStatus::NotCommitted &&
                  bounded_result.error == ErrorCode::RunDirectory,
              "bounded run-directory admission refuses unbounded residue");
}

void test_lowercase_revision_names(TestState &state) {
  const std::string root = make_root();
  const auto payload = make_wire(false, 2, {{0, "canonical-digest"}});
  SnapshotWriter initial(options(root));
  const CommitResult committed =
      initial.commit(nullptr, payload.data(), payload.size());
  const std::string revisions = root + "/revisions";
  DIR *directory = ::opendir(revisions.c_str());
  std::string original;
  if (directory != nullptr) {
    while (struct dirent *entry = ::readdir(directory)) {
      if (std::strlen(entry->d_name) == 90U) {
        original = entry->d_name;
        break;
      }
    }
    (void)::closedir(directory);
  }
  std::string uppercase = original;
  bool changed = false;
  for (std::size_t i = 21U; i < 85U; ++i) {
    if (uppercase[i] >= 'a' && uppercase[i] <= 'f') {
      uppercase[i] = static_cast<char>(uppercase[i] - 'a' + 'A');
      changed = true;
      break;
    }
  }
  if (!changed && uppercase.size() == 90U) {
    uppercase[21] = 'A';
    changed = true;
  }
  const int rename_result =
      changed ? ::rename((revisions + "/" + original).c_str(),
                         (revisions + "/" + uppercase).c_str())
              : -1;
  SnapshotWriter recovery(options(root));
  const CommitResult result =
      recovery.commit(nullptr, payload.data(), payload.size());
  state.check(is_success(committed) && changed && rename_result == 0 &&
                  result.status == CommitStatus::NotCommitted &&
                  result.error == ErrorCode::RecoveryEntry,
              "uppercase digest spelling is rejected during recovery");
}

void test_untrusted_recovery_rejection(TestState &state) {
  const auto payload = make_wire(false, 2, {{0, "untrusted"}});
  const std::string malformed_root = make_root();
  (void)::mkdir((malformed_root + "/revisions").c_str(), 0700);
  const std::string malformed_path = malformed_root + "/revisions/not-a-revision";
  const int malformed_fd =
      ::open(malformed_path.c_str(), O_CREAT | O_WRONLY | O_CLOEXEC, 0600);
  if (malformed_fd >= 0) {
    (void)::write(malformed_fd, "x", 1);
    (void)::close(malformed_fd);
  }
  SnapshotWriter malformed(options(malformed_root));
  const CommitResult malformed_result = malformed.commit(
      nullptr, payload.data(), payload.size());
  state.check(malformed_result.status == CommitStatus::NotCommitted &&
                  malformed_result.error == ErrorCode::RecoveryEntry,
              "unexpected recovery pathname is rejected");

  const std::string symlink_root = make_root();
  const std::string other = symlink_root + "/other";
  (void)::mkdir(other.c_str(), 0700);
  (void)::symlink("other", (symlink_root + "/revisions").c_str());
  SnapshotWriter symlinked(options(symlink_root));
  const CommitResult symlink_result =
      symlinked.commit(nullptr, payload.data(), payload.size());
  state.check(symlink_result.status == CommitStatus::NotCommitted &&
                  symlink_result.error == ErrorCode::RevisionDirectory,
              "revision directory symlink is rejected");
}

void test_crash_recovery(TestState &state) {
  const auto payload = make_wire(false, 2, {{0, "crash-recovery"}});
  const FaultStage stages[] = {
      FaultStage::ParentOpen,          FaultStage::LockOpen,
      FaultStage::LockAcquire,         FaultStage::RevisionDirectory,
      FaultStage::RunDirectory,        FaultStage::RecoveryScan,
      FaultStage::TemporaryOpen,       FaultStage::Write,
      FaultStage::TemporaryFileSync,   FaultStage::TemporaryClose,
      FaultStage::Rename,              FaultStage::VerifyOpen,
      FaultStage::VerifyRead,          FaultStage::VerifyClose,
      FaultStage::RevisionDirectorySync, FaultStage::ParentDirectorySync};
  for (FaultStage stage : stages) {
    for (bool before : {true, false}) {
      const std::string root = make_root();
      pid_t child = ::fork();
      if (child == 0) {
        ga37::FaultInjection fault;
        if (before) {
          fault.crash_before = stage;
        } else {
          fault.crash_after = stage;
        }
        SnapshotWriter writer(options(root, fault));
        (void)writer.commit(nullptr, payload.data(), payload.size());
        ::_exit(3);
      }
      int status = 0;
      (void)::waitpid(child, &status, 0);
      SnapshotWriter recovery(options(root));
      const CommitResult result =
          recovery.commit(nullptr, payload.data(), payload.size());
      state.check(WIFEXITED(status) && WEXITSTATUS(status) >= 90 &&
                      is_success(result),
                  "fork crash before/after stage recovers idempotently");
    }
  }
}

void test_multiwriter(TestState &state) {
  const std::string root = make_root();
  const auto payload = make_wire(false, 2, {{0, "multiwriter"}});
  constexpr int kChildren = 4;
  std::array<pid_t, kChildren> children{};
  for (int i = 0; i < kChildren; ++i) {
    children[static_cast<std::size_t>(i)] = ::fork();
    if (children[static_cast<std::size_t>(i)] == 0) {
      SnapshotWriter writer(options(root));
      const CommitResult result =
          writer.commit(nullptr, payload.data(), payload.size());
      ::_exit(is_success(result) ? 0 : 1);
    }
  }
  bool all_ok = true;
  for (pid_t child : children) {
    int status = 0;
    (void)::waitpid(child, &status, 0);
    all_ok = all_ok && WIFEXITED(status) && WEXITSTATUS(status) == 0;
  }
  state.check(all_ok && revision_count(root) == 1U,
              "one flock serializes competing identical writers");
}

}  // namespace

int main() {
  TestState state;
  test_basic(state);
  test_parser_rejections(state);
  test_fault_stage(state, FaultStage::ParentOpen, CommitStatus::NotCommitted);
  test_fault_stage(state, FaultStage::LockOpen, CommitStatus::NotCommitted);
  test_fault_stage(state, FaultStage::RevisionDirectory,
                   CommitStatus::NotCommitted);
  test_fault_stage(state, FaultStage::LockAcquire,
                   CommitStatus::NotCommitted);
  test_fault_stage(state, FaultStage::RunDirectory,
                   CommitStatus::NotCommitted);
  test_fault_stage(state, FaultStage::RecoveryScan,
                   CommitStatus::NotCommitted);
  test_fault_stage(state, FaultStage::TemporaryOpen,
                   CommitStatus::NotCommitted);
  test_fault_stage(state, FaultStage::Write, CommitStatus::NotCommitted);
  test_fault_stage(state, FaultStage::TemporaryFileSync,
                   CommitStatus::NotCommitted);
  test_fault_stage(state, FaultStage::TemporaryClose,
                   CommitStatus::NotCommitted);
  test_fault_stage(state, FaultStage::Rename, CommitStatus::NotCommitted);
  test_fault_stage(state, FaultStage::VerifyOpen,
                   CommitStatus::VisibleButDurabilityUncertain);
  test_fault_stage(state, FaultStage::VerifyRead,
                   CommitStatus::VisibleButDurabilityUncertain);
  test_fault_stage(state, FaultStage::VerifyClose,
                   CommitStatus::VisibleButDurabilityUncertain);
  test_fault_stage(state, FaultStage::RevisionDirectorySync,
                   CommitStatus::VisibleButDurabilityUncertain);
  test_fault_stage(state, FaultStage::ParentDirectorySync,
                   CommitStatus::VisibleButDurabilityUncertain);
  test_old_evidence_preserved(state);
  test_symlink_rejection(state);
  test_prefix_component_symlink_rejection(state);
  test_post_publish_allocation_is_terminal(state);
  test_run_cleanup_and_bounded_admission(state);
  test_lowercase_revision_names(state);
  test_untrusted_recovery_rejection(state);
  test_crash_recovery(state);
  test_multiwriter(state);
  std::cout << "SUMMARY passed=" << state.passed << " failed=" << state.failed
            << '\n';
  return state.failed == 0 ? 0 : 1;
}
