# 新基底直接修复：framebuffer 的 IOSurface 格式读取

## 当前结果

在已测试的 REPAIR2 新基底上直接修复 `ValidateTransaction` 的格式读取；本地机器码回放、交叉构建签名、镜像检查和实机补丁应用核验通过。**尚未启动 Metal 压测即失联；回到 NixOS 后完整取证，确认 SecurityAgent/MSAA rect-list 空指针 panic。** 这不是已证明的 GPU hang 修复。

用户明确要求在新基底修复。底稿为固定上游 `6f03560ef9694f9826caae15624d4a6cb1bf9ffc` 加现有 R3/R4/REC/KPOOL/IOSurface/rect/FF_DOP；旧 GA416 只作参考，没有移植旧实现。

## 已定位的具体缺口

实际 framebuffer：`AppleIntelTGLGraphicsFramebuffer`，UUID `B96A8448-9D17-3F78-B76D-15A0B359A9A0`，SHA-256 `285ee7a9c3d6c9a9647013f44fb40f312b1cb42879974ef0542544cf049442b5`。

`AppleIntelFramebuffer::ValidateTransaction` 在 `0x3ed68` 先设置 BGRA 默认值；非空 IOSurface 分支在 `0x3ed88` 读取旧字段 `+0xa4`，再写回局部格式，交给后续验证函数。新基底的 `XE-VALD` 把整个9字节读取/写回改成 NOP，所以非 BGRA 表面也只能按 BGRA 验证。

真实 25G83 IOSurface getter 已独立确认格式在 `+0x80`。REPAIR1 已修加速器侧 `performTransaction` 的读取，但 framebuffer 侧仍强制 BGRA，存在格式传递不一致。

本次只将该处改为读取 `+0x80`，保留非空条件和空 surface 的原 BGRA 默认值；应用前使用现有 getter/layout 校验结果。无法确认布局时维持基底行为并明确记录失败，新试验不允许越过这一门控启动负载。

| 项目 | 字节 |
| --- | --- |
| 原 donor | `8b80a40000008945b4` |
| REPAIR2 运行补丁 | `909090909090909090` |
| REPAIR3 运行补丁 | `8b80800000008945b4` |

源码3文件的变化只包括该补丁选择、运行日志及 getter 校验状态的只读查询声明/实现。完整 diff：`.local/driver-repair-20261103/repair3-fbabi/fbabi-vs-repair2.patch`。

## 本地验证证据

- 唯一机器码窗口和完整实际函数反汇编：`other-errors-audit/framebuffer-audit.json`、`framebuffer-ValidateTransaction.asm`。
- 回放完整函数的实际指令；外部 transaction getter 与最终硬件验证换成本地 stub，验证送往下游的格式。原 donor 读取被毒化的旧字段；REPAIR2 对所有格式给出 BGRA；REPAIR3 精确传递实际格式。每种版本含8种代表值和65536种额外32位模式。
- 两种 display transaction、空 surface 保留 BGRA、空 transaction 返回 bad argument、非 display kind 均通过。此回放验证格式传递及分支语义，不是实际 GPU 渲染测试。
- 使用现有固定工具链本地交叉构建；两份 CodeDirectory 全部代码页及 Info/Requirements/Resources 特殊槽完整性通过。
- 98份 EFI 资产只有 NootedGreen 主二进制不同，config 原 SHA 不变；签名 kext 逐字节读回、OpenCore 1.0.8 对应 `ocvalidate` 和只读 FAT 检查通过。

| 制品 | SHA-256 / 身份 |
| --- | --- |
| 基底 REPAIR2 IMG | `3047bd4377f41ba076ea418e177d91ac65064e26897a9119e92c534c6272e519` |
| REPAIR3-FBABI IMG | `420b30ef8aa561c22361079ed2092b7d4ac5110f83c3176b0cf7ad51dd339457` |
| NootedGreen | `ec08462f58ece20fdd98bb26012a014517e74a21616c19119e7306e6b94106e1` |
| NootedGreen UUID | `4C4C445E-5555-3144-A1D5-5800FD5D6406` |
| 源码 diff | `782c5ef0c3d2643ca8ff1ae881542258493dc70a12c4e8d8dcb41889cf22dcc0` |

私有证据根：`.local/driver-repair-20261103/repair3-fbabi/`。实际交付/启动状态以后续新 trial 回执为准。

## 首次实机启动及当前恢复状态

- 新 IMG 全图传输/读回成功；试前 USB 98份 EFI 与已测试 REPAIR2 一致，旧 consumed env SHA `400633bb5864de7187a1aa0f7328ea96984fabef10d183374e5ad1709be64c84`。独立一次性 env 备份/武装成功，07:37:28UTC代理请求正常重启。
- 07:39:08UTC认证 macOS25G83 boot `C8FE5201-CB1C-4EE2-BBD2-57C3D8309494`，NG UUID与候选相同，250项系统内容核验通过。40.807828秒 `HP-FBABI ... ready`、`XE-VALD ... fmtBGRA=0`，FF_DOP与其他安装门控通过。
- 最早采集还没有 R3 执行命中，观察器因此没有启动压测。稍后的完整快照已出现83.56秒 R3初始化成功、86.98秒 rect执行。07:40:28开始的完整 dmesg/IOReg/所有 DiagnosticReports/进程快照全部返回0。
- 新增同 boot 重新核验脚本（原试验脚本保留）；07:42:40确认全部补丁门控均通过。但下一项 kextstat 查询SSH超时，脚本在发送 Metal 命令前失败。**没有启动 Geekbench，也没有本轮 workload303 结果。** 不能把该轮记作压测GPU hang。
- 实时流154244行、可用history5045166行，gzip检查均通过且0坏JSON；history最后止于11月1日，不含本轮boot。实时流末条15:42:42.913084+0800，没有实际 GPU hang/reset 消息；包含panic词的条目均是bringup警告或背景文本。
- 后续两条SSH均不可达，只能记录失联。用户报告刚刚登录、认为可能有关，随后说“我直接重启吧”；这是用户报告的潜在触发和恢复计划，尚不能确立登录因果或重启完成。
- 既有观察器PID3102646继续等待经严格认证的新 NixOS boot，先完整收 EFI 和所有诊断报告。额外等待器只负责完成通知，不新增目标采集或压力负载；当前没有自动重试。

生命周期：`trial/lifecycle.ndjson`、`trial/run/events.ndjson`、`trial/gate-resume/events.ndjson`。完整现场：`trial/post-gate-live-snapshot/`。本地全流扫描：`trial/stream-preterminal-scan.json`、`history-preterminal-scan.json`。

## 其他报错的证据边界

### REPAIR3 新 panic 的终态核实

用户报告回到 NixOS 后，严格 SSH 认证新 boot `b38ae9a4-21b4-4d83-92fc-73616541f5c8`。原观察器于07:49:31UTC完成全部 EFI、系统及所有用户 DiagnosticReports 回收，采集及报告比较均 exit0；没有启动竞争采集。

- 10个数字 PanicInfo 块相较试前全部改变，共7680 packed bytes，解码后可逐字节重建原文。块均满768字节，文本尾部截断；只称全部可获得块已回收，不称完整panic文本。
- 本轮NG UUID与REPAIR3一致。`SecurityAgent` pid491；uptime **283.262208823秒**；`System shutdown begun: NO`。这是内核 page fault，不是此前 shutdown watchdog。
- 调用链：`process_MSAABufferResolve → NootedGreen::submitBlit → IntelAccelerator::submitBlit → blit3d_submit_commands → blit3d_submit_rectlist+0x845`。
- 故障VM `0x33cf5`，原指令 `41 89 46 08` / `mov [r14+8],eax`；R14=0、CR2=8，错误码2表示写访问。即向空命令缓冲区指针+8写入。
- 实际TGL二进制及重定位确认：`0x33caf`调用`getBufferPtrNoInc`，返回值在`0x33cb4`复制到R14；接着调用`getGPUVirtualAddress`，未判空即写入。当前HP-RECT hook在请求检查失败、原分配器失败或结果检查失败时可返回nullptr，因此这里的失败返回契约存在缺口。**尚不知实际是哪条路径返回空，也没有故障时pool字段。** 不能直接认定FBABI补丁或用户登录造成了它。
- 登录可能触发SecurityAgent图形请求，与调用链一致；用户操作不是已经证明的根因。没有Geekbench启动、没有本轮303结果。

证据：`trial/panic-decoded.txt`、`panic-decode-receipt.json`、`panic-analysis.json`、`panic-rectlist.asm`、`run/post-nixos/`。可复核脚本：`repair3-fbabi/analyze-panic.py`。

用户同时要求参照此前GA416修花屏，随后要求先查panic。GA416修复的单因素为L3 fallback 8→6；当前实机日志已确认80EU/10SS/L3=6，因此相同参数已经生效，不能当成新的修复。新候选尚未实现，后续继续在新基底定位。

此前问题的扫描结果在 `.local/driver-repair-20261103/other-errors-audit/`：完整实时流376305条，选出21487条 Error/Fault 或关键词消息，归并1282组；数量是日志条数，不是独立故障数。实时流每条 bootUUID 为空，归属依认证采集会话和同 boot 快照。历史回填最后止于10月27日，没有 REPAIR2 boot 记录，不能混入本轮。

- ACPI：3张表加载失败、3处缺名及 EC 方法错误；REPAIR1/2 均有。
- IOVersatile：依赖缺失/类型错误，在压测前已存在；不能只补一个猜测的 plist 依赖便称修好。
- 代码签名：`unsupported code signature page shift: 14` 与 cs_blob 错误，当前 dmesg 各925条；没有对应路径证据，不能归因给某个 GPU bundle。
- 显示：Unsupported DDI、link bandwidth、TCON 和 mode failure；触控板描述符及 USB/Wi-Fi/SMC 也有报错。启动成功或后续 route 成功的上下文保留在 `findings.json`。
- `mediaanalysisd` 的57条 Metal `Compiler failed to build request` 从14:43:02开始，晚于首 GPU hang，尚不能作为初始 hang 原因。
- `coreduetd` 本轮 CPU resource 报告：15秒窗口平均97%，未采取终止动作；这不是进程崩溃。

上述报错与本次格式缺口的因果关系仍待检验。FF_DOP 的既有代码修补和实机应用成功结论保持；本次不以其他故障否定它。
