# 新输入独立审查修复记录

原始`REVIEW.md`保留。审查只覆盖其注明的baseline/未提交工具，不倒填后续已成功链接
或新IOConnect/KDK工作为当时通过；这些由后续真实日志另证。

## N2：公开Darwin wait返回值归一化

`0006`两个wait分支现在将非负Apple waiter-count归零，仅保留-1与原errno；不变更
原compare-and-wait、deadline转换、wake及CPU/GPU边界。`review-n2-wait-contract-001`
从当前patch抽取原样Apple新增分支，CPU API故障注入＋ASan/UBSan验证7/4正waiter数、
EINTR/ETIMEDOUT/EINVAL、过期与数值已变时不等待、wake ENOENT和不支持count。
这是生产分支的CPU错误合同测试，不是Apple os_sync原生并发测试。

## N1：真正动态 provider 闭包与强引用保护

`darwin_link_inputs.py`从当前Clang `-###`实际ld64 argv解析显式dylib、-l和framework，
包含Clang隐式libc++/System；按该sysroot/searchpath解析TBD及其真实embedded/external
reexports，未知/缺失/歧义输入拒绝。当前13输入文件、68,968个动态导出名字加入闭包。
任何同时有strong undefined的名字不允许NULL fallback，即使另一个TU将它声明weak。
`review-n1-closure-witness-001`用真实Mach-O object/dylib证明动态provider排除NULL、
libSystem的malloc/os_sync叶reexports纳入、混合strong缺失拒绝以及真正严格link失败。
这些link-only fixture均不加载；不是CPU函数体冒充Vulkan实现。

## N3：最终输出检查属于链接工具的退出合同

成功link后工具内实际执行Mach-O inspector，强制x86_64/MH_DYLIB、294imports的绑定
ordinal、精确10dependencies、3个ICD导出、install_name和唯一@loader_path rpath。
检查失败进入工具返回码；link-exit.json分别记录link/inspection/strict_artifact_pass。
`anv-reviewed-closure-link-003`实际全部PASS，不是仅exit0。
`review-n3-rpath-negative-001`漏allow列表，按dependency拒绝，不能算隔离rpath负测；
002给全正确依赖后实际旧ANV build-path产物因rpath拒绝，保留原失败不改写。

该003仍链接N2修改前的已编译Mesa对象。下一fresh build必须应用当前0006再构建，
不可将旧对象的成功视为最新源码完整构建。源码独立复核闭环也仍待追加。
