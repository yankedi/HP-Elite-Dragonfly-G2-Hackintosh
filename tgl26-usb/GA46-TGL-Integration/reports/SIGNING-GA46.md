# Tahoe部署/签名可行性审计（仅研究，2026-10-23）

结论：**DEPLOYMENT_BLOCKED**。没有运行签名、安装、KC重建、加载或修改目标
安全策略的命令；没有签名身份/密钥输入，也没有运行目标新探针。

| 问题 | 证据与必要条件 | 本轮判断 |
|---|---|---|
| 自建NootedGreen与Lilu | MH_KEXT_BUNDLE只是格式；需目标KPI/C++ABI、OSBundleLibraries、实际Lilu兼容。Apple文档要求kext-enabled Developer ID Application，而非普通app证书；历史区分OID 1.2.840.113635.100.6.1.18；新/更新kext还涉及公证、用户批准与KC流程 | 本轮真实kext未签名；没有目标KC链接/加载证据 |
| 未修改Apple donor | 原签名在字节未变时才可能有效；仍需目标版本/架构、依赖KPI、bundle ID/硬件匹配及系统的驱动选择/加载策略 | 有LC_CODE_SIGNATURE不等于验证成功；跨版本未获加载许可 |
| 修改Apple私有驱动 | 三处MTL修改使原签名对应的代码页失配；普通Developer ID重签不能恢复Apple身份或私有entitlement授权 | 原签名不能继续视为有效；无已证明的符合当前约束加载路径 |
| 自建libxedrv/Compiler/Bridge | 自建签名Team ID不等于Apple；@rpath install name与注入的绝对路径需实际解析与host许可 | 严格链接但未签名；当前版本有意拒绝未知ABI，不能当功能driver部署 |
| WindowServer / MTLCompilerService接受整套组件 | library validation通常只接受同Team ID或Apple系统库；disable-library-validation属于host的entitlement，插件不能给Apple host追加它。插件sandbox/path allowlist是另一个限制，不能用`PrivateFrameworks/../Caches`字符串替换证明通过 | host当前真实entitlement/加载规则未获足够证据；无合法端到端路径证明 |

## Kernel Collection与平台差异

Apple文档说明macOS11起third-party kext进入AuxKC而非旧式随时动态加载。
正确外部/本地重定位和kmod_info并不取代KC构建、有效签名、用户批准、重启等
系统流程。此次没有执行这些流程。HP为Intel，不能把Apple silicon的1TR、
Secure Enclave/LocalPolicy或Reduced Security设置要求原样套用；更不能把
其不存在视为macOS签名/AMFI/library validation自动失效。官方Apple硬件文档
不是对此HP整合的兼容认证。

公证是扫描/签名检查结果，不是Apple授予私有GPU驱动/host注入权限，也不保证
程序兼容。Kext签名身份、公证、Team ID、entitlement、目标ABI、host sandbox
是独立约束，五个问题不能由购买普通Developer ID一次解决。

## 当前约束下的路线边界

不改变SIP/SSV/AMFI/Secure Boot，不使用`amfi_get_out_of_my_way=1`，也不安装
或替换系统GPU bundle。若无法获得Apple允许的修改后GPU组件加载机制，以及
host接受自建dylib的实证，**该部署分支在当前约束下终止**；不是仅缺一次
GPU测试授权。CPU观察探针能缩小ABI问题，不能解除签名/host政策阻塞。
离线工程仍可验证linker/符号/序列化，但不能把它等同第一次Metal Compute。

## 一手资料（本轮在线查询）

1. [TN2206 Kernel Extensions](https://developer.apple.com/library/archive/technotes/tn2206/_index.html)：kext-enabled identity/OID；归档文档仅用于证书区别，非Tahoe加载成功证据。
2. [Notarizing macOS software](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)：新/更新kext公证及host/plugin entitlement区别。
3. [Code Signing Guide — Library Validation](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/Procedures/Procedures.html)：同Team ID或Apple库政策。
4. [Securely extending the kernel](https://support.apple.com/guide/security/securely-extending-the-kernel-sec8e454101b/web)：AuxKC及Apple silicon专属要求。
5. [Enterprise management of legacy extensions](https://support.apple.com/en-us/102026)：Intel/Apple silicon范围区别、批准与更新流程。
6. [Intel boot process](https://support.apple.com/guide/security/boot-process-sec5d0fab7c6/web)：T2与无T2区别；2026版本资料。

这些资料支持必要条件；没有一份资料证明修改Apple TGL16.0.32并注入自建库
在25G83保持全部安全约束时可被这两个Apple host接受。
