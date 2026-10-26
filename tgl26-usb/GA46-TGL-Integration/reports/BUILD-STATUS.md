# GA4.6 构建状态（真实离线证据）

日期：2026-10-23。验收命令：

```sh
make check CHECK_OUT=logs/check-final-001
```

退出 0，日志末尾 `GA46 required offline checks PASS; target/GPU never executed`。
旧 GA45 构建报告保存在 `history-ga45/BUILD-STATUS.md`，不作为本轮成功证据。

## 工具链

| 工具/输入 | 本轮实际使用 | 限制 |
|---|---|---|
| 内核 linker | 独立源码构建 PR204805 head d575e436… 的 LLD24 | 非系统 LLVM21；未全局安装 |
| Clang | Nix clang21.1.8，后端禁用 atexit destructor lowering | 非补丁版 Clang；本轮用直接 ld64.lld 链接验证 |
| SDK | 只读 GA45 私有 MacOSX26.5.sdk | 非目标25G83逐字节同版KDK |
| kernel runtime | SDK真实libkmod.a | 没有伪libcc_kext.a或系统符号实现 |
| dylib linker | Nix ld64.lld21.1.8 | 不用于kext；3dylib严格two-level链接 |
| CPU回归 | 宿主真实libLLVM21.1.8 | 不证明Apple LLVM3902/32023 ABI |

LLVM来源、patch/source SHA和构建参数见 `PR204805.json`、
`toolchain/pr204805/acquisition.json`、`tools/build-kext-llvm.sh`。
最终linker SHA256 `f1b7547756dc64555c580dd8e30d1437a71a9c4c7bab7a13e496f9df95180661`。

## 真 kext

最终 `staging/final-001/NootedGreen.kext/Contents/MacOS/NootedGreen`：

```text
SHA256 0d920d5a42c1dac2364cd01cdb60c740c301562855d99a552d9e27310160a2b8
x86_64 MH_KEXT_BUNDLE (0xB)
14 objects; 1606 external/local relocations; 392 undefined names
KEXT_FILETYPE_VALID / KEXT_RELOCATIONS_VALID / KERNEL_SYMBOLS_AUDITED / KEXT_LINKED
```

14对象包括12个src/NootedGreen源码对象、plugin_start.o和module-info.o。
netdbg用内核stdarg.h，未再跳过；构造/析构节、真实libkmod跳板、Info.plist和
Lilu依赖均审计。完整结构在 `logs/check-final-001/kernel/structure.json/.txt`。
392个名称：362 kernel候选（公开KPI分类未证）、29 Lilu1.7.2导出、1 IOPCIFamily
metaClass。最新严格分类在 `KERNEL-SYMBOL-PROVIDERS.json`；初始日志A计数
只是历史名称分组，不能当目标公开KPI证明。

`logs/nootedgreen-kext-002`是**先前全源码链接候选**：1815relocs/397imports，
不是最终native-only产物。其历史报告 `KEXT-LINK-RESULT.md`应连同本报告阅读。
最终入口隔离见 `NATIVE-BRANCH-REVIEW.md`；kext当前不是功能完备GPU适配层。

## 用户态严格链接

全部实际类型/依赖/导入数/完整SHA在 `USERSPACE-BUILD.json`：

| 产物 | 实际结果 | 功能边界 |
|---|---|---|
| libxedrv.dylib | MH_DYLIB、NOUNDEFS | Metal私有schema未证，拒绝device初始化 |
| libMTLIGCCompilerPlugin.dylib | MH_DYLIB、NOUNDEFS | Create返回null，未知请求失败即停 |
| libLLVMbridge.dylib | MH_DYLIB、NOUNDEFS | 仅项目自有current-bitcode诊断接口，无旧C++ shim |
| metal-abi-probe | MH_EXECUTE、NOUNDEFS | 已交叉编译，未执行 |
| compiler-runtime-probe | MH_EXECUTE、NOUNDEFS | 默认NOLOAD，未执行 |

旧自建adapter命名Old与Apple donor用途冲突，本轮改为plugin正常名；旧命名仅
出现在历史证据。不能将符号较少/严格链接解释为旧编译器功能已恢复。

## 检查与失败记录

- PR原生kext及objcopy relocation测试2/2 PASS：`upstream-tests.log`。
- 合法fixture含真实KPI、模块元数据及全局构造/析构：PASS。
- CPU Metal size/alignment/offset负例：PASS。
- 真adapter null/fail-stop语义及未篡改SIGSEGV handler：PASS。
- 真LLVM bitcode error/ownership/8线程1600次roundtrip、ASan/UBSan：PASS。
- 重复donor staging的独立diff及reverse SHA一致：PASS。
- Git diff --check：PASS。

保留失败：cctools缺BlocksRuntime/dispatch；最初fixture错误析构降级；
upstream-tests-001/002缺测试工具；userspace-002末尾file列表还使用旧名字，
最终check已修复并显式test文件存在后才判通过。
编译警告（包括继承宏重定义）保留日志，不将exit0描述为warning-free。

## 尚未取得的验收

目标公开KPI allowlist、IOService/OSSymbol/Lilu C++布局、target KC解析，
Apple shared-cache libLLVM真实导出、请求/reply/降版ABI、Metal完整schema，
签名/host接受度均未通过。没有 `KEXT_LOADED`、`METAL_DEVICE_READY` 或
`GPU_SUBMIT_PASS`。最终 `RUNTIME_SYMBOL_UNVERIFIED / ABI_UNVERIFIED /
DEPLOYMENT_BLOCKED / GPU_NOT_TESTED`。
