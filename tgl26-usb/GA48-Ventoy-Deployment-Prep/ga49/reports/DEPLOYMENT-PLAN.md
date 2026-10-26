# HP 25G83 精确部署计划（等待后续独立授权）

**状态：条件式计划，不是可立即执行的安装单。** 本轮只完成审计、获批staging、本地准备。
驱动实现与文件布局依JulioNectar固定提交 `6a1afb337d1fb1ff07ca032b5c1868fe2bd005ef`，不引入另一套架构。

## 1. 唯一输入与原布局

源：`/Users/Shared/GA48-preflight/package/payload`，使用前重验原tar SHA256
`51aaffade75da6d5076071e304e4634aefe60e68d7e0cdd12d79981e31f1b143` 及逐文件manifest。
归档246项、31Mach-O、无链接/特殊成员；新增目录只含获批归档、manifest、其原始解包内容。

| 源相对payload与目的绝对路径（逐字一致） | 当前原状态 |
|---|---|
| `/Library/Extensions/HookCase.kext` | 不存在 |
| `/Library/Extensions/AppleIntelTGLGraphics.kext` | 不存在 |
| `/Library/Extensions/AppleIntelTGLGraphicsFramebuffer.kext` | 不存在 |
| `/Library/Extensions/AppleIntelTGLGraphicsMTLDriver.bundle` | 不存在 |
| `/Library/Extensions/AppleIntelTGLGraphicsGLDriver.bundle` | 不存在 |
| `/Library/Extensions/AppleIntelTGLGraphicsVADriver.bundle` | 不存在 |
| `/Library/Extensions/AppleIntelTGLGraphicsVAME.bundle` | 不存在 |
| `/Library/Extensions/AppleIntelGraphicsShared.bundle` | 不存在 |
| `/Library/GPUBundles/AppleIntelTGLGraphicsMTLDriver.bundle` | 不存在 |
| `/Library/GPUBundles/AppleIntelGraphicsShared.bundle` | 不存在 |
| `/System/Library/Caches/xe.bundle` | 不存在 |

准确状态命令和错误见`DESTINATIONS.json`，不是仅按目录名称推断。实际安装前须重新枚举，不能据旧“不存在”覆盖后来新增文件。
L/E MTL和GPUBundles MTL**不同**，后者带libxedrv/MTL补丁；不能用前者覆盖后者。
xe中Adapter、PluginOld、LLVMbridge、Gen12/TGLLP IGC及资源全部保留；不删除legacy组件，不用GA46隔离实现。

## 2. 阶段及独立授权

| 阶段 | 操作与成功条件 | 授权状态/停止点 |
|---|---|---|
| A 只读与staging | 本轮已完成版本/路径/签名/依赖/KC审计；staging真实APFS解包+native检查 | **已获批并完成**，不扩大到其他目标文件 |
| B KDK原生验证/安装准备 | 单独获批复制精确本地KDK到新审定位置；原生hdiutil只读验证、pkg签名与package内容/build/kernel核对；若需安装KDK再单独批准 | 尚未批准。社区镜像hash匹配不代替Apple pkg信任。25G241不能替代25G83 |
| C 完整备份与恢复演练前提 | 按RECOVERY-PLAN建立全新APFS备份，保存ACL/xattr/flags、11路径存在状态、AuxKC/Preboot整目录及状态；离机副本哈希一致 | 尚未执行目标备份。原始KC本地字节读回不等于完整恢复演练 |
| D 签名、权限、依赖方案定案 | 明确处置实际失败及五条缺LLVM依赖；保留原实现。确定是否需开发安全策略并逐项授权；保留原bundle/失败记录 | 当前阻塞，见SECURITY-PLAN。不能先写半套文件后再找办法 |
| E 系统文件安装 | 只有B/C/D均满足并获系统安装批准后，完整复制上述11项、root:wheel、逐文件hash与元数据验证；只处理精确目的路径 | 未批准。任一父目录权限不满足、hash变化或返回非零立即停止，保留日志；不自动chmod/chflags补救 |
| F KC注册 | 另外获得KC授权后，按目标支持的正常kmutil流程及用户批准注册HookCase/FB/TGL，检查生成KC、依赖、UUID和Preboot同步状态 | 未批准。没有`-z`或忽略错误；成功码不代替生成物核对 |
| G 首次GA48启动 | 用户单独批准重启/选择外置GA48及NVRAM行为；仅在首启条件全部满足后操作 | 未批准；本轮不重启 |
| H 首启后诊断 | PCI9A49→NG/HookCase/TGL FB/accelerator→MetalDevice→shader→最小GPU，逐层、逐实验授权 | 不属于本轮安装准备，不执行 |

## 3. 与原作者安装器的精确对应

原作者`macos/install-macos.sh`复制L/E三kext及五bundle、GPUBundles两bundle、Caches/xe，
修改加速器personality为9A49和版本16.0.2，然后注册TGL/FB/HookCase。GA47包已包含相应Info改动，不再临时改字节。
该固定脚本注释目标25G241，实际文件未见build保护判断；另一些包装器是否有限制不能用于推断此文件有guard。
本轮不直接运行原脚本，不使用`XE_FORCE=1`。其末尾`kmutil load -z ... || true`不符合用户边界，不能照搬。

审核用同一架构候选语法（**未执行，不能将本节复制运行当授权**）：

```sh
kmutil load --load-style match-only \
  -p /Library/Extensions/HookCase.kext \
  -p /Library/Extensions/AppleIntelTGLGraphicsFramebuffer.kext \
  -p /Library/Extensions/AppleIntelTGLGraphics.kext
```

这是匹配/加载命令，可能触发KC/设备动作，不是签名预检。先后关系以HookCase provider先可用、TGL依赖可解为准。
如需要重建KC，目标帮助支持`kmutil install --volume-root <实际目标> --kdk <原生已验证KDK路径> --update-all`。
该操作可影响多个collection；须对实际卷可写性、目标kernel、权限和Preboot工作流审定，不把它当成“只注册AuxKC”。
当前sealed根不证明Caches不可写，但也不保证此全KC重建命令成功。实际报错时停止，不加force/allow-missing-kdk绕过。

旧`tools/deployment-review.sh`是审查副本，未在目标执行。它仍要求全部结构签名通过，因此会因当前原包的真实失败停止；
不能把删检查、伪造receipt或adhoc重签当成部署方案。当前也不能将它宣称为端到端验证过的安装器。
恢复副本同样未执行；离线Recovery因firmlink映射未审定已设置硬停止。

## 4. 首次GA48启动必须满足

1. 重核25G83、原生9A49、目标卷组/启动来源；当前11目的路径原状态与完整备份一致。
2. VESA IMG哈希/独立配置无变化，有可用的独立Recovery，明确错误KC也可能影响VESA，并有恢复途径。
3. GPUBundles/Caches/L/E在获批策略下实际可部署；不以root W_OK代替完成安装时的真实结果。
4. 三kext和所有userland资源完整、hash明确；签名失败被以批准且可审计的方案解决，不隐藏。
5. 精确KDK原生验证/安装，provider compatible版本和真实符号/ABI链接通过；HookCase导出满足TGL。
6. 3802/3902消费者的动态可达性/处置及32023桥接、sandbox/library-validation前提明确。仅“主静态闭包不经旧库”不足以关闭此项。
7. 系统文件安装获批且完成；KC注册另批且每命令成功，检查对应AuxKC/活动Preboot、待批准/待重启状态。
8. 决定安全策略实际来源及外置GA48 CSR0的相互作用；不改内部EFI，不覆盖当前GA48，不临时复制Dell配置。
9. 保存NVRAM原boot-args；明确批准GA48 Delete/Add可能影响持久变量。保留原回退参数，禁Reset NVRAM。
10. 用户单独批准首次启动。启动不等于Metal通过；PLANES2默认关闭、FMT/VALD等既存风险仍按GA48诊断逐层验证。

当前至少3–9未完成，因此停在准备阶段。安装、KC、安全、重启授权互不替代。
