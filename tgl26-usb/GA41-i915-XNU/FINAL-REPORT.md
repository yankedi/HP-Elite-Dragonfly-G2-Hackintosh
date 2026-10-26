# GA4.1 中文工程交付报告

目标：HP Elite Dragonfly G2 / i5-1135G7 / Tiger Lake Iris Xe 8086:9A49，
Tahoe26.6.2 / 25G83，x86_64。日期：2026-10-21。

**本轮已有真实代码和构建产物；尚未实现可运行的macOS Intel GPU驱动。**
Linux ANV ICD已链接成功，Darwin DRM子集和GEM ownership切片已编译并隔离测试，
原生XNU四个单元已用公开kernel header kit交叉编译为Mach-O对象。
没有GPU执行、Metal成功、完整Darwin ICD或目标kext链接/加载的证据。

## M1–M4 实物

| 验收 | 交付 | 证据与实际范围 |
|---|---|---|
| M1 ANV | `anv/artifacts/lib/libvulkan_intel.so`＋ICD JSON；可复现build脚本 | 固定Mesa26.2.3真实Meson/Ninja、LLVM21.1.8、CLC与8内部SPIR-V；ELF/依赖/3 loader exports检查 |
| M2 DRM | `libdrm-darwin/drm_darwin.c`、公开libdrm类型、NMDRM wire/PCI/fd处理 | Linux可编译CPU syscall-injection测试；未在Darwin用户SDK下编译/运行；没有改名i915 |
| M3 GEM | `i915-xnu/gem/gx_gem.c`、两原样Intel函数、BSD copy dispatcher、`os-compat/xnu_memory.cpp/xnu_copy.cpp` | Linux CPU memfd页/映射闭环及负例；native四单元Mach-O编译；无native页管理运行或GPU可见性证明 |
| M4 整合 | 根CMake、3个CPU CTest目标、Linux/Darwin ABI编译、实际Mesa KMD分类 | drmIoctl→BSD dispatcher→Intel create/publish→CPU map/读写/close；nmdrm仍被Mesa拒绝；这不是完整ANV初始化 |

## Q1：ANV ICD 到底构建到了什么程度？

**Linux实际ICD链接成功**，27,514,976B，SHA256：
`e8c99be081ec15eeae6b7fdc5178c2c1871f5d1c79a5e5dd7dff50e69e15fe5a`。
ICD JSON SHA256：`f29074f09b7e0b5283a7b842f07ecf8b79395908b0c7b382084d695c3fb27736`，
API1.4.354。JSON仍指标准安装路径/usr/local/lib，未安装。

解决原CLC requires LLVM：取得开放LLVM/Clang开发输出、SPIRV translator/tools；
修正Nix分离clang archive libdir和clang/Config头路径。
没有关闭ANV必要CLC；mesa_clc与8内部shader SPIR-V实际生成。
readelf确认ELF64，依赖解析无missing，导出
vk_icdGetInstanceProcAddr / vk_icdGetPhysicalDeviceProcAddr /
vk_icdNegotiateLoaderICDInterfaceVersion。

**没有Darwin libvulkan_intel.dylib，没有用户态ICD Mach-O库，没有运行时加载/枚举/
设备初始化。** native GEM Mach-O `.o`不能和ANV `.dylib`混同。
合法完整Apple用户SDK及Darwin平台移植仍缺；公开kernel header kit不是用户SDK。
详见 `reports/ANV-BUILD.md`、证据补充及`logs/anv-*`。

## Q2：Linux i915 实际复用了哪些代码？

官方Linux v6.18固定commit **`7d0a66e4bb9081d75c82ec4957c50034cb0ea449`**；
完整源archive和7728个选定DRM/UAPI文件保留，逐文件hash可查。

真实编译进Foundation的函数是
`drivers/gpu/drm/i915/gem/i915_gem_create.c`的
**`i915_gem_create_ioctl`和`i915_gem_publish`**，函数体逐字未改，
提取脚本与函数hash在`sources/i915-function-reuse.json`。
它们编排system-region对象创建、publish handle和allocation引用转移。
原样UAPI `drm.h/i915_drm.h`提供布局；编译边界仅处理内核注解/packed属性。

必须准确限定：**只有这个窄切片**；新写的页/handle/ref/map hook和私有小类型
不是Linux完整drm_file/i915私有结构，也不是完整i915 GEM。
Linux shmem/VM、execbuffer、request、PPGTT、syncobj等只核对真实合同，尚未移植。
依赖实核后选择B式提取＋XNU承接，A式完整Linux/DRM兼容层暂不引入；
后续GT硬件算法仍优先复用官方源。

Linux整体GPL边界保留，但这两个原文件函数明确MIT，不应误标GPL。
其余Linux/DRM/UAPI逐文件许可、NullMoth PolyForm Noncommercial、
Mesa/libdrm和XNU/APSL各自保留，没有公开混合分发。
逐文件/函数/修改/许可见 `reports/SOURCE-REUSE.md`。

## Q3：XNU 内核接口实际实现了什么？

- 原生源码：IOLock、IOMallocZero/IOFree、IOBufferMemoryDescriptor分配与zero，
  createMappingInTask/IOMemoryMap、只读/长度验证、unmap错误保活；copyin/copyout桥。
- **实际编译**：上述native内存/复制两个C++单元和GEM/dispatcher两个C单元，
  用固定公开MacKernelSDK头，生成真实x86_64 Mach-O relocatable对象；另有ABI对象。
- **CPU测试**：运行的是明确命名的Linux memfd/mmap后端；不是把XNU API改成stub跑通。
- **目标验证**：无25G83 KDK链接、无kext bundle、无加载或macOS运行。

公开header kit commit `3f750085caa17ec3a7880f11c11bf4f48cd6a164`，
APSL与保留各文件声明，不是目标KDK。没有生成桩头骗编译。
原生API名称/头兼容性已经编译证明，实际生命周期/权限仍需目标内核验证。
详见 `reports/XNU-COMPILE.md`。

## Q4：GEM 是否已有可信内存所有权和映射？

**CPU隔离切片有可检查的所有权/映射机制，原生运行尚未证明。**
设备可睡眠锁保护表和ref；单调token防旧handle误复用；quota/size/offset溢出检查；
allocation→handle→map引用交接；handle/file关闭后map保活；最后unmap释放页；
失败分配/发布/copyout回滚；unmap失败保留引用供retry；owner-map撤销辅助。

Linux测试用真正zero-filled memfd backing和共享mmap，不是向GPU返回malloc地址。
8线程4000次生命周期与同file map/close竞争、跨open/stale/溢出/EFAULT/表满等负例覆盖。
native IOBuffer/IOMemoryMap分配/映射代码已编译，但未执行；
尚无真实per-open/user-client taskDied、复制fd/移除、cdev mmap pager接线。
显式copy dispatcher不等于已解决标准cdev返回后的自动copyout回滚。

**GPU可见性=未实现**：没有DMA/IOMMU/GT cache-domain、GPU VM/PTE或执行引用。
任何map成功均不代表GPU能访问。详见 `reports/GEM-LIFECYCLE.md`。

## Q5：现在 ANV 初始化最先在哪个函数失败？

没有运行Darwin ANV，所以不能冒充实机错误栈。

源码条件顺序明确：无完整DarwinICD先卡构建/加载；无shim/节点则枚举transport先失败，
可能对应用SUCCESS/count=0。假设NMDRM＋shim实际工作，
**`intel_get_kmd_type()`仍拒绝nmdrm**，且本轮已通过原样Mesa函数CPU整合测试验证。
后续device-info失败转内部INCOMPATIBLE_DRIVER，枚举循环跳过，未必向应用返回错误。

将来提供真实i915语义后，第一个专用query缺口是
`intel_i915_get_device_info_from_fd`中的GETPARAM(CS_TIMESTAMP_FREQUENCY)，
随后topology。GEM_CREATE/GET_TILING/CLOSE探针在枚举阶段已需要；
之后ANV还要求exec/fence/timeline、dma-buf sync_file和syncobj等。
新GEM切片尚未接NMDRM，不能称初始化已越过这些点。
精确表见 `reports/ANV-INIT-BLOCKERS.md`。

## Q6：距离第一次真实 Intel GPU Compute 还缺什么？（依赖顺序，五项）

1. 完整Darwin用户SDK/目标KDK与链接环境，真实ANV/macOS用户库和native backend构建/加载基础。
2. PCI资源唯一归属、可信fd/client/DRM query与nmx accelerator身份链；真实query后才宣布i915。
3. 原生GEM用户映射/回收接线及DMA/cache/GPU可见页，GGTT/PPGTT/VA/binding/context隔离。
4. 官方TGL engine/exec移植与同步完成合同：PRIME/dma-buf、syncobj/timeline/fence、IRQ/超时/reset。
5. 实际NMX/插件→同一PCI/ICD身份绑定和Metal→ANV连续Compute链，新的明确硬件批准后验证Fence＋CPU读回。

未恢复完整NMXGPU来源，不能伪造nmxgpu-claimed或IORegistry来跳过第2/5项。
NullMoth已有Metal→Vulkan前端保持复用；本轮不重做Metal或Intel Shader Compiler。

## Q7：什么时候申请真实硬件实验批准？

**当前不申请GPU batch执行就绪批准。**
下一次只读query/CPU GEM也须新的具体授权，并先有目标编译/链接、资源所有权、
合法内存/指针/权限与task死亡/移除/失败释放测试、准确卸载与回退合同。
首compute还需真实DMA/VM/context、初始化硬探针、完成/错误/超时/reset不死等，
并固定极小输入/expected readback/退出条件和采证流程。
这些条件满足后，再请求用户批准具体一次硬件实验。
详见 `reports/NEXT-STEPS.md`；WindowServer、IOSurface、显示整合随后独立处理。

## 证据缺陷与验收限制

首版ANV build脚本覆盖了几次最早失败/中断的原stdout/stderr。
完整原始流**未能恢复**；四段精确会话读回已私有保存并hash，但只是部分输出。
这不影响成功ICD的独立hash/ELF/链接证据，
**却不满足“所有失败原始日志必须保留”的严格验收要求**。
不把重跑或修复笔记伪装成原日志；新脚本已改为每次唯一目录、保留退出码、拒绝覆盖。
详情 `reports/ANV-BUILD-EVIDENCE-AMENDMENT.md`。

## 独立复核与最终检查

独立审查实际复现了3项发现：fd路径重开可混入另一设备、同BDF不同PCI元组被错误折叠、
dev>31未拒绝。全部修复并增加负例；另修PCI结构尾padding比较。
原审查/反例/原输出保留，复审`audit/review-001/FOLLOWUP.md`确认3项关闭、
新identity数组正常/失败/返回detach释放路径无已发现泄漏或double-free。
native task保活/死亡撤销/close-copyout串行化/teardown quiescence仍明确未接线。

- `logs/reviewed-tests-001/`：最终3个CTest目标通过，显式ASan leak检测和UBSan halt；
  GEM7组、4000线程生命周期、100次同file竞争；发现负例和整合闭环通过。
- `logs/native-final-001/`：4个真实native单元＋1个ABI对象编译为Mach-O x86_64；
  ABI静态断言验证BSD/Linux方向值差异和LP64布局。
- `logs/delivery-audit-001/`：17项实际产物/函数原样/测试/边界证据检查PASS。
- `logs/ga40-readonly-verify-001/`：GA40独立只读校验PASS，35198本地条目＋457外部输入，
  seal仍为`4c907f204e7c100040121107b6ede1184a374ca7aec405a451aed99d5b8ade6a`。
- 仓库`make check`已通过。最终manifest和独立只读复核结果见
  `logs/manifest-verification.json`收据；这项排除文件不会自包含到manifest造成循环hash。

## 最终状态与停止

**授权范围内可行代码、构建、隔离测试、复核和报告已交付；严格验收仍为部分未达标。**
除完整原失败日志不可恢复外，Darwin用户ICD/目标kext链接、真实NMX服务发布和native资源
接线仍受SDK/KDK/实现缺失阻塞，已按要求停止相关分支而不是填假成功。
goal不标记complete，按证据留痕为unmet，不能用“工程停止”替代“全部实现”。

没有安装/加载kext，没有SSH目标机，没有MMIO/BAR/页表/engine/batch操作，
没有EFI/OpenCore/BIOS/安全设置修改，没有IMG或媒体变化，也没有公开上传。
保持停止；下一步仅建议见`reports/NEXT-STEPS.md`，等待新的明确指令/硬件授权。
