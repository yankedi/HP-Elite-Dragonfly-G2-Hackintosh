# Intel GEM Foundation：实际生命周期和平台边界

## 实现

`gx_gem.c`编译两段原样Intel Create/Publish函数，以显式OS hook承接所有权。
设备内一个可睡眠锁串行保护open表、handle表、BO ref、map表、bytes预算。
无IRQ/spinlock上下文分配、无裸用户指针解引用、无GPU能力声明。

| 对象 | 所有权 | 释放条件 |
|---|---|---|
| gx_device | 驱动持有；外部必须先quiesce并保持到全部调用结束 | files/objects/maps均0才允许destroy |
| open token | 单调64位，绑定可信per-open/client，禁止用用户整数当授权 | close清除handle，映射仍持有BO |
| handle | 全设备单调32位、不回用；每open最大128 | close(handle)或close(file)各drop一次引用 |
| BO | allocation ref→publish handle ref；page-rounded size、64MiB/BO，256MiB/device预算 | 最后handle/map引用释放后free_pages/free_meta |
| map | 独立单调token，绑定owner，256上限 | 成功unmap才drop ref；失败保留供retry |

open最多32，map offset/length必须4KiB对齐，按`length <= size-offset`
拒绝越界和加法溢出。size上界先检查再roundup，不会UINT64_MAX绕过。
handle exhaustion在publish失败路径drop allocation引用，不泄页。
`gx_revoke_owner_maps`提供task/client撤销辅助，失败保持引用；
真正IOUserClient taskDied/fd-close glue尚未注册，不能称完整kext生命周期。
普通mmap式映射可在close(fd/handle)后继续存活；驱动卸载不能忽略这些引用。

`gx_ioctl.c`仅接BSD GEM_CREATE/GEM_CLOSE完整request+结构大小，
copyin/out由独立回调处理，create copyout失败回收handle。
这是**未注册的显式copy边界**，不是把标准cdev d_ioctl的自动copyout问题解决了：
后者失败发生在handler返回后，handler不能观察并回滚，需要后续真实transport设计。
unsupported Query/VM/exec/sync/mmap返回ENOTTY；`gx_gpu_bind/gx_exec`返回EOPNOTSUPP。
无VERSION='i915'，无fake MMAP_OFFSET，无CPU fence假完成。

## 真正原生平台源码

`os-compat/xnu_memory.cpp`：IOLock、IOMallocZero/IOFree，
IOBufferMemoryDescriptor(kernel_task, KernelUserShared)、显式zero，
createMappingInTask→IOMemoryMap，read-only选项、映射长度和unmap返回检查。
可信task应来自保活的IOUserClient owner，绝不由用户传task指针；
TASK_NULL/kernel_task映射拒绝。`xnu_copy.cpp`使用真实copyin/copyout名称和errno转换，
没有用CPU memcpy假冒内核指针验证。

参考API语义可逐行核对 `sources/xnu/iokit/IOKit/`及Kernel实现。
这不是GPU DMA映射：不调用IODMACommand/prepare、不写PTE、不返物理地址。
native编译的最终证据独立见 `XNU-COMPILE.md`；没有macOS加载/运行。

## 实际运行的后端和测试

`tests/gem_cpu_backend.c`是**显式Linux CPU隔离后端**，
用memfd_create/ftruncate获得zero-filled host pages，用真正MAP_SHARED mmap建立
同对象的多个CPU地址及read-only/read-write权限；不是新的fake GPU。
这能实际检查映射引用比handle/file长、共享读回和页销毁，但不能证明XNU内存或GPU可见。

根CMake/CTest：Clang21.1.8 + ASan/UBSan，
负例含零/巨大size、wraparound offset、跨open/stale handle、错误task、
meta/pages/map失败、unmap失败后retry、表满回滚、copyin/out EFAULT、
BSD/Linux方向混淆拒绝；8线程4000独立生命周期及同file map/close竞争。
每次运行原始命令/输出/exit保留在logs/gem-*、integrated-*；
最早失败001/002是u64类型不等、未经headers_install的__packed标注，
修复只作用编译边界，不改变上游函数体/结构。

## 尚未覆盖/未实现

- 实际XNU task/process资源回收、设备移除、fd duplication/跨进程继承、cdev mmap pager glue。
- GPU可访问页、DMA/IOMMU/cache-domain/PPGTT/驻留、GEM_CREATE_EXT。
- Linux完整shmem shrinker、reclaim/madvise、dma-resv、PRIME sharing。
- 硬件context/engine/exec/sync/IRQ/reset，任一缺失都不能宣称ANV初始化成功。

本轮可交付的是**可编译CPU测试的真实所有权切片＋原生XNU适配源码/编译证据**，
不是完整i915移植，也没有证明native GEM运行闭环。
