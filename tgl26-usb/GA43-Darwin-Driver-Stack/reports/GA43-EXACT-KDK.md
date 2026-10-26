# 后续本地精确25G83 KDK与真实KPI输入（2026-10-25）

恢复后的进一步本地库存发现GA49已经取得精确KDK；它不在旧GA43库存调查时间范围内。
DMG SHA256 `577cdc8b2c09eaebfb16b0372ab6d6dc128ad4a08eaae09428d84a6c8a1e53c3`，
路径`GA48-Ventoy-Deployment-Prep/ga49/private/Kernel_Debug_Kit_26.6.2_build_25G83.dmg`。
GA410 `private/commands/kdk-target-hash.json`记录同一hash；`kdk-pkg-signature.json`
原生pkgutil exit0、Status signed Apple Software。这是已有授权会话的原始证据，
不是本轮联网或重新目标验证。当前只读源DMG、本地hash核对、7z/bsdtar提取。

`build-private-kdk-001`及所有SDK/Apple输入均被Git忽略。先解XAR、再pbzx分块XZ到
CPIO，chunk长度逐一核验；只提取SystemVersion、System.kext KPI pseudoextensions、
IOPCIFamily和x86_64 kernel，没有安装KDK或写目标。SDK子包仅35个新增平台文件，
不是完整kernel headers；不能声称已用精确KDK头重新编译。

证据：`local-exact-kdk-inventory/extract/payload/sdk-decode/main-decode/selected-001`。
直接bsdtar读pbzx的失败保留，后续`tools/unpack-pbzx.py`成功验证297chunks，
4,973,553,004字节CPIO；未把压缩格式错误写成KDK不可用。

`native-exact-kdk-kpi-001`使用真实25G83 SystemVersion核验，解析官方KPI
pseudoextension的外部名称集合（其U符号正是KPI声明列表，而不是实现），对实际
IOPCIFamily则只读defined external。当前354imports均有KDK provider，353个在
本模块声明的OSBundleLibraries中，唯一例外`_thread_call_allocate_with_priority`
仅由`com.apple.kpi.private`给出。目标KC名字存在并不足以证明其可由当前依赖导出。
下一单元切换到同语义、已声明Mach KPI提供的`thread_call_allocate`；不加入private
依赖，不恢复已撤回的pending-return/F4解释。

KDK名字合同不是C++ vtable layout、KC rebuild/load验收。仍需官方headers的对象布局
与目标kernel比较及原生环境验证，不将`NOT_VERIFIED`倒填为PASS。

`native-public-kpi-link-001`将allocator替换为官方Mach KPI `thread_call_allocate`，保留
regular-call/free/pending/overlap生命周期语义。新真实模块SHA256
`c574afdecbd107ef0760fb3f56d0a298e2ba41418aefa44a4c1c45e11efaaae9`。
`native-public-kpi-check-001`全354imports在当前已声明的精确KDK KPI/IOPCI provider中，
无missing、不添加private依赖。与原先F4撤回并不冲突：这次依据新到位的精确导出合同，
不是将thread_call_enter_delayed返回值再解释为失败。
