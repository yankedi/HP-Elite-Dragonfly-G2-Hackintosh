# G2 独审整合补充（不改已审原报告字节）

本补充与 `GEN12-COMPILER-REPORT.md`、`ANV-BUILD-REPORT.md` 和 `audit/intel-anv/AUDIT.md` 一并读取。原报告/manifest保留独审固定SHA，真实修前版本、149行diff和修后SHA在 `reference/intel-build/repairs-001/`。后续新增证据不反写初始“未知”观察。

## 已解决的8B尾部身份

G2以现有二进制与固定源码证明，两候选最后8B都是 `60 00 00 20 00 00 00 00`，即 `0x20000060 0x00000000`，来自 `gen_compacter` 构造的compacted pad NOP（`gen/gen_compact.cpp:1442–1445,1579–1585`；NOP opcode `brw/brw_eu.c:255`）。200/328B前缀皆为8 mod16，追加pad后208/336B按16B对齐。原报告中“末8B原因未解决”的观察由这项后续证据补充为**编译器padding**。

这不改变实际完整IGA命令exit1，也不升级为完整静态验证：只保留“非padding指令前缀解码到EOT通过、full-file IGA部分完成”。实物 `audit/intel-anv/{IGA-TAIL.md,probes/iga-tail/result.json}`。

## 编译子集边界与独立重放

G2的release和启用assert的debug重放都逐字节复现208/336B；另一个shared-memory shader产生不同192B输出，排除固定输出假实现。零`anv_`符号、无Vulkan loader、strace无ioctl/无`/dev/dri`。所有四compiler archive及11manifest工件重新匹配。

harness没有ANV descriptor-set lowering：另一storage-buffer SPIR-V在debug报 `unknown intrinsic: vulkan_resource_index`，release fault。**仅选定shared-memory probe可运行**，不能把该CLI作为任意SPIR-V通用编译器；本轮不扩写完整ANV lowerings。

## 扩展/资源门禁

`audit/intel-anv/EXTENSION-GATES.md`给出16 device+3 instance逐项门禁。TGL可满足shaderInt64及bufferDeviceAddress这两个本路径硬要求；RT/ray query、默认cooperative matrix不可用，mesh也不可用。NullMoth枚举到才启用的optional路径应关闭；Linux DRM modifier/external-memory-fd虽在ANV表中advertise，在NMDRM上无GEM/PRIME仍不可用，更不等于IOSurface共享。诊断layer设置由loader/layer提供，不是ANV硬件特性。

编译结果不证明ISL surface布局、URB、descriptor ABI、3D pipeline或资源可见性；这些没有被本轮编译测试覆盖。

## 一项非门禁引用纠正

UAPI矩阵中对 `has_get_tiling(fd)` 的调用行引用 `i915/intel_device_info.c:620` 应读为 **`:616`**；`:620`是后续caching字段。GEM探针先于context isolation的顺序结论正确，47组请求表不变。为保留G2审查时字节，原矩阵不反写；本补充是该行引用的明确更正，源码仍是依据。

G2结论：无MUSTFIX；ANV实际配置失败、Darwin缺SDK、真实内核缺口不变。三轨闭环见 `reports/AUDIT-CLOSURE.json`；硬件批准NO。
