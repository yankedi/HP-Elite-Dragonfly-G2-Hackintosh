#include "snapshot_writer.hpp"

#include <cstddef>
#include <vector>

// Self-contained nominal bridge example only.  The real GA36 A executor must
// use &SnapshotWriter::callback_adapter<Capture36::WriteResult> from its
// unchanged header, not assume that PipelineWriteResult is nominally exact.
// The executor keeps ownership of the complete snapshot until result.success()
// is true; it does not acknowledge VisibleButDurabilityUncertain.
ga37::WriteResult write_complete_snapshot(ga37::SnapshotWriter &writer,
                                           const std::vector<std::uint8_t> &snapshot) noexcept {
  ga37::PipelineWriteResult callback = writer.pipeline_callback();
  const ga37::WriteResult callback_result =
      callback(&writer, snapshot.data(), snapshot.size());
  (void)callback_result;
  return writer.last_commit().success()
             ? ga37::WriteResult{0, snapshot.size()}
             : callback_result;
}
