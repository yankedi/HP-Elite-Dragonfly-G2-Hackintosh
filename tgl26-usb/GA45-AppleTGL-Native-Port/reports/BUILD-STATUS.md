# GA4.5 构建状态（实执行记录）

日期：2026-10-22/23。范围：本机离线；目标机只做了 `ls`/`sw_vers` 只读检查，
未在目标机上编译、执行探针、安装、加载或重启。

## 1. 工具链来源

| 项目 | 实际值 | 状态 |
|---|---|---|
| 目标 macOS | 26.6.2 / 25G83 / x86_64 | `REMOTE_READ_ONLY` |
| 目标 CLT | `/Library/Developer/CommandLineTools` 存在 | `REMOTE_READ_ONLY` |
| 目标 SDK | `MacOSX26.5.sdk`（另有 15.4/15/26/26.5） | 合法本机 CLT 文件 |
| 本机 SDK 副本 | `toolchain/MacOSX26.5.sdk`，约 831 MB，32350 文件 | 私有、Git 忽略 |
| 本机 clang | Nix clang 21.1.8（未包装的 `clang-21`） | 可用 |
| 本机 linker | Nix `ld64.lld` 21.1.8 | 可链接 `MH_DYLIB`/`MH_BUNDLE`/`MH_EXECUTE` |
| `libkmod.a` | SDK `usr/lib/libkmod.a`，SHA-256 `6be1c9ba…` | 存在 |
| `libcc_kext.a` | 目标 CLT/SDK 搜索未发现 | **缺失** |
| Apple Xcode | `/Applications/Xcode.app` 不存在 | 不可用 |
| `codesign` | NixOS 无；未执行目标 Apple 工具 | 签名未验证 |

SDK 副本来自目标机已有的 CommandLineTools，仅用于本机私有离线构建；没有
在目标机安装任何工具，也没有把 Apple SDK 提交到 Git。目标 SDK 版本为
26.5，目标系统 Build 为 25G83；二者不是逐字节同版，属于 `ABI_UNVERIFIED`
风险，不可把“本机能链接”当成“目标 ABI 已通过”。

## 2. 实际链接的 Darwin 用户态组件

构建命令：`tools/build-darwin-components.sh`。
SDK 存在后，以下文件均为真实 Mach-O x86_64：

| 文件 | 文件类型 | Install name | 状态 |
|---|---|---|---|
| `libxedrv.dylib` | `MH_DYLIB` | `@rpath/libxedrv.dylib` | `DARWIN_DYLIB_LINKED`；未签名 |
| `libMTLIGCCompilerPluginOld.dylib` | `MH_DYLIB` | `@rpath/libMTLIGCCompilerPluginOld.dylib` | `DARWIN_DYLIB_LINKED` + `DYLD_LOOKUP` |
| `libLLVMbridge.dylib` | `MH_DYLIB` | `@rpath/libLLVMbridge.dylib` | `DARWIN_DYLIB_LINKED` + `DYLD_LOOKUP` |
| `metal-abi-probe` | `MH_EXECUTE` | — | 已链接；未执行 |
| `compiler-runtime-probe` | `MH_EXECUTE` | — | 已链接；未执行 |

`libxedrv.dylib` 的 `llvm-nm -u` 仅显示 Foundation/Metal/IOSurface/libobjc/
libSystem 的正常导入符号，链接器输出为 `NOUNDEFS`。它没有经过目标运行，
`check_layout()` 的 0x338/0x30/0x10/0x8 等值仍是 **待实测预期**，不是
25G83 已证明结果。

`libMTLIGCCompilerPluginOld.dylib` 与 `libLLVMbridge.dylib` 使用
`-undefined dynamic_lookup`：`LLVM*`、`MTLCompilerBuildRequestWithOptions`
等符号在目标运行时解析；它们不是“完全自包含”的 dylib。状态必须读作
`DARWIN_DYLIB_LINKED` + `ABI_UNVERIFIED`，不能读作“编译器已可用”。

SHA-256（本地私有无签名构建）：

```text
libxedrv.dylib                 079972695e36d44bd78952176908dc891e669ad3332f32d3fd41ba6f041135aa
libMTLIGCCompilerPluginOld    3200464e1e456e795280b6218391fdcbb437b388469086044cdd20cf30a282d7
libLLVMbridge.dylib           274b8e3d9c4e1c464426ae2a529b0efcb080c896b1eaeee2d3e6b4235cb8e987
metal-abi-probe               0d00126f4effc96bad783a0a0c06fb4f8c2fdfe2e1cf5f26fa66df6fbcd1b65a
compiler-runtime-probe        5f10e93b8d55060f474a0f3dff6a0dc6fe3c70d6f15f011d9a901371ba04aa23
```

最小独立 dylib 探针 `libxeabi_probe.dylib` 也已实际链接为 `MH_DYLIB`，
SHA-256 `031962d3…`；这证明 SDK/linker 路径不是 ELF 伪装。

## 3. Donor 严格字节审计

使用 GA4.3 固定配置的 18 条 patch 条目（5 个 TGL accelerator pattern、10 个
MTL offset、3 个 VALD pattern）逐一检查 staging 中的 donor 16.0.32：

- 全部 18/18 **MATCH**（pattern 的 occurrence count 与 expected 一致；
  offset 的 `old_hex` 逐字节一致）；
- donor 文件身份：`AppleIntelTGLGraphics` `890735a9…`、
  `AppleIntelTGLGraphicsMTLDriver` `e21a8d12…`、
  `AppleIntelTGLGraphicsFramebuffer`（`le`）`285ee7a9…`、
  `libigc` `9ff8b3b3…`、旧 plugin `477083cb…`；
- 结果：`DONOR_ALL_MATCH`，证据 `manifests/donor-audit-18.json`。

这只证明 donor 字节/offset 与配置匹配；不证明 25G83 运行时语义或可加载性。

## 4. NootedGreen 对象与 kext 链接

`tools/build-nootedgreen.sh` 实际编译 **12 个 x86_64 Mach-O 对象**
（11 个 NootedGreen 源对象 + Lilu `plugin_start.o`）：

- `file` 全部为 `Mach-O 64-bit x86_64 object`；
- `kern_gen11.o` 包含 GA4.5 的 TGL 门控字符串；
- 对象哈希见 `logs/build/nootedgreen-objects-SHA256SUMS`。

kext 链接尝试：

1. `ld64.lld -kext`：退出 1，未生成文件；缺少 `OSSymbol`、`IOService`、
   `__cxa_atexit` 等 kernel/KPI 符号；不是源码编译错误。
2. `ld64.lld -kext -undefined dynamic_lookup`：退出 0，但文件类型为
   `MH_EXECUTE (0x2)`，不是 `MH_KEXT_BUNDLE`。该文件只保留在日志中，
   不进入 staging，不能称为 kext。
3. `ld64.lld -bundle`：退出 0，文件类型为 `MH_BUNDLE (0x8)`；同样不是
   kext，仅用于证明 linker 能生成 Mach-O bundle。

**`KEXT_LINKED` 未达到。** 最小缺失输入：

- 能生成 `MH_KEXT_BUNDLE` 的 Apple/cctools 链接器（或等价支持）；
- `libcc_kext.a` / 目标 KDK 的内核 C++ ABI 支持；
- 与 25G83 XNU 匹配的未定义符号策略。

`NootedGreen.kext` 没有进入 staging；`staging` 中不存在空壳 kext。

## 5. 离线探针

`tools/metal-abi-probe.m` 与 `tools/compiler-runtime-probe.cpp` 已用同一 SDK
链接为 `MH_EXECUTE`，但**没有在目标上执行**。它们只读：

- Metal descriptor 的 class size/ivar offset 和 `_descriptorPrivate` 返回的
  只读字节；
- 已加载 image 名称、`dlopen`/`dlsym` 的符号存在性。

不创建 `MTLDevice`/command queue，不发送 shader，不写私有内存，不进行 MMIO。
运行时数值必须在用户明确授权后另取；当前 `ABI_UNVERIFIED`。

## 6. 结论

- `DARWIN_DYLIB_LINKED`：libxedrv、adapter、bridge、最小 probe 均实际生成。
- `MACHO_OBJECT`：NootedGreen 12 个对象。
- `KEXT_LINKED`：未达到，原因具体为 linker/filetype/KPI 缺失。
- `ABI_UNVERIFIED`：所有 25G83 运行时布局/符号仍待目标探针。
- `NOT_TESTED_ON_GPU`：所有 GPU/Metal/驱动运行项。
- `DEPLOYMENT_BLOCKED`：无合法签名/加载路径证据。
