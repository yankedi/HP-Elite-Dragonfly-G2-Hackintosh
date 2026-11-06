# RCS 卡死、恢复路径和命令取证

## 03 与 GA410 R5 原始报告逐项对照

2026-10-31 重新直接比较两份原始 gpuRestart：两次 RCS HEAD `0x190`、
TAIL `0x1f8`、ACTHD `0x40008004`、IPEIR `0`、EIR/ESR `1/1`、
INSTDONE `0xffdfffff` 完全相同，报告都说 page table appears okay；
RCS ring 最后显示的 batch 目标均为 `0x40007e40`，ACTHD 比其高
`0x1c4` 字节，跨过 `0x40008000` 的 4 KiB 地址边界。03 context 51、
RING_START `0x40716000`、IPEHR `0x40238001`；R5 分别为 63、
`0x408e4000`、`0x40188001`。两份 ring dump 均 110 个 DWORD，
95 个相同、15 个不同（其中包含地址和数值），偏移 `0x184` 的
`0x18800101` 及随后的 batch 目标均相同。IPEHR 只是报告中的最后
指令头，不能推定它正是故障指令，也没有实际 ACTHD batch 全文；相同
GPU 虚拟地址不证明相同物理内存或 workload。跨页是可验证假说，不能
凭此认定越界或页面未映射；报告的页表判断也不证明访问一定有效。
可据此研究命令池容量/对齐的 R6 路径，但这两份报告未证明扩大池子
可解决当前 hang；与 R2、XE-GPUREC 的适用性需分别验证。

## 2026-10-31 原始 gpuRestart 成功取回

用户说明刚才误启未加修复的旧镜像后黑屏，现重新进入 macOS。SSH
确认新的 boot `CEDFE46C-C04A-42EB-AC09-1DD9D506FCFD`、NG UUID
`4C4C44A9-5555-3144-A1E8-AAA65E28379F` 匹配 03 构建；真实启动镜像
路径不单凭 UUID 断定。提权先全量复制 `/Library/Logs/DiagnosticReports`
到本地 tar，再本地提取 22:10:08 的 65,946 字节原始 gpuRestart；全量
tar SHA `21cb7143b9afed39122f6d6de996fc1e6839b679c7884342a47ce50a352cb436`，
报告 SHA `41a1107a1f2e47bc5d124072b4c5375932aa3e0a542d05797aafd365949b2690`，
回执与原件 `.local/additive-r3-first-20261031/live-repeat-planes-20261031/`。

该原始报告补全日志截断内容：context 51，RCS ring 最近 batch 地址
`0x40007e40`，ACTHD `0x40008004`，IPEHR `0x40238001`，EIR/ESR 均 1，
INSTDONE `0xffdfffff` 的 CS 未完成。含 RCS ring 部分原始 DWORD（偏移
`0x184` 为 `0x18800101`，后接 `0x40007e40`）；没有证据此报告含 ACTHD
处实际 batch 全文。老 GA410 R5 原始报告的 batch 地址、ACTHD、EIR/ESR、
INSTDONE 值相同，但 IPEHR `0x40188001`、context 63 与本次不同。
这是值得研究的重复模式，不足以证明同一个 GPU 物理对象、同一坏命令或
跨页本身就是根因。继续在本地安全解码和核查 batch 数据采集路径。

新启动已开始独立 root 全量实时流与全部可用历史回填，先保留未筛选数据。

## 本机实测

R3FIRST-03 的同一启动，完整 root 实时日志 22:10:08 报告 RCS 在
batch 中 hang（context 51），随后 `GPURestartBegin/End`。22:14:45
起至少 31 条 `no channel associated with stamp_idx`，涉及 1 和 24，
交替出现多次重启跳过；后续 WindowServer 120 秒不报到而 watchdog panic。
原始完整日志和本地筛选在
`.local/additive-r3-first-20261031/live-planes-20261031/`，panic 在
`post-planes-20261031/decoded/panic.txt`。整条日志记录本身的 GPU 摘要
被 macOS 截断在 RING_START，无法据此知道本轮 ACTHD/IPEHR 或 batch 内容。

03 源码 `kern_gen11.cpp:2129–2130` 中 XE-GPUREC 安装条件为
`!isRealTGL`；同次 sudo dmesg 的 V52 报 `isRealTGL=1`，因此该源码路径
不会在这台机型安装 GPU 恢复 hook。运行快照未见 `xe-rec` 或 XE-GPUREC
日志。**注意：没有 xe-rec 属性单独不能证明 hook 未安装；源码门控和运行
机型一起提供更直接依据。** R3/AUX/CCS/PLANES2 有各自的实际应用日志。

## 上游相似问题

上游 [issue #2](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/2)
报告 Raptor Lake Dell RCS hang、WindowServer watchdog，以及重启后反复
`no channel associated ... stamp_idx 24`；作者称渲染域重置也重置 CCS、
恢复不完整会导致后续通道无法完成，XE-GPUREC v2 提供跨引擎恢复并在其
测试机器报告成功（提交 `1c792c4`）。本机观察非常相似，但我们的真实
Tiger Lake、25G83 和所用组件不同，尚未读到本轮寄存器，不能认定同一根因。
恢复路径只能尝试使 hang 后恢复，不等同消除最初的 RCS hang 或花屏；在
真实 TGL 强开跨引擎复位尚未经本机验证，不能直接部署作为修复。

## 命令抓取方案

优先在下次发生 GPU hang、macOS 仍可 SSH 时，**先全量保存**
`/Library/Logs/DiagnosticReports` 下新增 `gpuRestart` 原文件、无过滤内核
日志和完整 IORegistry 到开发机，之后本地筛选，对照 ACTHD、IPEHR、
INSTDONE、RING_HEAD/TAIL、batch 地址以及 xe-rec 属性。旧的 GA410 R5
有完整 gpuRestart 寄存器但未转储 ACTHD 处 batch，不能推定本次值相同。
Intel 的 [GPU dump 指南](https://wiki.ubuntu.com/X/InterpretingIntelGpuDump)
解释了 ring buffer、batch buffer、ACTHD 和 IPEHR 的关系；旧 GPU 寄存器
位定义须核对 Tiger Lake，Linux 的 i915 debugfs 不能直接用于 macOS 现场。
若报告只有寄存器而无真实命令字节，则须另做有界、安全、能验证页表映射
的诊断方案；用户目前没有授权新驱动/固件变动，不作临时加载或写寄存器。
历史探索中已有诊断实现与记录但路径可能失效，不凭旧摘要声称本次已抓到
batch。采样、地址翻译及额外 debug 模式都需要先审计并以实际证据验证。

用户重新启动 03 后报告黑屏；固定 macOS SSH 地址两次不可达，未验证是否
进入当前启动、是否发生 panic。需用户现场确认或回 NixOS 收证。
