# GA43 XNU 链接实证与输入边界

## 2026-10-25 新输入后的当前结果

旧AndroidLLD失败保留在下文。新GA46 pinnedPR204805 linker由本轮只读复用，
`native-modern-module-001`、共享用户ABI后的`native-shared-uapi-link-001`均真实
`-kext`链接exit0，LLVM确认x86_64 MH_KEXT_BUNDLE；SHA256
`192037b047235edbd0c6c8f5a7e29e0d3eaa6f6ffbab09da1b083a3799b77d7e`。
`native-package-001`封装真实`GX43IntelGEM.kext`，保留与原kmod_info一致的GA42
bundle身份和CPU diagnostics personality；355未绑定kernel imports另存，不因
MH_NOUNDEFS标志或exit0而声称已解析目标KPI。未签名、未安装、未KC重建/加载。

**实际证明精确KDK包不是生成MH_KEXT_BUNDLE的必要前提**，但符号名字/公开KPI/
C++虚表布局/目标KC接受度仍须分别验证。

又发现后续GA49缓存的目标Preboot BootKC，RECOVERY-BASELINE.json给出readback
hash `c80161fa3065883753fc285339281361a8469cbb6fb27653c88e2a22eb4807a4`；本轮实际
SHA核验后仅本地解析204fileset的真实nlist，未接目标。`native-target-kc-names-001`
比较结果355imports中354可在目标external nlist找到，唯一缺失`___cxa_atexit`。
它来自当前GX42Service.o，而不是四个继承对象。后续GA46有相同Clang后端析构降级
证据；下一单元修该真实kernel编译语义。nlist presence并非公开KPI许可或ABI通过。
后续GA49/GA410还已有精确KDK dmg和原生Apple pkg签名成功日志，旧“本地无KDK”
不再适用；本轮尚未抽取/构建其headers，不以其他会话安装记录冒充本轮target验证。

`native-kernel-dtors-link-001`使用真实Clang后端
`-mllvm -disable-atexit-based-global-dtor-lowering`保留mod_init/mod_term，消除
错误的用户运行时注册；没有伪造`__cxa_atexit`。sections001记录真实析构重定位仍在。
实际新模块SHA `ee998092dbc94704b0e38a3a1eb6f838eba1b38d806179ebca6007aa2d778b54`，
354 kernel imports在精确缓存KC均有external nlist定义，missing_external_names为空。
这解决了一个真实编译/符号不兼容，**尚不证明**这些名字都在KPI导出集或虚表布局正确。
link脚本增加拒绝cxa_atexit残留的gate；最终KC构建/load仍未执行。

## 实际结果

`native-module-link-ga43-001` 使用原生kernel参数、公共MacKernelSDK的真实
`Library/x86_64/libkmod.a`，及九个实际Mach-O输入执行模块链接。
仅重编译因gx_client布局变化而受影响的GX42Service；复用本轮已验三core对象、
VM对象及GA42四个未修改对象，历史树只读。输入sha在
`artifacts/module-link-001/link-inputs.sha256`，原命令/stdout/stderr/exit均保留。

**XNU_MODULE_LINK：FAIL。** 最早诊断 `ignoring unknown argument: -kext`；
旧Android LLD不能识别模块输出种类，继而以可执行文件规则报 `_main` 和大量
IOKit/libkern引用未解析。没有通过dynamic_lookup、造exports或改安全策略绕过。

随后 `native-relocatable-ga43-001` 使用同九对象执行实际 `-r` 链接，exit0。
`native-relocatable-inspect-001` 的file/llvm-readobj确认 x86_64 `MH_OBJECT`，
所有项目内 `_gx_*` 引用已内部连接；剩余是IOKit/libkern/kernel依赖。
结果 `artifacts/module-link-001/GX43-relocatable.o` 是**真实可重定位组合链接单元**，
不是archive、MH_KEXT_BUNDLE、最终可加载驱动或KernelCollection验收。
没有把这个成功写成XNU_MODULE_LINK PASS。

## 精确KDK是否链接硬前提

**单元组合链接不需要精确25G83 KDK，本轮已实际证明。**
先前把“缺精确KDK”和“没有Mach-O linker”合并为一个原因不够精确。

模块输出需要能生成目标kext种类的链接器、正确kmod入口/运行时和目标符号合同。
当前实际先卡在旧LLD不识别 `-kext`，而不是已证明某个Tahoe KPI不存在。
`IOService/IOUserClient` C++ vtable及reserved槽、task/threadcall、IOLock、
IOMemoryDescriptor/IOMemoryMap等引用仍需对**匹配目标的真实exports/ABI输入**验证。
精确KDK通常提供这些输入；等价的、合法取得且匹配25G83的kernel/KC符号与头也可
用于相应检查，不能把KDK包名当作唯一逻辑前提。用户SDK不能代替内核符号，公共
MacKernelSDK仅证明较旧公开头能编译，不能证明25G83 ABI和KPI可加载。

本地无精确目标exports，不能据缺输入推断某KPI已被移除，也不能宣称传统kext在
Tahoe可加载。独立初审 `audit/ga43-initial-native-review/REVIEW.md`保留原意见，
本段补充实际-r证据和“匹配符号输入不一定必须精确KDK包”的限定。
`Info.plist`保留CPU diagnostics、真实PCI匹配与IOKit/libkern依赖；不注册Metal加速器。
DriverKit是不同的用户态架构，不能直接复用kernel task/map/copy KPI；本轮尚无
证明必须迁移的目标证据，暂不重写。SIP/AMFI、KC安装/签名/load均未改、未执行。

## 复现入口

`tools/link-xnu.sh`显式接收kernelSDK、linker、LLVM工具、旧对象、当前core/VM对象及
全新输出路径，拒绝覆盖。`GA43_LEGACY_LLD=1`选择已验证旧参数；默认现代参数。
实际KextBundle输出仍需检查imports与目标合同，此脚本不把容器成功等同加载成功。
所有原生runtime/GPU/Metal状态 NOT_TESTED。

## 独立审查F1修复

原脚本只记录caller-supplied core/VM对象hash，不能阻止旧gx_client布局混用。
现在所有5个ABI受影响单元在同一新输出目录、同一编译参数/SDK下编译，拒绝任意
core/VM缓存；4个未修改对象仅接受固定GA42封存路径，经固定receipt/index hash、
manifest链、每对象hash、当前原样source与公开值类型布局、kernel-kit seal验证。
每输入还需实际x86_64 MH_OBJECT检查。`verify-inherited-native.py`负责fail-closed。
`inherited-native-gate-001` PASS；`inherited-native-reject-stale-001`按预期拒绝任意路径。
`native-module-link-reviewed-001`通过来源/ABI门仍因旧LLD不支持-kext而FAIL；
`native-relocatable-reviewed-001`新鲜5单元加已验4对象/libkmod真实-r PASS，
`artifacts/relocatable-reviewed-001/GX43-unit.o` SHA256
`65fb4020bcade403f8ee63d2beac28c2ef916af2b4819089976f659ca4d76b97`。
源码HEAD/diff/文件hash和对象headers保留，与历史未审核link输出分开。
