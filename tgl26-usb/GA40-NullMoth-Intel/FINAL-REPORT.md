# GA4.0 — NullMoth Intel Native Acceleration Port

> 本轮授权离线工程已完成整合。最终完整性以 `logs/seal-verification.json` / `.txt` 的实际create、双只读verify及selfhash结果为准；manifest摘要见 `manifest.sha256`。本报告不宣称真实GPU或macOS Metal加速。

## 一、结论与路线

推荐唯一主线：**复用NullMoth中可分离的Metal/AIR前端，采用Vulkan→Mesa ANV/Intel原生编译器，并建设真实i915/XNU设备/内存/提交后端**。不再把关闭全部Apple Gen11→Gen12 NF/ACC二进制翻译未知作为前置条件。

本轮已经取得实际Linux CPU代码成果：中立C接口和明确的软件Vulkan原型、精确i915 UAPI模型、真实上游Rust翻译器的LLVMIR→SPIR-V子集，以及Mesa Gen12原生命令格式的极小离线验证。**这些都不是macOS Metal硬件加速。** 真实Intel提交、显示加速、macOS Metal加速全部NOT_TESTED，硬件批准NO。

## 二、来源身份与许可

- NullMoth：`47f818b11cef59acb480210afdf9065fdd44e356`，tagv2.4.3；639 tracked文件逐个SHA，独审639/639匹配。source tree保持干净。
- 选定Intel Mesa：26.2.3 / `31e9a6b2e95e30d84bf3177d1f497d063e59b6b2`；官方GitLab和镜像tag原始refs相同；tracked文件完整清单在sources。
- NullMoth自带NVK patch基线另为 `17ca6174dcc6cb22059ac343bc29f8af7800f42e` / 26.3.0-devel（实际完整commit及VERSION响应）；与选定Mesa不能混同，未把该NVK补丁应用到ANV。
- 历史GA39只读seal入口verify通过，manifest pin `1e039df9b6dcb166f0e5a8af6b7ac925bf8c77de15334d6d8c0644852edd263e`；旧源、失败证据、报告和封存未改。

原仓库不是MIT整体：plugin/kext治理条款PolyForm Noncommercial；Rust translator LGPL-3.0-or-later；Mesa逐文件许可。NVIDIA双重/冲突头、外部AIR runtime许可Unknown分别记录，不能依据一个SPDX覆盖整库或清除外部payload。未公开分发、未上传私有捕获、未创建PR/issues。

证据：`sources/provenance.json`、`reference/nullmoth-api-inventory/`、`reference/licenses/`、`reference/mesa-licenses/file-level.json`、`reference/MESA-VERSION-DISTINCTION.md`。

## 三、真实NullMoth架构边界

1. Metal对象/command/pipeline等实现存在，但plugin是一个Objective-C translation unit，`nvmtl_vk.c`由`NVMTLDevice.m`包含；它不是可直接替换的独立C库。
2. core Buffer/Image/pipeline/command使用标准Vulkan，但设备选择依赖NVAccel/NMXAccel，默认NVIDIA；固定树未找到完整公开NMXGPU/NMXAccel实现。
3. IOSurface零拷贝走NVK私有hook和假`/dev/null` fd，不是通用Vulkan资源共享；WindowServer还依赖NVAccel共享标记/完成合同。
4. Metal事件主要是CPU NSCondition与fence等待，不是Vulkan timeline semaphore；跨进程shared event没有证明。
5. SASS/NVVM/VideoToolbox NVIDIA路径必须替换或关闭；不能用能力空实现替代。
6. NMDRM只有通用枚举类ioctl，所有i915 GEM/context/VM/submit/sync缺失；NMIntelFB只接管固件已点亮的linear framebuffer，未实现计算/3D。

逐函数、行号、分类和正控制见metal两份审计及drm/display报告。README对Sequoia/NVIDIA的声明不构成Tahoe26.6.2/9A49验证。

## 四、已运行的原型与数值

### 4.1 C中立后端与跨组件

`metal/backend-adapter/nm_backend.c/h` 提供设备/能力、Buffer/Image生命周期、命令copy/fill、submit/wait/释放。真实复用了NullMoth上传lifetime helper，测试还覆盖原sample-position helper。没有从零重写MetalAPI，也没有宣称Objective-C插件已接入。

- 显式CPU模型、直接固定Lavapipe软件ICD两后端均通过release和ASan+UBSan。
- 每次常规运行4线程256资源生命周期；独审另有8线程、双Lavapipe设备、配额、stale handle、队列顺序、注入失败等对抗控制。
- 跨组件为CPU模型backing bytes显式复制→Metal-like C facade→中立adapter→CPU/软件Vulkan→独立Python预期回读，双后端PASS。
- IOSurface、SASS、Metal设备、Intel硬件提交能力明确unsupported。Image仅创建/绑定/销毁，未实现render/共享。

证据：logs006–011、018/019及 `prototype/results/cross-component-001/`，独审 `audit/drm-safety/`。Lavapipe设备类型核为CPU，直接加载固定ICD，未走loader硬件自动发现。

### 4.2 实际Rust翻译器

原样NullMoth crate在隔离目录构建，只有Cargo.lock按实际依赖重生；8个选定AIR-dialect LLVMIR fixture真实转换SPIR-V，8个现代spirv-val通过。LLVM bitcode路径与同文本输入、重复运行字节一致。

上游integration test target **24/38通过**；其余14保留，不伪称全绿：缺外部public fixtures、源码自检、PATH以及一项真实未支持llvm.memcpy。旧validator拒绝FloatControls2是工具版本不符；现代结构验证成功也不能证明TGL支持该功能。

**没有真实Apple metallib/AIR容器、air-opt、Metal运行时或GPU语义等价验证。** 详见 `metal/translator-prototype/REPORT.md`，032为主代理实际摘要核验PASS。

### 4.3 精确UAPI模型

原样Mesa头文件C probe实录Linux x64 ioctl数字、size/align/offset，含40B syncobj_wait及deadline offset32。Python模型提供CPU BO、模拟context/VM ID、synthetic pointer arena、sync状态和错误路径；identity明确GA40_MOCK_ONLY，拒绝真实ANV设备用途。

初始015失败及修前源保留；独审后来发现VERSION非零copy长度/null指针假成功F1，真实pre-edit/diff及反例保留，修后14项通过。模型更严格的alignment/精确长度只作为自身拒绝策略，不能冒充真实Linux errno证明。

### 4.4 Intel原生编译与命令生成

实际构建了Mesa IntelCompiler的NIR、Gen、BRW、Jay四个库；没有重写编译算法，只在隔离源码副本调整Meson构建图与增加离线harness。Gen12走BRW，Jay只编译未用于该目标。

实际输入为glslang生成的compute SPIR-V，经 `spirv_to_nir → brw_preprocess_nir → driver-contract lowering → brw_compile`，按静态build table选择8086:9A49/TGL，导出208B候选（SHA256 `a4ee1b005c50977d6bd894d9839318eae0ca785172c82e28fa4ba874d18bd51f`）。另一直接NIR输入独立导出336B，不能与SPIR-V路径混同。真实编译过程中发现的lowering/payload/callback断言和补齐前提都有原日志，未关闭编译器断言。

IGA对完整208/336B在最后8B返回解码错误；200/328B前缀可解码到EOT。G2后续以固定源码与原bytes证明末8B为编译器compacted pad NOP，非遗漏真实指令；见 `intel/INDEPENDENT-AUDIT-ADDENDUM.md`。**原生Gen12候选已生成，完整IGA静态验证并未通过**；padding归因不改写完整解码exit1。G2启用assert的debug重放亦与原候选字节相同。harness只支持所选shared-memory子集，缺descriptor-set lowering，不能用于任意SPIR-V。输入是glslang SPIR-V，不是NullMoth翻译器产物，本轮未把两项成功拼称同一端到端shader链。

ANV ICD **没有构建产物**：实际Meson配置在 `CLC requires LLVM` 停止，缺可用LLVM开发/CLC工具链；并未到ANV C源码编译、ICD加载或设备初始化。Darwin隔离编译probe另因无Apple SDK/sysroot缺 `stdint.h` / `sys/stat.h` 停止。这是两个不同构建条件，不能把它们写成已经运行ANV后的i915错误。精确命令/原失败/生成二进制/IGA输出均在 `reference/intel-build/` 和两份Intel报告。

原样Mesa Gen12 genxml生成器→C pack函数已实际生成并核验8B MI_NOOP+MI_BATCH_BUFFER_END；这是**极小格式子集**，没有shader/pipeline/dispatch/资源绑定/ANV工作负载，也没有提交。详见 `prototype/vulkan/NATIVE-PACKET-REPORT.md`。

## 五、三个决策

### 决策一：Metal Plugin复用程度

- **直接复用**：小型纯C合同/数据helper（许可保留），已实际编译并做106个检查。
- **有限修改**：Metal对象/命令前端、标准Vulkan路径、Rust翻译器及反射。当前更强运行证据来自真实Rust子集，不是整个Metal plugin。
- **NVIDIA专属必须替换/关闭**：SASS/NVVM、NVK私有IOSurface导入/共享、NVRM/NVAccel内核资源与完成路径。
- **尚无法证明**：Tahoe私有MetalABI、真实AIR前端、IOSurface/WindowServer一致性、9A49实机兼容。

### 决策二：ANV macOS最早阻塞

本机最早实际ANV构建失败为CLC强制LLVM而开发链不足；Darwin target最早probe失败为无SDK/sysroot。补齐构建环境后，首先要有Darwin libdrm/节点/真实PCI shim；否则没有可供ANV识别的设备。即使具备shim，NMDRM的name=nmdrm也会被原样Mesa KMD分类函数拒绝。7个CPU原函数回放控制实证这一分支；不是ANV初始化实验。

不能改名i915骗过门禁：其后真实首i915 query为CS_TIMESTAMP_FREQUENCY，随后拓扑、GEM/tiling、context隔离等合同仍缺。第一关键内核基础是可靠设备query和GEM/映射/页所有权；再往后才是GPU VM/context/submit/sync。详见 `DEVICE-INIT-BLOCKERS.md` 和精确UAPI矩阵。

### 决策三：主线及GA41

原生路线能复用真实IntelCompiler/ANV/ISL/genxml，避开旧Gen11机器级隐式状态恢复瓶颈；并不省略Metal数值约束、资源ABI、内核和WindowServer工作。推荐GA41唯一目标：**Tiger Lake i915/XNU Probe & GEM Foundation——真实设备探测与GEM内存对象闭环**。它只规划，未实施。

## 六、审查、未实现与安全边界

G1/API许可：原三项MUSTFIX是错误compile recipe、host Vulkan header存在性、tex-upload缺SPDX的表述；初审/第一次仍有残留均保留，最终recheck002独立确认0open。G3/DRM安全：真实VERSION空copyout指针假成功F1已最小修复，另修__s64 timeout解码F2；69针对性控制和14模型测试通过，旧源码成功/修后EFAULT对照保留，0open。G2/Intel独审已完成，无MUSTFIX；独立compiler/debug/ANV失败/packet重放、扩展门禁及padding证据均保存。三轨闭环 `reports/AUDIT-CLOSURE.json` 的PASS只覆盖离线子集。

G2逐项扩展审查还确认：TGL能满足shaderInt64和bufferDeviceAddress硬要求，但RT、默认cooperative matrix及mesh不适用；应按现有optional feature协商禁用。external_memory_fd和DRM modifier虽在ANV源码advertise，仍依赖真实GEM/PRIME/dma-buf，不会变成可用于macOS的IOSurface共享。独立编译没有验证ISL surface、URB、descriptor ABI或完整3D pipeline。

真实i915内核、GPU地址/页表/context、实际提交/fence/IRQ/reset/电源、eDP/modeset、IOSurface共享/WindowServer、睡眠恢复都没有实现或实测。本轮没有部署kext、改EFI/固件/安全门禁、SSH改机、真实MMIO/Batch/Hang或受保护物理内存访问。

## 七、完整性与迁移

最终完整性回执是 `logs/seal-verification.json` / `.txt`，需实际create、只读verify、独立实现verify与selfhash一致才接受交付。源码、构建、日志、负例和审查记录均保留；Rust debug派生构建75项作无损gzip且逐项解压SHA核验，节省空间不等于删除证据。迁移需完整私有Lab及外部工具/ABI运行时，不只Git仓库；封存原件禁止重放/生成新文件。本文与state不回填自指manifest摘要，最终hash以checksum和回执为准。

## 八、16项状态（证据限定）

机读值及逐项代码、输入、输出、测试指针见 `reports/FINAL-STATUS.json`。

| 状态 | 值 | 必须同时读取的限定 |
|---|---|---|
| NULLMOTH_SOURCE | VERIFIED | 固定639源码文件，不是验证macOS运行 |
| METAL_PLUGIN_REUSE | VERIFIED_SUBSET | 真实两helper及Rust子集；整个ObjC插件未接入 |
| AIR_SPIRV_PATH | VERIFIED_SUBSET | 8选定LLVMIR→SPV+validator，不是真实metallib；24/38targets通过 |
| BACKEND_ABSTRACTION | IMPLEMENTED | 有限C资源/transfer与能力接口 |
| VULKAN_CPU_PROTOTYPE | PASS | CPU+明确Lavapipe软件Vulkan，非Intel设备 |
| MESA_ANV_SOURCE | VERIFIED | 固定12816文件与TGL路径，非ICD完成 |
| INTEL_COMPILER | BUILT | 四真实库；TGL使用BRW |
| GEN12_NATIVE_SHADER | GENERATED | 208B SPIR-V路径候选；完整IGA最后8B失败，硬件未验证 |
| ANV_MACOS_BUILD | BLOCKED | Linux CLC/LLVM开发链；Darwin缺SDK/sysroot；无ICD |
| NMDRM_I915_UAPI | MOCK_ONLY | ABI/CPU模型运行；无真实i915内核、映射/submit |
| INTEL_GPU_SUBMISSION | NOT_TESTED | 未提交 |
| INTEL_DISPLAY_ACCELERATION | NOT_TESTED | scanout源码参考不是加速 |
| MACOS_METAL_ACCELERATION | NOT_TESTED | 未运行Metal/IOSurface/WindowServer组合 |
| INDEPENDENT_AUDIT | PASS | 三轨实际独审与具体修复闭环，仅限披露的离线子集 |
| GA41_DIRECTION | Probe & GEM Foundation | 唯一规划目标，未实施 |
| READY_FOR_HARDWARE_APPROVAL | NO | 离线工作不批准实机 |

## 九、四里程碑收据与边界

| 里程碑 | 实际工件/结果 | 未实现/下一条件 |
|---|---|---|
| M1 来源与架构 | 完整commit、官方tag refs、逐文件hash/许可、Metal/Vulkan依赖、NMDRM/FB源码审计；G1三具体文档错误及重复残留独立复审关闭 | 外部AIR许可Unknown、NVIDIA混合头冲突、完整Intel私有组件未找到；不以README替代Tahoe实测 |
| M2 中立原型/UAPI | release/sanitizer双后端、跨组件独立回读；47请求组/255布局；G3原空指针反例修复，69针对性控制+14测试通过 | 仅CPU backing，真实query/mmap/VM/submit不支持；模型alignment/length策略不能证明内核errno |
| M3 原生编译/ANV | 真实Rust8fixture子集；Mesa四compiler库、SPIR-V→208B Gen12；直接NIR另有336B；Gen12 pack极小子集；ANV/Darwin真实失败日志 | IGA完整解码未过；无完整工作负载/ICD/init/submit；实际工具链与内核合同需分别补齐 |
| M4 决策与封存 | 中文三决策、新旧路线、唯一GA41、16状态；三轨独审0open；完整性以最终实际验证回执为准 | 完整性只证明交付字节，不证明Shader等义/硬件可用；完成本轮后停止 |

各命令、cwd、exit、stdout/stderr/hash由 `logs/*/receipt.json` 与相关构建manifest承载；失败输出保留原退出码，不从“报告完成”反推“所有测试成功”。例如translator24/38与IGA完整解码失败都不属于已清除的测试失败。
