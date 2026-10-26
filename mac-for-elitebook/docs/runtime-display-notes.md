# HP 显示运行态：DVMT 与面板时序

补充只读观察，2026-10-16。脱敏数据与原始哈希见 [display-runtime.json](../hardware/display-runtime.json)。原始证据存于私有 capture 的 `analysis/display-followup/`，没有修改原始 62 文件的 manifest。

## DVMT / stolen memory 已有更强证据

1. Host `00:00.0` 与 GPU `00:02.0` 的 PCI config `0x50.w` 均为 `0x10c1`，只执行无 `=` 的 `setpci` 读操作。
2. 固定 Linux v6.18 的 `i915_drm.h` 定义 GMS 在 bits 15:8；`early-quirks.c` 将 Tiger Lake 匹配到 `gen11_early_ops`，其大小函数是 `gen9_stolen_size`。`GMS=0x10` 位于普通编码范围，按 32MiB 增量为 **512MiB**。
3. Gen11+ 的 base 应读 GPU `0xc0/0xc4`，不是继续沿用旧平台 `0x5c`。本机读到 `0x30800001` / `0`，掩码后 base=`0x30800000`。
4. 同次内核日志明确记录预留范围 `[0x30800000–0x507fffff]`，含首尾共 `0x20000000` 字节，即 512MiB，与 BIOS 菜单及 GMS 解码相符。

因此这台 HP **没有呈现参考实验所关注的 `0xf0+` 特殊 GMS 编码**。仍不能在未启动 Apple framebuffer 前断言 Apple 驱动绝无其他问题，但不应仅因为 CPU 同属 Tiger Lake 就先加入 `-igfxdvmt`。当前 VESA 原型没有此参数。

来源以 Linux [`7d0a66e4…/early-quirks.c`](https://github.com/torvalds/linux/blob/7d0a66e4bb9081d75c82ec4957c50034cb0ea449/arch/x86/kernel/early-quirks.c) 与 [`i915_drm.h`](https://github.com/torvalds/linux/blob/7d0a66e4bb9081d75c82ec4957c50034cb0ea449/include/drm/intel/i915_drm.h) 为准。它是固定源码解释参考，运行中的 NixOS 内核为 6.18.56，不能声称二者完全相同。

## 面板电源时序

读取现有 `i915_panel_timings`、最大 lane/link rate 与 output_bpc；不触发 retrain、force link、改亮度或重置显示器。

| Linux 选择的时序 | 毫秒 |
| --- | --- |
| panel power up | 200 |
| panel power down | 50 |
| panel power cycle | 500 |
| backlight on | 50 |
| backlight off | 200 |

单位依据固定版本 [`intel_pps.c`](https://github.com/torvalds/linux/blob/7d0a66e4bb9081d75c82ec4957c50034cb0ea449/drivers/gpu/drm/i915/display/intel_pps.c)：相关字段从 `pps_units_to_msecs` 赋值，并供 `msleep` 使用。它们是 Linux 选择后的运行态，不是可直接注入的 macOS 参数。

最大链路为 2 lane / `270000`（i915 link clock 标尺，对应 2.7Gbps/lane），最大 8bpc，与首次工作状态一致。它不证明连接器已被 macOS 驱动正确训练。

## OpRegion 与背光

本机离线解码已采集 OpRegion：`IntelGraphicsMem`，版本原值 `0x02010000`；ASLE BCLM 表为 0%→`0x19`，100%→`0xff`；扩展 VBT size 字段 `rvds=0x2200`（8704 字节）。

**不要混淆三个标尺：** OpRegion 软件亮度表、Linux `max_brightness=19200`、实际 PWM 寄存器频率/周期。它们不能直接替代 Dell `igfxtglblmax=0xAD9`。实际硬件 PWM ceiling 与 HP Sure View 切换仍待独立核实。

这些观察缩小了 HP 相对 Dell 的差异，不需要重启或触碰目标机固件；本轮未执行任何显示电源/合盖/睡醒测试。
