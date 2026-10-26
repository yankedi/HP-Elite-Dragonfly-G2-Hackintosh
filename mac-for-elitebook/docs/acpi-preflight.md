# HP ACPI 部署前审阅

来源是首轮完整性验证通过的 32 张 AML 的本机独立反编译结果。DSDT SHA-256 为 `7afb4e662e79265a1a7c42c1af7ad448c003e8dbfa735b354e77dbb82f1ab343`；私有 DSL 位于 capture 的 `analysis/acpi/`。以下是静态解释，不执行任何目标机 AML 方法。

## 已能确定的 EC 行为

- 真实 EC 位于 `\_SB.PC00.LPCB.EC0`，`_HID=PNP0C09`、`_UID=1`、`_GPE=0x6e`；`_STA` 无条件返回 `0x0f`，没有可直接复用的 Darwin 分支。
- `_CRS` 为 I/O `0x62` 与 `0x66`，各一字节。还有 `P3EC` 的 `SystemIO 0x6a` 区域；不能把它误认作可随意读写的调试寄存器。
- `ERAM` / `ECRM` 是 255 字节 EmbeddedControl 区域。`_REG` 在 EmbeddedControl handler 连接时调用 `ECRI`，该方法设置 EC 状态、通知及调用其他固件方法。禁用或改名真实 EC 会影响真实固件路径，不能仅为获得名为 `EC` 的设备就套用桌面模板。
- `ECRM` 虽声明 `ByteAcc`，仍包含 32 位 `PMCD`、16 位功率/电压/电流及其他多字节字段；`ByteAcc` 不等于每个命名 Field 的宽度都为 8 位。后续电池驱动须逐方法核对实际访问和 ECEnabler 的需要。
- 本轮扫描全部已反编译 DSL，未发现现成 `Device (USBX)` 或 `ACID0001`。这是对已取得表的文本扫描结果，不是完整运行态 namespace 的不存在证明。

## 原型的处理

当前 VESA 原型仅编入已明确 CPU 路径的 Darwin-only SSDT-PLUG。真实 EC 保留，尚未注入 fake EC、USBX 或电池补丁。

部署前需要在固定 OpenCore/AppleACPIPlatform 目标下审阅 laptop fake-EC 的需求，并决定是否添加与真实 `EC0` 并存、Darwin-only 的兼容设备；不能先把 `EC0._STA` 改成零。USBX 的电源属性属于独立配置，不能据 BIOS 的显示内存值或 USB 总容量推出供电参数。

## 输入资源边界

触控板 `\_SB.PC00.I2C0.TPD0` 与 Wacom `\_SB.PC00.I2C1.TPL0` 的 `_CRS` 依赖动态 GPIO/IRQ 值。独立反编译得到的模板初始零值不等于 Linux 最终选定资源；不能把零值固定进自建 SSDT。已有 HID descriptors 和首轮 Linux 设备信息可用于后续匹配，详见 [周边分析](peripherals.md)。

`iasl -da -dl` 曾因 `AE_ALREADY_EXISTS` 失败；32 表独立 `iasl -dl` 退出 0 不消除 DSDT/SSDT6 的 namespace 诊断。这里不声称 OEM DSDT 可重编译替换，也不把离线 AcpiExec 模拟当作硬件电源/EC 测试。
