# 实机基线与证据边界

研究日期：2026-10-16（用户所在日期）；原始采集时间使用 UTC。以 `hardware/elite-dragonfly-g2.json` 的 `captured_at` 及证据哈希为准。

## 1. 已核实

- SSH、非交互 sudo 可用。目标在线运行 NixOS，不需要切换到 Windows 才能开展第一轮采集。
- DMI：`HP Elite Dragonfly G2 Notebook PC`，`SBKPFV3`，主板 `8716`，BIOS `T90 Ver. 01.25.00`，日期 `06/05/2026`。
- CPU：family 6、model 140、stepping 1，i5-1135G7，4 核 8 线程。
- SMBIOS：8 个板载 2048MiB 器件，Samsung `K4UBE3D4AA-MGCR`，type 30（LPDDR4），4267MT/s。LPDDR4X 电压子类型未另测。
- GPU：`0000:00:02.0`，`8086:9a49 rev 01`，子系统 `103c:8716`，Linux i915 旧采集报告 B0、80EU、5 subslice；后续独立运行态观察为 80EU / 10 subslices（见 [当前状态](../configs/install-preparation.json)）。GPU 空闲时的 Enabled EU=0 不表示物理 EU 缺失。
- 内屏 EDID：IVO8596，型号字符串 `X133NVFF R0`，1920×1080，138.8MHz pixel clock，约 60.0097Hz。
- i915 工作配置：pipe A / DDI A / PHY A，eDP-1，2 lane，每 lane 2.7Gbps。HDMI 和外部 DP 当时未连接，无法据此确认外接线序。
- VBT 8704 字节；已取得 EDID、VBT、IGD opregion、触控板/触屏 HID report descriptor 原始文件及 SHA-256。
- `/sys/class/backlight/intel_backlight/max_brightness=19200`。这是 Linux 背光接口的标尺，不直接等于 Dell 补丁的 PWM MMIO 最大值。

## 2. 存储与 BIOS

Micron 2210 `MTFDHBA512QFD-1AX1AABHA`，PCI `1344:5404`，固件 HPS1022。SMART：critical warning=0、media errors=0、percent used=13；兼容性仍需 macOS 验证。

PCI 中存在 VMD `8086:9a0b`，但 SSD 路径为普通 `00:1d.0 → 55:00.0`，HP BIOS 的 `Configure Storage Controller for VMD=Disable`。不能因为看到 VMD 控制器就要求切换存储模式。

内置 476.9GiB 磁盘存在 NixOS btrfs、NTFS、其他 EFI/ext4/swap 分区，未发现可直接宣称可用于安装的空白区域。没有挂载 NTFS 或改变分区，Windows 启动状态与 BitLocker 状态未验证。

| 设置 | 当前值 | 后续判断 |
| --- | --- | --- |
| UEFI Secure Boot | Enable | 首次外部启动前另行确定策略；与 OpenCore `SecureBootModel` 不同 |
| Fast Boot | Enable | 首轮调试可由用户手动关，记录恢复值 |
| VMD storage mapping | Disable | 保持，不做无依据切换 |
| Video Memory Size | 512 MB | 保留；另记录 GGC 原值 `0x10c1` |
| VT-x / VT-d | Enable / Enable | VT-x 保留；先分析 DMAR 与 OC quirk，不默认关闭 VT-d |
| USB Storage Boot / Thunderbolt | Enable / Enable | 保留；不等于已完成 macOS USB/TB 适配 |

本轮没有写过这些选项。用户表示可手工改 BIOS，但没有授权远端自动重启或自动写固件。

后续只读补充已将 GGC、Gen11+ BDSM 与内核预留范围交叉确认为 512MiB，另取得面板运行态时序和 OpRegion 表；详见 [运行态补充](runtime-display-notes.md)。这是带独立时间及哈希的新证据，不改写首轮 capture。

## 3. 输入、USB、音频

| 设备 | 实机标识 / 路径 | 适配含义 |
| --- | --- | --- |
| 键盘 | i8042，AT translated set 2 | PS/2 路线；JIS 特殊键需后续按键验证 |
| 触控板 | `SYNA30B6`，`06cb:cd74`，`\_SB.PC00.I2C0.TPD0` | HID over I²C，先研究 VoodooI2C + HID，不按 SMBus/PS2 触控板猜配置 |
| 触屏 / 笔 | `WACF4233`，`056a:4924`，`\_SB.PC00.I2C1.TPL0` | Wacom I²C；不能由触控板可用推断触屏/笔可用 |
| Wi-Fi | AX201 `8086:a0f0` | Tahoe 驱动版本与安装环境网络需独立验证 |
| 蓝牙 | `8087:0026`，XHCI HS10 | 内建 USB 端口，最终映射为 internal |
| RGB / IR 摄像头 | `0408:5349`，HS02，4 个 USB 接口 | UVC 与 IR/生物识别体验分别验证 |
| 指纹 | `06cb:00f0`，HS07 | 不作为首轮验收条件 |
| 音频 | ALC285 / `10ec0285` / `103c8716` | 需 HP GPIO 放大器初始化；SOF/DSP 数字麦克风另列问题 |

**现有 USB 清单仅是已插入设备的快照，不是完整 USB map。** USB-A、两侧 USB-C、USB2/USB3 companion、Type-C 翻转和 Thunderbolt 外设尚未逐口测试，不能据此生成最终 USBPorts.kext。

## 4. ACPI 读出与解析

- 原始采集：DSDT 261046 字节，23 张静态 SSDT，8 张动态 CPU SSDT；另含 DMAR、NHLT 等白名单表。未采集 MSDM、SLIC 或整个 NVRAM。
- `iasl 20260930 -da` 一次性共享 namespace 解析失败：HP 条件定义出现 `HS02._S0W` 重名，动态 CPU 表亦有重叠。
- 保留原表不改字节，改用每表独立 `iasl -dl`，32 张 AML 均输出 DSL，退出码均 0。
- DSDT 仍有 `ECMX/ECRG/PSCF/BCSC` 父路径解析和 external 冲突警告，SSDT6 有 namespace 诊断。日志保留在私有 capture；**不能将成功输出 DSL 描述为完整 namespace 已验证或可直接重新编译固件 DSDT**。
- 触控板 `_INI` 将 I²C 地址设为 `0x2c`、HID descriptor 地址设为 `0x20`；GPIO/IRQ 由 `GNUM(GPDI)` / `INUM(GPDI)` 动态求值。资源模板中的 `0x0000` 占位值不是可照抄的实际 GPIO pin。
- 触屏基本对象在 DSDT，HID 和资源方法主要补充于 SSDT17（INTTPL）。I²C 地址、HID descriptor 地址由 TPSA、THHA 等固件变量设定，需 runtime 资源与报告描述符交叉确认。
- 平台 namespace 使用 `\_SB.PC00`，不是随意套用的 `\_SB.PCI0`；CPU、电池、EC、图形及输入 SSDT 的路径必须按实机核对。

## 5. 电池与传感器

- 电池设计值 7.3Ah × 7.7V ≈ 56.21Wh；charge full 6.864Ah，cycle count=64。按设计电压换算是估算值，不是放电实测。
- Linux 可见 `[s2idle] deep`，当前选择 s2idle；没有执行休眠或唤醒测试，不能推断 macOS S3 可用。
- ISH 枚举 incli_3d、dev_rotation、magn_3d、als、accel_3d、gyro_3d、geomagnetic_orientation、gravity、relative_orientation、hinge 共 10 个 IIO 设备。
- `LSM6DSOX/LIS2MDL`、1000-nit、Sure View Reflect、HP Active Pen G3、日版 SKU、无 SIM/WWAN 等补充保留为用户资料；其中未由当前日志独立确认的项目不升级为实测结论。

## 6. 本机 U 盘

Lexar USB Flash Drive，USB `21c4:0809`，约 116.1GiB（128GB 级），现为 MBR / Ventoy：约 116GiB exFAT（用户卷标已从公开副本删除）+ 32MiB FAT `VTOYEFI`，采集时均未挂载。

后续使用 UDisks 非交互授权 **只读挂载**，通过 findmnt 核实 VFS 与文件系统均为 `ro` 后读取容量，并正常卸载：exFAT 文件系统约 116.03GiB，已用约 23.63GiB，**可用 92.40GiB（99,215,736,832 字节）**。没有请求密码，没有改动文件、Ventoy EFI 或分区。容量足够制作安装资料；实际启动集成与安装目标仍需单独解决。

既有 Ventoy EFI 分区属于 Ventoy，不能默认拿它覆盖成 OpenCore。保留数据条件下的启动介质方案、实际可用空间及最终 macOS 安装目标是后续部署前的独立门槛。
