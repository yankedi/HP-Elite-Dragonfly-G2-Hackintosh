# 受控构建检查（任务 D3）

本阶段只做 NixOS 离线编译/链接探针，不执行上游 `install.sh`、不加载 kext、
不修改 EFI/NVRAM、不连接目标 macOS。所有原始输出保存在 `logs/build/`。

## 0. 工具链事实

| 工具 | 实际值 | 状态 |
|---|---|---|
| clang / clang++ | 21.1.8，target `x86_64-unknown-linux-gnu`，可用 `-target x86_64-apple-macos13.0` 编译 Mach-O 对象 | 可用（有 Nix wrapper 警告） |
| GNU ld | binutils 2.46，只支持 ELF emulation | 不能链接 Mach-O |
| ld64.lld | Android NDK 27.1 自带 **LLD 18.0.2** | 可做部分 Mach-O 链接，但 `-kext` 未文档化，输出不是 `MH_KEXT_BUNDLE` |
| Python | 3.14.8 | 可用 |
| Xcode / xcrun / otool / codesign / dyld_info | 不存在 | macOS 专用工具缺失 |
| macOS SDK | 不存在 | `BLOCKED_SDK` |
| `libcc_kext.a` | 不存在 | `BLOCKED_SDK` |

原始工具链记录：`logs/build/toolchain-001.txt`。

## 1. NootedGreen 源码对象编译

本地使用固定树内的公共头：

- `inputs/upstream/nootedgreen/MacKernelSDK/Headers`
- `inputs/upstream/nootedgreen/Lilu.kext/Contents/Resources/Headers`
- `inputs/upstream/julio-xps13/src/NootedGreen`

命令（实际执行，未下载任何依赖）：

```sh
clang++ -target x86_64-apple-macos13.0 -mkernel -nostdinc -nostdinc++ \
  -fno-builtin -fno-common -fno-stack-protector \
  -DKERNEL -DKERNEL_PRIVATE -DDRIVER_PRIVATE -DAPPLE -DNeXT \
  -DDEBUG=1 -DAPPLE_KEXT_ASSERTIONS=1 \
  -DPRODUCT_NAME=NootedGreen -DMODULE_VERSION=1.0.0 \
  -isystem inputs/upstream/nootedgreen/MacKernelSDK/Headers \
  -Iinputs/upstream/nootedgreen/Lilu.kext/Contents/Resources \
  -Iinputs/upstream/julio-xps13/src/NootedGreen \
  -std=gnu++17 -fno-exceptions -fno-rtti -fapple-kext \
  -Wno-deprecated-declarations -Wno-inconsistent-missing-override \
  -Wno-unused-parameter -c <source>.cpp -o <source>.o
```

结果：**12 个 x86_64 Mach-O 对象全部编译成功**，每个 `file` 均为
`Mach-O 64-bit x86_64 object`。原始逐文件日志：
`logs/build/probe-002/build.log`；对象 SHA-256：
`logs/build/probe-002/SHA256SUMS`。

| 对象 | 结果 |
|---|---|
| `DisplayMergeNub.o` | `COMPILED` |
| `DYLDPatches.o` | `COMPILED` |
| `Firmware.o` / `FirmwareADLP.o` | `COMPILED` |
| `HDMI.o` | `COMPILED` |
| `IntelDPLinkTraining.o` | `COMPILED` |
| `kern_gen11.o` | `COMPILED` |
| `kern_genx.o` | `COMPILED` |
| `kern_green.o` | `COMPILED` |
| `kern_patcherplus.o` | `COMPILED` |
| `kern_start.o` | `COMPILED` |
| `plugin_start.o`（Lilu） | `COMPILED` |

**这不是一个可加载的 kext。** 对象编译只能证明源码/头文件在该目标三元组下
语法和代码生成通过；不能证明符号解析、kext 链接、签名或运行。

## 2. NootedGreen 链接探针

### 2.1 clang + GNU ld

```sh
clang++ -target x86_64-apple-macos13.0 -nostdlib -static \
  -Xlinker -kext -Xlinker -export_dynamic -mmacosx-version-min=13.0 \
  logs/build/probe-002/obj/*.o \
  inputs/upstream/nootedgreen/MacKernelSDK/Library/x86_64/libkmod.a \
  -lcc_kext -o /tmp/opencode/NootedGreen.kext
```

实际失败：

```text
ld.bfd: unrecognised emulation mode: llvm
Supported emulations: elf_x86_64 elf_i386 elf32_x86_64 elf_iamcu
```

这是 GNU ld 不认识 Darwin/LLVM kext 链接参数，不是源码错误。
原始日志：`logs/build/probe-002/link.log`。

### 2.2 ld64.lld 18.0.2

先直接使用 `-kext`（未加 `-undefined dynamic_lookup`）：

```text
ld64.lld: warning: Option `-kext' is undocumented. Should lld implement it?
ld64.lld: error: undefined symbol: _main
...
ld64.lld: error: undefined symbol: __ZN11OSMetaClassD2Ev
...
exit=1
```

这些是内核/kext 运行时符号；正式链接应由 Apple 的 kext 链接环境和
`libcc_kext.a` 提供（或按 kext 规则允许未定义符号）。原始日志：
`logs/build/probe-002/link-ld64.log`。

再加 `-undefined dynamic_lookup`：

```sh
ld64.lld -arch x86_64 -kext -platform_version macos 13.0 13.0 \
  -undefined dynamic_lookup -o /tmp/opencode/NootedGreen.kext \
  logs/build/probe-002/obj/*.o \
  inputs/upstream/nootedgreen/MacKernelSDK/Library/x86_64/libkmod.a
```

结果：退出 0，但 `file` 报告：

```text
Mach-O 64-bit x86_64 executable, flags:<NOUNDEFS|DYLDLINK|TWOLEVEL|PIE>
```

**这是 `MH_EXECUTE`，不是 `MH_KEXT_BUNDLE`。** lld 18 的 `-kext` 只是
未文档化选项，没有生成 kext bundle 类型；同时没有使用 `libcc_kext.a`。
因此不能把这个文件称为已链接的 NootedGreen.kext，也不能作为构建成功证据。
原始日志：`logs/build/probe-002/link-ld64-002.log`。

**最小缺失输入：**

1. 能生成 `MH_KEXT_BUNDLE` 的 Apple `ld`/cctools（或支持 kext bundle 的
   等价链接器）；
2. macOS SDK 中的 `libcc_kext.a`；
3. 与目标 XNU/KDK 匹配的未定义符号解析策略。

当前状态：对象 `COMPILED`；完整 kext `BLOCKED_SDK` / `NOT_TESTED`。

## 3. 用户态组件探针

### 3.1 `libxedrv.m`

命令：

```sh
clang -x objective-c -target x86_64-apple-macos15.0 -fsyntax-only \
  -isystem inputs/upstream/nootedgreen/MacKernelSDK/Headers \
  inputs/upstream/julio-xps13/macos/src/libxedrv.m
```

实际失败：

```text
fatal error: 'Foundation/Foundation.h' file not found
```

缺少 Foundation、Metal、IOSurface、objc runtime、Darwin libc/libSystem 头。
这不是可以用 MacKernelSDK 补上的：MacKernelSDK 是内核头，不含用户态框架。
状态：`BLOCKED_SDK`。原始日志：`logs/build/probe-003/libxedrv.m.log`。

**最小缺失输入：** 合法 macOS 用户 SDK（Foundation/Metal/IOSurface/objc/
libSystem/libc++），以及 macOS `clang`/`codesign`（构建 dylib 时）。

### 3.2 `compiler-adapter.cpp` / `llvm-bridge.cpp`

同样用 `-target x86_64-apple-macos15.0 -fsyntax-only` 尝试。实际失败不是
单一“缺某个头”，而是宿主 glibc 头与 Darwin target 冲突：

```text
cstddef: error: no member named 'max_align_t' in the global namespace
dlfcn.h: error: expected function body after function declarator
cstring: error: no member named 'memchr' in the global namespace
...
```

这说明 NixOS 的 glibc/libstdc++ 头不能冒充 macOS libc++/libSystem；不能用
伪造头文件掩盖依赖。原始日志：
`logs/build/probe-003/compiler-adapter.cpp.log`、
`logs/build/probe-003/llvm-bridge.cpp.log`。

状态：`BLOCKED_SDK`。最小缺失输入：macOS 用户 SDK 的 libc++/libSystem/
`mach-o/dyld.h`/`mach-o/getsect.h`/`syslog.h`/`execinfo.h`，以及
`GPUCompiler.framework` 的 `libLLVM`/tbd（构建 bridge 时需要）。

### 3.3 `build-shader-compiler.sh` / `build-all.sh`

**没有执行。** 原因：

- 需要 macOS 的 `clang`、`codesign`、`install_name_tool`、`dyld_info`；
- 需要运行中的 Tahoe 系统导出 `GPUCompiler.framework/Versions/32023`；
- 会读写 `/System/Library/Caches/xe.bundle`（即使是构建脚本的目标路径）；
- 本任务禁止在目标系统上执行安装/构建脚本。

状态：`BLOCKED_SDK`，未执行；不能声称 `xe.bundle` 已构建。

## 4. 可以安全执行的下一次构建

在拿到合法 macOS SDK/KDK 和匹配的 Mach-O 链接器后，建议顺序：

1. 只编译 NootedGreen 的 12 个对象（已有成功基线）。
2. 用 Apple `ld` + `libcc_kext.a` 链接 `MH_KEXT_BUNDLE`；检查
   `file`/`otool -hv` 的 filetype、`kextutil -n` 的符号/依赖检查（不加载）。
3. 单独编译 `libxedrv.m` 为 dylib；用 `codesign -s -` 只为离线检查，
   不安装。
4. 单独编译 `compiler-adapter.cpp`/`llvm-bridge.cpp`；用目标
   `GPUCompiler` 的 tbd/导出做链接检查。
5. 只有目标 25G83 二进制通过 `check-tgl-compat.py` 后，才生成 MTL 输出
   bundle；仍不安装。

## 5. 状态汇总

| 组件 | 状态 | 证据 |
|---|---|---|
| NootedGreen 12 个对象 | `COMPILED` | `logs/build/probe-002/build.log` + `SHA256SUMS` |
| NootedGreen 完整 kext | `BLOCKED_SDK` / `NOT_TESTED` | `link.log`、`link-ld64*.log`；无 `MH_KEXT_BUNDLE` |
| `libxedrv.m` | `BLOCKED_SDK` | 缺 Foundation/用户 SDK |
| `compiler-adapter.cpp` | `BLOCKED_SDK` | 宿主 glibc vs Darwin libc++ |
| `llvm-bridge.cpp` | `BLOCKED_SDK` | 同上 |
| `xe.bundle` / MTL 输出 | `NOT_TESTED` / `BLOCKED_SDK` | 未执行 macOS 脚本 |
| 目标 kext 加载 | `NOT_TESTED` / `UNSAFE_FOR_TARGET` | 本阶段禁止 |
