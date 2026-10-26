# tgl26-usb 存储占用报告（2026-10-21）

## 结论

`/home/USER/tgl26-usb` 的 btdu **物理归属采样估计为 11.19 GiB**，约为当前文件系统已用空间的 **2.4%**；普通 `du` 报 **29.16 GiB**。差异主要来自 Btrfs 共享 extent 被多个文件路径重复计数。当前开发主机磁盘接近满载的主要项目相关热点是 `mac-for-elitebook/.local`（约 **134.70 GiB**），并非 GA42 新增了数 GiB 独立数据。

本报告仅作分析。没有删除文件。GA42 goal 保持 paused；GA40/GA41 封存树未修改。

## 方法和限制

- 工具：btdu v0.7.2，`--physical --expert --procs=4 --max-time=60s --export-seen-as --prefer='/home/USER/tgl26-usb/**' --du /`。
- 对整个 Btrfs 文件系统采样，从结果筛选目标目录；`--prefer` 控制共享 extent 的代表路径选择，不把扫描范围限制为目标目录。
- 共 2,361,019 个样本，单样本代表约 211.3 KiB。以下 btdu 数字都是估计，不是逐 extent 精确核算；很小或零采样的目录不能据此断言没有独占空间。
- 表中“物理归属”采用 btdu represented 指标：每个 extent 选一个代表路径；shared 指标会按引用路径重复累计，不能把它当作去重后的物理总量或删除可释放量。
- 普通用户读取 extent tree 实测 EPERM；后续 pkexec 提权进行元数据只读采样。提权用途应在操作前说明。
- stderr 记录采样完成、导出完成，之后 worker 打印 Broken pipe。JSON 已完整解析，当前无残留 btdu 进程；原超时 shell 未留下完整退出码，因此不声称全过程无错误。
- 原始 JSON 649,871,441 B、du 导出 64,901,707 B，合计约 0.67 GiB，属于本次分析输出，不在 tgl26-usb 内。磁盘状态会随其他进程写入变化。

## 文件系统现状

设备 `/dev/nvme1n1p2`，Btrfs，挂载 `/`；它是本地开发主机文件系统，此处目录名中的 usb 不表示实际 USB 挂载。

| 最新 df 快照 | 容量 |
| --- | ---: |
| 文件系统总量 | 475.84 GiB |
| 已用 | 465.73 GiB |
| 普通用户可用 | 1.87 GiB |
| df Use% | 100% |

采样时与后续 df 并非原子快照；Btrfs 数据/元数据 profile、已分配空闲 chunk 和保留空间也使不同口径无法简单相减。

## tgl26-usb 主要占用

| 目录或文件 | btdu 物理归属估计 |
| --- | ---: |
| GA40-NullMoth-Intel | 4.063 GiB |
| HP-Tahoe-TGL-Kmin.img | 1.258 GiB |
| HP-Tahoe-VESA-Rescue-NVRAM.img | 1.249 GiB |
| HP-Tahoe-TGL-GA1a.img（共享镜像组代表） | 1.249 GiB |
| GA41-i915-XNU | 1.115 GiB |
| GA35-Driver-Reversing | 0.625 GiB |
| GA39-Translator-Repair | 0.546 GiB |
| GA32-ISA-Lab | 0.319 GiB |
| GA38-Shader-IR-Lab | 0.272 GiB |
| GA34-Offline-Lab | 0.181 GiB |
| GA37-Engineering-Closure | 0.143 GiB |
| GA42-Intel-Darwin-Integration | 0.065 GiB（约 66.5 MiB） |
| 其他 | 约 0.17 GiB |
| **合计** | **11.192 GiB** |

目标目录 btdu exclusive 估计 11.170 GiB；shared 引用累计 28.847 GiB。前者也不是对实际删除收益的承诺，后者不是额外占用。

### GA40 构建目录

`GA40-NullMoth-Intel/build` 归属约 **3.463 GiB**，其中：

| 构建子目录 | 物理归属估计 |
| --- | ---: |
| translator-test | 2.265 GiB |
| translator-release | 0.472 GiB |
| intel-src-006 | 0.364 GiB |
| intel-mesa-debug-018 | 0.220 GiB |
| intel-mesa-compiler-007 | 0.120 GiB |

它是目标目录内最大的构建热点，但属于已封存 GA40，当前只读要求仍然有效。

### GA42 的 6.50 GiB 为什么不是新增 6.50 GiB

普通 `du` 报 GA42 **6.504 GiB**；btdu 物理归属约 **66.5 MiB**，其中 `build` 约 41.3 MiB、`anv` 约 18.6 MiB、`logs` 约 5.0 MiB。

`anv/work` 有约 17 份 Mesa 补丁验证/构建尝试工作副本。btdu shared 引用累计约 **6.100 GiB**，但 represented 仅约 **18.6 MiB**。`seenAs` 直接显示这些副本与 `GA40-NullMoth-Intel/sources/mesa` 的相同 extent 共享。因此删除验证副本不会按 du 数值释放 6 GiB；大量基础数据仍被其他路径引用。

### 12 个 IMG 为什么不能按 12 × 1.25 GiB 估算收益

根目录 12 个 IMG 的文件长度及 stat 分配块均各约 1.251 GiB，路径累计约 15.01 GiB。btdu 归属合计约 **3.76 GiB**。

`seenAs` 显示 GA1a/b、GA2a/b、GA31a/b、GA32a/b、Kmin-512、eDP-483F 共 10 个镜像共享大量 extent，多数由 GA1a 代表。Kmin 和 VESA-Rescue-NVRAM 各归属约 1.25 GiB。不能把某镜像在 represented 列近零解释成空文件，也不能据文件名直接断言它们字节完全相同。

## 真正较大的相关热点

同次 btdu 采样中，`/home/USER/lib/mac-for-elitebook/.local` 约 **134.70 GiB**，约为 tgl26-usb 的 **12 倍**：

| 相对 .local 的路径 | 物理归属估计 |
| --- | ---: |
| install-prep | 107.51 GiB |
| └ full-installer | 35.59 GiB |
| └ hp-handoff-4d86t0fx | 17.32 GiB |
| └ offline-volume-b7w1q9_e | 4.00 GiB |
| └ 多代构建/采集目录 | 多个各约 2–3.24 GiB |
| recovery-vm | 20.18 GiB |
| recovery-repair | 6.79 GiB |

install-prep 子项包含在 107.51 GiB 内，不能重复加总。这里保存安装源、镜像、历史采集和备份，尚未逐文件核实保留关系；本报告不认定可删除。

同文件系统其他较大归属还有 `/nix/store` 约 78.45 GiB、`/tmp` 约 29.00 GiB，以及 swapfile 约 16.04 GiB。它们是全盘背景，不属于 tgl26-usb；Nix 引用闭包、临时目录活跃状态和 swap 用途未在本轮审计。

## 下一步建议

如要释放明显空间，优先对 `.local/install-prep` 和 `.local/recovery-vm` 做文件级保留/重复/依赖清单，核对原始证据、恢复备份和安装源后再决定处理范围。当前 GA42 重复工作副本的独占占用很小，清它们收益有限；GA40/GA41 仍保持封存只读。

## 证据

- 私有持久摘要与原始命令输出：`.local/storage-analysis/btdu-tgl26-20261021/`。
- `summary.json` SHA256：`3a8c7e9dd1881e9239b4d5f59f954fd9a335a4a70a16e22f79c68e6222c20381`。
- 原始完整采样：`/tmp/opencode/btdu-tgl26-20261021/physical-pkexec.json`，SHA256 `142ebae8c1a5cb485a60dfe82e229c6999aff13b1da9eb4f8e29f4e20dffabd4`。
- 原始 du 导出已保留在上述私有目录，SHA256 `7d309a08045ebc79f4b836565333b3d919d1c08c1abec87e9e3276435c601b17`。
- 完整 JSON 目前仍在临时目录；迁移/清理临时目录前须私下转移并核验 hash，仓库本身不足以保存完整原始采样。
- 本轮没有源/结果 IMG 变更，无媒体交付或目标机操作。
