# Recovery 已启动后的输入适配

## 已安装 Tahoe 后续：触控板未送达 HID 事件（2026-10-17）

用户报告当前内置触控板不能移动指针。新启动的 macOS 26.6.2/25G83 中，`VoodooI2C` PCILake 控制器、`TPD0`及`VoodooI2CPrecisionTouchpadHIDEventDriver`均为 registered/active；Synaptics HID `06cb:cd74`也在 `hidutil list` 中。但`hidutil dump services`中的触控板 service counter 为`EventCount=0`、`LastEventTimestamp=0`、`NotificationCount=0`。同一快照触屏 service 的`EventCount=119`，当前触控板因而没有把报告送到HID事件服务；驱动已绑定并不等于物理输入正常。最近10分钟没有匹配到I2C/VoodooI2C/TPD0/TPL0 kernel日志。`USBMouseStopsTrackpad=0`；两处查询均未找到`TrackpadEnabled`偏好键，无法据此判断偏好状态。

用户已按要求连续滑动约3秒；随后 HID 计数仍为0（见`.local/install-prep/hp-offline-install-20261017/tahoe-touchpad-after-user-swipe-20261017T112042Z/report.json`）。因此该次物理动作没有到达触控板 HID 事件服务。用户报告外接USB鼠标可移动；物理重启已由kern.boottime19:27:08证实，代理未重启。重启后触控板和触屏计数都回到0基线；未做重启后物理触摸测试，因此功能状态仍待用户实测。尚未修改驱动、EFI、设置或系统卷。

## 最新：RHUB 版实机成功，USB 完全恢复（含外接鼠标）

PCH `XHCI@140000.RHUB` 在 Darwin 下隐藏后，驱动自行建立 12 USB2 + 3 USB3 端口（macOS 报 15 端口上限、余 1 未建）。
Lexar `21c4:0809`（HS06）挂载为可移动 exFAT 卷，目录/4MiB 读取与校验单读取实测通过；
HP 摄像头 `0408:5349`（HS02）、Intel 蓝牙 `8087:0026`（HS10）、Synaptics `06cb:00f0`（HS07）均枚举；
**外接 USB 鼠标 ATK A9 Mini+ `373b:128e`（HS04）HID 鼠标可用：实测 47,287 次输入报告，用户确认鼠标工作**（会话内报告）。
TXHC 对照仍为通用类、0 端口、电源 0。触控板仍 Polling、触屏仍 APIC；Wi-Fi/SSH 保持。
dmesg 从 0.000183 秒起已保存（802,023 字节）；证据 `.local/install-prep/hp-rhub-boot-kefc4lbr/`，
索引 [`hp-rhub-runtime-check.json`](../manifests/hp-rhub-runtime-check.json)。

## 前轮：DebugEnhancer实测扩大到10MiB，早期日志已取回

`kern.msgbuf=10485760`、插件1.1.1已加载，dmesg从0.000175秒起；USB依然无设备。
实际早期日志证实`XHCI.RHUB.HS09`缺失导致OEM `HP_XHC_P`表加载失败，另有EC `_REG`错误。
两个XHCI的`createPorts`均打印6种unsupported speed mantissa/exponent2。
实际KC反汇编确认该打印分支继续PSI循环，不能直接把这条提示定性为USB失败根因。
stock路由组报错与缓冲分配成功并存。完整141文件归档和37个轮转日志文件保存；
PCH-only RHUB回退对照现已交付、只读重挂完整回读并安全卸载，尚未实机启动。
该表仅让`_SB.PC00.XHCI.RHUB._STA`在Darwin返回0，测试驱动回退建端口；TXHC保持作对照。
原50文件/其余配置/kext保持；iasl0、OC1.0.8 ocvalidate0、本地AML命名空间fixture返回15/0/15。
本地ACPICA退出另有4个缓存分配诊断，原log保留；不是实机结果。
实际后续ACPI树已有HS09，不能按早期缺名推断物理端口缺失；新表也不直接修复HP_XHC_P加载报错。
DBGENH实测原IMG/52文件已先保存，51旧文件不变，新增一份EXITBS日志。
本轮3新文件回读通过，232旧文件元数据/七个旧IMG/995个EFI文件摘要、配置与几何保持。
下一次选`HP-Tahoe-VESA-XHCI-RHUB.img → HPRECOVERY (dmg)`，原Wi-Fi/SSH入口不变；
见[`hp-rhub-retry-check.json`](../manifests/hp-rhub-retry-check.json)。
见[`hp-dbgenh-runtime-check.json`](../manifests/hp-dbgenh-runtime-check.json)。

## 最新：msgbuf启动参数无效，改查实际早期分配路径

Log版已实机启动，bootargs含`msgbuf=1048576`，但只读`sysctl kern.msgbuf`仍131072。
两控制器依旧无USB子设备。完整141文件观察和轮转日志已取回；
立即dmesg从68.041s、轮转syslog内核记录从10.054s起，仍无最早USB初始化失败行。
原源码审阅漏看`CONFIG_XNUPOST`外围条件，已追加纠正记录；不把参数存在写成生效。
见 [`hp-logbuffer-runtime-check.json`](../manifests/hp-logbuffer-runtime-check.json)。

本地下一候选采用固定stock DebugEnhancer1.1.1，保留成功的XHCI/Wi-Fi/I2C配置，
去掉无效的msgbuf请求，以插件自带备用分配路径申请10MiB。
实际KC中备用路径4符号、msgbuf布局/magic/128KiB初值已核对；
其独立路由组预计因非mangled睡眠函数名缺失而失败，不能宣称完整日志重定向生效。
该组失败不阻断其后的缓冲分配源码路径。ocvalidate0、
12二进制kext+1injector原生注入0、新调试二进制坏导入负对照255；现已交付并完整回读，尚未实机验证。
见 [`hp-dbgenh-retry-check.json`](../manifests/hp-dbgenh-retry-check.json)。
Log实测IMG/50文件已先保留，48旧文件不变、两份新增booter日志到达EXITBS。
本轮3新文件回读通过，229旧文件元数据/六个旧IMG摘要/995个Ventoy EFI文件摘要与几何保持；两分区安全卸载。
下次选择`HP-Tahoe-VESA-XHCI-DBGENH.img → HPRECOVERY (dmg)`，原网络/SSH入口不变。

以下是前轮过程，后续结果以上述最新记录为准。

## 最新：SPT匹配生效，USB仍失败（2026-10-17）

新实机归档证实 `8086:a0ed/XHCI` 已变为 `AppleUSBXHCISPT`，publisher为
`org.rehabman.injector.XHCI.unsupported`，probe900；`9a13/TXHC`仍为通用类。
两者当前/驱动电源0、I/O0、没有下游子服务，物理Lexar仍不在磁盘清单。
这排除了“新增人格没有匹配到”的解释，未确定初始化失败的根因。
Wi-Fi/SSH/SFTP仍工作，触控板Polling、触屏APIC；完整141文件归档和轮转日志已保存。
见 [`hp-xhci-runtime-check.json`](../manifests/hp-xhci-runtime-check.json)。

当前内核日志缓冲只有128KiB，早期dmesg已被后续日志覆盖；轮转syslog的内核消息仅从约11.979s起。
`logd`服务不在此Recovery，不能用`log show`补齐。驱动On统计约5.18s本身不是超时错误证据。
下一轮本地诊断镜像只追加`msgbuf=1048576`，保留全部驱动、ACPI与USB设置；
47个其他文件和其他配置保持、同版ocvalidate0；后续现已交付并回读，尚未实机启动。
该上限来自固定公开XNU12377.1.9源码，实际12377.161.14接受性仍待验证。
见 [`hp-logbuffer-retry-check.json`](../manifests/hp-logbuffer-retry-check.json)。
实测XHCI IMG/49文件已先保留；新Log IMG、说明和校验单在只读重挂后完整回读，
226个原文件元数据、五个旧IMG摘要、995个Ventoy EFI文件摘要和分区几何保持，两USB分区安全卸载。
下次选`HP-Tahoe-VESA-XHCI-Log.img → HPRECOVERY (dmg)`，加入Wi-Fi并运行原内置SSH入口。
代理优先保存日志缓冲大小、dmesg和轮转syslog，再执行完整collector。
以下为前一轮候选的制作与交付过程，实机结果以上述最新证据为准。

## 后续完整运行态证据（2026-10-16）

Wi-Fi、root SSH 和 SFTP 已打通，第一份完整观察归档取回，见
[`hp-recovery-runtime-check.json`](../manifests/hp-recovery-runtime-check.json)。
实际 `TPD0/SYNA30B6` 为 **Polling**，`TPL0/WACF4233` 为 **APIC**；precision-touchpad 服务存在。
此前未知的中断模式字段现已取得，但不是卡顿根因或触屏完整功能的证明。
两个 XHCI 实际仍为通用 `AppleUSBXHCIPCI`、当前/驱动电源状态 0、无下游 USB host devices/interfaces，
Lexar 仍缺失。完整 registry 已保存；`log show` 因 logd store 不可用失败，有限 dmesg 中未取得早期 USB 错误。
以下保留早期采集/试验过程，标为未知的字段以本段后续证据更新。

## 下一轮：精确 a0ed → AppleUSBXHCISPT（已交付，实机待测）

已基于成功 Wi-Fi IMG 制作独立 `HP-Tahoe-VESA-XHCI.img`，私有目录
`.local/install-prep/hp-xhci-6atazozs/`。源 IMG SHA-256 为
`8ff91489c5c533644af60eee9ed5cd245fa805e6065263b4562992586845c54c`，
结果为 `e55eb607858afda49cda89fe8a9f023143ff49ce20a937424cd9ba704a66ae72`。

依据是 DalianSky/OS-X-USB-Inject-All 固定提交
`ce55e00966ac90c5e2504fb39b4ecf3fcebab51a` 的 SPT 500 personality，
以及实际 25G83 KC 中已有的 `AppleUSBXHCISPT` 类。派生版仅保留这一项，
将两个 ID 的匹配列表缩至 `0xa0ed8086`，保留其他元数据与许可证并附修改说明。
OpenCore 配置仅追加该 plist-only injector，限定 Darwin 25.x；`8086:9a13` 不在匹配范围。
这是控制器类选择的单项假设，实机初始化及 Lexar 枚举结果仍未知。

验证结果：

- OpenCore 1.0.8 `ocvalidate=0`；44 个原 IMG 文件、其余配置和私有身份保持。
- 11 个原二进制 kext 与一个新 injector 在实际 KC 原生注入退出 0；
  生成 KC 内回读到唯一精确 a0ed → SPT personality，无新增可执行文件。
- 本地 validator 增加 plist-only 支持；隐藏 executable、把二进制项伪装为 plist-only、
  缺失 personalities 和损坏 Mach-O 四个负对照均拒绝，恢复后 12 项通过。
- 最初原生工具因 plist-only 路径中的 `FreePool(NULL)` abort（-6）；原日志和工具保留。
  独立源码副本保留既有 link-only 修改，并仅为该 host-harness 调用增加非空判断，
  生产注入库及候选中的 OpenCore 二进制没有修改。补丁为
  `patches/opencore-kextinject-plist-only-free.patch`。

索引见 [`hp-xhci-retry-check.json`](../manifests/hp-xhci-retry-check.json)。
**候选已交付原 Lexar，尚未实机启动，USB 尚未修复。**
交付前已只读保存 WiFi 实测 IMG 与全部 46 个文件，45 个原文件未变，新增 booter 日志仍到达 EXITBS。
WiFi 实测 SHA 为 `af6893a6a2ddb56dd7c3f353ae2290f5070f5e60e4b48dbcb416dfde6c203b6e`。
新候选、独立 PID-wait 调试包、说明和校验单四个新文件均在卸载/只读重挂后完整回读通过；
222 个旧文件大小/mtime、四个原 IMG 摘要、995 个 Ventoy EFI 文件摘要及分区几何保持，两 USB 分区安全卸载。
记录 `.local/install-prep/hp-xhci-delivery-7z4ju925/report.json`。
后续由用户启动 `HP-Tahoe-VESA-XHCI.img → HPRECOVERY (dmg)`，加入 Wi-Fi 并执行原内置
`sh /Volumes/*/hpdiag/s`；代理再通过 SSH 分别检查实际控制器类、电源状态、下游端口与物理 Lexar。
新 PID-wait 修订仅在独立 USB 包中，内置入口和当前 listener 未改。

## 实机证据与当前故障

最新输入候选实测：用户确认**触控板可以移动指针，但连续移动断续、卡顿**；
Terminal 照片证明能输入并执行 `diskutil list`、`ioreg` 等命令。
`diskutil list` 显示内置 512.1GB NVMe 分区表及 115.9GB 空闲区、2.7GB Recovery 映像，
没有约 124.6GB 的物理 Lexar。`ioreg -p IOUSB -w0` 显示两个
`AppleUSBXHCIPCI` 节点为 registered/matched/active，但没有下游 USB 设备。
这证明控制器类已经绑定，不证明控制器启动流程、端口服务和实际传输正常。
触控板的实际 `Interrupt Mode`、USB IOService 端口树及错误日志尚待读取；
不能直接把卡顿全部归因于轮询或无图形加速。完整观察归档尚未取得。

后续用户照片给出了两个 `AppleUSBXHCIPCI` 的完整属性：均为通用类，
`CurrentPowerState=0`、`DriverPowerState=0`、`kUSBInterruptCount=0`，
查询输出中未显示下游端口服务。它将诊断重点收敛到控制器初始化/电源转换/端口创建路径；
单张 registry 快照仍不能证明其中哪一步失败。用户跳过较长的 I2C 模式命令，
该字段保持未知；后续优先使用短命令取 USB 错误信息。

用户随后报告 `dmesg | grep -i xhci` 没有输出。这不能排除错误，只表明未取得匹配日志。

## 上轮对照：仅开启 USB 所有权释放（结果仍无 Lexar）

USB 回到开发机后，已保存完整实测 IMG 和全部 43 个 FAT 文件到
`.local/install-prep/hp-usb-input-capture-g_ezwmbb/`。最新
`opencore-2026-10-16-130433.txt` 仍含 `-vi2c-force-polling`，KC 读取 `Ok(0)`，
随后到达 EXITBS，没有旧 `MM.AKM` 错误。其配置与交付输入版一致；没有 USB 运行态日志。

固定 OpenCore 1.0.8 文档将 `ReleaseUsbOwnership` 定义为尝试从固件驱动释放 USB
控制器所有权；通常不必开启。本轮只将它由 false 改为 true，检验固件到 OS 的 USB
接管假设。它不能独立证明 Ventoy 是否致因，也没有替换 USB 驱动 personality 或端口映射。

生成入口：

```sh
python3 scripts/prepare_hp_usb_ownership_retry.py \
  --source .local/install-prep/hp-usb-input-capture-<capture>/tested.img
```

全部其他配置字段、私有身份和 42 个 IMG 文件保持，包含 34 个其他 EFI 文件、
Recovery、观察脚本和四份历史 booter 日志。同版 ocvalidate 退出 0。
当前启动 IMG SHA-256 为
`0610299a23fff511149ddb84f1d8da15d63f25b66aeb00e3bceb55118010f490`，
已写回同名普通文件并完整回读。刚实测的输入版另存为
`HP-Tahoe-VESA-I2C-Baseline.img`，含日志的摘要为
`0c6ed48345eb34e29914e49bfb6c8af3cfda97a2842af7b7747578177bcd604e`。

MMIO 基线与完整离线数据的摘要保持，Ventoy 配置、分区和 214 个其他文件大小/mtime
保持，USB 已安全卸载。证据见
[`hp-usb-ownership-check.json`](../manifests/hp-usb-ownership-check.json)。
下一轮仍选 `HP-Tahoe-VESA-Recovery.img → HPRECOVERY (dmg)`；先确认能否进入 Recovery，
再用短命令 `diskutil list` 查看约 124.6GB 的物理 Lexar 是否出现。
若仍未出现，再拍 `ioreg -p IOUSB -w0`；触控板中断模式暂不要求手输长命令。
本轮所有权释放对照尚未实测，不能描述为 USB 已修复。

此前 2026-10-16 用户照片确认 HP 已进入 Recovery 工具窗口，报告触控板、触屏和外接鼠标
都无响应；键盘空格可能有响应，完整文字输入尚未验证。

USB 重新接回开发机后，代理只读保存了完整实测 IMG、配置和新日志
`opencore-2026-10-16-102405.txt`，位于
`.local/install-prep/hp-recovery-input-6pg65q76/`。新日志确认：

- 有效参数仍含 `slide=0`，配置中的 `DevirtualiseMmio=true` 与交付版一致。
- KC 读取 `Ok(0)` 后，到达 `LOG:EXITBS:START`（10:25:44）。
- 没有前两轮的 `EB.MM.AKM / EB.MM.MKP`、RT 分配失败或 `STOP 0x16`。
- 文件止于 Apple booter 阶段，不包含进入 XNU 后的 USB、I2C、PS/2 运行态 registry。
  因此可以确认上一关已越过，不能从这份文件判定外接鼠标没有驱动的具体原因。

## 开发机鼠标的只读识别

开发机可观察到 `Compx ATK A9 Mini+`（USB `373b:128e`）和键盘
`SINOWEALTH VGN V98Pro V3 2.4G Dongle` 的 Mouse 接口（`258a:024f`）。
两者的 Linux input bustype 均为 USB `0003`；ATK 设备还暴露
HID class/subclass/protocol `03/01/02` 的 Boot Mouse 接口。

用户说明是开发机使用的鼠标，但未在这两个接口中明确指定；没有把键盘 dongle 的
Mouse 接口误当成唯一物理鼠标，也没有把 USB 接收器等同于蓝牙。
这些身份/协议证据来自开发机，不是 HP Recovery 已枚举它们的证明。

## 本轮候选：I2C HID + 轮询请求

当前成功启动基线只启用 PS/2 键盘路径。内置设备为：

| 设备 | 已采集路径 | 对应输入 |
| --- | --- | --- |
| Synaptics `SYNA30B6` / `06cb:cd74` | `PC00.I2C0.TPD0`，controller `8086:a0e8` | 触控板 |
| Wacom `WACF4233` / `056a:4924` | `PC00.I2C1.TPL0`，controller `8086:a0e9` | 触屏/笔 |

采用官方 VoodooI2C **2.9.1** release，固定源码 commit
`e3ac3ed207170c39db88d6a67a76cc9fd3a1895a`，asset SHA-256：
`368e5eb60794583c340764813bd7e8244e94d3d3c06ea5b67034addd539487f4`。

核对源码与实际 asset 后发现，`VoodooI2CPCILakeController` 默认匹配列表没有本机的
两个 Tiger Lake ID。该类带有 Ice/Comet Lake 的 PCI D0 配置路径；
上游 [Tiger Lake 讨论 #478](https://github.com/VoodooI2C/VoodooI2C/issues/478)
及社区轮询测试提供了沿用这一类的依据，但不是本机 Tahoe 实测。

候选新增以下内容：

1. `VoodooI2CPCILakeController/IOPCIMatch` 追加精确的 `0xa0e88086` 和 `0xa0e98086`。
2. 依赖顺序为 **VoodooGPIO → VoodooI2CServices → VoodooInput → VoodooI2C → VoodooI2CHID**。
   所有新增项限定 Darwin 25；没有同时加载第二份 VoodooInput。
3. boot-args 追加 `-vi2c-force-polling`。
4. 更新 IMG 和物理 USB 中的观察脚本，增加 I2C controller、device nub、HID 与 IOHID 查询。

固定源码 `VoodooI2CDeviceNub.cpp` 的轮询标志是在 valid-APIC 检查之后处理，
所以准确说法是“请求避开 GPIO 中断”，不是保证任何资源形态下都强制纯轮询。
VoodooGPIO 作为依赖保留，不代表已经适配本机 Tiger Lake GPIO pin 表。

TPD0 的 `_CID=PNP0C50`、`_DSM` 资源与 HID satellite 匹配；本轮不使用仅因厂商为
Synaptics 就选取的专用 legacy satellite。原始 `_INI` 的 I2C 地址 `0x2c`、
HID descriptor 地址 `0x20` 及动态 GPIO/IRQ 计算保持。

20 个原有 EFI 文件逐字节保持，原配置中 CPU、MMIO、PS/2、ACPI、图形与私有身份保持。
没有增加全局 OSI 重命名、静态 GPIO/IRQ 或未经实测的 USB 端口映射。
最新实测已确认触控板指针移动但卡顿；实际点击、触屏与笔仍需逐项验证，外接 USB 故障未解决。

## 校验与原生 KC 注入

候选由 [`prepare_hp_input_retry.py`](../scripts/prepare_hp_input_retry.py) 生成：

```sh
python3 scripts/prepare_hp_input_retry.py \
  --source .local/install-prep/hp-recovery-input-<capture>/tested.img
```

- 匹配版本 OpenCore 1.0.8 `ocvalidate` 退出 0，架构、SSDT 校验及第三方依赖顺序通过。
- 五个新增 executable 与官方 release 字节完全一致；只改 core 的一个 plist 匹配字段。
- 从最终 IMG 回读的 Recovery DMG 和 chunklist 与原签名通过的 Apple 输入摘要一致。
- 同版 OpenCore `TestKextInject` 已在 Linux 原生构建，AUDK 固定于
  `dfd5516702b4911f1fc1919a429d637b456df913`。

原版 TestKextInject 会顺带执行大量与候选无关的 patch 自测，其中部分针对本 KC 失败。
为隔离链接行为，使用[两行测试补丁](../patches/opencore-kextinject-link-only.patch)
关闭 `ApplyKernelPatches` 和 `ApplyKextPatches` 调用，保留实际 prelink/injection 实现。
该测试工具仍带上游的 plist-only dummy injection，不能当作完全复刻实际 boot 流程。

实际 **25G83 原始 KC** 加全部 10 个配置内 kext 后，注入和完成均成功、退出 **0**。
另将 HID 副本真实导入 `_clock_get_uptime` 改成不存在的 `_bogus_get_uptime`，
负对照注入被拒绝、退出 **255**。原 KC 与生产 kext 未修改；测试输出 KC 没有部署。
`nm` 单纯统计时缺少的 `_RESERVED...` vtable 名称不能单独当作链接失败结论。

最终候选的全部 35 个 EFI 文件与原生链接检查的输入相同。证据索引见
[`hp-input-retry-check.json`](../manifests/hp-input-retry-check.json)。
这是原生文件解析/链接测试，没有启动 VM，也没有执行 HP 的输入驱动。

## 下一次实机观察

仍启动 `HP-Tahoe-VESA-Recovery.img`，选择 `HPRECOVERY (dmg)`。
首先分别验证触控板移动、实体点击、轻点、触屏和 USB 鼠标；键盘再确认文字输入。
若能打开 Terminal，运行 USB `ISO/linux/collect_macos_handoff.sh --save-usb`，
让脚本核对已挂载 USB 并自动保存私有归档；失败时保留 `/tmp` 副本和提示。
脚本新增限时、其他硬件观察和自动摘要，详见[自动观察脚本](recovery-observer.md)。

已进入 Recovery 但无指针的上一版完整 IMG 单独作为 MMIO 基线保留，便于回退对照。
完整离线 app 数据映像继续保留；安装器执行仍待输入、物理 USB 和磁盘观察完成。

## 首版输入候选 USB 交付结果

输入候选已替换同名普通文件，完整回读 SHA-256：
`54f13d49772c5eb246efa00889d1afa5025e2bb3f0a407bdda2b7ead4fd8a47b`。
实测基线另存为 `/ISO/linux/HP-Tahoe-VESA-MMIO-Baseline.img`，
摘要与私有原始保存完全一致：`db802b78c1ad33299ec9bbc6057411609acded524a06956c9e631e7651d0ff44`。

离线数据映像完整重读后仍为原 SHA-256；Ventoy 配置、分区布局保持，
212 个不涉及本次替换的文件大小/mtime 清单保持。新观察脚本、交接说明与 checksum 清单
已写回，USB 已安全卸载。收据：`.local/install-prep/usb-input-delivery-rrst50dq/report.json`。
本地交接集：`.local/install-prep/hp-handoff-4d86t0fx/`。

随后按用户要求扩充了自动观察脚本，并同步到物理 USB 和 IMG 内。
该次 IMG SHA-256 为 `12cd17fc42333762a2363f02adbea34a278b2c52f82713eee0a438885a8290ca`，
全部 35 个 EFI 文件、配置和 Recovery 与上述候选相同；当次收据为
`.local/install-prep/hp-observer-gl2yv42p/usb-delivery.json`。
11 个隔离原生 fixture 测试、同版 ocvalidate 和 USB 回读通过，USB 已安全卸载。
证据见 [`hp-observer-check.json`](../manifests/hp-observer-check.json)。
