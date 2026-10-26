# GA4.5 — Apple Tiger Lake 16.0.32 原生驱动实质移植（第一批）

日期：2026-10-22/23。目标：HP Elite Dragonfly G2 / i5-1135G7 /
`8086:9A49` / macOS 26.6.2 / 25G83 / x86_64。

本报告只记录**实际执行**的结果。没有安装、加载、替换目标驱动，没有修改
EFI/OpenCore/NVRAM/BIOS/SIP/SSV/AMFI，没有在目标机执行新编译探针，没有
重启或 GPU 实验。**没有声称 Intel Iris Xe Metal 加速成功。**

## 一、SSH 与工具有关结论

目标机可以通过现有 SSH 只读连接；`sw_vers` 返回 macOS 26.6.2 / 25G83，
目标 CLT 存在。目标机 `/Applications/Xcode.app` 不存在。目标 CLT 的 SDK
列表包含 `MacOSX26.5.sdk`；目标 CLT 中没有找到 `libcc_kext.a`，但有
`usr/lib/libkmod.a`。

本轮把目标机**已经存在**的 `MacOSX26.5.sdk` 只读复制到本机私有的
`toolchain/MacOSX26.5.sdk`（Git 忽略），用于离线链接；没有在目标机安装
任何东西，也没有把 Apple SDK 放进 Git。该 SDK 是 26.5，目标 Build 是
25G83，ABI 仍需运行时探针，不能视为同版 KDK。

本机工具链：

- Nix clang 21.1.8（未包装的 `clang-21`）；
- Nix `ld64.lld` 21.1.8；
- SDK `MacOSX26.5.sdk`；
- NootedGreen 对象编译与 userspace dylib 链接均实际执行。

## 二、NootedGreen 修改

### 真 TGL 身份

新增 `isNativeTgl` 与 `getIsNativeTgl()`：

- Intel vendor `0x8086`；
- GPU device `0x9A49`；
- CPUID family 6 / model `0x8C` 或 `0x8D`；
- 拒绝 `device-id=0x8A5A` 或 `AAPL,ig-platform-id=0x8A5C0002` 的 ICL 伪装。

历史 `isRealTGL`（CPU-only）保留用于旧路径；新的 TGL/Tahoe layout 路径使用
更严格的 `getIsNativeTgl()`。设备/CPU 不一致时，TGL-only 布局补丁不会运行。

### XE-FMT / XE-PLANES2 / XE-VALD

- 保留 `-ngreentgltahoe` 作为 TGL/Tahoe profile 总开关。
- XE-FMT：在 native TGL + Tahoe 下，按精确原始字节、exact match count 1
  应用；可用 `-ngreennofmt` 单独关闭；失败不覆盖 Apple 代码，只记录
  fail-closed。
- XE-PLANES2：实现独立 `-ngreennoplanes2` 开关，但因为 `IOSurface+0x98`
  还没有 25G83 运行时证据，**默认不应用**；只有
  `-ngreenplane2experimental` 才进入应用路径，并有 exact byte/count 检查。
- XE-VALD：从无条件执行改为受控；native TGL 需要 `-ngreentgltahoe`，
  可用 `-ngreennovald` 独立关闭；三种 pattern 分别记录，任一失败会记录
  `INCOMPLETE/fail-closed`。
- FMT/PLANES2 有 `static bool` 防止同一启动重复应用；V500 在 native TGL
  不安装。
- donor 字节匹配只作为 16.0.32 目标存在性证据；没有把它当成 25G83 语义
  验证。

### RPL Hook 隔离

以下在 native TGL 默认不执行，或转发 Apple 原实现：

- `-ngreenxefix` 整个 RPL/display-13 组合：native TGL 直接拒绝，除非显式
  `-ngreenallowrplfixes`；
- display 13 寄存器过滤、XE-BLR、FBDPMS：在 native profile 下不启用；
- ForceWake 替换 / HANGCHECK：route 默认跳过；即使进入 replacement，也
  转发 Apple 原 forcewake，不做 GGTT remap/dump；
- GTFREQ、IDLEBOUND：native TGL 调用原实现，不抬高频率/跳过等待；
- V40 IOAF2 capability bypass：native TGL 默认跳过，`-ngreenallowv40` 才
  允许；
- V221 waitForStamp：native TGL 默认不安装；如果显式允许，wrapper 也
  **不会**在 stamp 超时时伪造成功；
- V500 `set_id_mode`：native TGL 不安装（25G83 无该符号）；
- XE-RESFREE：native TGL 默认关闭，`-ngreenresfree` 才启用；
- NOAUX/NOCCS/CSB/ELSQ/ADL-P DMC 等 RPL/ADL 路径由 xefix 或各自 boot-arg
  控制，不是 native 默认路径。

### WhateverGreen/Lilu 互斥

`native TGL + -ngwegcoex` 被视为互斥 profile：默认拒绝 layout fixes 和
accelerator personality 注入；只有 `-ngreenallowweg` 显式诊断才继续。
没有修改目标 EFI，也没有把 ICL `8A5A` 伪装用于 native profile。

### 源码/对象结果

`tools/build-nootedgreen.sh` 实际编译 **12 个 x86_64 Mach-O 对象**：
11 个 NootedGreen 源文件 + Lilu `plugin_start.o`。`file` 全部为
`Mach-O 64-bit x86_64 object`。`kern_netdbg.cpp` 不在这 12 个基线对象中，
因为它需要宿主 libc++ `<cstdarg>`。

NootedGreen 源码测试 `tests/test_tgl_profile.py` 15 项全部通过；这是
`SOURCE_IMPLEMENTED` + `CPU_TEST_PASS`，不是 kext 完成。

## 三、libxedrv

`libxedrv.m` 已修改并实际链接为：

```text
logs/build/darwin-components-003/libxedrv.dylib
file: Mach-O 64-bit x86_64 dynamically linked shared library
install name: @rpath/libxedrv.dylib
SHA-256: 079972695e36d44bd78952176908dc891e669ad3332f32d3fd41ba6f041135aa
```

实际改动：

- `check_layout()` 现在严格要求 `MTLRenderPipelineDescriptorInternal`
  size `0x338`、`_private@0x30`、Color Attachment size `0x10`、
  `_private@0x8`；
- 检查 `rasterSampleCount@0xB8`、`vertexDescriptor@0x110` 和
  `MISC[17]` 的 logicOp `old 27 / new 32` 映射；
- 任何 size/offset/encoding/`_descriptorPrivate` NULL 失败都会关闭转换
  （fail-closed），不进行盲写；
- `xe_abi.h` 的纯 C 边界测试 `tests/test_xe_abi.c` 通过；
- native TGL（CPUID model 0x8C/0x8D）默认保留 `allowGPUOptimizedContents`
  原生压缩路径；RPL 仍走旧的禁用路径。

**25G83 运行时数值仍未实测**：0x338/0x30/0x10/0x8 是待验证预期，
`ABI_UNVERIFIED`，不是已证明的 25G83 结果。

## 四、Compiler Adapter / LLVM Bridge

实际链接：

```text
libMTLIGCCompilerPluginOld.dylib
  MH_DYLIB, @rpath/libMTLIGCCompilerPluginOld.dylib
  SHA-256 3200464e1e456e795280b6218391fdcbb437b388469086044cdd20cf30a282d7

libLLVMbridge.dylib
  MH_DYLIB, @rpath/libLLVMbridge.dylib
  SHA-256 274b8e3d9c4e1c464426ae2a529b0efcb080c896b1eaeee2d3e6b4235cb8e987
```

`compiler-adapter.cpp` 现在：

- 拒绝空/超大/不完整请求，返回 0，不伪造成功；
- 对 LLVM context/buffer/module 做正常路径释放；
- 使用 `pthread_once` 安装信号处理；
- 对 libigc 崩溃路径设置 fault 标志，避免对半损坏 module 做不安全释放；
- 旧编译器返回“成功但没有 reply”时拒绝；
- 旧 plugin 路径不可用时返回 null 并记录，不伪造 compiler。

`llvm-bridge.cpp` 现在：

- 依次尝试 `GPUCompiler 32023`、`Current`、framework executable、
  裸 `libLLVM.dylib`，再扫描已加载 image；
- 不再把路径不存在直接当库不存在；
- `WriteBitcodeToFile` 缺少 dst、module/ostream 为空时拒绝；
- getSerializedModule 返回非法范围时回退 API C，不伪造；
- 扫描 `MTLCompiler`/`MTLCompilerService` image，而不是只匹配单一路径。

这两个 dylib 使用 `-undefined dynamic_lookup` 解析 `LLVM*` 与旧 plugin
符号；它们不是完全自包含的。状态：`DARWIN_DYLIB_LINKED` +
`ABI_UNVERIFIED`，不是“编译器已在 25G83 可用”。

## 五、Donor 与 kext

### Donor 严格匹配

对 GA4.3 固定配置的 18 条 patch 条目逐字节检查：

- 5 个 TGL accelerator pattern；
- 10 个 MTL offset；
- 3 个 VALD pattern；

结果 **18/18 MATCH**（pattern 计数、offset old bytes 全一致）。
证据：`manifests/donor-audit-18.json`。
这证明 donor 文件/字节是 16.0.32，不证明 25G83 可加载或运行。

### 实际 kext 链接

- 12 个 Mach-O objects 已生成；
- `ld64.lld -kext` 退出 1，缺少 OSSymbol/IOService/`__cxa_atexit` 等
  kernel/KPI 符号；
- `ld64.lld -kext -undefined dynamic_lookup` 退出 0，但输出是
  `MH_EXECUTE (0x2)`，不是 `MH_KEXT_BUNDLE`；
- `ld64.lld -bundle` 输出 `MH_BUNDLE (0x8)`，也不是 kext；
- `libcc_kext.a` 未找到。

**`KEXT_LINKED` 未达到。** `staging/NootedGreen.kext` 不存在，没有空壳
kext；日志中的 MH_EXECUTE 文件不进入 staging，也不称为成品。

## 六、离线 staging 与签名

`staging/` 已建立：

- `staging/compiler/`：实际构建的 libxedrv/adapter/bridge dylib；
- `staging/probes/`：实际链接的 probe executable 和最小 dylib；
- `staging/private/donor/`：Apple 16.0.32 donor 原件，私有、Git 忽略；
- `staging/manifests/components.json`：来源/哈希/构建/签名/可加载性；
- `staging/NootedGreen.kext/`：**不存在**（没有有效 kext）。

Apple donor 原件不进入 Git；staging 不复制到目标 macOS。所有本地构建
dylib 都未签名（没有 `LC_CODE_SIGNATURE`）。

签名/加载结论：**`DEPLOYMENT_BLOCKED`**。没有证据表明在不修改
SIP/SSV/AMFI/Secure Boot、不使用 `amfi_get_out_of_my_way=1` 的前提下，
修改后的 Apple 私有 GPU 驱动会被 WindowServer/MTLCompilerService 接受。
详见 `reports/SIGNING-RESEARCH.md`。

## 七、十个验收问题

1. **NootedGreen 真 TGL 路径是否独立于 RPL xefix？**
   源码层面是：新增 native identity + `-ngreentgltahoe`，`-ngreenxefix`
   在 native TGL 默认拒绝。未在目标上运行；状态 `SOURCE_IMPLEMENTED` /
   `CPU_TEST_PASS`。

2. **哪些无条件 Hook 已修复？**
   ForceWake/HANGCHECK、display 13、GTFREQ、IDLEBOUND、FBDPMS、V40、
   V221、V500、XE-RESFREE 均增加 native TGL 门控/原实现；xefix 整体拒绝。
   XE-VALD 从无条件变为受控。仍只是源码/对象测试，不是运行时证明。

3. **是否完成真实 `libxedrv.dylib`？**
   是，`MH_DYLIB` 已链接、install name 正确、未签名；但 25G83 运行时
   descriptor ABI 仍 `ABI_UNVERIFIED`，没有目标执行。

4. **是否完成真实 Compiler Adapter/LLVM Bridge dylib？**
   是，均实际链接为 `MH_DYLIB`；但使用 dynamic lookup，`LLVM*`/旧插件
   符号未在目标解析；状态 `DARWIN_DYLIB_LINKED` + `ABI_UNVERIFIED`。

5. **是否生成有效的 NootedGreen kext？**
   否。12 个对象只有 `MACHO_OBJECT`；`-kext` 失败，fallback 输出是
   `MH_EXECUTE`/`MH_BUNDLE`，不是 `MH_KEXT_BUNDLE`；`KEXT_LINKED` 未达到。

6. **Apple 16.0.32 donor 的补丁是否严格匹配？**
   是，18/18 个配置 patch 条目均 MATCH；donor 文件哈希与 donor 16.0.32
   一致。仅为静态字节证据。

7. **Tahoe 25G83 仍存在哪些 ABI 未验证项？**
   - libxedrv 实际 class size/ivar offsets、sample/vertex、logicOp；
   - IOAF2 内部 offset 与 TGL display-pipe transaction 行为；
   - GPUCompiler/MTLCompiler shared-cache libLLVM 路径、`getSerializedModule`
     签名和 `MTLCompilerBuildRequestWithSerializedBitcode` 映射；
   - donor 16.0.32 kext/MTL driver 与 25G83 的实际加载/匹配；
   - MTL header/plugin path 的目标文件偏移；
   - 签名/加载路径。

8. **是否存在满足当前约束的合法加载方案？**
   没有已证明方案。状态 `DEPLOYMENT_BLOCKED`。没有修改安全策略。

9. **哪些组件已经具备进入下一阶段离线构建条件？**
   - NootedGreen 12 个对象、源码与测试；
   - libxedrv、adapter、bridge、最小 dylib、两个 probe executable；
   - donor 16.0.32 staging 文件；
   - 缺 `MH_KEXT_BUNDLE` linker/`libcc_kext.a`，缺目标运行时探针和签名。

10. **距离首次真正 Metal Compute 还缺什么？**
    仍需：有效 NootedGreen kext + 合法签名/加载；25G83 运行时 descriptor/
    IOAF2/编译器 ABI 探针；可解析的 libLLVM/旧 IGC；目标 `AppleIntelTGLGraphics`
    与 MTL driver 的实际加载；Metal device/command queue/shader 提交；
    以及一次新的受控实机授权。当前没有 GPU 执行，不能称为 Metal。

## 八、本地 Git

分支：`ga45/apple-tgl-native-port`；无 remote/push；历史 GA4.0–GA4.4
未修改。提交见 `reports/GIT-COMMITS.md`。

## 九、明确未做

- 未安装/加载/替换任何目标驱动；
- 未改 EFI/OpenCore/NVRAM/BIOS；
- 未改 SIP/SSV/AMFI/Secure Boot；
- 未在目标机编译或执行新二进制；
- 未重启目标机；
- 未执行 GPU MMIO/Batch/Shader 实验；
- 未声称 1536 MB/3FB 或任何 SSH/文件读取等于 Metal 成功。
