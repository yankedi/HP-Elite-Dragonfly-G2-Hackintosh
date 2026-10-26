# Native XNU adapter compile

Date: 2026-10-21

## Result

**PASS: four actual GA41 adapter translation units compile to real x86_64
Mach-O relocatable objects.** The compile is source/header evidence only. It is
not a target KDK build, ABI-25G83 proof, link, kext bundle, install, load, or
hardware test.

Compiled without changing the adapters:

| Translation unit | Object | SHA-256 |
|---|---|---|
| `i915-xnu/os-compat/xnu_memory.cpp` | `build/xnu-header-check/xnu_memory.o` | `55b6859841544043c97211c09e7d1ede10bfbcd9ff427b3b78bea1b49f6f95ad` |
| `i915-xnu/os-compat/xnu_copy.cpp` | `build/xnu-header-check/xnu_copy.o` | `2bc0152ee694cf44981cbdeaf08a971ca828c5bd3ebd9c91bd1b93af6be39b8c` |
| `i915-xnu/gem/gx_gem.c` | `build/xnu-header-check/gx_gem.o` | `ea1922762ef7f8c182914f3e960580f32a664e87d6e727c4a49fb225f563115b` |
| `i915-xnu/drm/gx_ioctl.c` | `build/xnu-header-check/gx_ioctl.o` | `39aa67eea7326dcbe543282f461959e1596571c31523cbed0f9b97025160fa30` |

`file` and LLVM object inspection both identify every artifact as `Mach-O
64-bit x86_64 object`, `FileType: Relocatable`, `CpuType: X86-64`, and
`Magic64 (0xFEEDFACF)`. The complete inspection is in
`logs/xnu-sdk-009-object-audit/stdout.txt`.

## Public source kit and license

The missing `libkern/c++/OSPtr.h` was supplied by the public upstream
MacKernelSDK source kit, fetched only after checking its origin and license:

| Item | Value |
|---|---|
| Origin | `https://github.com/acidanthera/MacKernelSDK` |
| Pinned ref | `master` at `3f750085caa17ec3a7880f11c11bf4f48cd6a164` |
| Archive | `https://codeload.github.com/acidanthera/MacKernelSDK/tar.gz/3f750085caa17ec3a7880f11c11bf4f48cd6a164` |
| Archive SHA-256 | `8931e622b6d16a7052cb2c2dabe16be06963a34b747f19e6cda2bbe8bc7e2557` |
| Archive size | 2,679,518 bytes |
| Local source | `sources/mackernelsdk/` (1,232 files, 16M) |
| License | Apple Public Source License 2.0, `sources/mackernelsdk/LICENSE.txt` |
| License SHA-256 | `e5881019d8766c1e88a5fe1dbca4ba40c78011d41fcb18f6e9f50df60182685b` |

The kit is an open/public kernel-extension header and library collection. It
is not a full Apple user SDK and no Apple SDK binary, Xcode SDK, or target KDK
was acquired. Its README says it is based on the macOS 11 SDK and includes
additional public/community headers; that provenance does not make it an
exact Tahoe `xnu-12377.161.14` KDK or `25G83` ABI contract. Relevant source,
license, and file hashes are retained in
`logs/xnu-sdk-010-provenance/stdout.txt`; the origin/license retrieval and
the 404 for the repository's non-existent bare `LICENSE` path are retained in
`logs/xnu-sdk-001-origin-license/`.

## Toolchain and command boundary

The Nix wrapper was not used to drive the Darwin target. The script
`tools/compile-xnu.sh` discovers the wrapper with `readlink`, reads its
`nix-support/cc-cflags`, extracts the resource directory, and extracts the
underlying unwrapped compiler from the wrapper script:

```text
wrapper:      /nix/store/2msw5nclhpsm80z65dqmjiv8kkras989-clang-wrapper-21.1.8/bin/clang++
cc-cflags:    /nix/store/2msw5nclhpsm80z65dqmjiv8kkras989-clang-wrapper-21.1.8/nix-support/cc-cflags
unwrapped:    /nix/store/jmgw1yz3xm3bpgrk9r84jkcynskdbd40-clang-21.1.8/bin/clang++
resource-dir: /nix/store/2msw5nclhpsm80z65dqmjiv8kkras989-clang-wrapper-21.1.8/resource-root
clang:        21.1.8
target:       x86_64-apple-macos26
```

The compile uses `-ffreestanding`, `-nostdinc`, kernel C++ flags
(`-fno-exceptions`, `-fno-rtti`), the genuine MacKernelSDK `Headers`, GA41
headers, and the already-pinned Linux UAPI source. It invokes `-c` four times;
there is deliberately no linker invocation and no use of `libkmod.a`.

The C adapters use Linux DRM UAPI declarations only. Since the Darwin target
does not define Linux's `__linux__`, `drm.h` takes its BSD/UAPI branch, which
uses the MacKernelSDK `stdint.h`, `sys/types.h`, and `sys/ioccom.h` types. This
is not a generated compatibility header or a redefinition. The first attempt
to force `__KERNEL__` exposed that the partial Linux source selection lacks
`linux/types.h`; that failure is preserved in
`logs/xnu-sdk-006-c-probe/`. The successful C probe and final build are in
`logs/xnu-sdk-007-c-probe/` and `logs/xnu-sdk-008-native-build/`.

## Failure history and evidence

The pre-SDK probes are preserved and not rewritten:

* `logs/xnu-compile-001/` records the initial wrapped-Clang/resource-path
  failure.
* `logs/xnu-compile-002/` records the corrected resource path reaching the
  genuine XNU header and stopping at missing `libkern/c++/OSPtr.h`.
* `logs/xnu-sdk-004-native-probe/` records the first SDK-backed C++/C probe;
  C++ passed, while the C units first stopped at missing `errno.h`.
* `logs/xnu-sdk-005-c-probe/` records the genuine SDK `Headers/sys` include
  correction, then the missing `drm.h` path.
* `logs/xnu-sdk-006-c-probe/` records the DRM UAPI path correction, then the
  missing `linux/types.h` caused by forcing the Linux-kernel branch.
* `logs/xnu-sdk-007-c-probe/` records the successful C UAPI-branch compile.
* `logs/xnu-sdk-008-native-build/` records the reproducible four-unit script
  invocation, empty stderr, return code 0, object hashes, and `file` output.
* `logs/xnu-sdk-009-object-audit/` records Mach-O headers, relocatable file
  types, sections, symbols, and external references.
* `logs/xnu-sdk-011-repeat/` reruns `bash -n` and the complete compile script;
  all four object hashes match the first successful build.

No source/result IMG, EFI, kext, target machine, SSH session, VM, driver,
MMIO/BAR/page table, GPU engine, or GPU submission was touched. The resulting
objects remain local build evidence only.

## Remaining blocker / parent integration note

This proves native-source compilation against a legally retrieved public
header kit, not target ABI compatibility. Exact Tahoe KDK headers and a
matching Darwin kernel/kext link environment remain unavailable. Before any
future link or deployment, the parent must obtain a legally available exact
target KDK or explicitly accept a separate non-target compile experiment; no
claim of ABI25G83 or bootability follows from these objects.
