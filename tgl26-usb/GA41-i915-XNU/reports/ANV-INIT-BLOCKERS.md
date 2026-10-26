# ANV/i915/XNU 调用合同与下一处真实阻塞

所有Mesa行号指固定26.2.3，Linux指本轮v6.18。下述调用顺序由实际源码确定；
只有标注CPU执行的项目有运行证据，没有macOS ANV或硬件运行。

## 现在最先失败在哪里

1. 本轮实际Linux ICD生成了，但未运行Vulkan枚举，更未把Darwin shim链接进该Linux ICD。
   完整Darwin ANV dylib尚未生成，因此不能报告“实机运行到函数X”。
2. 若是原样Darwin无libdrm fallback，`vk_instance.c:418`调用`drmGetDevices2()`，
   其fallback失败会令应用看到`VK_SUCCESS/count=0`。
3. 新shim能在**注入CPU系统调用**中枚举真实形状的NMDRM数据；尚无macOS实际节点验证。
   假设实际NMDRM节点和shim均工作，下一个确定拒绝是
   **`intel_get_kmd_type()` (`src/intel/dev/intel_kmd.c:31–51`)**，
   nmdrm仍不是i915/xe。此函数本轮确实原样CPU编译执行，拒绝结果已验证。
   `intel_get_device_info_from_fd()`失败→`anv_physical_device_try_create()`内部
   `VK_ERROR_INCOMPATIBLE_DRIVER`，枚举循环跳过，可能最终对应用`SUCCESS/count=0`。
4. 将来有完整可信i915身份后，第一个i915专用缺口仍是
   `src/intel/dev/i915/intel_device_info.c:567`的CS_TIMESTAMP_FREQUENCY，
   紧接真实fuse/topology；不是先跑到execbuffer。
   不允许改名i915来跨过这个门禁。

新GEM切片没有接入现有NMDRM，不改变上述顺序，也不把memfd页当硬件查询数据。
timestamp、fuses、engine、GTT、isolation均不能填“看起来正确”的TGL常数。

## 逐层合同

`init`表示原样ANV物理/逻辑初始化依赖，`first`表示首次compute真正需要。
“硬件”是验证最终能力是否需要真实GPU；纯CPU可先验证结构/失败路径。

| 功能 | 真实Mesa入口 | Linux v6.18入口 | XNU承接设施/合同 | init / first / 硬件 | 本轮状态 |
|---|---|---|---|---|---|
| DRM身份/PCI/open | vk_instance枚举；anv_physical_device_try_create；intel_get_device_info_from_fd | drm_ioctl/VERSION；drm_file；i915_driver_open | devfs fd、IOPCIDevice身份、可靠per-open、ioctl/copyin/out | 是/是/身份实测需 | shim CPU测试；真实平台未运行 |
| Device Query | intel_i915_get_device_info_from_fd、intel_i915_query_alloc | i915_getparam_ioctl；i915_query_ioctl:597 | 真实已初始化GT数据、受控query快照/两阶段长度、EFAULT | 是/是/是 | 未实现，ENOTTY；不假数据 |
| GEM backing/create/close | dev/i915 has_get_tiling探针；vulkan/i915 anv_kmd_backend create | i915_gem_create_ioctl:224；drm_gem_handle_create/delete | IOBufferMemoryDescriptor、引用/handle表、quota、zero | 是/是/CPU可先 | 两原样编排函数＋新OS切片；CPU页闭环；原生源码编译证据单列 |
| CPU mmap/cache coherence | anv_i915_bo_map→GEM_MMAP_OFFSET→mmap | i915_gem_mmap_offset_ioctl；i915_gem_mmap.c | IOMemoryMap或cdev pager、真正task权限、cache/domain合同 | 部分/是/GPU coherency需 | gx_map原生source＋CPU测试；无ANV mmap-offset transport |
| GGTT | ANV不直接写GGTT；GTT/aperture/context探针依赖内核 | gt/intel_ggtt.c ggtt_init_hw | PCI资源所有权、受控MMIO、PTE/TLB、映射撤销 | query准备/是/是 | 未移植，不访问寄存器 |
| PPGTT | anv_i915_device_setup_vm:412、setup_context:268 | i915_gem_vm_create_ioctl:1807；gt/gen8_ppgtt.c gen8_ppgtt_create | 真实DMA页地址、页表页、隔离、TLB、销毁顺序 | logical/是/是 | 未实现 |
| GPU VA / softpin | ANV VMA allocator、anv_batch_chain exec object offset | i915_vma_pin；execbuffer eb_pin_vma | 每VM VA区间/溢出/别名验证、pin引用、DMA residency | logical/是/是 | gx_gpu_bind明确EOPNOTSUPP |
| GEM Context | anv_i915_device_setup_context→intel_gem_create_context[_engines] | i915_gem_context_create_ioctl:2365 | per-client/context所有权、engine map、上下文隔离 | 是/是/是 | 未实现 |
| Object Binding | anv_i915_bo_alloc/execbuf object list | gem/i915_gem_execbuffer.c eb_pin_vma；i915_vma.c | VM bind/unbind、页保活、cache sync、失败回滚 | 部分/是/是 | 无GPU-visible BO |
| Engine | engine info query和anv_i915_set_queue_parameters | intel_engine_setup；gt/intel_engine_cs.c | 电源、PCI/IRQ、ring、HW context、真实RCS | query/是/是 | 未初始化；不伪造engine query |
| Execbuffer2 | i915/anv_batch_chain.c→intel_ioctl(EXECBUFFER2) | i915_gem_execbuffer2_ioctl:3568 | copied object/fence数组、softpin、batch校验、驻留、submit事务 | capability探针/是/是 | BSD dispatcher拒绝ENOTTY；gx_exec拒绝EOPNOTSUPP |
| Fence | anv_i915_physical_device_get_parameters:75–128要求fence array等；队列提交 | i915_request.c i915_request_add:1844；dma_fence | 完成/错误/取消状态、不允许CPU提前signal、BO最后引用 | 是/是/是 | 未实现 |
| Syncobj | vk_drm_syncobj_get_type及create/wait/destroy探针 | drm_syncobj.c drm_syncobj_create_ioctl/handle_to_fd | 真实fd资源、引用/跨进程、CPU wait及错误语义 | 是/是/软件管理可先，GPU完成需 | 未实现；无能力声明 |
| Timeline Wait | vk_drm_syncobj.c timeline wait/transfer/query | drm_syncobj_timeline_wait_ioctl:1389 | deadline、单调point、阻塞/唤醒、丢设备错误 | 是/是/最终需 | 未实现 |
| dma-buf / sync-file | i915_gem_supports_dma_buf_sync_file（common/i915/intel_gem.c:317–366）；anv_device:124–128硬检查 | drm_prime.c、drivers/dma-buf/dma-buf.c、sync_file.c（后两者在保留完整archive中，未解出） | fd导入导出、共享页与fence依赖、close/revoke | 是/是/管理可CPU，GPU完成需 | PRIME标量0保持；没有fake fd |
| GPU Completion | queue submit→syncobj wait/readback | intel_breadcrumbs、i915_request_completed | 完成序列号来源、内存屏障、GPU写回可见、等待超时 | capability/是/是 | 未实现 |
| IRQ | 无直接用户调用；所有completion依赖内核 | gen11_gt_irq_handler:169（用于Gen11+路径） | IOInterruptEventSource/IOWorkLoop、ack/mask、锁/延迟工作 | backend/是/是 | 未注册/触发 |
| Reset | anv_device lost status/GEM_RESET_STATS | intel_gt_reset:1201、intel_gt_reset_engine:1322 | 有界恢复、拒新提交、失败所有fence、pin解除、与当前显示驱动资源所有权 | backend/首实验准入需/是 | 未移植/未触发 |

表中XNU设施是明确待承接的合同，除GEM native-source适配外都不是已实现的替代函数。
不得因普通compute应用不用共享，就删除ANV初始化自身的dma-buf/syncobj硬探针。

## NMX / Metal发布与身份

指定NullMoth上游HEAD仍为47f818b。其
`kexts/NVRM/accel/nvrm-accel.cpp:8–10`包含缺失的nmx_accel_names.h，
`:584–587`要求IOPCIDevice的nmxgpu-claimed为true，否则start返回false。
`:614`registerService后，Metal可见MetalPluginName/MetalPluginClassName。
已存accelerator plist是NVIDIA personality，不能改vendor字符串就称Intel模块恢复。

源码显示NMXAccel以IOPCIDevice为provider，NMXGPU先claim该PCI设备并re-register匹配，
不是凭空创建另一个PCI层级。NMDRM旁路service也以IOPCIDevice匹配，
尚无与真实Intel GPU backend共同拥有资源的合同。目标应绑定同一PCI身份：
accelerator port→provider ancestry→BDF/vendor/device→render node GET_PCIINFO→ICD physical device。
新nmx/identity只CPU检查PCI人格/身份；完整GPU/Accelerator发布未恢复，明确阻塞。
`NVMTLDevice.m`的Intel识别、nvmtl_vk.c的Intel dlopen仍复用；
单进程g_vendor和第一个physical device选择尚未与上述链完成一一绑定。
本轮没有伪造nmxgpu-claimed、IORegistry节点或Metal可用返回。

## 仅建议的下一工程顺序

1. 合法完整Darwin用户SDK＋目标KDK/IOKit链接环境；完成用户shim与native source目标编译/链接。
2. 真实PCI/open/client/task资源归属及受控query快照，解决最早身份拒绝；未满足前不宣布i915。
3. 将GEM原生页/映射切片接入真实transport，解决task死亡/复制fd/移除、CPU cache和DMA可见性。
4. 复用官方Gen12 VM/context/RCS/exec及真实syncobj/dma-buf/fence/IRQ/reset。
5. 静态和隔离错误恢复条件满足后申请新的短小硬件实验；Metal前端对接Compute读回随后。

WindowServer、IOSurface、eDP/scanout和系统电源整合不属于首compute的前置交付。
