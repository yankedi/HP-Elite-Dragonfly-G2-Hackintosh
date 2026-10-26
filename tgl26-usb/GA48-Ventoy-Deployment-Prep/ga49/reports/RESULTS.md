# GA4.9 — HP 25G83 系统端部署前提审计

**结论：准备审计已完成，但完整系统栈目前不具备获证的安装/加载条件，不能开始首次GA48加速启动。**
原GA47包未改变。仅获批的新APFS staging完成；系统安装、KC注册、安全变化和重启均未执行。

## 九项回答

| 问题 | 本轮实证结论 |
|---|---|
| 完整系统端驱动现在能否安装？ | **还不能按“可加载的完整安装”放行。** GPUBundles受SIP限制；真实签名失败/adhoc不受信任；缺失legacy LLVM；KC链接与批准未完成。仅将文件放进staging不等于安装成功。 |
| Caches是否确实属于Data卷？ | **是。** firmlink映射、同设备/inode、df、diskutil都一致：`/dev/disk1s1`、Data可写。Caches仅sunlnk，无restricted；root只读W_OK=yes。没有写探针。 |
| 是否必须调整SIP/AMFI？ | 在**保持当前原包、上游布局**的前提下，当前SIP全开不能直接满足受限GPUBundles写入及未受信任kext加载。需要批准并验证的策略方案，或由上游提供满足正常签名/安装条件的完整包。**尚不能证明必须使用上游整个A13或全局AMFI参数，也不能声称NG加载后没有AMFI hook。** 详见[策略表](SECURITY-PLAN.md)。 |
| 是否真的需要修改SSV？ | **本轮没有证据要求修改SSV/authenticated-root。** Caches是Data firmlink；撤回GA48仅凭sealed根得出的必改判断。GPUBundles的restricted不是SSV问题。 |
| 哪些kext有签名或依赖问题？ | TGL accelerator签名被修改；framebuffer、EFI Lilu未签名；HookCase、NG结构验证通过但均adhoc，无Developer ID信任。两个TGL需要HookCase，尚未安装。系统provider ID/版本/compatible已核实，但符号链接/C++ ABI未证明。 |
| 是否存在匹配25G83 KDK？ | **存在精确公开资源，已本地下载并匹配目录SHA256。** 26.6.2/25G83，1,179,774,396字节，内核字符串与HP相同。未复制/安装到目标，尚未原生验DMG/pkg Apple签名。 |
| 能否不改内部EFI安装？ | **布局和KC流程不需要修改内部EFI。** 外置GA48提供NG；系统组件在Data及KC路径。当前GA48保留CSR0且不带上游AMFI参数，因此外置策略如何生效仍须单独审定；不能靠既有镜像自动解决策略。 |
| VESA回退是否足够？ | **可提供独立启动介质，但不足以单独保证系统恢复。** 哈希及独立配置复核通过；它不会撤销系统文件、AuxKC、Preboot或安全变量，也不能保证错误KC下一定启动。还需完整备份、可用Recovery及批准的KC恢复方案。未进行新物理启动测试。 |
| 何时可首次GA48启动？ | 完整备份/恢复、可写原路径、签名与加载政策、原生KDK、依赖/LLVM/sandbox处置、获批系统安装、成功KC注册及检查均满足，并单独批准启动及NVRAM Delete/Add行为后。具体见[部署计划](DEPLOYMENT-PLAN.md)。 |

## 原生检查结果

用户单独批准后，独占新建 `/Users/Shared/GA48-preflight/`；原归档及manifest传输哈希一致，安全解包后逐文件SHA通过。
本轮没有在目标放置审计脚本或执行包内程序。原生检查由本地工具通过SSH调用目标已安装工具完成。

`codesign --verify --strict --deep --verbose=4` 共13个真实bundle：3通过、10失败。

| 实际包位置 | rc / 真实结果 |
|---|---|
| EFI Lilu.kext | 1 / code object is not signed at all |
| EFI NootedGreen.kext | 0 / valid on disk，adhoc、无TeamIdentifier |
| L/E HookCase.kext | 0 / valid on disk，adhoc、无TeamIdentifier |
| L/E AppleIntelTGLGraphics.kext | 1 / invalid signature (code or signature have been modified) |
| L/E AppleIntelTGLGraphicsFramebuffer.kext | 1 / code object is not signed at all |
| L/E MTLDriver、GLDriver、VADriver、VAME、GraphicsShared（5项） | 各1 / resource envelope is obsolete (custom omit rules) |
| GPUBundles MTLDriver | 0 / valid on disk，adhoc、无TeamIdentifier |
| GPUBundles GraphicsShared | 1 / resource envelope is obsolete (custom omit rules) |
| xe.bundle | 1 / code object is not signed at all |

所有31个Mach-O均用原生otool读取依赖；逐二进制签名检查24通过、7失败，也单独记录。13个真实Info.plist均通过原生plutil lint。
xe.bundle是编译资源容器，顶层未签名结论不能代替内部dylib检查。
旧bundle的obsolete envelope也不能解释成“新签名通过”；实际加速器二进制签名错误仍存在。没有自动重签。

`plutil`记录真实Info.plist。加速器`com.xxxxx.driver.AppleIntelTGLGraphics` 16.0.2（compatible字段缺失），
FB `com.xxxxx.driver.AppleIntelTGLGraphicsFramebuffer` 16.0.0（compatible1.0）；HookCase8.0.1/compatible1.0。
NG1.0.0需要Lilu>=1.6.4，包Lilu1.7.2/compatible1.2.0。缺失字段按缺失记录，不虚构值。

## 依赖、LLVM和sandbox

- 实机IOAcceleratorFamily2 487.4.3/compatible2.0.0、IOSurface393.5.8/1.0、IOGraphicsFamily600/1.0.0b1、IOPCIFamily2.9/1.0.0b1。
  其余provider及每项OSBundleLibraries见 `PROVIDERS.json`、`PREREQUISITES.json`。
- IOGraphicsFamily采用flat Info.plist，初次按Contents路径读取失败已保留；改为识别真实layout后13个provider均与KC ID/版本一致。
- Lilu的旧`com.apple.kernel.6.0` ID不在KC枚举中；当前EFI的同版本Lilu已加载，不把该旧ID直接判定为缺失阻塞，也不当作新包KC链接成功。
- 五条`LC_LOAD_DYLIB`强依赖：两份GraphicsShared各自的libIGIL-Metal→3802、旧libMTLIGCCompilerPlugin→3902，以及xe中的libIGIL-Metal→3802。
  目标普通路径及dyld cache map没有这两版；原生dyld_info也报file not found，**即使它错误地返回rc0，仍按stderr判断失败**。
- 主Adapter的包内静态重导出闭包是Adapter→PluginOld→LLVMbridge，外接32023；32023可由目标dyld cache工具解析。
  五个旧消费者不在此静态闭包，**若动态加载它们，缺LLVM是真实阻塞；是否会走到这些路径仍未实测**。没有删库、改依赖或自造bridge。
- 目标MTLCompilerService sandbox允许System路径读取、System/Library执行映射；GPUBundles显式allow在apple-internal条件内。
  还存在dyld-support规则及运行时entitlement/extension/library-validation交互，因此仅看路径规则既不能保证自定义库加载成功，也不能断言必须改SSV。未运行编译/GPU探针。

## KDK与KC

精确资源：[KdkSupportPkg 25G83](https://github.com/dortania/KdkSupportPkg/releases/download/25G83/Kernel_Debug_Kit_26.6.2_build_25G83.dmg)。
SHA256：`577cdc8b2c09eaebfb16b0372ab6d6dc128ad4a08eaae09428d84a6c8a1e53c3`。
本地位于 `ga49/private/Kernel_Debug_Kit_26.6.2_build_25G83.dmg`；目标标准KDK目录仍不存在。
目录和镜像哈希是社区镜像证据，不等于Apple原生pkg验签通过；后续复制、验签、安装须另批。

实机`kmutil install --help`明确：macOS13起重建KC需要匹配build的KDK，支持`--kdk`、`--volume-root`、`--update-all`。
`load --load-style match-only -p ...`是可变更/匹配驱动操作，**不是只读链接测试**。
原作者一次提交TGL/FB/HookCase并使用`-z`、忽略错误；本轮没有执行，也不复制这些绕过。
正常路径是满足受信任kext/依赖、用户批准、精确KDK之后使用目标原生kmutil；当前包尚不满足这些条件。
没有执行新KC构建，不能将帮助输出或版本号比对宣称为符号/ABI验证通过。

## 交付与边界

- [DEPLOYMENT-PLAN.md](DEPLOYMENT-PLAN.md)：精确11目的路径、授权步骤、停止条件和首次启动门槛。
- [RECOVERY-PLAN.md](RECOVERY-PLAN.md)：现状、备份清单、KC原始字节读回及Recovery限制。
- [SECURITY-PLAN.md](SECURITY-PLAN.md)：所需/候选策略的七项说明。
- [GA48纠错](../../reports/GA49-CORRECTION.md)：旧报告与部署/恢复预检已修正，不重写历史GA48收据。
- JSON证据、逐命令stdout/stderr/rc、完整manifest和KC/KDK二进制分别保留在reports与忽略的private目录。

本轮未制作IMG、改驱动源码、改内部EFI、安装系统组件、注册KC、改SIP/SSV/AMFI/NVRAM/快照、重启或执行Metal。
现有staging留在原处供下轮复核，不自行删除；所有代码/工具变更本地commit，不push。
