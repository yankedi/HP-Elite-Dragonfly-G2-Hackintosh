#!/usr/bin/env python3
from pathlib import Path
root = Path(__file__).resolve().parent.parent
a = (root / 'src/compiler-adapter.cpp').read_text()
b = (root / 'src/llvm-bridge.cpp').read_text()
checks = {
    'adapter_rejects_malformed': 'refusing malformed request' in a,
    'adapter_no_fake_success': 'return 0;   // never report a fake compilation success' in a,
    'adapter_reply_check': 'old compiler returned success without a reply; rejecting' in a,
    'adapter_llvm_cleanup': all(x in a for x in ('LLVMDisposeModule', 'LLVMDisposeMemoryBuffer', 'LLVMContextDispose')),
    'adapter_thread_once': 'pthread_once' in a and 't_jb' in a,
    'adapter_fault_guard': 'faulted' in a and 'retains LLVM objects' in a,
    'adapter_plugin_paths': 'libMTLIGCCompilerPluginOld.dylib' in a and 'plugin path unavailable' in a,
    'bridge_versioned_and_current': 'Versions/32023' in b and 'Versions/Current' in b,
    'bridge_dyld_images': '_dyld_image_count' in b and 'libLLVM via loaded image' in b,
    'bridge_no_dst_guard': 'missing dst string' in b,
    'bridge_invalid_range': 'invalid range' in b and 'falling back' in b,
    'bridge_mtlcompiler_service': 'MTLCompilerService' in b,
}
bad = [k for k, v in checks.items() if not v]
print(f"checks={len(checks)} failed={bad}")
raise SystemExit(1 if bad else 0)
