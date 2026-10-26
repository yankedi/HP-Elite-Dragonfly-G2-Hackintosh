# GA43 VM / Context / BO 所有权基础

生产源码 `gx_vm.c` 实现每client的host-side VM/context名字空间与GPU VA规划。
在真实 `gx_client_init` 创建，close/death/detach清理先context、再VM名字、
再GEM handle和task；GEM lease实际增加现有BO引用，非另一套模拟BO。

- VM名字destroy后context仍保活同一VM及绑定BO；最后引用才释放。
- 单client最多16个存活VM（包括无名字但context仍引用者）、32context，
  每VM64个规划绑定；ID不回收复用。
- VA按4KiB对齐、48bit上限及溢出/重叠检查；这里只保存normalized GPU VA范围，
  不写GGTT/PPGTT，不宣称GPU-resident，不创建硬件context。
- BO lease只允许原owner/handle取得，保持原16MiB计费，即使GEM handle关闭；
  同BO多引用只计一次，解绑/VM销毁后回收。
- Submit仅验证保活的batch范围；有效范围仍返回 `-EOPNOTSUPP`，无fence或完成计数。
- 不向标准VM/context ioctl谎报成功，不报告HAS_FULL_PPGTT或logical-context能力。
  这是将来硬件后端前的实际资源生命周期基础，完整i915 VM/执行仍PARTIAL。

## 官方复用与许可

| 函数/文件 | 来源 | 使用边界 | 许可 |
|---|---|---|---|
| `i915_gem_vm_destroy_ioctl` | Linux固定commit `7d0a66e4bb9081d75c82ec4957c50034cb0ea449`，`gem/i915_gem_context.c:1850-1869` | 原函数逐字节保留；私有类型与xa_erase/i915_vm_put适配只用于本项目host VM表，不是Linux内核布局/RCU替代 | MIT，Intel 2011–2012 copyright保留 |
| `i915_gem_create_ioctl` / `i915_gem_publish` | 继承GA42 `upstream_create.inc`，同一固定Linux输入 | 原窄切片system-memory GEM create/publish，未扩充硬件声明 | MIT，原copyright保留 |
| i915 DRM UAPI | `sources/linux/include/uapi/drm` | 原结构/布局，不改功能能力 | 各头原SPDX与copyright保留 |
| `gx_vm.c`、lease/生命周期集成 | 本轮原生胶水 | client锁下资源管理，真实BO backing ref | MIT |

`vm-upstream-source-001` 直接比较整段官方函数与include，PASS。
`vm-tests-001`：ASan/UBSan下新增VM目标及受影响GEM/client两个既有目标PASS。
覆盖分配失败回滚、跨owner拒绝、BO关闭仍计费、VM destroy/context保活、范围、
孤儿VM上限、unbind、detach/death回收，无泄漏。
`vm-darwin-compile-001`：新生产单元真实x86_64 Mach-O编译PASS；不是模块链接。

## 请求所有权与失败传播基础（2026-10-25）

新增 `gx_request_plan_*` 接在实际VM/context规划层，不是另一套BO模型。prepare只
对已绑定batch范围创建有界所有权快照，保活同一VM和真实GEM backing；请求未释放
前对应binding不能unbind。VM名字/context/BO handle关闭之后，保留的请求仍保活资源，
context关闭将pending请求取消，最后request release才可释放孤儿VM/backing。
每client最多32条记录，ID不复用，close/death清理先请求、再context、再VM名字。

状态只有 `-EINPROGRESS` 或第一个负错误；拒绝error=0和伪pending错误，无成功或
signal函数。`gx_context_plan_submit`实际用prepare→fail(EOPNOTSUPP)→release，
保留有效结构请求的硬件拒绝并收回全部引用，不导出DRM syncobj、GPU fence或完成数。
这是将来真实fence前的资源/错误寿命基础，**没有GPU fence实现**，PPGTT/residency/
scheduler/IRQ/reset仍缺。不把host计划创建成功视作GPU submit。

`request-error-tests-001`两相关ASan/UBSan目标PASS，验证pending、禁止成功、首错不被
timeout覆盖、unbind忙、context取消、名字/context/handle全关后的request保活、
孤儿VM计数、请求上限和detach/client close全部释放；全部VM调用遵守client gate。
`request-error-darwin-001`修改生产VM单元Mach-O编译PASS。新代码是MIT原生胶水，
只借鉴官方i915首错/引用生命周期概念，不声称逐字移植GPU request或dma_fence。

后续审查R2已补齐host admission：VM state/create、context create、bind、request
prepare/submit统一调用真实device/file admission gate；detach之后新工作返回ENODEV，
destroy/unbind/fail/status/release及close仍允许。检查是新host工作的线性化点；
与detach重叠但已获准的工作可完成，不声称中止先前已入场操作。
`review-admission-tests-001`两相关ASanUBSan目标PASS，`review-admission-native-001`
两个修改单元Mach-O编译PASS。

原followup R1声称可积累超过16个孤儿VM，与同报告列出的vm_objects创建上限不一致。
当前上限已经包括request-held/context-held孤儿，实际17号创建返回ENOSPC；新增16个
不同request-held孤儿VM的ASan/count witness验证此不变量。另加显式count容量防御，
未来若放宽VM总量也返回EOVERFLOW而非越界。保留原finding，交独立澄清，不将未能
证明的溢出写成已复现漏洞。
