# GA418：USB / 集成雷电 / 音频 / 其余平台设备

2026-10-26。入口[README](README.md)，可复验结果[PLATFORM-AUDIT.json](reports/PLATFORM-AUDIT.json)。这里的“源码候选”不等于HP上功能修复成功；目前仍有完整驱动实现及现场证据缺口。

## 本轮实际依据

- `private/linux-platform.json`（08:20:47Z）和`private/linux-io.json`（08:30:50Z）：同boot `8b2033f0-fcf7-47b6-be6d-fe012f099ab4`，SSH exit0，前后boot一致；`ga417-awake.service` active/running、Transient=yes、PID5459，实际` sleep:idle:handle-lid-switch / block`保持。只读sysfs、procfs和两条systemd查询；未开相机、播放/录音或触发睡眠。
- 真实25G83历史封存KC：GA35 `inputs/macos-readonly`中的Boot/System/Auxiliary KC。脚本只读取它们，通过GA35的有界Mach-O reader解析`__PRELINK_INFO,__info`，本次不写GA35。报告记录三个KC完整SHA/UUID和reader自身SHA。
- 当前EFI指GA417已经回读的封存配置，不把它说成正在运行的NixOS驱动。所有新候选均未启用。
- 原始来源固定文件与回执在`private/sources`。`python3 tools/audit-peripherals.py`核验来源SHA；`python3 -B tools/audit-platform.py`核验这里的硬件/匹配/布局结论。后者还将实际lspci **22个PCI功能逐一映射**，缺一项则断言失败；这只是覆盖检查，不是22项功能测试。

## 1. USB：两个控制器，15-port限制分别计算

| 真实PCI设备 | Linux root hubs | 软件报告的端口数 | 当前/候选路径 |
|---|---|---:|---|
| CPU `00:0d.0 / 8086:9a13` | usb1 HS、usb2 SS | 1 HS + 4 SS = **5** | 封存AppleUSBXHCIPCI没有9a13专用ID，但有`0x0c033000` generic class personality；实际attach/全口能力待macOS验证 |
| PCH `00:14.0 / 8086:a0ed` | usb3 HS、usb4 SS | 12 HS + 4 SS = **16** | 当前XHCI-unsupported只给a0ed注入AppleUSBXHCISPT、score900；不是新USB控制器实现，也不是端口map |

上述是sysfs `maxchild`，**不代表所有16个逻辑端口都已接线或在用**。PCH总数超过15，需物理确认后按该控制器保留≤15；不能把CPU和PCH共21端口压成全机15个，也不能根据“只有几个外壳插孔”忽略HS/SS各算一个逻辑端口。封存配置`XhciPortLimit=false`；本轮没有依靠开启该quirk绕过映射。

当前XHCI-unsupported的plist只有一条`0xa0ed8086`匹配，class `AppleUSBXHCISPT`，没有代码可执行文件；它不匹配CPU9a13，更不匹配NHI9a1b。真实25G83原生ICL personality列`38ed/8a13`，不是`9a13`；generic class存在说明不能用“专用ID没列出”断言完全无USB支持。不能直接把CPU9a13伪装成8a13而省略probe/start和数据传输验收。

### 可用映射方案及最小变更

固定[USBToolBox kext b9887b8](https://github.com/USBToolBox/kext/tree/b9887b8dd86f3fdbb2300b2938a902ecbc436267)可以按PCI控制器实例匹配、移除错误ACPI RHUB与旧Apple map；官方明确**不修15-port limit，也不内置完整map**。固定[tool 0c6823a](https://github.com/USBToolBox/tool/tree/0c6823a2c643a4488888938451194723dc9ae29a)仅支持Windows/macOS，不能说当前NixOS能直接运行该映射工具。

后续用户在场的最小候选：一份按两控制器实际路径匹配的map（原生AppleUSBHostMergeProperties，或USBToolBox+UTBMap二选一）；保留需要的a0ed驱动匹配。只有逐物理口采集完成才生成正式map。`UTBDefault`只是临时枚举辅助，不与最终UTBMap长期并用，也不将USBInjectAll、RHUB禁用表、两个不同map一并叠加。

当前明确内部设备：相机`0408:5349 / HS02`，指纹`06cb:00f0 / HS07`，蓝牙`8087:0026 / HS10`。这三个内部口应在最终map分别确认并标internal255；仅它们不能构成全机map。外部Type-C要分别观察USB2、USB3正反插，以及是否为一个SS switch端口还是两个独立SS逻辑端口，再决定type9/type10。Type-A按真实连接器类型，不把内置端口设成外置Type-C。

### 验证与回退

用户在场逐口插拔USB2/USB3设备、Type-C双朝向，记录真实controller/port编号与协商速度；同时确认内部三设备仍attach、USB键鼠可用、外部盘读写校验和与热拔插。最终每控制器port数≤15、无重复map、无必需口被删，才可验收。睡眠/唤醒另排用户控制试验，不在无人值守执行。

回退只移除独立新增map/USBToolBox并恢复原a0ed injector组合，保留现有独立启动镜像。没有物理外设/逐口观察时，完整map是**明确缺失输入**，本轮不编造它。

## 2. Tiger Lake集成雷电/USB4：发现原生匹配缺口，尚无完整修复

本机NHI为`00:0d.2 / 8086:9a1b`，根端口`00:07.0 /9a23`、`00:07.1 /9a25`。Linux实际绑定`thunderbolt`，正确bus sysfs路径为`/sys/bus/thunderbolt/devices`，不是早期采集用的`/sys/class/thunderbolt`。新快照确实得到：domain0 security=`none`、iommu_dma_protection=`1`，host router0-0 generation=`4`、authorized=`1`。没有下游设备和链路速率的实测；host authorized不等于外接PCIe设备已授权/隧道正常。

真实25G83封存AppleThunderboltNHI仅有两条PCI personality：

| 类 | PCI ID约束 | Class约束 |
|---|---|---|
| AppleThunderboltHAL | `0x15008086&0xff00ffff` | `0x08800000&0xffff0000` |
| AppleThunderboltHALType4 | `0x8a008086&0xff00ffff` | 同上 |

**9a1b不符合两条ID约束。** 现机lspci把它归为USB controller（0c03），也与上述system-other 0880类别不同。报告的numeric matcher只验ID部分，没有把满足匹配等同HAL支持。封存NHI映像UUID `12CDD634-0946-3FCE-89CC-3901A975E66C`已读取；本轮没有改KC或注入假的NHI class-code。

固定Linux v6.18 `nhi.c`把ICL和TGL列为不同PCI表项，**二者共享`icl_nhi_ops`**，并支持USB4 host；这提供了研究共用低层逻辑的依据，但Linux成功不能证明Apple Type4 HAL寄存器/固件mailbox、DMA rings、原生connection manager及电源状态都兼容。仅加9a1b personality、伪造8aXX或class-code不是完整修复证据。

进一步已对精确NHI UUID的十个完整symbol-bounded片段做只读反汇编；含HAL start298字节、createNHI510字节、Type4 start530字节、createNHI116字节，以及Generic/IntelPCI父类probe/start/unpoweredStart/createNHI。逐指令bytes、函数SHA、RIP符号/字符串保存在`private/nhi-function-fragments.json`，由`tools/audit-nhi.py`重现。

GenericHAL::unpoweredStart实际读取provider的**device-id到this+0x90、vendor-id到+0x94**。Type4 createNHI对该字段执行`(device-id-0x8a0d)≤0x0a`和bitset0x405检查；枚举验证仅**8a0d/8a0f/8a17**进入`AppleThunderboltNHIType4::metaClass`专用分配分支，9a1b不进入，之后经IntelPCIHAL的superclass vtable fallback。GenericHAL createNHI另引用基础AppleThunderboltNHI metaclass。尚未证明全部间接vtable目标和硬件寄存器/USB4语义，因此不把这段当绝对“不可能支持”的证明；但它进一步说明只改外层匹配plist不足以证明走了正确NHI实现。最终仍需物理雷电设备进行双向数据/热插拔验证。

已有ThunderboltReset固定9158eb1的项目说明针对AlpineRidge；通用Thunderbolt4教程主要使用离散MapleRidge卡。它们不构成本机集成TGL NHI支持，也不能据教程启用TbtForcePower或刷离散卡固件。当前没有找到对应9a1b/HP/25G83、可核验的完整HAL/USB4修复产物。

分别验收：USB-C普通USB；DP Alt Mode输出/音频；USB4/雷电router拓扑；PCIe隧道；真实下游NVMe/网卡数据；热插拔；电源恢复。前两项成功不能代替后五项。既有GA416外屏连接器和图形栈保持，不能为雷电套RPL Display13配置。任何未来独立NHI候选都应可移除回原组合；当前未生成或部署候选。

## 3. 音频：找到与真实模拟通路重叠的layout71，但有两层前置缺口

### 同机codec与真实通路

新proc原件明确：RealtekALC285 `10ec:0285 /103c:8716`，controller `8086:a0c8`；codec0地址0。当前Linux配置：

| 功能 | 实际pin/通路 | 证据边界 |
|---|---|---|
| 内置扬声器 | pin**0x17 → DAC0x03**，PinDefault90170110 | Linux当前路由，未实际播放左右声道 |
| 耳机 | pin**0x21 → DAC0x02**，04211020 | 未插拔耳机验收 |
| 外接模拟麦 | **ADC0x08 → mixer0x23 → pin0x19**，03a11040 | 不是内置SOF DMIC |
| codec内部mic pin0x12 | PinDefault40000000，当前N/A | 不要当本机内部阵列麦已连在ALC285 |
| 数字麦 | ALSA **PCM00-06 DMIC、00-07 DMIC16kHz**；SOF card | 实际PCM枚举，未录音；不等于macOS驱动 |
| 显示音频 | codec2 IntelTigerlakeHDMI `8086:2812` | HDMI1/2/3 PCM存在，未做外屏音频测试 |

### controller和layout已具体比较

固定[AppleALC ff01db2](https://github.com/acidanthera/AppleALC/tree/ff01db21749271916d44605503499ceaa61d94b2)的Controllers.plist已经列`Device=41160=0xa0c8 / Tigerlake Smart Sound Technology Audio Controller`，并有AppleHDAController补丁；所以2023教程里“必须手动device-id spoof”的说法不是当前版本的充分依据。先确认实际AppleHDAController attach，再决定是否需要额外ID处理。

ALC285资源有layout11/21/31/33/52/61/66/**71**/88，没有注释对应DragonflyG2/103c8716。71来自HP Spectre x36013-ap0xxx；**不能因为同HP就称本机支持**。但已离线解析其Platforms71，确有`[0x17,0x03]`、`[0x21,0x02]`和`[0x08,0x23,0x19]`，与本机上述三条模拟路由一致，故是比随机遍历alcid更有依据的定制起点。

71还启用本机N/A的扬声器0x14与内部mic0x12；其ConfigData重设pin配置。要么未来独立试71时逐路识别影响，要么基于实机pin定制删去不存在的路径，不能将它们当成功的第二组扬声器/内置麦。报告保存九layout的pin defaults和71的完整节点路径，未把单纯pin匹配当成功。

### 功放不应漏掉，也不应按函数名乱写GPIO

固定Linux `fcf57d0… / alc269.c:7398`把普通G2 **103c:8716**匹配到`ALC285_FIXUP_HP_GPIO_AMP_INIT`。**该版本真实函数体**是仅INIT阶段：`msleep(100); alc_write_coef_idx(codec, 0x65, 0x0)`；不是从名字推测的GPIO mask/direction/data写序列。当前proc的GPIO0/2 enabled也不构成应在macOS重放任意GPIO位的理由。

九个ALC285 layout的ConfigData都没有显式`SET_COEF_INDEX0x65`，但这只描述资源数据，**未排除AppleALC通用初始化或AppleHDA其他路径**。需要在真实codec初始化/功放失败轨迹上确认该步骤是否缺失；如需移植，保留就绪后100ms/coef65=0及恢复时机合同，而不是只把两个无延时verb追加并称完成。没有使用hda-verb对现场写寄存器。

### Tahoe AppleHDA是独立前置条件

当前封存EFI没AppleALC。对真实25G83历史Boot/System/AuxKC的fileset解析也没有AppleHDA映像。该结果与Tahoe常规AppleHDA缺失路线相符，但只代表封存时状态，不冒充今天macOS新快照。

固定[OCLP238a876 modern_audio.py](https://github.com/dortania/OpenCore-Legacy-Patcher/blob/238a876f9a08d405745ae25ef0fd563af6bc28e1/opencore_legacy_patcher/sys_patch/patchsets/hardware/misc/modern_audio.py)采用26.0Beta1 AppleHDA恢复，要求Tahoe KDK；这是一条恢复候选，不是证明HP上整套OCLP root patch可直接执行。需独立固定donor、依赖/签名/精确KC链接和原卷回退；本轮未取得/部署音频donor，不以一包AppleALC消除这个前置缺口。

完整模拟音频候选顺序：AppleHDA可用性及依赖 → Lilu/AppleALC a0c8匹配 → 真实布局/amp初始化 → 扬声器/耳机切换/模拟麦/音量/静音键 → 显示音频独立验证。回退必须同时恢复独立音频kext/config和任何未来被改的AppleHDA/KC/系统snapshot，不能只删alcid。现用KC、图形及USB均未变。

### SOF DMIC仍未找到macOS修复

数字麦走IntelDSP/SOF固件、topology及DMIC链路，不能由ALC285的模拟layout0x12替代。当前已从“Linux加载SOF”推进到真实DMIC PCM枚举，但没有找到可核验的macOS TGL SOF/DMIC完整实现。VoodooHDA常规HDA路线也不能仅凭名称覆盖DSP DMIC。外接USB麦是另一设备，不计为本机内置麦修复。

## 4. 指纹与传感器：传输协议和系统功能不能混写

### Synaptics指纹06cb:00f0

新封存libfprint官方支持表包含**06cb:00f0 / Synaptics Sensors**，说明此前“Linux也无支持”的笼统说法不成立。它是Linux用户态识别栈，不能作为macOS kext安装。搜索到同ID的EliteBook840G8 Linux配置也只是外部Linux反馈。

本轮未找到该USB协议的可核验macOS实现/HP实测。即便将来移植USB用户态识别库，也需单独实现macOS授权/登录集成，不能把它写作原生TouchID。[Apple105095](https://support.apple.com/en-us/105095)明确匹配和指纹数据属于SecureEnclave架构；这台PC没有Apple T2/AppleSilicon的对应硬件，Synaptics驱动不能补出原生TouchID配对链。**普通自定义指纹认证与原生TouchID是两个验收项，目前均未找到本机修复。** 未进行指纹注册或修改系统认证链。

### Intel ISH a0fc及十个IIO功能

新sysfs链路把十个功能全部追到`00:12.0 /8086:a0fc`后的ISHTP client GUID `33AECD58-B679-4E54-9BD9-A04D34F0C226`及HID设备`8087:0ac2/0ac3`。这些是hub暴露的接口身份，不是已识别实际加速度/ALS芯片厂牌。功能为rotation、geomagnetic_orientation、incli、accel、magn、als、gyro、relative_orientation、gravity、hinge。

Linux[ISH原始文档](https://docs.kernel.org/hid/intel-ish-hid.html)明确其传输是PCIIPC/ISHTP，**不是I2C或USB**。VoodooI2CHID的sensor-hub personality匹配INT33D0/IOHIDInterface；新GPIO支持INT34C5也不会自动成为PCI ISHTP transport。SMCLightSensor虚拟ALS仅提供Apple侧键，不会自动读取此ISH的lux；姿态、铰链和平板模式也不会由该插件一并修复。

当前缺少a0fc的macOSIPC/ISHTP+HID枚举实现、各功能数据转换，以及接到AppleALS/自动亮度/平板模式的桥接。没有找到可核验的整条实现；这是软件实现缺口，不是少一个设备ID的plist。没有读取持续传感器流或改ISH固件。

## 5. 电源、存储和其他PCI功能

- **SMC/电池读数**：当前只启用VirtualSMC，无SMCBatteryManager。固定VirtualSMC `b5c62c2…`与SMCBatteryManager源码是电池/AC上报候选；旧本机ACPI确有BAT0 `_BIX/_BST`转BTIX/BTST，BAT1 `_STA=0`，AC `_PSR`转EC0.GACS。源码ACPIBattery.cpp458行先尝试扩展BIX再fallbackBIF，并按BIXPowerUnit转换；因此不能因HP没有BIF就断言不适用。原DSDT ECRM字段**BDC/BFC/BDV/BCC/BSN/BDAT/BPR/BRC/BPV均16bit**，BTIX/BTST确实引用这些字段；固定ECEnabler `29dcde7…`支持10.7–26的多字节EC读是一条具体适配线索。最低电量候选为匹配VirtualSMC的SMCBatteryManager，实际Darwin遇到16bit EC访问错误时再核验ECEnabler；不先拆写整个DSDT。验证电量/电压/单位、AC状态/充电标记/变化通知且不重复注册BAT1，回退移除新增插件/独立候选。本项是电量/AC状态显示，不重开用户已排除的电池故障/RTC换电池路线。
- **CPU/温控**：保持既有PLUG与EC-USBX。CPUPlugin/XCPM频率/空闲驻留及传感器插件必须从macOS实际记录验收；不把SMCProcessor温度显示等同CPU动态调频，不把LinuxDynamicTuning `9a03`或Telemetry `9a0d`绑定当成macOS已有实现。没有可据以替换HP固件风扇/热管理的方案，不使用通用CPUFriend数据覆盖现有配置。
- **NVMe**：新真实path为`pci0000:00/00:1d.0/55:00.0`，Micron2210 `MTFDHBA512QFD-1AX1AABHA /HPS1022 /1344:5404`；明确没有经VMD域重映射。与此同时**VMD设备9a0b确实在当前Linux枚举并绑定vmd**，所以旧“VMD关”快照不能改写为当前整个VMD控制器不存在。不改BIOS；是否映射SSD看真实path。
- **NVMeFix候选**：固定`4862220…` README支持到26、依赖Lilu≥1.4.1，用于APST/主机活动电源管理；明确部分新系统timeout panic fix可能无效。没有证据Micron2210是本机pmap/wrong-zone Panic根因；不因“非AppleSSD”直接加force-ASPM或改APST。未来独立功耗候选验`apst`/NVMePMProxy、空闲功耗、真实I/O/错误恢复并可移除回退；本轮不做I/O压力或睡眠。
- **其余平台功能**：HostBridge9a14、SharedSRAMa0ef、CSMEa0e0、eSPIa082、SMBusa0a3、SPIflasha0a4与SSDrootporta0b0均列入22项覆盖表。枚举不等于每个都应安装专用kext；没有对应用户功能失败/依赖证据，不用SMBus触控驱动替换实际HID-over-I2C，也不以刷SPI/MEI固件修外围输入。既有平台/图形策略保持。

## 6. 下一步与真实缺口

1. 已完成离线：NHI selector的device-id来源/Type4 metaclass、AppleBacklight现用binary直接引用、SMCBatteryManager/BIX与HP16bit EC字段以及全部22PCI覆盖。NHI完整寄存器/USB4实现不是仅补plist可交付的已知修复。
2. 用户未来控制的物理macOS窗口：新I2C/GPIO事件、AppleBacklightattach与PWM合同、相机PROBE/首帧、蓝牙真实配对、模拟音频恢复/功放。只靠Linux枚举不能补这些证据。
3. 需用户在场外部输入：逐USB口/朝向/设备、雷电下游设备、实体JIS/笔/热键；准确ICC还需测色仪及固定SureView状态。
4. 仍未找到完整macOS实现：TGL集成NHI/USB4、SOFDMIC、Synaptics指纹认证、ISH十项功能及完整AWDL高级功能。不能把没有源码、没有产物或没有HP运行轨迹的部分标成“已找到修复”。

整体目标尚未完成。以上离线研究、真实Linux快照和候选审计均保存；NixOS防睡眠保持，部署/重启/休眠继续由用户控制。
