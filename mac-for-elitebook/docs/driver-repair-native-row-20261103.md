# REPAIR5：原生 TGL engine ROW_CHICKEN2 修补与实测

## 当前结论

继续保留固定上游 `6f03560ef9694f9826caae15624d4a6cb1bf9ffc` 的新基底，直接以实测 REPAIR4 为底稿。已补上一个具体的引擎初始化遗漏：**TGL 的 `Wa_1606931601` / `ROW_CHICKEN2[14]`（disable early read）**。本地实际机器码回放、交叉编译、签名、IMG 内容及 OpenCore/FAT 检查通过。

**已交付并实测，用户仍观察到少量局部花屏。** 原 USB 恢复后完整采集及98EFI核验通过，独立镜像整图回读、武装并于14:44:57UTC请求启动；macOS boot为`CBBC0736-CB26-42BE-A20B-452D4AC42014`，准确NG UUID及250项内容通过。原缺盘失败证据仍保留。

实际 ROW `0xffff0000→0xffff4000`、MCR `0x8f000000→0x8f000000`，ACK=`0x2`；现有读回判定要求ACK bit0，与实测不符，日志`verified=0`使自动门控提前中止。必须核对donor requester，不能将此次判定失败解释为bit14没有写入。未执行R8、Metal或截图，用户现场报告是当前局部花屏未通过的依据。

监督器在收完整现场后于14:46:48UTC主动请求正常重启；14:47:42UTC认证NixOS boot`9a80ad12-d943-4382-b299-f7ac7758ee33`。完整EFI及全部存在的系统/用户reports已回收、逐源compare通过；postEFI未见数字PanicInfo/SleepWake块，相对重启前reports新增一份shutdownStall，不据此判为panic。

**用户纠正：问题是macOS脚本在测试基本未开展时就提前重启，不是全局禁止或允许重启。** 代理此前扩大成“所有重启重新询问”的规则已删除。用户要求先测试新引导，准备和验证通过后正常切换进入测试；macOS监督器保留无回程重启/自动停进程路径，失败或结束后保留现场与采集。已执行旧脚本按哈希另行保留，trial历史事件不改写。

离线验证覆盖门控失败、Metal结束、GPU reset、现场采集失败四条路径，均只调用采集、没有重启。当前无活动trial自动化进程；`make check`及`git diff --check`通过。回执为`automation-no-reboot-20261103/verification.json`。

## REPAIR4 实测及恢复

- macOS boot `607DD58A-E51E-4B84-BA04-3FF0127819DD`，准确 NG UUID、250 项系统内容及八项安装门控通过。
- 67 秒 R3 实际初始化成功，70 秒实际 rect 分配；first-reset 完整 dmesg 未见 `HP-RECT4: allocation rejected`。
- 163.7 秒开始 GPU reset；首份报告为 RCS/context49，`IPEHR=0x7a000004`、`ACTHD=0x40006ba8`、`EIR/ESR=0`。
- 首 hang 早于 GUI Terminal 启动请求，**R8 与 Metal 均未启动**。回收精确本轮 cache 只有四个上传文件，没有脚本输出或截图。Terminal 后续 CPU 报告显示其占用一个核；不能归为初始 hang 的原因。
- harness 服务重启取消了本地观察进程。原 gzip 均缺尾；保留原件，单独派生恢复 stream 150781 个有效 JSON 行和旧 history 141920 行。实时流覆盖 16:30:35–16:34:50 +0800，历史回填只到 10 月 25 日，不能冒充本轮完整日志。
- 恢复后先收回完整 EFI、系统及所有存在用户的 DiagnosticReports、精确本轮 cache；采集和归档逐源比较均退出 0，之后才在本地筛选。
- 六个新鲜数字 PanicInfo 块共 3913 packed bytes，精确往返解码为进入 darkwake 途中睡眠转换超时 17 秒，IOGraphicsFamily 的 `closeGate` 路径，uptime `4615.611855299` 秒、`System shutdown begun: NO`。这不是 REPAIR3 的 SecurityAgent 空指针 trap；此 panic 未列 NG UUID，没有据此宣称所有登录/MSAA 路径已通过。监督器没有留下主动回程重启意图，返回机制不能由 SSH 状态推断。

原件与审计：

```text
.local/driver-repair-20261103/repair4-rect-topology/trial/recovered-post-nixos/
.local/driver-repair-20261103/repair4-rect-topology/trial/recovery-audit/
.local/driver-repair-20261103/repair5-native-row/preceding-rcs-analysis.json
```

## 确认的初始化缺口

实际固定 TGL 二进制 SHA256：

```text
1b2f5aa3131f9b909fe984877e41d5ebcdb2837572b45e1e901a72a6271515a2
```

`startGraphicsEngine` VM `0x25100` 在 `0x25125` 先调用原生 `SafeForceWake(true,7)`。其 ROW_CHICKEN2 初始化窗口 `0x25425–0x25463` 只构造 bits 0/1/8 的掩码，没有显式设置 bit14。当前新基底中另一个 ROW 修补在 `!isRealTGL` 分支内，原生 TGL 不会执行；后面的通用 workaround 清单又位于提前返回之后，不能拿清单存在当成实际应用。

依据是 Linux **v6.18 / `7d0a66e4bb9081d75c82ec4957c50034cb0ea449`** 的 `intel_workarounds.c`。`rcs_engine_wa_init` 对 TGL 明确要求 `GEN12_DISABLE_EARLY_READ`，使用 MCR masked write。源文件 SHA256 `0b1f9fd2205786d87926d10e269700fdf39ee0bcf5069d3c99c77904f2184dae`，来源及归档哈希见既有 GA41 `sources/provenance.json`。

旧 RPL 注释把 `READ_SUPPRESSION` bit15 也混入 TGL 说明；在此固定 Linux 版本中，该 bit15 规则的条件是较新 DG2/MTL，不能整块搬给 TGL。本候选只增加 bit14。

**边界：REPAIR4 没有直接读回运行态 ROW bit14，不能说已经测到该位为零；确认的是初始化代码缺口，不是 RCS 唯一根因。** 对应 batch 正文与 PPGTT 资源映射仍缺失；`IPEHR` 是最后指令头，不能独自证明故障指令。PPGTT 的 `0x40006000` 与其他 GGTT 数值相等也不等于别名。

## 实现与验证

只有两个 NG 源文件相对 REPAIR4 改动：`kern_gen11.cpp`、`hp_repair_policy.hpp`。

1. 在已持 forcewake、尚未启用/提交 context 的原生初始化无条件路径 VM `0x25183` 注入 94 字节 prefix。
2. 暂存完整 MCR selector，临时启用 multicast，写 `ROW_CHICKEN2` 的 `0x40004000` 掩码，读取前后值及 render ACK，恢复并读回原 selector。
3. 保存全部触及的寄存器和入站 flags，再执行原始 16 字节 PIC MMIO load/store。原始 PERCTX 写入保留。
4. `HP-ROW5` 分别报告安装状态及每次引擎启动的实际读回。验收要求 bit14 置位、render ACK、完整 MCR restore、原引擎成功；不将最低 steering 实例的读回冒充所有 DSS 的逐一读回。

65536 个原始 low16 状态的**实际 prefix 与 donor 指令**本机回放通过；flags/RAX/RCX/RDX/栈和 selector 恢复，原 MMIO 指令保留。独立掩码运算证明只新增 bit14、bit15 保持。普通 host 内存不具备 GPU masked-MMIO 语义，因此运行态读回仍是必须的实机门控。

无新增未解析导入；构建 warning 类别及计数与 REPAIR4 相同。签名页及特殊槽通过；98 个 EFI 文件只有 NG 二进制变化，config 不变；匹配的 OC 1.0.8 validator、FAT 只读检查通过。

| 制品 | SHA256 / UUID |
|---|---|
| 源 REPAIR4 IMG | `c73cc10b7033be5c180f09c7c1f13709e15e962a1493d55a167591748482bd59` |
| REPAIR5 IMG | `563d7a04b83b45f288decaee0edbe5c02eead8f6256625b27e79d2686427f3c6` |
| NG | `8b3d5aa4aeac65fec3b6c95d29a043b66c8587afa3839c6bae1cab9f68b0656d` |
| NG UUID | `4C4C447C-5555-3144-A127-E23F93535131` |
| 源码 diff | `4341b863c7faf0ba8ceaa62f738ed954571b39e4374ddd6cee206739677609ba` |
| config | `7df7f1f674e485195bfb5e8c94779047976131e5da7b2b573e4043d181ac71fd` |

私有目录：`.local/driver-repair-20261103/repair5-native-row/`。旧源码、镜像、回执及 trial 均保留。

## 接续实测

### 独立重测 RETEST1 的实际结果

Mac boot `44E5B111-BA84-4067-A278-C066CCE73470` 下安装/读回门控全部通过。相同IMG，仅主机判定改用实际donor的requester index1和boolean低字节。一次R8命令正常完成（status4、exit0），完整试前/后reports及制品归档均exit0；独立像素审计结果却是 **GPU copy回读0/16705坏像素，managed texture的CPU getBytes为16705/16705坏像素、47633有效字节不同**。因此整体PIXEL_FAIL，尚未启动Metal；不能把进程exit0或GPU副本正确当成整条CPU可见路径正确。

用户要求截图后，直接SSH截图失败，通过已登录Terminal执行系统`screencapture`成功，1920×1080原PNG已本地保存。实际图像可见菜单栏、widget、窗口/卡片边缘和Dock彩色竖条及坏图标；主体内容大多可读。局部花屏已由图像证实，尚不能将其唯一归因于R8 CPU读回异常、压缩或某个GPU命令。

原图：`.local/driver-repair-20261103/repair5-native-row/retest1-20261103/desktop-user-request/extracted/terminal-desktop.png`，SHA256 `8a1f9029cecce6006ef98c4471d9549ed6a41450b4a044a3e78b0a3f5b4c0a72`；分项审计`desktop-user-request/visual-review.json`。没有改TCC权限数据库；系统保持运行并继续全量采集，没有自动回程重启。

当前R5首轮trial已完成，不能重跑覆盖。精确donor反汇编已确认requester index1和startGraphicsEngine低字节boolean，因此修正host端解析，不改被测IMG/驱动；独立重测先开展实际桌面、R8/Metal。测试入口按准备判断正常启动，macOS测试脚本不提前回程。

新版 runner 的完整 reports 采集与 smoke 并行，避免上轮先等待约三分钟归档才请求绘制。图像先用现有 capture helper 直接尝试，不依赖已证实未能运行脚本的 Terminal；权限不足如实记录，不修改 TCC。通过身份/ROW5 读回及旧补丁门控后做一次既有 R8，再按执行门控运行 Metal；发现 GPU reset 不继续发送 Metal。实际桌面、登录/MSAA、像素和 hang 各自评价。

早先缺盘证据为 `target-usb-missing.stdout` 与 `pretrial-boot-assets-failed-no-usb/boot-assets-collection.stderr`；此阻碍随后已解除，原件保留。当前实测证据在`trial/run/`、`trial/supervision/`，自动化修改前原脚本在`automation-no-reboot-20261103/`。
