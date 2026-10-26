# 下一阶段最小工作计划

本阶段到此停止。以下计划**不会自动执行**；需要用户明确进入 GA4.4/第二阶段，
并另行授权目标机操作。当前不允许安装、加载、修改 EFI/NVRAM/SIP/SSV/AMFI，
也不允许 SSH 控制目标 macOS。

## P0 — 先取 25G83 真实文件（阻塞项）

目标：把 `NEEDS_TARGET_BINARY` 变成可判定的 `[2]`/`[3]` 证据。

1. 用户按 `reports/TAHOE-25G83-COMPAT.md` §10 只读复制：
   - `AppleIntelTGLGraphics.kext` 的二进制、`Info.plist`、`version.plist`；
   - `AppleIntelTGLGraphicsFramebuffer.kext` 的二进制、`Info.plist`；
   - `AppleIntelTGLGraphicsMTLDriver.bundle` 的二进制、`Info.plist`；
   - `AppleIntelGraphicsShared.bundle` 的 `Info.plist`、`libigc.dylib`、
     `libMTLIGCCompilerPlugin.dylib`；
   - 目标 `GPUCompiler`/`MTLCompiler`/`libLLVM` 的只读导出信息。
2. 运行（不写文件）：
   ```sh
   python3 tools/check-tgl-compat.py \
     --config configs/tgl-9a49-25G83.json \
     --input-dir /path/to/tgl-25G83-input \
     --audit-unselected --json
   ```
3. 只有目标哈希/Mach-O/版本/选中 patch 全部通过，才把新增目标哈希写入
   `configs/tgl-9a49-25G83.json` 的 `known_hashes`，并保留原始输出。

**退出条件：** `overall == "TARGET_PREFLIGHT_OK"`，或明确记录哪一项拒绝
（哈希、架构、版本、字节、符号）。不得用 donor 结果替代。

## P1 — 建立 TGL 专用 NootedGreen 补丁层

目标：不直接用 RPL `-ngreenxefix`，把 B/C 项拆出来。

最小改动建议（先在离线副本，形成 patch；不部署）：

1. 新增 `-ngreentgltahoe`（或逐项 boot-arg）作为 TGL 专用开关。
2. 把 `XE-FMT`、`XE-PLANES2` 从 `if (!isRealTGL)` 块移出，放到 TGL/Tahoe
   开关下；保留 `-ngreennoplanesfix` 等禁用路径。
3. 给 `V40`、`V221`、`forceWake` 替换、`HANGCHECK` 增加显式 TGL gate；
   默认不执行 RPL 版本。
4. 把 `XE-POOL/POOLALIGN`、`XE-PAGESYNC`、`XE-NOORPHAN`、`XE-RESFREE`
   从 `-ngreenxefix` 中拆出，默认关闭，单独测试。
5. 保持 `XE-VALD`，但加目标二进制/版本校验；如果目标函数布局变化，
   失败要显式记录，不能静默跳过。

验证：

- 源码/对象编译（现有 12 对象基线）；
- 静态测试：TGL 分支不进入 RPL 拓扑/CSB/GTFREQ 代码；
- 用 `git diff --check`、`make check`；
- 不生成或加载 kext。

**退出条件：** 形成可审阅的 patch + 单测；仍未证明运行。

## P2 — MTL/编译器适配的 25G83 预检

1. `libxedrv`：
   - 增加 `MTLRenderPipelineDescriptorInternal` size `0x338`、`_private@0x30`、
     颜色附件 size `0x10`/`_private@0x8` 检查（对齐 25G83 独立项目）；
   - 把 `allowGPUOptimizedContents=NO` 改为 TGL 默认保留压缩（可用环境变量
     或编译期开关），RPL 才禁用；
   - 保留 v15/v16/v17，但标记为“按目标测试逐项启用”。
2. MTL driver：
   - 只应用 `configs/tgl-9a49-25G83.json` 选中的 3 条（header、load command、
     compiler path）；
   - 生成一个只读预检 + 离线输出副本的脚本；**不要**直接运行上游
     `patch-mtl17.py`（它会应用全部 10 条 + PoshDisable）。
3. 编译器：
   - 在目标系统只读检查 `MTLCompiler` 的
     `MTLCompilerBuildRequestWithSerializedBitcode` 与
     `getSerializedModule` 签名；
   - 检查 `GPUCompiler.framework` 版本/路径；
   - 若签名/路径不同，修改 bridge 的签名扫描，不写死 offset。

**退出条件：** 生成的目标 bundle 仅在私有离线目录；哈希、Mach-O、
`codesign -v`（不安装）通过；仍不部署。

## P3 — 合法签名/加载路径（硬阻塞）

参考实现依赖 `amfi_get_out_of_my_way=1`，本任务禁止。必须满足以下之一：

- 有合法 Apple 开发者签名/公证路径，使 WindowServer/MTLCompilerService
  接受注入的旧 driver；或
- 有用户明确授权的新安全策略变更（当前没有）；或
- 放弃方案 A 的部署，只保留离线研究。

**退出条件：** 在不修改 SIP/SSV/AMFI、不使用 `amfi_get_out_of_my_way=1`
的前提下，有可验证的加载方案；否则本阶段不应进入实机。

## P4 — 一次受控目标实验（只有新授权才做）

前置：P0 通过、P1/P2 离线审查通过、P3 有合法方案、用户明确批准。

最小变量：

1. 完整备份 EFI/`/Library/Extensions`/`/Library/GPUBundles`；
2. 只做一次启动，不自动重启、不自动安装；
3. 只读采集：`sw_vers`、`ioreg -c IntelAccelerator`、`kmutil showloaded`、
   WindowServer/MTLCompiler 日志、`system_profiler SPDisplaysDataType`；
4. 不以“framebuffer 有输出”代替 Metal；不以“kext 加载”代替 GPU 提交；
5. 出现 panic/hang 立即停止，保留现场，不循环重试。

**退出条件：** 有真实 GPU 提交/完成和 Metal 设备证据，或明确失败原因。

## P5 — 路线决策门

如果出现以下任一情况，暂停方案 A，重新评估方案 B：

- 25G83 目标文件的关键字节/符号与 16.0.32 不匹配，且无法安全适配；
- `MTLCompiler`/`GPUCompiler` 无法桥接；
- 合法签名/加载路径不可行；
- 9A49 上 Apple TGL 驱动无法接管显示或 GPU，且差异无法用少量补丁解释。

不要因为方案 A 在 RPL 25G241 上被报告成功，就跳过上述门槛。
