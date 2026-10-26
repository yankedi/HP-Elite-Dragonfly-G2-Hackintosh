# 决策：原生Intel路线优先于GA3.9二进制翻译

## 明确推荐

**唯一主线推荐：NullMoth可复用前端 → Vulkan → Mesa ANV/Intel原生编译器 → 真实i915/XNU。** GA3.9原件保持封存；它的ISA/命令反例、消息/资源未知只作为回归参考，不再是新路线的准入前提。

这不是声称原生路线更快完成或已经接近硬件成功。它把最难的“恢复Apple私有Gen11机器级隐式语义”替换成成熟Intel用户态代码与显式内核合同的移植，架构收益更明确；真实内核工作量仍然很大。

## 对比

| 维度 | GA3.9 Gen11→Gen12二进制翻译 | GA4.0原生Intel路线 |
|---|---|---|
| 可复用资产 | Apple现成Metal/资源/显示栈，但其私有ABI、旧命令和机器码语义需完整恢复 | NullMoth对象/前端/翻译器部分实现，Mesa ANV/BRW/NIR/ISL/genxml成熟源码 |
| Shader | NF/ACC、scratch、SEND、隐式调度/线程payload等未知必须证明或拒绝 | 从SPIR-V/NIR进入真实TGL编译器，不需要先恢复Apple Gen11 NF/ACC二进制隐式状态 |
| 资源ABI | Apple跨代资源/消息/RT/URB/payload仍需恢复 | Metal→SPIR-V descriptor/reflection与ANV→Intel state各自可读源码，但仍要验证连接、内存可见性与IOSurface |
| GPU命令 | 必须翻译Apple旧命令和状态，已有真实格式反例 | 复用Intel原生命令生成器；真实设备/内存/页表/上下文仍缺 |
| Apple原驱动依赖 | 强依赖已有ICL驱动/私有状态布局 | 可减少对Apple ICL GPU执行后端依赖；Metal注册/IOAccel/IOSurface/WindowServer私有ABI仍存在 |
| 内核 | 仍需正确落地到TGL执行，并处理Apple驱动行为差异 | 需要真实i915/XNU的PCI所有权、查询、GEM/VM、Context、submit、sync/IRQ/reset/PM |
| Display/WindowServer | 已有Apple显示架构但机器代际兼容未知 | NMIntelFB只有固件scanout参考；NVK共享/完成私有hook必须替换或重新实现 |
| 安全风险 | 错译语义、命令/资源ABI不足可产生Hang或越界 | 内存/页表/submit/同步实现不足同样危险；Mock不得假装完成 |
| 本轮可运行证据 | 历史严格孤立MOV子集；四完整Shader仍拒绝 | 中立CPU/Lavapipe transfer跨组件回读、精确UAPI模型、真实Rust翻译器选定LLVMIR→SPIR-V子集；Intel编译里程碑以intel报告实录为准 |

## 还需要的独立工程组件

至少可分成七项独立验收单元，不能把源码目录数量当成现成实现：

1. Tahoe可工作的Metal设备注册/Objective-C私有ABI前端。
2. 有合法可用输入/运行时的AIR→SPIR-V链及功能交集验证。
3. 与ANV功能相符的Vulkan资源/pipeline/同步适配层，排除NVIDIA私有路径。
4. Darwin ANV/libdrm/节点/PCI/OS接口移植。
5. 真实i915/XNU设备、内存/VM/Context/提交/恢复/电源后端。
6. IOSurface跨进程共享、CPU/GPU可见性及WindowServer完成合同。
7. 显示模式/eDP/硬件VBlank、睡眠恢复和Apple驱动所有权协调。

本轮只完成其中受限离线子集和可信缺口定位，没有宣称上述任一整项全部完成。

## NF/ACC是否仍需要研究

不再需要证明“某条Apple Gen11 NF机器指令被手写lowering替换成普通GRF后是否等义”，因为不使用该转换。然而仍需验证Metal/AIR→SPIR-V数值约束、IntelCompiler选项、浮点收缩/舍入/fast-math及目标支持；原生编译器的成熟度不能替代前端语义证明。`SPV_KHR_float_controls2` 等扩展/feature也必须与目标TGL条件协商，软件验证器接受不是硬件支持证明。

## 为什么下一步不是继续扩大CPU Mock

CPU Mock、Lavapipe与小型packet pack已经足以验证当前接口的正向/拒绝/生命周期。继续堆叠模拟特性不会产生真实GEM、CPU映射、GPU页表或IRQ。按照 `DEVICE-INIT-BLOCKERS.md`，下一轮应收敛为 **真实设备探测与GEM内存对象闭环**，为原生编译产物提供合法承接基础。

本轮完成后停止，不实施GA41、不部署。三个硬件加速状态保持NOT_TESTED，批准NO。
