# GA46：真实 kext 链接结果

## 实际产物与判定

`logs/nootedgreen-kext-002/NootedGreen.kext/Contents/MacOS/NootedGreen`
SHA256 `7571241e3b5b1be7795d491ef6ebd357d97afcb5fe55cf1c345c998732a1b666`。

**KEXT_LINKED / KEXT_FILETYPE_VALID / KEXT_RELOCATIONS_VALID /
KERNEL_SYMBOLS_AUDITED**，同时 **ABI_UNVERIFIED / DEPLOYMENT_BLOCKED /
GPU_NOT_TESTED**。未签名，未进入目标 Kernel Collection。

PR204805 head `d575e43643f7c90a1a2728352a24867d7105d9e9`，patch SHA256
`0465346e1210f2d3889a08348da1a37c2eb9bf8896b500f6af73b3aafbbf3b6c`。
最终 linker SHA256 `f1b7547756dc64555c580dd8e30d1437a71a9c4c7bab7a13e496f9df95180661`。
构建参数见 `tools/build-kext-llvm.sh`；完整日志 `logs/llvm-build-001/002/003.log`。
第一次 tarball 构建的版本字符串误取父仓库 Git revision，002已关闭该展示功能；
源码来源以下载SHA/commit为准，未把父仓库revision当LLVM来源。

## 验证范围

- 合法最小fixture同时含真实 IOMalloc/IOFree 引用、kmod_info、全局构造/析构。
  `logs/fixture-pr204805-001` 实际链接和检查PASS。
- 上游 `lld/test/MachO/kext.s`、`llvm-objcopy/MachO/kext-relocations.test`
  **2/2 PASS**，包含非法SIGNED relocation、chained-fixup、arm64拒绝，
  外部/本地重定位、strip/remove-section后索引重建。最初缺count/strip的两次
  测试失败日志保留，最终 `logs/llvm-upstream-tests-003.log` 才是通过证据。
- 完整NootedGreen共14对象（含netdbg和module-info），无宿主libc++头，
  无假系统定义，无libcc_kext.a替代物；真实SDK libkmod.a提供启动跳板。
- `__TEXT/__DATA/__LINKEDIT`、section/file/VM界限、symtab/dysymtab索引、
  **1815个**外部/本地重定位类型及本地addend检查通过，无TLV或用户态dyld命令。
- 核验 `_kmod_info`、`__start/__stop`、Lilu插件start/stop、构造/析构节；
  Info.plist展开Xcode变量并保留OSBundleLibraries/Lilu依赖。
- 与只读上游附带Lilu1.7.2及16.0.32两个Apple donor kext用同一parser比较通过。

## 397个undefined，不等于397个缺失

独立provider gate（非链接器 blanket dynamic_lookup）逐个核验：
367个存在同build25G83 Recovery KC的kernel符号表（A），29个在附带Lilu1.7.2
真实导出（C），1个由KC其他原生文件集提供（B）。无D/E名称缺失。
全部映射、输入SHA和限制在 `logs/nootedgreen-kext-002/symbol-providers.json`。

**A只证明声明/符号存在，不把kernel全符号表冒称公开KPI allowlist。**
Recovery KC不是目标boot KC；IOService/OSSymbol的vtable布局、Lilu对象成员布局、
KC符号允许集和实际加载仍待目标验证。匹配C++mangling不证明对象ABI完全兼容。
PR的-kext语义会保留undefined，即使传`-undefined error`也不会拒绝；因此
本项目必须依靠额外provider gate，不能把exit0当runtime解析成功。

此前真正的链接器filetype和后端析构问题已解决；下一阻塞是目标KC/内核C++ABI
及加载政策，而非笼统SDK缺失。
