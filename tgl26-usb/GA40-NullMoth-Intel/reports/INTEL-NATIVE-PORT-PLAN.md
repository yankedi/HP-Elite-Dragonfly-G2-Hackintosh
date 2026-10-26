# Tiger Lake 原生 macOS 驱动实施路线（离线规划）

目标设备：HP Elite Dragonfly G2 / i5-1135G7 / Intel8086:9A49，Gen12.0 Xe-LP，x86_64 Tahoe26.6.2/25G83。本轮源码审计/CPU测试不是该机器上的兼容性验证。

## 1. 唯一主线

采用 **NullMoth可复用Metal/AIR前端 → 标准Vulkan子集 → Mesa ANV/IntelCompiler → 真实i915/XNU设备与内存/提交合同**。不再把关闭 Apple Gen11 NF/ACC 二进制翻译未知作为本路线前置条件。GA39只作为历史ISA/命令格式/资源错误的回归参考，不改历史交付。

## 2. 组件边界

| 层 | 可复用资产 | 必须实现或重新验收的内容 |
|---|---|---|
| Metal入口/对象 | NullMoth Objective-C实现作为有限修改基础 | Tahoe私有MTL/IOAccel ABI、设备注册、错误及生命周期；当前未在Linux构建整个plugin |
| AIR/Shader接口 | 原Rust AIR/LLVM→SPIR-V翻译器与反射/descriptor ABI | Apple外部air-opt/LLVM运行时及真实metallib输入，翻译器输出的功能与TGL支持交集 |
| Vulkan资源/命令 | 已运行的CPU/Lavapipe中立transfer子集，原插件标准Vulkan路径 | 接回真实前端；能力和feature协商、渲染/计算pipeline、资源可见性，不使用NVK私有假fd导入 |
| Intel用户态 | Mesa ANV/BRW/NIR/ISL/genxml原生实现 | Darwin构建、libdrm/节点/PCI shim和OS同步/映射接口 |
| Intel内核 | Linux i915的设计与UAPI是参考 | XNU PCI所有权、设备信息、GEM、VM/页表、context、submit、IRQ/fence/reset/PM |
| 显示/共享 | NMIntelFB固件linear scanout参考 | eDP/modeset/硬件VBlank、IOSurface内存与跨进程同步、WindowServer完成合同 |

## 3. 按真实依赖推进

1. **设备探测/内存合同**：Darwin libdrm枚举/PCI与版本、真实i915 query、GEM对象及CPU映射。未具备i915行为前不把nmdrm改名i915。现有Mock只检验布局/错误/状态。
2. **地址空间/Context**：GPU页表、GGTT/PPGTT及GTT大小、对象驻留/缓存一致性、context隔离与销毁。模拟VM标识不能变成“已分配GPU地址”。
3. **可恢复提交**：明确PCI控制权、必要初始化/固件、RCS引擎、interrupt、同步对象和reset。必须在提交前具有有界失败/恢复及电源管理方案，不能靠ioctl返回0穿透。
4. **独立Compute验收**：用户另授权后才可能进行真实IntelGPU计算与确定性回读。CPU/软件Vulkan结果不能替代。
5. **Render及共享验收**：shader/pipeline/surface布局完整组合、真实render回读，再到IOSurface跨进程可见性和WindowServer；最后才可能说Metal硬件加速。
6. **系统完整性**：显示切换、睡眠/恢复、reset后资源生命周期及Apple现存驱动竞争，都有独立验收，不借桌面能显示宣称通过。

## 4. XNU内核必须有的具体能力

PCI设备只能由明确的所有权方案控制；需确定与AppleIntelICLGraphics/Framebuffer/WhateverGreen的匹配、BAR、IRQ、电源资源竞争。此处不授权卸载、替换或禁用任何现有驱动。

GGTT/PPGTT不是普通用户虚拟内存；CPU BO backing不是GPU可见映射。必须有页固定/所有权、缓存域、页表生命周期及故障回收。GEM create/close、CPU mmap、GPU VM、context、batch引用和同步点必须共享一致对象模型，防止close后GPU仍访问。

GuC/HuC/GSP不能混称：NVIDIA GSP实现不适用于Intel；Tiger Lake i915的具体提交方式、固件/认证/电源依赖应依据所选内核配置决定，不能假定一律需要或一律不需要GuC/HuC。reset、IRQ、runtime PM和系统睡眠均非本轮已实现能力。

## 5. 三种成功必须分开

- **DISPLAY_ONLY**：固件已点亮linear framebuffer，CPU写scanout。NMIntelFB静态设计属于此层；本轮未部署/实测。
- **COMPUTE_ACCELERATION**：真实Intel计算执行、真实Fence完成、独立正确结果回读。
- **RENDER_ACCELERATION**：真实图形渲染、资源ABI、IOSurface共享及WindowServer组合正确。

本轮三个实机状态均NOT_TESTED。后续任何硬件试验都需要新的明确许可和独立批准，`READY_FOR_HARDWARE_APPROVAL=NO`。

## 6. 边界与投入

成熟Intel编译器和命令生成器可以复用，不能因此省掉真实内存/提交/同步后端。NullMoth最难替换的NVIDIA耦合集中在NVK私有资源导入、NVRM/NVAccel共享与完成、SASS/NVVM路径；相对独立的Metal对象和Rust翻译器仍有显著复用价值。具体实际构建/编译结果以 `intel/` 报告和独立审计为准。

下一工程收敛目标见 `GA41-NEXT-STEPS.md`；本文件只是规划，不执行GA41或硬件实验。
