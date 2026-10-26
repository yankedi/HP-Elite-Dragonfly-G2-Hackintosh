#!/usr/bin/env python3
"""Check invariant source regions against the archived GA4.12 workload."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def region(text, start, end):
    return text[text.index(start):text.index(end, text.index(start))]


def main():
    paths = [ROOT / 'ga412/tools/managed-rt-probe.m', ROOT / 'ga413/tools/managed-rt-probe.m']
    old, new = [path.read_text() for path in paths]
    spans = [
        ('geometry_event_save_attrs_snapshot_helpers', '#import', 'static id<MTLCommandBuffer> beginCommand'),
        ('input_shader_pipeline_allocations_descriptors_upload', '    NSMutableData *input =', '    NSMutableArray *commands ='),
        ('renderpass_draw', '    MTLRenderPassDescriptor *rp', '    if (!finishCommand(renderCB'),
        ('GPU_copy_parameters', '    [blit copyFromTexture:', '    if (!finishCommand(copyCB'),
        ('snapshot_CPU_getBytes_tracer', '    NSData *gpu =', '    // A capture is not self-certified'),
    ]
    checks = []
    for label, start, new_end in spans:
        new_text = region(new, start, new_end)
        if label.startswith('geometry'):
            old_text = region(old, start, 'int main(')
        elif label.startswith('input'):
            old_text = region(old, start, '    uint64_t createNS =')
        elif label.startswith('renderpass'):
            old_text = region(old, start, '    id<MTLBlitCommandEncoder> blit =')
            new_text = new_text.replace('[renderCB renderCommandEncoder', '[cb renderCommandEncoder')
        elif label.startswith('GPU_copy'):
            old_text = region(old, start, '    CBStamp *stamp =')
        else:
            old_text = region(old, start, new_end)
        if old_text != new_text:
            raise ValueError('invariant region changed: ' + label)
        checks.append({'region': label, 'identical_after_CB_variable_rename_only': True,
                       'sha256': hashlib.sha256(old_text.encode()).hexdigest()})
    for token in ['drawPrimitives:', 'synchronizeResource:target', 'copyFromTexture:target']:
        if old.count(token) != 1 or new.count(token) != 1:
            raise ValueError('GPU operation count changed: ' + token)
    if new.count('= beginCommand(queue,') != 3 or new.count('if (!finishCommand(') != 3:
        raise ValueError('not exactly three separately completed command boundaries')
    result = {'status': 'SOURCE_SCOPE_PASS_NOT_GPU_EXECUTION', 'checks': checks,
              'GPU_operation_counts': {'render': 1, 'synchronize': 1, 'copy': 1},
              'explicit_CB_boundaries': 3, 'extra_pre_sync_copy': False,
              'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
