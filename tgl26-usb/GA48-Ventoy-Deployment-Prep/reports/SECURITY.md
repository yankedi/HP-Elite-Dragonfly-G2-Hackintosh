# 上游与 HP 安全策略差异

> GA49纠正Caches路径判断，真实包签名和权限新证据见 [GA49-CORRECTION](GA49-CORRECTION.md)。本表其余内容为GA48时点记录。

“上游已验证”指固定上游提交对 Dell9320/25G241 的配置和作者运行报告，非本轮复现实测。
本轮 HP 证据来自当前25G83只读状态与本地静态核验，不能跨机器等价替换。

| 项目 | 原作者配置/报告 | HP 当前与 GA48 | 尚需什么；本轮允许性 |
|---|---|---|---|
| SIP | CSR=`0xA13`，plist130a0000 | 当前 CSR0、SIP enabled；IMG保留0 | 实际加载能否接受ad-hoc/unsigned未通过；改变SIP须另批，本轮不允许 |
| authenticated-root/SSV | A13含unauthenticated-root位；不能据此推断作者改过哪个snapshot | 目标authenticated-root enabled，sealed RO root；Caches是Data firmlink | Caches不要求因此改SSV；真正GPUBundles restricted和加载信任另行审查，不自动修改保护 |
| AMFI | `amfi_get_out_of_my_way=1`；保留 `_cs_validate_page` hook | 当前无此arg；GA47候选有，GA48默认与三候选移除 | 不能假定CSR0+该arg足够；不自动加AMFI绕过 |
| 保留驱动 hook | 上游早期路由 `_cs_validate_page` 并进行映像修补 | GA47真实实现原样保留；本轮未加载执行 | 即使去掉AMFI boot-arg也不表示未来加载NG没有签名验证hook；启动/加载必须另批 |
| OpenCore Apple Secure Boot | `SecureBootModel=Disabled` | HP母版本来即Disabled，保持 | 不把它等同UEFI硬件Secure Boot；不自动改配置 |
| UEFI firmware Secure Boot | 作者INSTALL要求off | 本轮没有改变固件，未单独读取其完整key/模式状态 | 由实际启动环境确认；本轮禁止更改 |
| 签名 | 上游patch后二进制/ad-hoc及部分unsigned输入 | 静态代码页匹配；原生包验证未做 | Apple codesign完整bundle、信任、entitlement、KC接受情况待授权实检 |
| kext approval | 作者要求系统设置批准；脚本还用kmutil -z | 目标无新栈，未注册 | 不照搬skip-approval；用户批准、完整依赖/KDK/策略先满足 |
| 默认启动/NVRAM | 作者可安装内部EFI | 内部EFI/BootOrder保持；只生成外置IMG | 本轮不运行IMG；未来boot-args Delete/Add影响见CONFIG-DIFF |

`0xA13` 包含 untrusted/unapproved kext、unrestricted filesystem、task-for-pid、unauthenticated-root相关位。
这里列出是说明差异，不是建议自动照抄。未满足加载前提就是明确阻塞；不会通过放宽保护或仅提供 EFI
宣称 HP Metal 可用。当前部署审查脚本不会自动改 SIP、SSV、AMFI、Secure Boot、签名或快照。
