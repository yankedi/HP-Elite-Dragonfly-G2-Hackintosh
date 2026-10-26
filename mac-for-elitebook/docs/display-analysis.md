# Elite Dragonfly G2 显示与 VBT 分析

## 证据与方法

- 本分析来自只读采集 `.local/hardware/20261015T174049.365004Z`；解码器为 IGT `intel_vbt_decode`，intel-gpu-tools 版本 **2.3**，退出码 0。
- 原始 VBT（8704 bytes）SHA-256：`715772cebbc951aef00ddec4bc76fe571c5f4f5dc5c0c26b8171a53f6333241d`。
- EDID（128 bytes）SHA-256：`229597c3c0f0577d85202c7928c8ad4718a7624558e41afde1f8b7dce15adba5`。
- 解码 stdout SHA-256：`42c9f8c6640cd70ded81f1aab6e0fcf0c6547705da706ae8f8419ee8074681a6`；stderr SHA-256：`140281e2cde6a56386c74e01fd0bd294ed4b590f383530a650a2069cd7f2263c`。
- 已知 nixpkgs 元数据为 path pin，`narHash`=`sha256-jBYGPi4udQ9uo4KQp9m2J0546nJVQitG15gvZSaVVAs=`；没有 Git revision 记录，不推定 commit。
- 可复跑：`python3 scripts/decode_vbt.py .local/hardware/<capture> --decoder intel_vbt_decode`。脚本先调用 `verify_evidence.verify` 校验采集清单，再调用解码器；派生文本和命令记录仅写入 capture 的 `analysis/vbt/`，脱敏摘要写入 `hardware/display-analysis.json`。

## 发现

- VBT header 声明 **8571 bytes**（`0x217b`），采集文件 **8704 bytes**；尾部多出 **133 个零字节**，属于捕获尾随填充。BDB 版本为 **237**。
- VBT 将内屏 LFP1 路由记为 **DP-A / AUX-A**。子设备表还包含外部 DP/TB/USB-C 逻辑端口标记；其中 DP-D、DP-E、DP-F、DP-G 有 Thunderbolt 与 USB-C 标志。它们是固件逻辑路由记录，不能据此认定机器有四个对应的物理接口或完成物理端口映射。
- VBT panel type 为 **2**，第二 panel type 为 **3**。相应默认 LFP1/LFP2 DTD 分辨率是 **1024×768** 和 **1280×1024**；采集到的面板 EDID 首选分辨率则为 **1920×1080**。这说明默认 profile 与实机 EDID 不同，但不能单凭差异判断 VBT、固件或面板损坏。
- i915 实际观察到的显示状态优先作为运行时依据：**pipe A / DDI A / PHY A / eDP-1，1920×1080，2 lanes，2.7 Gbps/lane**。这与 EDID 首选分辨率相符。
- VBT 默认 backlight profile 报告 LFP1 PWM **1000 Hz**、最低亮度码 **6**（LFP2 为 200 Hz）。这些是表内配置值，不是已经核实的实机 MMIO PWM 设置；sysfs 亮度上限也不能替代 MMIO 读数。

## 解码限制

- 原样保留的 stderr 包含 `min size less than block size`（Block 10、20、57、253）以及四次 `Generating LFP data table pointers`。
- 解码器对若干块报告 `min size ... less than block size ...` 并生成 LFP 指针；这条 stderr 本身是“最小结构比块短”，不能反过来说这些块被截断。stdout 另有旧版块小于当前结构最小值的提示。这里保留全部诊断，不凭长度提示断言固件损坏；header、哈希、EDID 和 i915 观察可交叉验证，profile/逻辑端口字段仍按解码结果谨慎引用。
- 本记录不证明 macOS 可启动，也不证明图形加速或系统睡眠可用。
