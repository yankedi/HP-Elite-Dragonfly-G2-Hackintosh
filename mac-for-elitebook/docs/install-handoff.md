# 实机安装与运行记录（历史）

> **当前状态（2026-10-27）：** Tahoe 26.6.2 / 25G83 已安装并进入桌面。四次启用实验性 TGL 图形栈的启动发生 panic；一次软件显示对照约 62 分 35 秒无用户报告冻结。确切组件和根因未证明。当前摘要见[公开续接入口](continuation.md)与[公开事件索引](../manifests/experiment-history.json)。
>
> 下文保留 Recovery、安装准备和早期运行记录；“当前/最新/下一步”等文字均指原记录当时状态。原始 `.local/` 材料、私有身份和编排历史未复制到公开副本，缺失的私有证据不视为已验证。

## Tahoe 安装与后续状态

Tahoe 26.6.2 / 25G83 已到达桌面。功能、图形与稳定性结论以当前公开状态为准，不重放下文早期待办。

## 历史 Recovery 与安装准备记录

**离线源核验（历史）：**目标26.6.2／25G83，HFS SHA-256=`75f6cab00020ad6c2124579bc4641ca0f9029ad0ff23cf3d8112d01211523c92`；Recovery端完整哈希一致，HFS只读挂载。`startosinstall`曾从本地完整App启动（无`--eraseinstall`，因为APFS卷刚重建）；随后首启完成，当前实测build为25G83。
**此前未完成的26.7.1阶段已清理。** GPT恢复后原槽位和p7 GUID已精确恢复；p7现为Tahoe APFS。Setup Assistant地区页照片是历史节点；后续用户完成首设，代理现在已通过SSH核对实际build 25G83。
**参数边界：**Recovery侧先前尝试`startosinstall --eraseinstall --volume`被26.6.2 App拒绝（两参数互斥），没有写入；后续已通过APFS容器重建建立空Tahoe卷。GPT短暂意外变化已按批准备份恢复，主／备表全量回读通过。
内置OpenCore/systemd-boot菜单已获准部署并回读验证，旧Debian引导备份后清理。用户随后现场启动进入p7上的Tahoe并完成安装；SSH侧确认物理store为disk0s7，菜单中的精确启动选择过程未由代理另行观察。精确变更/备份见[内置引导](internal-boot.md)。
USB已回开发机；RHUB实测原件已保存，SHA `77d39f2f6b218ee0988ea5bab3e466f7af7dbe8f1220f6360a56b8fda8562644`，52原文件不变，仅新增3个Recovery booter日志；未修改USB。
最新证据 `.local/install-prep/hp-postreboot-20261017/report.json`；GPT 只读校验通过。此前 macOS 分区工具丢弃 WinRE GPT 条目后已恢复其原 GUID／范围并双校验；实际 Windows 恢复功能仍待后续 `reagentc /info`。

最新RHUB版实测：2026-10-16 19:02:05 新启动；dmesg从0.000183秒起完整保存，
详见[最新运行态证据](../manifests/hp-rhub-runtime-check.json)。
下文DBGENH交付/启动步骤已经执行，不能作为尚未完成的队列重放。

该轮执行流程：`ISO/linux/HP-Tahoe-VESA-XHCI-RHUB.img → HPRECOVERY (dmg)` 已启动成功。
实测 IMG 尚未回收（含新 booter 日志）；所有旧候选、离线数据、Ventoy文件和分区保持。
见[运行证据](../manifests/hp-rhub-runtime-check.json)与[交付证据](../manifests/hp-rhub-retry-check.json)。
下一步：U盘回收后保存实测 IMG/新日志，然后推进安装准备。

2026-10-17 新交付：`ISO/linux/HP-Tahoe-VESA-XHCI.img` → `HPRECOVERY (dmg)`，
精确 a0ed → AppleUSBXHCISPT 的独立对照，SHA-256
`e55eb607858afda49cda89fe8a9f023143ff49ce20a937424cd9ba704a66ae72`。
已保留 WiFi 实测原件和新日志，交付回读、安全卸载完成；**后续已实机启动，SPT类生效但USB仍未恢复**。
Wi-Fi/SSH/SFTP继续可用，第二份完整运行态归档已保存，见
[`hp-xhci-runtime-check.json`](../manifests/hp-xhci-runtime-check.json)。
后续Log版已实测：启动参数存在，但缓冲仍128KiB，USB未恢复；完整观察和轮转日志已保存。
源码审阅纠正：msgbuf参数解析位于`CONFIG_XNUPOST`条件中，之前漏看了该条件。
下一stock DebugEnhancer诊断候选已交付原Lexar、完整回读并安全卸载，**且已实机启动（10MiB缓冲生效，USB当时仍无）**。
后续 PCH-only RHUB 对照已启动成功并恢复 USB；Log实测原IMG/50文件已先保存，所有旧候选、离线资源和Ventoy文件保留；以续接文档顶部最新状态为准。
详情见[输入/USB 对照](input-recovery.md)与[续接入口](continuation.md)。

后续新增：通过已有 SSH reverse tunnel 提供只读网络 HFS，真实 Recovery 已附加安装 app 与
内部 SharedSupport，并完整流读 18,356,020,461-byte 系统载荷；SHA-256 与 Apple catalog 一致。
资源访问已可绕过 USB，见[网络附加实证](offline-installer-inputs.md)。
`startosinstall --usage` 退出 0，但整个 app 原生 codesign 报 obsolete resource envelope/custom omit rules，
原始入口与规则均匹配已验证包；这不等于正式安装接受性通过。两层实验映像及临时服务已清理，当前未安装。

本轮先读 [Recovery 网络交接](recovery-network.md)：**WiFi IMG** → `HPRECOVERY (dmg)` 已完成。
加入网络并执行 `sh /Volumes/*/hpdiag/s` 后已实际连接；后续无需用户手输采集命令。
原同名 `HP-Tahoe-VESA-Recovery.img` 保留刚实测的所有权版及日志。下文早期同名候选说明作为历史。

上轮交付的 `/ISO/linux/HP-Tahoe-VESA-Recovery.img` 仅在输入版基础上开启
`UEFI.Quirks.ReleaseUsbOwnership`，SHA-256：
`0610299a23fff511149ddb84f1d8da15d63f25b66aeb00e3bceb55118010f490`。
其他配置字段和 42 个 IMG 文件逐字节保持，同版 ocvalidate 退出 0。
刚实测的输入版连同新日志保存为 `HP-Tahoe-VESA-I2C-Baseline.img`；
更早能进入 Recovery 但无指针的原版仍保留为 `HP-Tahoe-VESA-MMIO-Baseline.img`。
离线 HFS+ 数据映像、Ventoy 配置和分区保持，USB 已安全卸载。
上轮交付收据：`.local/install-prep/hp-usb-ownership-q5mk863d/usb-delivery.json`；
最新收据为 `.local/install-prep/hp-recovery-network-2lk4c8rz/usb-delivery.json`。
输入来源、原生 KC 注入验证和下一轮观察见[输入适配](input-recovery.md)。

## 最新实机结果：Recovery GUI 已进入

2026-10-16 用户提供的四张实机照片中，一张显示完整 Recovery 工具窗口
（Time Machine、Reinstall macOS Tahoe、Web Browser、Disk Utility），另两张显示
Apple 的鼠标/键盘连接提示。此次测试已越过之前的 booter 内存分配失败，
不再把 Recovery 启动本身记为待验证。随后 USB 回到开发机，新 booter 日志已提取：
有效 `slide=0`、KC 读取 `Ok(0)` 后到达 `LOG:EXITBS:START`，旧 `MM.AKM / STOP 0x16`
不再出现。尚未取得进入 Recovery 后的 IORegistry 日志。

- 内屏能显示 Recovery UI；这证明当前显示输出，不证明 Xe/Metal 加速。
- 用户报告触控板、触屏和外接 USB 鼠标都无响应；具体接收器及 HP 接口路径尚未确认。
- 空格可能有响应属于用户的初步观察，文字输入、方向键和组合键仍待确认。
- 此次进入 Recovery 的基线包含 VoodooPS2Controller 与键盘插件，没有 VoodooI2C；
  Synaptics 触控板和 Wacom 触屏在两条 I2C 总线上，不能靠 PS/2 键盘驱动带动。
- 用户说明外接鼠标就是开发机使用的鼠标。开发机实读为 USB 输入路径，含
  ATK `373b:128e` 和键盘 dongle 的 Mouse 接口；具体哪一接口在 HP 被测试尚未明确。
  外接 USB 的 XHCI/端口/HID 路径仍需运行态核对，不能仅凭设置提示认定 USB 控制器损坏。

现场优先尝试方向键、Tab、回车确认键盘导航，再用 Control-F2
（功能键模式需要时加 Fn）选择菜单栏，通过方向键进入 Utilities → Terminal。
如果可输入，先保存 `ioreg -p IOUSB -w0` 与 `diskutil list` 的观察结果。
当前没有 Recovery 远控通道；输入故障的进一步判断依赖这一步实机观察。

## 首次实机失败与单项重试

用户现场已从原有 Ventoy 启动 IMG，OpenCore 菜单识别了 `HPRECOVERY (dmg)`。
随后出现禁止符号并返回 OpenCore。镜像内的日志只读提取到私有证据目录：

1. `EB.LD.LKFS` 和 `EB.LD.LKC` 均返回 `Ok(0)`；KC 读取耗时约 76 秒。
2. 后续出现 `EB.MM.AKM ... EB.MM.MKP`、`EB.BST.FBS|RT!`，记录申请
   `0x110b2000`（285,941,760）字节，随后 `STOP 0x16`、`StartImage failed - Aborted`。
3. 有效参数包含自动选择的 `slide=91`。按失败后 memory map 和此申请大小推算，
   slide 91 的候选区间与两段 runtime data 重叠；slide 0 的同等长度区间全部位于
   conventional memory。失败后的图不能证明更早阶段的内存布局，也不能证明单项重试必然成功。
4. `OS.dmg.root_hash` 缺失也见于此前能进入 XNU 的对照日志，因此没有单凭该行
   改动 SIP 或 Secure Boot 策略。首轮主要待验证假设是低地址内存分配/slide；
   第二轮结果及后续 runtime MMIO 证据见下节。

已生成**仅追加 `slide=0`** 的重试镜像：其余 plist 字段、私有身份、其他 EFI 文件保持一致，
同版本 OpenCore 1.0.8 `ocvalidate` 退出 0。该镜像已写回 U 盘并回读校验，
**实机重试确认参数生效，但仍在同一处失败**，详见下节。
原始镜像含实机日志的副本已在开发机保留，不需要靠重复启动来取得本次错误。

```sh
python3 scripts/analyze_hp_boot_memory.py \
  --log .local/install-prep/hp-boot-failure-<capture>/opencore.txt \
  --output .local/install-prep/hp-boot-failure-<capture>/memory-analysis.json
python3 scripts/prepare_hp_slide_retry.py --source /path/to/HP-Tahoe-VESA-Recovery.img
```

OpenCore 固定源码
[`CustomSlide.c`](https://github.com/acidanthera/OpenCorePkg/blob/6fe4d15cb66596d99d8cfedce69d8fc6dad71886/Library/OcAfterBootCompatLib/CustomSlide.c)
定义 slide 范围计算和可用性分析；
[`BootCompatInternal.h`](https://github.com/acidanthera/OpenCorePkg/blob/6fe4d15cb66596d99d8cfedce69d8fc6dad71886/Library/OcAfterBootCompatLib/BootCompatInternal.h)
当前以 200MiB 加 runtime pages 估算内核区域。日志所见实际申请更大，但不能据此断言
上游算法缺陷；扫描时机、后续分配和 Ventoy 链中的内存占用仍是未分离因素。

## `slide=0` 实测失败与 runtime MMIO 单项对照

第二份实机日志 `opencore-2026-10-16-092138.txt` 确认：

- `MBA:OUT` 包含 `slide=0`；没有继续使用旧参数或旧镜像。
- KC 读取约 76 秒后返回 `Ok(0)`，仍在相同的 RT 申请处失败，申请量仍为
  `0x110b2000`（285,941,760 bytes），随后 `STOP 0x16`。
- 失败后低地址图的候选区间全为 conventional，并未使启动通过。因此之前的
  slide/低地址重叠分析仅是试验假设，不能据此认定已找出或修复根因。

进一步将两份实机日志和 NixOS 下的 EFI runtime map 做了只读对照：

| 量 | bytes |
| --- | ---: |
| booter 的 RT 申请 | 285,941,760 |
| 两段 MMIO 合计：`0xc0000000` / `0xff000000` | 285,212,672（272MiB） |
| booter runtime code/data 合计 | 684,032 |
| 剩余差值 | 45,056（44KiB） |

Linux 的 `/sys/firmware/efi/runtime-map` 确认上述两段 MMIO 的属性均为
`0x8000000000000001`，包含 `EFI_MEMORY_RUNTIME`。它来自另一次 Linux 启动，
不是 booter 申请前的同一时刻快照，但地址和长度与失败图对应。

固定 OpenCore 1.0.8 文档说明 `DevirtualiseMmio` 可移除 MMIO runtime 属性、
减少 booter 所需的虚拟内存，部分平台否则会在 loader 阶段分配失败；固定源码
[`ServiceOverrides.c`](https://github.com/acidanthera/OpenCorePkg/blob/6fe4d15cb66596d99d8cfedce69d8fc6dad71886/Library/OcAfterBootCompatLib/ServiceOverrides.c)
仅处理具有 runtime 属性的 `EfiMemoryMappedIO` 描述符。

当时下一版**保留 `slide=0`，仅把 `Booter/Quirks/DevirtualiseMmio` 从 false 改为 true**。
20 个其他 EFI 文件及私有身份保持，匹配版本 `ocvalidate` 退出 0。
此项依据比继续换 slide 更直接；随后已实测进入 Recovery，见本文顶部。

当时下一次日志的判别点是是否越过原 `EB.BST.FBS|RT! / STOP 0x16`，
以及是否出现 `LOG:EXITBS:START` 或 XNU 输出。如果仍在 RT 分配失败，
比较申请量是否仍为 `0x110b2000`；单纯减去两段 MMIO 得到 `0xb2000`
只是便于核对的大小推算，不保证 Apple booter 必须采用该数值。

该版交付时已写回同一路径并独立回读 SHA-256 通过：
`ffe4093a37bb54f19dc522e5817f5934c35717dd21c19baae61ddc8bc8371e67`。
交付收据为 `.local/install-prep/usb-mmio-delivery-8stutzqv/report.json`，
Ventoy 配置与分区布局核对保持，未写 USB EFI 文件，写回后已安全卸载。

复现入口：`scripts/analyze_hp_runtime_map.py`、`scripts/prepare_hp_mmio_retry.py`。
原始日志、实测 IMG 与 Linux runtime map 保存在
`.local/install-prep/hp-slide0-failure-20261016T092510Z/`；脱敏证据索引见
`manifests/hp-booter-runtime-check.json`。

## 越过 booter 后的 USB、磁盘与键盘预检

`scripts/audit_hp_recovery_paths.py` 已对**同一 25G83 Recovery 的实际 KC**、
私有候选的启用项与 HP 只读采集做静态交叉核对：

- 两个 XHCI 控制器 `8086:9a13` / `8086:a0ed` 的实读 PCI class 都是 `0x0c0330`。
  KC 中的通用 `AppleUSBXHCIPCI` personality 按 `0x0c033000` 匹配；
  缺少 Tiger Lake 专用 ID 条目本身不等于没有任何匹配驱动。
- Micron `1344:5404` 的实读 class 为 `0x010802`，匹配 `IONVMeFamily` 的
  `GenericNVMeSSD` class 条件 `0x01080200&0xffffff00`。这不是该 SSD 的 I/O 成功证明。
- HP `PS2K` 的 `_CID=PNP0303` 在当前 VoodooPS2Controller 2.3.7 的匹配列表中；
  控制器与键盘插件已启用，加载顺序正确。设备块没有按 OS 隐藏键盘的 `_STA` 方法。
- Recovery 内含 `hdiutil`、`diskutil`、`PlistBuddy`、exFAT kext 元数据，
  KC 中包含 HFS 与 USB Mass Storage bundle。

以上只核对声明匹配与输入完整性，不把它当作驱动已绑定。实际端口映射、USB 文件读取、
NVMe 访问和键盘按键仍需进入 Recovery 观察。证据索引见
`manifests/hp-recovery-path-check.json`。新增的只读观察项包括 XHCI、NVMe、PS/2、
挂载表和附加映像，便于区分“设备没有驱动”与“驱动存在但实际路径失败”。

## 完整安装包核验进展

Apple 官方 `InstallAssistant.pkg` 已完整下载，**18,384,624,402 bytes**，SHA-256：

```text
376923d7494cfa32b69f383bcfdce46aeedb609fe6a242ea12a6e015bfb77ba4
```

- XAR TOC 的 RSA 签名、独立固定 Apple Root CA 的证书链以及所有五个成员的
  archived/extracted checksum 均通过；篡改签名的负对照被拒绝。
- 包同时是合法 UDIF。内部 Shared Support 的 MobileAsset catalog 确认
  **26.6.2 / 25G83**；包含当前 `MacBookPro16,2` 对应 board 的记录。
- 18,356,020,461-byte 主安装 ZIP 已独立流式读出，其 SHA-256 与内部 catalog 一致：
  `0b44a71bd6a721f5ddfb46f8dba39b09ee46bf9678a1c3100b978f512acfc07c`。
- 记录中的 `SUDocumentationID` 为 `PreRelease`，不把第三方索引中的渠道描述当作包内事实。
- 已从通过验签的 Payload 重建完整 `.app`。包的 postinstall 本身会把**整个混合
  XAR/UDIF 包**链接为 `Contents/SharedSupport/SharedSupport.dmg`；本地按相同布局重建。
  没有执行包脚本或运行 macOS 安装器。

复现入口：`scripts/verify_install_assistant.py`、`scripts/inspect_installer_support.py`、
`scripts/reconstruct_installer_app.py`。完整组装说明见[离线安装输入](offline-installer-inputs.md)，
固定来源与摘要见 `manifests/offline-installer-inputs.json`。
完整包或重建 app 不等于 Apple `createinstallmedia` 已制作成功，也不等于实机安装已验证。

已生成并独立回读通过的 **19,922,944,000-byte HFS+ 离线 app 数据映像**，
包含完整 `Install macOS Tahoe.app` 及 SharedSupport。只读 fsck 退出 0；
695 个 app 普通文件、26 个链接与执行权限通过比对，18,384,624,402-byte 完整包
从新映像内再次读出并核对摘要一致。它是 Recovery 后续挂载的数据输入，不是启动盘。

离线准备阶段的本地交接集：`.local/install-prep/hp-handoff-cx_b7lpn/`，包含：

| 文件 | 用途 | 当前状态 |
| --- | --- | --- |
| `HP-Tahoe-VESA-Recovery.img` | 历史 `slide=0` 首启重试 | 已实测仍失败；USB 中已被下一版替换 |
| `Tahoe-26.6.2-Offline-App.hfs` | 完整离线安装 app 数据卷 | 本地结构/字节/权限检查通过；HP 挂载与安装器执行未测 |
| `collect_macos_handoff.sh` / `SHA256SUMS` | Recovery 观察和交付校验 | 已打包；观察脚本尚未在 HP Recovery 运行 |

用户已明确要求移除禁止读写挂载规则，`AGENTS.md` 已更新。代理已自行挂载 Lexar、
替换测试 IMG、同步并回读校验，随后安全卸载。交付记录：
`.local/install-prep/usb-slide0-delivery-mnaa1d4q/report.json`。
该次交付的 SHA-256 为 `e9777e26023e65d273a4e0dd20cb29a68a8c53c2255eee2ab6af52d3f6492261`；
Ventoy 配置、EFI 文件和分区布局保持。该时点 19.9GB 离线数据映像尚未复制。
之后用户已实测此版仍失败；当时 USB 替换为上文记录的 `DevirtualiseMmio=true` 单项重试版，
本地候选在 `.local/install-prep/hp-mmio-wzni_k8q/`。

### 离线完整交付：数据已上 USB

代理已把 **19,922,944,000-byte** 离线 app 数据映像作为普通文件复制到
`/ISO/linux/Tahoe-26.6.2-Offline-App.hfs`，同步后完整回读 SHA-256 与本地已验证产物一致：
`75f6cab00020ad6c2124579bc4641ca0f9029ad0ff23cf3d8112d01211523c92`。

该次交付中 MMIO 单项重试 IMG 摘要保持 `ffe4093a…371e67`，Ventoy 配置和分区布局核对保持，
211 个原有其他文件的大小/mtime 清单保持；随后已安全卸载。交付证据：
`.local/install-prep/usb-offline-delivery-38vmry8y/report.json`。
实际目录名是 `ISO`；exFAT 不区分大小写，旧记录的 `/iso/linux` 指向同一目录。

同目录还新增当前版 `collect_macos_handoff.sh`、`attach_hp_offline_installer.sh`、
`HP-TAHOE-HANDOFF.txt` 与 `HP-TAHOE-SHA256SUMS.txt`。观察脚本新增 XHCI/NVMe/PS2
及挂载状态；附加助手只读挂载数据映像，详见[Recovery 接入](offline-installer-inputs.md#recovery-接入边界)。
两个助手均只完成 shell 语法检查，尚未在 HP Recovery 运行。

当时本地交接集为 `.local/install-prep/hp-handoff-wae7ve17/`，
内容为当时的 MMIO 重试、离线数据及两个助手。之前的 `hp-handoff-cx_b7lpn`
保留为历史 `slide=0` 交接集。

本次交付后用户已用照片确认 MMIO 重试进入 Recovery；当前阻塞转为输入设备，见本文顶部。
离线资源已经在 USB，尚未验证 Recovery 能读取物理 exFAT 卷。

## 最新实机分区核对（2026-10-16）

用户已自行完成分区调整，并回到 NixOS。代理经现有 SSH 进行了只读查询：

- 原 p7 已删除，p6 与 p8 之间留下 **107.94140625GiB 连续未分配空间**。
- p5 起始位置保留，现为 **128.2509765625GiB**；实际缩小 **56.548828125GiB**，
  与下文先前的 40GiB 几何计划不同。无需为了凑原计划再调整。
- p6 已左移且紧邻 p5；其容量、分区 GUID 和类型与调整前一致。
- p1、p2、p3、p4、p8 的 GPT 分区记录与调整前一致。
- `sfdisk --verify` 退出 0，报告无错误；Btrfs 报告设备大小与新 p5 一致、slack=0，
  五项设备错误计数均为 0。这不是全盘数据校验，也未校验 p6 的文件内容。
- 原始快照和逐项比较留在忽略的 `.local/install-prep/post-partition-*/`。

当前安装候选区域起始 **373840MiB**，结束 **484372MiB**，容量 **110532MiB**。
它尚未创建为 APFS 分区；进入 Recovery 后应按位置与容量重新对应。

## 用户接手实机首启测试

用户要求停止 VM；本地测试 VM 已停止，后续由用户现场测试。
已生成私有 `HP-Tahoe-VESA-Recovery.img`（1,343,225,856 bytes），包含：

- 独立 VESA EFI、私有 SMBIOS 身份及 HP EC/USBX 候选；
- Apple 签名通过的 Recovery，92 个分块重新核验通过；
- 介质内 EFI 和 Recovery 已独立回读并逐字节摘要比对，同版 OpenCore 1.0.8
  `ocvalidate` 对回读配置退出 0。

这是**首启测试镜像，不是完整离线安装盘**。生成入口：

```sh
python3 scripts/build_install_candidate.py
python3 scripts/build_first_boot_image.py --candidate .local/install-prep/hp-vesa-<run>
```

初版 IMG 已**作为普通文件**新增到现有 Ventoy 数据区，并完成一次用户现场启动。
它位于 `/iso/linux/HP-Tahoe-VESA-Recovery.img`；该路径随后依次更新为 `slide=0`、
MMIO 修正版与当前 I2C 输入候选，各次交付均有回读摘要记录。
不用镜像写盘工具写入整只 USB，不替换现有 `EFI`，不改 USB 分区表。
若进入 OpenCore，选择 macOS Recovery 条目；记录最后画面，不选择 Reset NVRAM。
HP 后续已实测进入 Recovery 并显示工具界面；当前待验证输入候选、物理 USB 和磁盘访问。
此镜像含私有身份，不公开上传。

停止 VM 前的最小协议探针已验证：新建的 Ventoy 1.1.18 **FAT32 虚拟盘**可以启动
分区化 IMG，IMG 对 EFI 程序暴露可用文件系统和 Block I/O，且能读取第二个标记文件。
这只排除了该测试路径的部分协议疑虑；现有 Lexar 是 **exFAT**，也尚未确认其 Ventoy
版本。该虚拟探针本身不能证明实机 Recovery 或内核启动成功；后续独立实机证据见本文顶部。

## 本次用户已确认的安排

- 用户现在可以在机器旁操作，先从现有 NixOS 安装介质启动分区工具。
- macOS 预定覆盖原 `nvme0n1p7` 上的 Debian 13，不覆盖 NixOS 或 Windows。
- 先从 NixOS 的 p5 划出 **40GiB（40960MiB）**，用于扩大原 Debian 所在区域。
- 只有现有 Lexar/Ventoy；继续保留其文件、EFI 和分区表。
- 已知无线设备是 AX201 `8086:a0f0`、蓝牙 `8087:0026`。没有另行确认的有线网卡；
  不能把内置蓝牙或 Linux 的 Wi-Fi 联网当作 Recovery 网络已可用。
- 本次准备不授权代理远程执行重启、改固件、分区写入或安装。

## 分区布局与空间转移

2026-10-16 的最后一次在线只读快照核对了 GPT、挂载点与固件状态。
原始含分区 GUID 的快照保存在 `.local/install-prep/`，不提交公开仓库。

**按物理位置**的顺序为：p1 → p2 → p3 → **p5 → p6 → p7 → p8** → p4。
GPT 分区编号并不是磁盘上的物理顺序。

| 分区 | 快照时用途 | 大小约 GiB | 计划 |
| --- | --- | --- | --- |
| p1 | 已挂载 `/boot` 的 EFI | 0.293 | 保留 |
| p2 / p3 / p4 | Microsoft reserved / Windows / Windows recovery | — | 保留 |
| p5 | 正在运行的 NixOS，btrfs | 184.800 | 在 Live 环境先缩文件系统，再缩分区，左边界不动；目标约 144.800GiB |
| p6 | 独立 FAT EFI | 0.954 | 保留内容、容量与身份，几何方案为左移 40GiB |
| p7 | Debian，ext4 | 51.393 | 用户已选择覆盖 Debian；最终预留约 91.393GiB 给 macOS |
| p8 | swap | 2.854 | 本次空间方案不涉及它 |

p5 与 p7 **不是相邻分区**。只缩 p5 会得到 p6 左侧的空闲空间，不能直接扩 p7。
在放弃 Debian 的前提下，几何方案是缩 p5、左移 p6、删除原 p7，随后把 p6 后的
连续空闲区域留给 macOS；不需要先搬动约 51GiB 的 Debian 文件系统再抹掉它。

以上是**先前几何方案**，实际完成结果见本文顶部。用户调整后 NixOS 已恢复在线，
GPT 与 Btrfs 容量检查通过；这些旧几何数字不应被再次作为待执行分区队列。

纯本地计算入口，不执行磁盘命令：

```sh
python3 scripts/plan_install_space.py \
  --inventory .local/install-prep/<capture>/partition-table.json \
  --transfer-gib 40
```

macOS 中磁盘编号可能不同，删除再创建也可能改变分区编号。不能仅把 Linux 的
`nvme0n1p7` 机械替换为 `disk0s7` 后抹盘。须用大小、起始偏移和邻接分区重新对应。

## HP 固件设置：Secure Boot

最初只读采集读到 `Secure Boot=Enable`、`Fast Boot=Enable`、`USB Storage Boot=Enable`。
现场测试后没有重新读取或替用户修改固件配置。
现有 OpenCore EFI 没有按这台机器信任的 UEFI 密钥签名，因此首次测试采用
**在固件中关闭 UEFI Secure Boot** 的路线。

- HP 启动时通常以 Esc 进入启动菜单、F10 进入 BIOS Setup、F9 选择一次性启动设备；
  具体选项按本机界面确认。使用 UEFI，不为此切换 Legacy/CSM。
- 只切换 Secure Boot 开关；不要选择清空 Secure Boot keys、清 TPM 或恢复全部 BIOS 默认值。
- 不必关闭 TPM、VT-x 或 VT-d；当前 VMD 已关闭，不需要为此次准备再更改存储控制器模式。
- 固件 Fast Boot 与 Windows 的 Fast Startup 不同。若 USB 枚举不完整再核对前者。
- OpenCore 的 `Misc/Security/SecureBootModel=Disabled` 是 **Apple Secure Boot 模拟策略**，
  不会替你关闭 HP 固件 Secure Boot，也不表示关闭 SIP。原型保留 SIP、只允许 signed DMG。
- 若 Windows 的系统盘启用了 BitLocker/设备加密，改变 Secure Boot/启动测量可能要求恢复密钥；
  应在改变前确认能取得该盘的恢复密钥。现有 NTFS 检测本身不能判断加密状态。

依据：[固定 OpenCore 1.0.8 配置文档](https://github.com/acidanthera/OpenCorePkg/blob/6fe4d15cb66596d99d8cfedce69d8fc6dad71886/Docs/Configuration.tex)
的 UEFI Secure Boot、Apple Secure Boot 与 `LauncherOption` 章节。
本次没有注册新证书、删除已有 keys 或修改任何固件变量。

## 介质与图形：还剩哪些实际准备

完整签名验证的 **26.6.2 / 25G83 BaseSystem** 已取得，见
[Recovery/kext 验证](recovery-kext-validation.md)。它是恢复环境，**不是离线完整安装器**。
它能在 VM 执行系统命令，不代表在没有网络的 HP 上能完成安装。

当前工作顺序：

1. 分区核对已完成；候选空闲区已建成 APFS 卷 Tahoe，macOS 安装已开始准备（2026-10-16 晚；事件级原始编排历史未复制到公开副本）。
2. 完整安装输入已下载、验签并核实内部 build；离线 app 数据映像已组装并独立回读。
   不能只改名为 ISO，也不能把 InstallAssistant.pkg 本身当作已经制作好的启动盘。
3. 保留 Ventoy 的 IMG 路线已在实机进入 Recovery；单独 `slide=0` 实测未解决，
   开启 `DevirtualiseMmio` 后越过 RT 申请失败阶段。I2C 输入候选已交付，待实机复测。
4. HP 的私有身份、EC/USBX 与独立 **VESA 首启候选**已生成，同版 ocvalidate 和文件
   校验通过；实际 USB 映射仍不完整。现有 `build/vesa-prototype` 保持空身份，不能直接部署。
5. Recovery 显示已确认；下一轮记录各路输入、物理 USB 和磁盘，再决定安装。
   首轮 VESA、framebuffer-only 和 Xe 实验分开，不用安装过程同时试验加速补丁。

## 重启后如何交接

此前远程连接是 NixOS 内的 SSH；进入固件、Live ISO 或 macOS 后无法沿用。
尚未建立 Recovery 的联网远控或自动回传链路。现场依靠用户操作、截图和保留日志。
另一台能继续对话的设备可用于发送启动画面/错误，不能把“人在机器旁”当作代理已能控制 BIOS。

如果进入 macOS/Recovery 的 Terminal，可以手动执行：

```sh
sh /path/to/collect_macos_handoff.sh --save-usb
```

对应脚本是 [`scripts/collect_macos_handoff.sh`](../scripts/collect_macos_handoff.sh)，
当前版已放在 USB 的 `ISO/linux/`；请按现场实际挂载路径运行 `collect_macos_handoff.sh`。输入候选 IMG 内也已更新为此版；MMIO 基线保留旧版。
不依赖 Python，默认在 `/tmp` 新建私有观察目录和 tar.gz。增加 `--save-usb` 后会自动核对
已挂载的外置物理 exFAT 交付卷，在其唯一新目录保存并逐字节比较归档。
自动摘要、命令限时、磁盘枚举及更多输入/USB/网络/音频/电源观察见[自动观察脚本](recovery-observer.md)。
不抹盘、不挂载卷、不运行安装器、不改 NVRAM、不启用 SSH。
`/tmp` 日志重启会丢失，用户需在离开前复制到明确选择的保存位置。

完整 raw 日志可能含磁盘标识或机器身份，仅放 `.local/`，不要公开提交。
这些查询不能替代内屏功能测试或 Metal 实际渲染/计算测试。
脚本当前仅做 shell 语法检查，尚未在 HP Recovery 运行。
