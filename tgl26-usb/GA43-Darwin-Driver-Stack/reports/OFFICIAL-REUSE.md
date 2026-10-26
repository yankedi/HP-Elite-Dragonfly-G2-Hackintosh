# GA43 官方源码复用、适配与许可矩阵

固定输入仍为Linux `7d0a66e4bb9081d75c82ec4957c50034cb0ea449`、Mesa
`31e9a6b2e95e30d84bf3177d1f497d063e59b6b2`、NullMoth
`47f818b11cef59acb480210afdf9065fdd44e356`。本轮不下载、不提交第三方SDK/KDK。

| 真实函数/组件 | 来源与本地工件 | 复用方式及限制 | 许可/保留 |
|---|---|---|---|
| `i915_gem_create_ioctl` | Linux `gem/i915_gem_create.c` → `i915-xnu/gem/upstream_create.inc` | 继承原函数body，经私有subset glue接真实CPU backing；不是完整Linux DRM struct ABI | MIT，Intel2020 copyright原样保留 |
| `i915_gem_publish` | 同上 | 原handle发布及初始引用释放；copyout回滚由gx glue负责 | MIT，原copyright |
| `i915_gem_vm_destroy_ioctl` | Linux `gem/i915_gem_context.c:1850-1869` → `upstream_vm_destroy.inc` | 新增逐字函数，xa_erase/i915_vm_put为受client gate保护的私有host VM表/ref；原函数对照`vm-upstream-source-001` PASS | MIT，Intel2011–2012 copyright保留 |
| DRM/i915 UAPI | `sources/linux/include/uapi/drm` | 原结构/常量；host和BSD方向位薄转换，不新增虚构能力 | 各头原声明分别保留；该目录含MIT、GPL-2.0 WITH Linux-syscall-note、双许可等，不统一改标MIT |
| `intel_get_kmd_type` | Mesa `src/intel/dev/intel_kmd.c` | 原函数在CPU组合测试编译，仍拒绝nmdrm身份；未改为假i915 | MIT，原文件copyright |
| `spirv_to_nir`、`brw_preprocess_nir`、`brw_compile_cs` | GA40既有固定Mesa真实harness二进制 | 本轮单一NullMoth来源SPIRV实际调用，validator成功但brw路径SIGSEGV，无新Gen12输出；未改官方compiler | Mesa各源原MIT/license，原harness原声明 |
| NullMoth Metal→Vulkan Device/Queue/Buffer | 原plugin＋四份GA42补丁 | 原前端保留，各vendor路径/冻结/loader边界不变；无原生plugin/device运行 | NullMoth原LICENSE/NOTICE及各源声明保留 |
| `metal2vulkan` translator | 原`translator/translator`及GA40已生成SPIRV | 不改、不重建、不重写翻译器；文本AIR-dialect不等于真实metallib容器API | LGPL-3.0-or-later（原translator声明） |
| XNU IOKit/libkern/task/thread_call | 公共MacKernelSDK只读GA41及本轮GX42Service glue | 真实头编译，不冒充用户SDK或25G83KDK；调用合同可读，目标exports/ABI/runtime未验 | 原SDK源许可按各文件，未复制SDK入Git |
| `gx_vm`、request plan、BO lease、cookie、native client glue | GA43生产源码 | MIT原生所有权/错误/适配代码；request不是i915_request/dma_fence，未声称逐字复用Linux执行驱动 | 本项目MIT/SPDX；私有subset类型有明确非Linux布局注释 |

## 尚未移植或未验证的官方功能

真正 `i915_ppgtt_create`、GPU页表walk/bind、engine context image、residency、DMA/cache、
scheduler、硬件request/fence、IRQ、timeout/reset不在已复用成功集合。
本轮VA是host规划，request只有pending/负错误；没有GPU成功signal接口。
官方ANV实际需要exec fence array/timeline、context/VM和reset stats；不能因为同名
host对象存在就向这些标准ioctl返回成功。首次Compute依赖见`ACCEPTANCE.md`。
