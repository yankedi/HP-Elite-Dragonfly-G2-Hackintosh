# GA43 NullMoth Intel 连续链与单来源Shader试验

## 固定前端与身份

四份 `nullmoth/patches/0001..0004` 原样继承；本轮未改前端、重建翻译器或重复
已通过的vendor/冻结/loader合同测试。继承seal验证涵盖其来源，最终清单涵盖字节。
Intel8086→ANV、AMD1002→RADV、NVIDIA10de→NVK及跨厂商拒绝仍为源码合同，
不是本轮原生运行结果。

固定NullMoth `47f818b11cef59acb480210afdf9065fdd44e356` 源码读到：

| 连续节点 | 实际位置与前提 | 当前缺口 |
|---|---|---|
| Intel PCI claim→NMXAccel | `kexts/NVRM/accel/nvrm-accel.cpp:560-589`，NMX模式需8086/1002显示设备且`nmxgpu-claimed=true` | GA43 diagnostics并未拥有GPU，不设置claim，不注册伪加速服务 |
| NMXAccel→Metal plugin | 同文件614及`kexts/NVRM/accel/Info.plist:37-38`，plugin `NVMTLDriver`、class `NVMTLDevice` | 无目标注册/加载证据；厂商级选择不能证明同一PCI实体 |
| Device→Vulkan device | `plugin/nvmtl_vk.c:971`实际`vkCreateDevice`，patch冻结厂商和ICD选择 | 本轮无Darwin ANV dylib，不能创建VkDevice |
| Metal Queue | `plugin/NVMTLDevice.m:631-638`调用`nvmtl_vk_init`和command-pool创建 | 无真实VkDevice/queue和内核context |
| Metal Buffer | 同文件642-661及`plugin/nvmtl_vk.c:1323`实际CreateBuffer/AllocateMemory路径 | CPU GEM backing不等于Vulkan/GPU buffer |
| Submit/完成 | `plugin/nvmtl_vk.c:5735`实际`vkQueueSubmit`；ANV `i915/anv_batch_chain.c:697-766` | 无GPU页表、执行/IRQ、fence/timeout/reset；禁止触发 |

不得只给GX42Service增加plugin/claim属性来跳过这些依赖。还需将registry PCI身份、
render设备PCI身份和ANV物理设备匹配为同一GPU，目前没有运行证明。

## 单一合法已有fixture

使用GA40已经封存的NullMoth仓库内AIR-dialect LLVM IR `sp1.ll`；不是新下载SDK内容。
本轮复用原翻译输出SPIR-V和原已编译Mesa工具，不改GA40、不重复旧翻译/构建。

| 阶段 | 路径（GA40根下） | SHA256 / 状态 |
|---|---|---|
| AIR-dialect文本 | `metal/translator-prototype/fixtures/ll/tests/fixtures/leaf_memcpy/sp1.ll` | `f06b92ae9426488958b9bc5c1b7038fc487e87610ac9f9dd503ec6bf539b3799` |
| 原NullMoth translator | `build/translator-release/release/metal2vulkan` | `a12927a38538f0708aa47d9bcf99c7019bf8564f9f300cc627a392703c763486`，LGPL-3.0-or-later |
| 既有真实SPIR-V | `metal/translator-prototype/results/run-001/spv/sp1.spv` | `29ae2dafd0c86bc84a3663f6b0c2a2a03da96ec94853ac1fafb4ae6507efb3b9` |
| 原固定Mesa compiler harness | `reference/intel-build/bin/intel_gen12_compile` | `a20848cfb5435bcf9d9aaceb8cba95e1133f3edae91783d6f1d4492cf605c1e7` |
| Gen12输出 | GA43 `artifacts/shader-chain-001/` | **无输出，实际SIGSEGV** |

`shader-fixture-integrity-002` hashes和`spirv-val --target-env vulkan1.2` exit0。
001因初始ll路径拼错exit1，原日志保留，不作为validator结果。
SPIR-V1.4具备Shader和Int64能力、GLCompute `main`、set0 bindings0/1/2/3的
StorageBuffer以及48字节dispatch-region push block；必须提供匹配的descriptor
layout、buffer范围和push ABI、shaderInt64与workgroup设置。不是无资源空kernel。

新增跨组件实验 `nullmoth-intel-single-fixture-001`：真实原Mesa工具读取此SPIR-V，
结果exit **-11 SIGSEGV**，无Intel二进制。关闭core、禁shader cache，无设备打开。
`nullmoth-intel-single-fixture-backtrace-001`保留gdb栈：
`brw_builder::fix_unsigned_negate → brw_from_nir_emit_block → brw_from_nir → brw_compile_cs`。
gdb进程exit0只是诊断命令成功，shader依然FAIL。

原harness只有spirv_to_nir、brw_preprocess_nir、少量CS/shared lowering；固定ANV
`anv_shader_compile.c:1450,1571,2107`还有真实pipeline-layout、push-layout与最终
compile准备。缺少这一集成路径是有证据的差异，尚不能断定为唯一崩溃根因。
不篡改官方编译器、删除资源或替换为另一条已成功shader来掩盖该失败。
完整shader链目前PARTIAL/FAIL，需要在真实ANV编译合同中补齐descriptor lowering
及其资源接口，之后复验该同一输入。无metallib容器/runtime或GPU/Metal成功。

## 从ANV反查内核最短功能合同

固定Mesa `src/intel/vulkan/i915/anv_device.c:100,118`要求真实exec fence array/
timeline能力，285-311创建context，412-420创建VM；不能仅因本轮host VM表存在就
返回这些能力。`anv_batch_chain.c:523-580`组装exec对象与timeline wait/signal，
697后走真实exec。GA43仍拒绝相应硬件能力；实际fence同步、residency/cache、
IRQ/reset没有后端，不应通过预先signaled CPU计数器满足探测。
