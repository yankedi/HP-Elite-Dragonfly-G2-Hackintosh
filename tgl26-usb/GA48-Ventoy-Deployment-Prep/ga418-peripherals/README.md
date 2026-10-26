# GA418：HP Elite Dragonfly G2 全硬件驱动续查

2026-10-26，无人值守来源/适用性研究已覆盖硬件清单，整体修复目标尚未达成。目标 `155bd26c-396b-4bcf-bf59-1452c4a9c84e`。

**当前结论：新触控板/GPIO官方CI二进制已经取得并核验；蓝牙有Tahoe专项候选；相机有UVC1.5线索；音频有匹配真实模拟通路的定制起点。完整USB map缺物理逐口输入，NHI/DMIC/ISH/指纹等仍未找到完整macOS修复。不能宣布“所有修复已找到”。** 全项状态与阻塞见[REPAIR-MATRIX.json](reports/REPAIR-MATRIX.json)及[最终审计](FINAL-AUDIT.md)。

## 本轮可复验工件

- `private/linux-readonly.json`：2026-10-26T07:33:40Z，Linux 同 boot `REDACTED-MACHINE-ID`；`ga417-awake.service` active/running、Transient=yes、PID5459，实际 `sleep:idle:handle-lid-switch` block。
- `private/linux-resources.json`：同 boot 前后校验；只读 GPIO debugfs、USB 描述符、EDID，没有打开相机流或改变亮度。
- `private/linux-platform.json`：08:20:47Z，同boot再次确认防睡眠PID5459及实际block；只读ALSA codec/PCM与PCI sysfs。ALC285内部扬声器pin0x17、耳机0x21、外接麦0x19，以及独立SOF DMIC PCM已实际枚举；未播放或录音。
- `private/linux-final-awake.json`：09:00:16Z最终只读核验，同Linuxboot、服务PID5459仍active/running/Transientyes且实际block。只代表该采样时刻，不承诺未来持续状态。
- [静态审计](reports/STATIC-AUDIT.json)：来源逐 SHA、两个 release 的 GitHub digest/ZIP CRC、实际封存 EFI、Mach-O defined symbols、GPIO pin 表、相机 UVC 版本和 EDID。
- `private/sources/*`：固定提交/发行版原件、原始 issue 评论，逐文件 `*.receipt.json` 保存 URL、时间、字节数和 SHA。抓取失败也保留回执；不是成功来源。
- 复验命令：`python3 tools/audit-peripherals.py`（在本目录）；只访问开发机文件。
- 平台复验：`python3 -B tools/audit-platform.py`、`python3 -B tools/audit-nhi.py`、`python3 -B tools/audit-backlight-binary.py`。后两项私有报告保留精确Apple/NGreen指令，不公开上传。

## 1. 触控板 / 触屏：官方最新 GPIO 实现

### 已核实

本机 `SYNA30B6` / `06cb:cd74` 在 `I2C0.TPD0`；触屏/笔 `WACF4233` / `056a:4924` 在 `I2C1.TPL0`。Linux GPIO HID 为 **INT34C5**，不是旧 personality 的 INTC1055。

当前封存 VoodooGPIO 的 plist 有 TigerLakeLP personality，但 Mach-O defined symbols 和全文件字符串均无 `VoodooGPIOTigerLakeLP`。**只修改匹配 HID 不能给该二进制增加驱动类。** 当前 I2C 2.9.1 手加 a0e8/a0e9 到 PCILake，boot-args 仍有 `-vi2c-force-polling`。

官方 [VoodooI2C commit 6be653a2](https://github.com/VoodooI2C/VoodooI2C/commit/6be653a2d2234ac1f7464ebf12716314975c3920)，2026-10-25：

- 增加 TigerLakeLP 独立 personality，匹配 `0xa0e88086&0xFFFCFFFF`，本机两个控制器均覆盖；`I2CClkRate=120000000`、`I2CSdaHoldTimeNs=230`。
- VoodooGPIO 子模块更新为 [d415406e](https://github.com/VoodooI2C/VoodooGPIO/commit/d415406ecf25b5e322d3db9a4abab5719106fac1)，2026-10-24。
- GPIO 项目真正把 TigerLakeLP 源文件加入编译，新增 `INT34C5` alias；其 LP pad-group 数值表与 Linux v6.18 对照相同。
- GitHub 最新正式 release 仍是 **2024 年的 2.9.1**。重新下载这一 release 不会自动得到昨天的修复；需固定新 commit 和递归子模块构建，或核验明确含该 commit 的 CI 产物。

新 Linux 证据把动态资源缩小为：

| 设备 | Linux IRQ | GPIO/ACPI offset | 原生硬件 pin ordinal | pad 复用名称 |
|---|---:|---:|---:|---|
| TPD0 触控板 | 198 | **175 / 0xAF** | 114（GPP_D15） | ISH_UART0_RTSB |
| TPL0 触屏 | 199 | **267 / 0x10B** | 182（GPP_C11） | UART0_CTSB |

`/sys/kernel/debug/gpio` 两者均为 `GpioInt(0)` / IRQ / ACTIVE LOW。IRQ198/199、GPIO175/267、pin114/182 是不同编号。新 GPIO `intel_gpio_to_pin()` 用 offset→pad-group→硬件 pin 转换，不能把114/182或198/199填进 ACPI pin 表。pad 名称不意味着设备真的在使用 UART。

### ACPI与polling选择的进一步核对

固定DeviceNub源码200–253显示：先解析`_CRS`/TP7G `_DSM`，`_DSM`同时返回I2C与GPIO时优先选择它；然后先接受有效APIC IRQ（≤0x2F），再检查`-vi2c-force-polling`或控制器`force-polling`属性，最后才选择GPIO。因此force-polling只阻止GPIO，并不压过有效APIC。这解释了此前同一参数下触控板Polling而触屏APIC的现象；“该参数强迫所有输入设备轮询”不准确。

旧本机DSDT26204–26295中TPD0 `_INI`已经把`GNUM(GPDI)`写入SBFG的INT1，HID descriptor0x20、I2C地址0x2C；TP7G UUID `ef87eb82-f951-46da-84ec-14871ac6f84b`的`_DSM`通过TP7D返回I2C+GPIO资源。TP7D在41507–41531实现，不需凭空增加同名UUID补丁。Darwin是否得到有效且被parser接受的资源仍要用实际日志确认；应先测原生方法+完整新GPIO，再决定是否需要最小资源补丁，不能先覆盖`_CRS`或抄模板零pin。

### 最小候选路线与验证

1. 独立构建/审计上述 I2C 与 GPIO 精确组合，连同匹配的 I2CServices、VoodooInput、I2CHID；确认实际产物有 TigerLakeLP defined class 和 INTC1055/INT34C5 matching。
2. 本机 ACPI `_CRS`/`_DSM` 在 Darwin 路径仍需离线核对；Linux 资源只能提供对应证据，不能保证 macOS 求值相同。不要覆盖整个 DSDT。
3. 未来独立输入候选移除 force-polling，保持 GA416 图形栈；不得保留重复 satellite 或旧 GPIO 混载。
4. HP 用户在场验证：GPIO 类 attach、TPD0/TPL0 各自显示 GPIO interrupt mode、滑动/多指手势/触屏动作产生 HID 事件、空闲 CPU、点击及掌压。此前曾滑动后事件计数仍0，所以枚举、去掉参数、甚至 IRQ 注册都不是功能通过。
5. 回退为现有独立正常镜像/原 I2C 组合及 polling 参数；本轮未生成/启用启动候选。

### 已取得官方合入后的实际二进制，不再停留在待构建

官方[CI run40157687159](https://github.com/VoodooI2C/VoodooI2C/actions/runs/40157687159)的push SHA准确为`6be653a2d2234ac1f7464ebf12716314975c3920`，结论success。artifact `12584862177 / VoodooI2C-6be653a2`已下载到`private/sources/i2c-6be653-ci-artifact.zip`：**SHA256 `71a8ad60b5e05dc8d95fa405d7e3920f5f76c7664ece6d902e1efacba19500ba`与GitHub artifact digest相同**。通过nightly.link取得字节，最终是GitHub Actions的Azure artifact存储；不只信任镜像文件名。

外层与内层Debug/Release三个ZIP均CRC通过，**两个实际GPIO Mach-O都有TigerLakeLP的defined symbols及INT34C5 personality**；I2C实际plist有TGL控制器时序。匹配产物内有I2CServices、VoodooInput1.1.7、I2CHID及其他satellites。构建产物的版本字符串仍然是**2.9.1**，所以不能以版本字符串区分2024旧release和2026新CI。可重现检查已加入`tools/audit-peripherals.py`的`new_i2c_ci_binary`字段，包含内层包、GPIO二进制hash、class symbols、依赖与完整personality。

此CI的workflow递归取得固定submodules，但MacKernelSDK、ocbuild与VoodooInput bootstrap引用master；因此现有CI字节可以封存核验，不能声称任意未来重建都bit-for-bit相同。未来候选只选需要的**I2CHID**，不用因为品牌Synaptics再叠加专有Synaptics satellite，不把所有包内satellites全启用。

### 触屏、笔与JIS键盘的边界

新I2C固定的I2CHID submodule为`27277936bc16c215ae7f9b31e76e3231778d04bd`。其plist分别按Digitizers usage page0x0D的Touchscreen0x04、Pen0x02、Touchpad0x05匹配。对旧实机HID descriptor的离线读取确认：Wacom843字节（SHA`5ad43785…`）确实有Touchscreen0x04和Pen0x02 application collections；Synaptics700字节（SHA`0ee8e6bd…`）有Touchpad0x05。不是只凭厂商品牌选satellite。

源码`VoodooI2CStylusHIDEventDriver`走Touchscreen父类的`checkStylus`，会转发坐标、压力、barrel/eraser和tilt；这比“笔只可能当鼠标”更具体，但**没有HP/Tahoe实测**。`pressure_physical_max`、坐标范围和报告parser仍需匹配本机descriptor，不能用NativeEngine里的模拟ForceClick代替真实笔压验证。分别验收触屏绝对坐标/边角、多指/旋转，笔hover/落笔/压感/侧键/橡皮/倾斜和掌压；没有笔硬件时应保留笔功能未测。

PS/2键盘与I2C/GPIO分开。保持现用VoodooPS2Keyboard路线，按实键的scan code与macOS输入源核对JIS的英数/かな、¥/\\、_、修饰键和Fn。现有材料没有每个实体键的事件，不能凭注入一个JIS键盘类型就宣布键位修复。BrightnessKeys只负责实际panel通知的桥接，见下方亮度；不要向键盘同时装多个PS/2控制器。

## 2. AX201 蓝牙：有可测试组合，但新版仍有源码差异

本机 USB **8087:0026 / HS10**，当前 EFI 无 IntelBluetoothFirmware、IntelBTPatcher 或 BlueToolFixup。Wi-Fi 可用不能代替蓝牙驱动。

### 源码与发行包核验

- [lshbluesky v2.5.2](https://github.com/lshbluesky/IntelBluetoothFirmware/releases/tag/v2.5.2)，2026-10-18，对应 commit `14787a2a73210a75c0e5a650f30b42e581da0fe2`。RELEASE ZIP SHA `c26140b2091e7b41aab5e5fbdd322112908efc509f9fde3d71d4e3f91396b991`，与 GitHub asset digest 相等、ZIP CRC 通过。
- 实际固件 plist 有 8087:0026 personality；不是只凭“AX201”名称判断。
- [cbbe844f](https://github.com/lshbluesky/IntelBluetoothFirmware/commit/cbbe844f537aeb77c128008557c7ee7d2087c6c2) 加入 26.5+ 的 `ConfigurationDescriptor` 管道初始化符号，保留旧符号；二进制含新符号字符串。
- v2.5.2 加入 LE Data Length Change，源码 handle 位于事件 `[3][4]`，13字节事件序列在实际 binary 可找到。
- 配套 [BlueToolFixup 2.7.2](https://github.com/acidanthera/BrcmPatchRAM/releases/tag/2.7.2)，发行说明明确加入 macOS26 bluetoothd patches。RELEASE ZIP SHA `e1c1c55347526d031a8ae2fdd1f52efa3019161e497fb38e1cfa809752f8af21`，GitHub digest 和 CRC 通过。只取 BlueToolFixup，不能把包中其他 Broadcom 固件 kext 全装入。

**不能把 v2.5.2 说成完整实现 issue514：** [issue514](https://github.com/OpenIntelWireless/IntelBluetoothFirmware/issues/514) 作者描述还需要三个 `IOUSBHostIOSource::io` overload hooks；固定 v2.5.2 源码仍只 hook `IOUSBHostPipe::io`，binary 也无 IOSource hook 字符串。源码的新事件状态是函数静态全局三阶段状态，不是每连接独立状态。多 BLE 并发/重连/失败恢复均需测试；尚未证明此 HP 的25G83是否走旧 Pipe callback。

### 外部实际反馈与边界

原始 [issue505](https://github.com/OpenIntelWireless/IntelBluetoothFirmware/issues/505) 的68条评论已封存，包括：

- 2026-05-31：AX201 + MX Anywhere3S 上26.5新符号修复成功。
- [2026-07-01](https://github.com/OpenIntelWireless/IntelBluetoothFirmware/issues/505#issuecomment-4852052902)：v2.5.1、26.5.2/26.6beta3，AX201及AX210配对/连接/开机重连报告。
- [2026-07-06](https://github.com/OpenIntelWireless/IntelBluetoothFirmware/issues/505#issuecomment-4897121196)：AX210 升26.6beta4后回归 Address NULL/BCM_4350C2，固件上传成功也未恢复；不能漏掉负反馈。
- [2026-09-17](https://github.com/OpenIntelWireless/IntelBluetoothFirmware/issues/505#issuecomment-5708318072)：另一 HP 的 AX200 在 **26.6.2 /25G83** 用 v2.5.1+BlueToolFixup2.7.2，加 NVRAM Delete/Add 修复 ghost state；不是本机AX201复测，且原AX210作者同法失败。

### 最小候选路线与验证

独立蓝牙候选：Lilu → IntelBluetoothFirmware → IntelBTPatcher + BlueToolFixup（后两者在 Lilu 后；现代系统不启用 IntelBluetoothInjector）。HS10 在真实 USB map 中标 internal255；检查实际蓝牙 USB attach、固件版本、有效地址，再测试传统音频与 BLE 鼠标/键盘、passkey、多设备及重新连接。

按官方 FAQ 核对 `bluetoothExternalDongleFailed` 为一字节00、`bluetoothInternalControllerInfo` 为14字节00及其 OpenCore Delete/Add 语义；这些是未来候选项，本轮未改 NVRAM。保留原始值用于回退，不做通用 NVRAM reset。`BCM_4350C2` 是可能的 fallback/ghost 显示，不能单独诊断 Intel 固件损坏。源码 hook 缺失与 ghost state 是不同问题。

回退为原无蓝牙kext配置；如果未来修改持久值，回退还必须恢复原值，不能只删除kext。用户未在场，本轮没有进行配对或睡眠试验。

## 3. 相机：本机确为 UVC1.5 RGB+IR，修复需按失败路径选择

本机 **Quanta 0408:5349 / HS02** 四接口。新只读描述符 SHA `16366443a18aba336190d89cad6f51bed33dbbbe130f9006088916ad8a792c5b`：两个 VideoControl header 均 **bcdUVC=0x0150**。Linux video0/1为RGB function、video2/3为IR function；同一 function 的两个 video node 不应算成两个独立传感器。

候选及适用条件：

| 路线 | 原始证据 | 本机适用边界 |
|---|---|---|
| Apple原生UVC | USB Video class，Linux正常绑定；HS02内建映射 | 先在macOS区分未枚举、权限、无帧与图像格式问题；枚举不足以证明取帧 |
| UVC1.5 Probe/Commit长度 | [RealtekUVCFix fixed8315e94](https://github.com/trungkiengrxer/RealtekUVCFix/tree/8315e9462ee9a1155d3bacbcaf1676c53a932b91) 在Dell0bda:58f4/Tahoe26.5修34→48字节 | HP也声明1.5，因此是具体协议线索；但未确认HP要求48字节、25G83的UVCFamily字节模式与实际协商，不能按相同版本号直接安装 |
| malformed PROBE恢复 | [UVCProbeFix原帖](https://olarila.com/topic/48678-uvcprobefix-for-macos-tahoe-fix-broken-usb-webcam-video-and-black-screen-on-hackintosh/) Lenovo S145、640×480YUV42230FPS运行轨迹成功，Darwin25.6目标 | 稳定版只验证原相机；descriptor-driven generic是独立实验路线。HP未取得相同失败轨迹，不能套固定frame/payload |
| Legacy Camera override | [Apple108387](https://support.apple.com/en-us/108387) 针对依赖旧软件、非现代camera extension的设备 | 不是对所有USB UVC黑屏的通用修复；不因相机未工作就改恢复环境设置 |

IR能输出图像不等于Face ID/Touch ID/Windows Hello认证可移植到macOS。下一步本地审核UVC修复源码和HP各function formats；后续用户启动macOS后确认AVFoundation设备、服务日志、首帧和协商长度。回退按各独立候选移除新增kext；保持原Apple UVC栈和图形组件。

### 进一步源码/实际包核验

- 本机RGB function的格式包含MJPEG1280×720/30fps及640×480等、uncompressed640×480/30fps等；IR function有640×360/15fps uncompressed。描述符可证明相机不属于必须依赖IPU6/MIPI专用栈的路线，但不证明这些格式均被macOS接收。
- RealtekUVCFix源码不是仅匹配Realtek VID/PID：它在共享缓存页搜索17字节模式并修改全局UVCFamily长度计算。这会把旧1.0相机的26字节分支也变成34字节；需保留1.0/1.1/1.5三分支的完整合同，不应只看到HP的1.5就直接复用。
- 下载的UVCProbeFix稳定包为0.3.1，SHA `36ed0e0a582a401e531a10aa8672f75120dfc4c10ce038bcd010cbbc79f1e81d`，CRC通过。plist中的设备专用merge为 **174f:1176**，不是本机0408:5349；还有IOResources插件，不能仅改plist VID/PID就断言二进制算法适配。
- 标为PassiveTrace-v1.1的ZIP实际含 **v1.4.command**，SHA `888559eeb1b670db38ab64919e38e9e24241649c516409e067ebc634995ab668`。源码会LLDB attach并暂停UVCAssistant，默认Objective-C accessor还会执行target getter；本轮仅静态读取，不能当无人值守无扰动观测直接运行。未来可提取纯离线描述符/ABI解析部分，现场捕获由用户在场决定。

## 4. 亮度 / 色彩：先核实本机路径，发现现有参数门控

面板 `IVO8596 / X133NVFF R0`，1920×1080/eDP。Linux亮度4311/19200只是该时刻的软件标尺；本轮没改亮度，没读GPU MMIO，不把19200当PWM ceiling。

静态读取实际GA416源 `kern_gen11.cpp`（SHA `e5860a108ffdb8e8377a1681ff33bde4a51048349bc615d52b993a9bff97e040`）：

- `xeFixEnabled()` 在 `getIsRealTGL()` 时直接返回false（3690–3695）。
- `xeFixFilterWrite()` 在3856先 `if (!xeFixEnabled()) return val;`，之后才读取 `ngreenblmax` 并缩放PWM（3865–3877）。
- 因此 **现有GA416真实TigerLake上，直接加 ngreenblmax 不会启用这条缩放路径**。不得为了亮度解锁RPL Display13 DPT/DBUF策略或整体合并上游。
- 同门控下的 GAMMA_MODE_A bypass（3888）也不能说已在HP开启；ICC颜色问题仍需检查真实输出。
- `kern_green.cpp` 675–685保留AppleIntelPanel::setDisplay/backlight字符串补丁；有hook源码不证明当前AppleBacklight已attach或滑块可用。

当前ACPI无PNLF。后续先审核 OpenCore1.0.8 SSDT-PNLF 原件与本机 IGPU路径，避免复制AML中的寄存器初始化；再验证 AppleBacklightDisplay、滑块→真实亮度、单调范围/最大值/低端熄屏、键盘事件。若需PWM修复，应为真实TGL单独提取最小背光逻辑并保留现有图形策略；需真实Apple参考值、硬件频率和输出证据。

**PNLF样板已发现具体不适用点：** OpenCore1.0.8原样本只有到IceLake的device-id表，不包含9a49；默认未指定`RMCF.FBTP/LMAX`时会落入Skylake式组合寄存器处理，并写`LEVX`。本机ACPI路径则是`\_SB.PC00.GFX0`，样板是PCI0.GFX0。最小方向是Darwin限定、对应路径的PNLF标识/UID/profile，去掉未经证明的MMIO初始化；不是直接放入原样板。GA416源有F19 profile，但仍需确认实际attach与PWM合同。

亮度键也有本机固件证据：旧封存DSDT的EC `_Q86/_Q87` 经`G289`条件调用`\_GPE.G400(0x86/0x87)`，SSDT11内屏DD1F提供`_BCL/_BCM`。这比另一机器的键位表更具体，但不能证明当前macOS按键进入了这个分支。[BrightnessKeys fixed37bdf47](https://github.com/acidanthera/BrightnessKeys/tree/37bdf473b4cb33c804760125795aa591bb0c9835)能接收ACPI panel的brightness通知并转为PS2键事件；若实际走HP HIDD/WMI路径，则还需对应事件桥接，不能把所有未知Fn键重映射为同一个F20。后续要分别观察上/下/麦克风键的ACPI或PS2事件，保持JIS布局独立。

色彩有两层：先排除RGB/BGR、范围/位深、gamma格式等显示路径问题，再用ColorSync/ICC校色。EDID校验和/标称gamma/chromaticity已离线解析，**不是测色仪校准**。未找到可确证此HP面板且同SureView状态的ICC；不拿另一面板ICC或软件亮度filter当背光修复。准确校准需固定SureView/亮度状态及测色仪；用户提供的1000nit尚非本轮测量。

本轮EDID SHA `229597c3c0f0577d85202c7928c8ad4718a7624558e41afde1f8b7dce15adba5`，标称gamma2.2，红(0.63965,0.32910)、绿(0.29980,0.59961)、蓝(0.14941,0.05957)、白(0.31250,0.32813)，接近sRGB/D65。可作为未校准的sRGB基准选择依据，不能反推实际100%色域、亮度或SureView开启后的测量结果。

### 新发现：AppleBacklight注册也被注释，不能只看保留的hook函数

实际GA416 `kern_green.cpp:151–153`的`lilu.onKextLoadForce(&kextBacklight)`在块注释内，连同MCCS/IOGraphics注册被禁用；675行以`kextBacklight.loadIndex`分发的hook代码和F19数据虽保留，**不能据此声称该回调已注册/执行**。因此“先补PNLF就必然得到注入F19曲线”缺少前提；应先确认实际AppleBacklight加载、panel attach及NG回调index，再评估仅注册Backlight的独立最小候选。不要顺带启用同注释中的其余组件或RPL策略。

已进一步审计封存现用Mach-O UUID`4C4C44D4-5555-3144-A13A-DFB86EFBE513`：精确`NGreen::init`完整符号片段有1处AGDP结构直接引用、**0处Backlight结构直接引用**；`__text`按真实符号边界分别解码，成功解码范围内的Backlight结构2处直接引用都在`processKext`。私有`backlight-binary.json`记录bytes/SHA与直接引用，同时列出5个部分解码符号片段（init不在其中）；支持上述源码门控发现，但不证明排除全程序的其他/间接引用，也不是运行时panel attach证据。没有编译/部署新图形驱动。

已有HP macOS原件`ga417/private/rtc-live/initial-20261026T013125Z.json`中dmesg在27.686814秒确实出现`EFI using a different backlight frequency`（AppleIntelController::hwGetCRTC），是本机相关线索，但不是已经测得频率或证明缩放系数。后续需同一boot的AppleBacklightDisplay层级、原生/Apple PWM period和duty合同；当前19200不能直接替代这些值。

固定Linux v6.18 `intel_backlight.c`显示CNP及以后PCH使用独立BXT式**CTL / FREQ / DUTY**，从VBT选controller，读取FREQ作为pwm_level_max；eDP还先尝试AUX backlight。与旧SKL组合寄存器的PNLF初始化不能等同。最低只标识PNLF的方向可在`PC00.GFX0`下放APP0002/backlight并Darwin限定、无OperationRegion；**UID19仅是待核对profile选择，不能把其0xffff标尺当成本机period**。本轮不生成声称已就绪的AML或PWM修复。

SureView需要独立验收：相同亮度百分比在隐私屏开/关可能有不同光学输出/色偏；面板隐私功能、Fn键事件与背光滑块不是一项功能。固定v6.18 hp-wmi有brightnessup/down键映射，但没有SureView/privacy实现，不能把安装一般HP WMI热键驱动当完整SureView修复。现机没有取得可证实隐私状态/事件桥接的macOS记录，准确ICC和SureView控制仍未找到完整修复。

## 5. Wi-Fi：当前原生Tahoe分支已识别，另有新版专项候选

现用AirportItlwm2.4.0 binary SHA **fe4459c95596348cff31e784f09e73af45c30e4c24cfb753eed0c850a0fca4d8**，本轮与旧固定asset逐hash相等。来源为 **laobamac/itlwm commit bbe368ec7d55a5395d08c729e88eeaabebae8255**，旧asset `AirportItlwm-Tahoe-v2.4.0-RELEASE-alpha-bbe368e.zip` SHA `f47b8320f90b71c25d1bf3d37e471c6e50c016e2e70c1eb7069e599b22dc6878`。实际依赖是IO80211Family/IOSkywalkFamily原生ABI；不能把Ventura-ABI教程的OCLP根补丁当成本机现状。

1. **保留现有联网组合优先。** 本机AX201已实测网络和SSH，可作为后续修复的管理通道。
2. 同一分支新 [738d4c61](https://github.com/laobamac/itlwm/commit/738d4c61b5a64433b27c1ab09dba94916ab77d8d)，2026-10-18，`ItlIwx.cpp`只有一处队列条件：`fwqid <= IWX_QID_MGMT`改为`fwqid <= sc->first_data_qid`，在`AIRPORT_VTD`内；两个完整固定源码已比较。属于较小升级候选，但需核实当前构建是否走该路径和本机队列日志，不能当已定位内存Panic原因。
3. [itlwm1062最新9月反馈](https://github.com/OpenIntelWireless/itlwm/issues/1062#issuecomment-5665728941)已指向独立 **[AirportItlwm-Tahoe](https://github.com/kgp-macPro/AirportItlwm-Tahoe)**。因此不能沿用6–7月“所有Intel Tahoe均不创建awdl0”的旧结论。
4. 该项目1.0.0在AX210/25G83有作者物理验证：AppleVTD和传统配置、active awdl0/P2P、流量、双向AirPlay/ScreenMirroring；**不声称AirDrop、Continuity Camera、Personal Hotspot修复，也不自动覆盖AX201**。它依赖OCLP恢复的Ventura legacy无线环境，与本机原生ABI方案不能混换。
5. 当前固定 [4025c88](https://github.com/kgp-macPro/AirportItlwm-Tahoe/tree/4025c88fd063c01e46c2aed2eedf060d41cd0e4b) 文档含10月20日的1.1.0-beta.1 ZC28比较活动，以及10月22日AX201 DMA指导更正：不能凭AX201名称认定Mode1/2；`EXPECTED_MODE`只验证实际模式，不切换模式。本机8086:a0f0的正确硬件身份已固定，但该活动还不是本机稳定性证明。

本轮只审源/文档，没有安装新Wi-Fi或root patch。后续如只修蓝牙，先保留当前Wi-Fi；如测无线升级，保持独立候选并预留同版本原bundle回退。AWDL接口存在、AirPlay、AirDrop双向真实传输分别验收。

## 6. 其余硬件与待推进项

详细来源、实际25G83 KC匹配、22个PCI功能覆盖及验证/回退见 **[IO-OTHER.md](IO-OTHER.md)** 和 [PLATFORM-AUDIT.json](reports/PLATFORM-AUDIT.json)。08:30:50Z新Linux只读采集再次核验同boot/防睡眠；还确认NHI host generation4、安全域、两XHCI的端口计数和NVMe直连路径。

| 项目 | 已固定事实 | 后续工作 |
|---|---|---|
| Wi-Fi / AWDL | 现用laobamac bbe368e原生ABI已核验；新KGP项目有AX210 awdl0/AirPlay成功但仍无完整AirDrop | 尚需核对beta与原生分支具体功能/本机适用性；不为普通网络问题盲换根补丁栈 |
| USB | a0ed当前SPT注入已审，PCH12HS+4SS=16；CPU9a13为1HS+4SS=5 | generic原生XHCI路径存在；物理逐口/翻转map仍缺，PCH需≤15，不是全机≤15 |
| 集成雷电/USB4 | Linux host router generation4；25G83原生NHI两personality均不匹配9a1b，Type4专用allocator还有selector分支 | LinuxICL/TGL共享icl_nhi_ops是研究线索，非AppleHAL支持证明；完整修复未找到，不套离散卡教程 |
| 音频 | 真实ALC285 pin17→3/21→2/8→23→19与layout71部分重叠；a0c8已有AppleALC controller补丁 | TahoeHDA恢复/功放coef65及无效路径需独立审验；SOFDMIC真实PCM存在但未找到macOS实现 |
| 指纹 | 06cb:00f0 HS07确在libfprint支持表 | Linux支持不是macOS实现；普通认证与原生TouchID均未找到本机修复 |
| ISH/ALS/姿态/铰链 | a0fc→ISHTP GUID→8087:0ac2/0ac3→10IIO链路已实采 | 不走I2C/USB；缺macOSIPC/ISHTP及功能桥接，不把SMCLightSensor当ISH驱动 |
| 电源/存储 | SMCBatteryManager支持BIX；HP电池字段16bit对应ECEnabler线索；MicronNVMe直连00:1d.0 | 当前VMD枚举但不重映射该SSD；NVMeFix26只为独立功耗候选，非pmapPanic修复；仍不做睡眠/电池故障路线 |

## 研究进度与下一步

已取得并核验新GPIO实际官方CI产物，完成NHI device-id字段/Type4 metaclass分支、AppleBacklight现用binary直接引用、22PCI覆盖及其余功能矩阵。GPIO/相机/蓝牙/亮度/音频真实功能，物理USB/雷电/笔/JIS和ICC仍需macOS/外设/测量输入；DMIC/ISH/指纹等缺完整实现。新候选均按独立最小变更、可验证结果及回退组织。最终审计按真实阻塞判断，不将研究文档交付计成“全部修复”。

公开来源 Exa MCP 已触发额度限制；匿名 GitHub API 对PR评论抓取返回403，失败回执保留。已通过可用原站/raw和其他搜索继续；两者不是硬件不支持的证据。
