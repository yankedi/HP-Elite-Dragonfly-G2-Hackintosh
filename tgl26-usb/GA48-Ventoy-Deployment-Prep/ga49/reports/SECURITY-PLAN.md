# HP 25G83 策略与信任前提（仅审查，未授权执行）

## 当前与上游

HP：SIP/authenticated-root enabled；当前启动CSR0。外置GA48也保留CSR0，SecureBootModel原本就是Disabled；
无`amfi_get_out_of_my_way=1`。上游固定提交的config：CSR bytes `130a0000`即`0xA13`，
boot-args含`amfi_get_out_of_my_way=1`，SecureBootModel Disabled。

`0xA13`包含0x1 untrusted kexts、0x2 unrestricted filesystem、0x10 Apple internal、0x200 unapproved kexts、0x800 unauthenticated root。
这不是HP最小必要值的实验证明。尤其0x800不能因Caches路径而照搬；0x10也无本轮必要性证据。
NG上游`_cs_validate_page` hook原样保留；去掉AMFI boot-arg不代表未来加载该NG没有放宽代码页校验的行为。

## 逐项七要素

| 设置 | 修改原因/当前证据 | 安全影响 | 上游值 | HP当前值 | 不修改的替代/结论 | 失败恢复 |
|---|---|---|---|---|---|---|
| SIP filesystem（CSR 0x2，候选） | GPUBundles root:wheel/restricted，root W_OK=no；完整原布局当前不能正常写 | 放宽受保护系统路径，影响超过本项目 | A13含0x2 | 0，限制开启 | 先确认是否有系统支持且仍保留上游布局的安装通道；未找到当前包可用通道。Recovery仅能作为另批离线文件操作，不证明随后加载可行；不能用Data别名绕过或删restricted当替代。 | 从独立Recovery按部署前CSR确值恢复；先还原文件/KC，避免将无信任kext留在需要正常引导的状态。不得盲用全局reset。 |
| SIP untrusted kext（0x1，候选） | FB未签名、加速器签名无效、HookCase仅adhoc；当前包无法当正常受信任kext | 允许不受正常签名信任保护的内核代码 | A13含0x1 | 0 | 上游/合法签名方提供有效kext-enabled Developer ID及完整seal、正常用户批准。当前原包不具备；本轮不重签，adhoc不解决平台信任。 | 恢复原文件和匹配KC并验证后，在Recovery恢复CSR旧值；不要带坏KC直接收紧后重启。 |
| SIP unapproved kext（0x200） | 原作者配置放宽批准；本用户要求不跳批准 | 放宽用户批准控制 | A13含0x200 | 0 | **优先保留批准机制**，按系统流程明确批准后继续。正常批准仍不能修复无效签名；没有证据要求照抄此位。 | 若将来另批改动，恢复CSR精确原值并复核批准状态；不删除其他现有kext批准数据库。 |
| AMFI boot-arg与NG hook | 多个userland seal/二进制校验失败，NG已有代码页hook；尚无目标运行错误证明全局参数不可替代 | 全局关闭AMFI削弱可执行代码校验；NG hook本身也是信任放宽 | `amfi_get_out_of_my_way=1`，并保留NG hook | 当前运行无NG/无该arg；GA48将加载有hook的NG | **不能宣称必须全局关AMFI**；先解决有效签名/信任及准确加载错误。也不能声称保留原NG功能时无任何AMFI影响。运行验证另批，不靠自动重签掩盖失败。 | 若获批更改，先修复文件/KC，再仅恢复备份boot-args/相关策略；检查外置OC Add/Delete，防止旧arg被再注入。 |
| authenticated-root / SSV（0x800） | 没有必改证据；Caches已经Data且可写检查通过 | 允许未认证系统根、可能破坏SSV保障 | A13含0x800；不据此推断作者是否改了snapshot | authenticated-root enabled，根sealed RO | **本计划保持不变**。GPUBundles与Caches问题不能证明要改SSV；不做根卷remount或自建snapshot。 | 本轮无变化无需恢复；将来若有独立证据和授权，须先设计完整OS/snapshot恢复，不临时用bless猜测。 |
| OpenCore SecureBootModel | 当前两者都Disabled，没有新增改变需求 | 保持当前OC策略；非等同AMFI或SIP | Disabled | Disabled（GA48同） | 不改。不能靠此设置替代kext签名/依赖；不照搬其他Dell参数。 | 未改无需恢复；未来只恢复经批准变更的外置配置，不写内部EFI。 |
| NVRAM boot-args/CSR | 首次GA48 Delete boot-args再Add可能影响现有持久变量；WriteFlash=false不保证Delete无影响 | 更改后续启动策略/参数 | 上游配置写入其自身值 | 已只读保存nvram -xp及kern.bootargs；GA48 CSR0 | 当前不写。首次启动前单独批准Delete/Add效果，先保存原值；不能以“只从USB启动”当作无NVRAM影响。 | 单独批准后仅还原原变量；不Reset NVRAM，不改BootOrder，不盲恢复整份nvram plist。 |

以上是证据约束的方案选择表，**不是已经验证的最小CSR掩码**，也不意味着用户批准了任何一项。
不建议直接使用A13或猜测0x203即可解决。若坚持完全原包原布局，必须先在这些约束下决定受信任加载/权限策略，再申请对应精确变更。
本轮停在此处，不创建新IMG、不自动改外置或内部EFI，也不请求用不完整栈先碰运气启动。

## 正常安装路径与仍未通过的门槛

1. 有效bundle seal/代码签名、适用于kext的信任身份，或明确获批的开发策略；用户批准不能修复无效签名。
2. 三个L/E kext完整，HookCase提供正确export；真实provider版本兼容区间与符号/ABI都满足。
3. 对任何KC rebuild，原生验证并安装精确25G83 KDK，使用当前kmutil支持的参数，明确影响的KC与Preboot。
4. 按系统批准要求处理待批准状态；不使用`-z`/`--no-authorization`、missing-KDK绕过或错误忽略。
5. AMFI/用户态library validation及sandbox是否接受实际compiler链必须另行得到证据，静态codesign通过不保证运行通过。

参考：目标 `kmutil install/load --help` 的原始证据；Apple [Kernel](https://developer.apple.com/documentation/kernel) 的kext签名/安装说明。
Apple Silicon Reduced Security指引不能直接当作本HP Intel的操作步骤。`codesign` adhoc验证的定义见
[Apple Security StaticCode.cpp](https://github.com/apple-oss-distributions/Security/blob/main/OSX/libsecurity_codesigning/lib/StaticCode.cpp)：adhoc结构有效没有CMS证书信任链。
