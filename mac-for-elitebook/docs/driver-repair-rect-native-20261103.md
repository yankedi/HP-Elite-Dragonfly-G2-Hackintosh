# REPAIR4：rect 空指针与原生 TGL 拓扑联合候选

日期：2026-11-03。用户要求：“修复，下次和花屏修复一起验证”。

## 当前结果

以实测 REPAIR3-FBABI 为直接底稿，在固定上游 `6f03560ef9694f9826caae15624d4a6cb1bf9ffc` 的新基底继续修补。已完成本地回归、交叉编译签名和联合 IMG 打包。用户纠正应继续实测后，**已于08:28UTC实际交付、武装并请求正常重启；联合试验结果等待实际事件，尚无成功结论。**

## rect 分配器的具体缺口与修复

REPAIR3 panic 在 `SecurityAgent → process_MSAABufferResolve → submitBlit → blit3d_submit_rectlist+0x845`，R14=0、CR2=8。此前完整 EFI 和所有用户/系统 DiagnosticReports 已回收，再本地解码分析。

进一步核对实际 IOAcceleratorFamily2 `B77A42EC-6B0C-3A8D-89A2-B8F4CDBAC8C9` 的完整函数，发现旧 hook 错把 pool `+0x1848` 当成 backing allocation base。该字段其实是**当前提交段起点**：`submitBuffer` 的非零 alignment 分支会推进它，它不保证页对齐。真实 backing base 是 `pool + 0x40 + 24*currentIndex`；原始分配器和 `getGPUVirtualAddress` 均使用这个数组。

因此，一个合法、非页对齐的后续提交段会被旧 `rectRequest` 当成坏 base，返回nullptr，而 donor caller 不判空即写入。这一缺口已在本地复现；**尚不能确定它就是本轮 panic 实际经过的失败分支**，因为故障时 pool 字段未保留。

本轮实现：

1. 使用有索引/数量边界检查的真实 backing base，分配后重新读取，兼容首次分配和 rollover。
2. 保留现有完整批次拆分、4KiB page-local 限制、CPU/GPU 相同偏移及 MI_NOOP padding。
3. 在 donor `VM 0x33cea` 的首个命令写入前，经精确15字节和目标 epilogue 字节核对，安装空指针跳转保护。非空路径执行原15字节；空路径跳到 donor `0x3588b` 的 stack-canary/epilogue。
4. 失败时清理本组此前设置、尚未提交的 submission tag；记录原因及 pool 字段。通过栈上、按线程关联且支持嵌套的 failure scope，把失败带回 `submitBlit` 的 **boolean false**，避免仅跳过绘制却上报成功。实际 donor 反汇编确认该函数返回布尔值，不把 IOReturn 错误码塞进布尔接口。

Lilu `1.7.2` / commit `e4748cc081bf060302c7d3c44a643ce1d11b7e1d` 的 `routeBlock/createTrampoline` 已核查：注入19字节 guard 后，复制15字节无 RIP-relative 的 donor 指令，接回原位置。分配器调用的 return address 保持原值，现有 callsite gate 仍适用。新 `_current_thread` 和 `routeBlock` 导入分别在实际 kernel fileset 和 Lilu 二进制中确认。

## 花屏侧：按上次依据修正原生路径

GA416 的已验证关键改动是 L3 fallback 8→6。REPAIR3 已通过参数显示80EU/10SS/L3=6，因此重复加同一参数不能算新的修复。

本轮针对新基底仍存在的另一处不一致：真实 TGL 也进入通用 RPL topology override，并被写入固定1000/450MHz及通用拓扑字段。现在为真实 TGL/Tahoe 增加原生分支，保留 donor 的完整拓扑、镜像字段、dispatchers及频率；仅对已测的 GT2 / 1 slice / 10SS / 8EU-per-SS / 80EU / nativeL3=0 使用测量支持的6-bank fallback。其他SKU及非零原生L3不被猜测值覆盖。记录 donor/effective L3、原生频率和镜像字段，供下一次现场核验。

这是依据上次硬件事实形成的**花屏侧候选修正**，不是已经证实当前花屏消失。没有整块移植旧驱动实现；仍保留 REPAIR3 的真实多平面/格式 ABI 和 FBABI 修补。

## 本地验证

- 从实际候选源码提取 hook 函数，替换外部 kernel/allocator 环境：101370个分配场景、6132次rollover；复现旧版非对齐段起点误拒绝；验证首次分配、padding、越界索引、请求/原分配器/结果三类失败、tag清理、嵌套与跨线程隔离。
- 原有785664个边界场景、95139个128KiB in-slot padding场景及矩形守恒回归通过。
- 执行真实 donor guard/写入片段，空指针避开写入、非空保留正确写入；补充执行真实20字节prologue及34字节canary/epilogue，验证正常/空指针返回和损坏canary分支，栈和callee-saved寄存器正确恢复。
- 从实际候选提取 `submitBlit` 返回处理，验证原始true/false保留，分配失败把原始true改为false。
- 18个完整原生GPUInfo对象对照：除精确目标的L3=0→6外，其他所有字节（含频率/镜像）保持不变。
- 本地编译及ad-hoc签名通过；两份CodeDirectory代码页/特殊槽通过；编译warning类别及数量与REPAIR3一致。
- IMG内98个EFI文件仅NG二进制改变；config原哈希、精确kext读回、匹配OpenCore1.0.8的ocvalidate与FAT检查通过。

上述 host stub/native snippet 验证不等于真实GPU执行验证。

## 制品与证据

| 项目 | 值 |
|---|---|
| 镜像 | `HP-UPSTREAM-6F03560-REPAIR4-RECT-NATIVE.img` |
| 源IMG SHA256 | `420b30ef8aa561c22361079ed2092b7d4ac5110f83c3176b0cf7ad51dd339457` |
| 结果IMG SHA256 | `c73cc10b7033be5c180f09c7c1f13709e15e962a1493d55a167591748482bd59` |
| NG SHA256 | `a16f5addddbed07f4a828239549f6c5132ab6c6dde06396bab33a484b1902dd8` |
| NG UUID | `4C4C4465-5555-3144-A194-41B5AF06525C` |
| 源码diff SHA256 | `168e9bc3ee01309a779e62ab9e2a749cce9f87e8a1a175fb6d61f6a9048a858c` |
| config SHA256 | `7df7f1f674e485195bfb5e8c94779047976131e5da7b2b573e4043d181ac71fd` |

私有根：`.local/driver-repair-20261103/repair4-rect-topology/`。`source-receipt.json`、`verification.json`、`failure-path-verification.json`、`integration-audit.json`、`build-receipt.json`、`signature.json`、`image-receipt.json`及全部原始构建/测试日志保留。首次host测试仅缺少`initializer_list`头，修正后通过，原失败日志保留。

## 下一次联合验收

### 已开始执行

用户原话“那就继续测啊，不要停，我要你停止了吗”。此前把本地候选完成当作停止点是误解。已严格认证仍为NixOS boot `b38ae9a4-21b4-4d83-92fc-73616541f5c8`，收回完整USB boot文件/env，98EFI与REPAIR3逐字节一致、consumed目标正确。试前env SHA `f868beaca1ddca72b3a5951351b1ca0cabb1541d98fde0d1043b73fc08b81c64`，完整EFI变量另存。

08:28:53UTC整图上传/完整哈希回读exit0；独立env备份/一次武装exit0，armed SHA `6942f0fae1272b3629e247582b7451ca69eec050e0b4a60feab5325749409310`；08:28:59UTC同boot/env guard通过，请求正常reboot，SSH exit0。SSH退出码本身不证明启动成功。新观察器PID3817018，证据`trial/lifecycle.ndjson`、`trial/run/`。

自动序列为完整实时流/可获得历史回填→系统内容/身份/新增安装门控→GUI截图尝试及一次原封存R8→完整现场→R3/rect执行门控→Metal。R8只覆盖自身像素路径，不能冒充登录/MSAA实际覆盖；如果没有图形用户会话则明确保持桌面/登录待定。监督器在负载完成或实证GPU reset完整取证后追加完整现场，才停止本轮精确测试进程并正常回NixOS；后续关机watchdog必须归为agent请求恢复阶段。原观察器完成终态后顺序补收root reports及本轮测试cache。

按用户要求将panic路径和花屏放在同一新候选启动验证，机器可读计划为`next-validation.json`。先认证OS/boot、准确UUID、250项系统内容、FBABI/FF_DOP/既有补丁与新增`HP-RECT4 ready`、原生80EU/10SS/L3=6。全量采集立即开启；对延迟执行的R3/rect区分安装与实际命中，不以最早未执行直接判补丁失败。

现场先检查登录后的Settings/Finder/Dock等真实桌面及MSAA resolve，保存完整截图/元数据，再进行Metal；记录任何allocation rejected及其false返回。**只有不panic而仍拒绝正常绘制，不算修复验收通过。** 图形结果、登录路径、303及后续负载分别记录，不能互相替代。完整未过滤日志先收回本地，故障恢复后继续全EFI/所有DiagnosticReports取证。当前没有本轮运行结果。
