# GA43 验收分级（最终结论以 FINAL-REPORT / receipt 为准）

| 等级 | 已有实证 | 不能推导 |
|---|---|---|
| HOST_COMPILE | 新VM、GEM/client、libdrm生产源码在Clang21警告为错误下编译 | 不等于Darwin API/ABI正确 |
| DARWIN_CROSS_COMPILE | 新VM、三core及受布局影响Service是真x86_64 Mach-O | 不等于模块/dylib |
| DARWIN_LINK | 九真实单元-r组合为MH_OBJECT；诊断dynamic_lookup dylib带Undef binder | 严格用户dylib未通过；不是ANV/kext |
| XNU_MODULE_LINK | 实际-kext尝试FAIL：旧LLD不识别；真实kernel imports保留 | 无可加载驱动 |
| CPU_SANITIZER | 新VM生命周期、cookie映射及原Linux请求转换的相关目标PASS | memfd测试不是XNU runtime/GPU residency |
| DRM_TRANSPORT_TEST | 标准mmapoffset/kernelclient代码与注入syscall的Linux→BSD合同验证 | native fd/pager/用户IOConnect未接通，整体PARTIAL |
| XNU_RUNTIME | NOT_TESTED | 未加载、未安装、未改安全策略 |
| GPU_EXECUTION | NOT_TESTED | 未写MMIO/页表、无batch/engine/IRQ/完成证据 |
| METAL_ACCELERATION | NOT_TESTED | 前端存在与厂商分支不等于Compute成功 |

## 七项直接答案

1. `libvulkan_intel.dylib`：**没有**。真实用户SDK/libSystem/libc++及现代linker缺失，ANV gate实际exit2。
2. 真实链接XNU内核驱动：**没有最终驱动模块**；只有实际-r组合链接单元，格式MH_OBJECT，不是MH_KEXT_BUNDLE。
3. 目标Tahoe25G83运行：**没有，NOT_TESTED**。
4. ANV初始化：**没有，NOT_TESTED**。生产nmdrm身份仍不被原Mesa i915选择器接受，未谎报。
5. Intel GPU命令：**没有，NOT_TESTED**。
6. Metal Compute：**没有，NOT_TESTED**。同来源shader新桥接还遇真实SIGSEGV。
7. 硬件实验准入：**未达到**。GPU可见内存/隔离、页表、执行、IRQ/可靠fence、超时恢复和目标ABI/transport均未闭环，本轮也未授权硬件动作。

## 第一次真实GPU Compute最短剩余依赖链

1. 私下提供合法完整macOS用户SDK（stdlib、libSystem/libc++、Frameworks、tbd）、
   现代Darwin linker或其完整离线源/构建依赖；核对来源和hash，重跑五个严格探针。
2. 真正链接ANV Mach-O ICD和Darwin libdrm，确认exports/installname/rpath、系统/C++依赖，
   无LinuxELF污染；同fixture补齐descriptor/push lowering，不将gdbexit0算shader成功。
3. 取得25G83匹配的合法kernel ABI/exports输入（精确KDK或等价匹配资源），用支持kext
   输出的linker产生可检查模块，检验所有imports、C++vtable及KC约束；不能用用户SDK替代。
4. 完成并验证native fd→每openclient→standardioctl/mmapcookie→XNU memory通路，
   包括任务认证、fd复用/dup/fork、嵌套指针、close/death/detach及映射撤销；保留真实身份。
5. 原生运行验证通过后建立真实GPU可见BO、cache/DMA一致性、隔离GGTT/PPGTT、
   Context与residency；ANV实际要求的syncobj/timeline、engine与exec对象合同必须完整。
6. 可靠IRQ/fence、超时/复位/错误传播闭环后，再另获明确硬件授权，执行一个有界Compute
   并检查结果；此前不得触发batch。
7. 将同一PCI实体的NMX claim/Accel/plugin/VkDevice/Queue/Buffer贯通，最后验证Metal
   Compute输入输出；不通过注册伪claim提前显示Metal能力。

这些是前置依赖，不是自动执行队列；未授权下载、目标机操作与GPU状态保持原边界。
