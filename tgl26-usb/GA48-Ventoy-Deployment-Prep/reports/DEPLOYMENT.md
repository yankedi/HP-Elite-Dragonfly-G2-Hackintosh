# 下一轮受控部署计划——本轮不执行

> GA49 更新：[路径纠错](GA49-CORRECTION.md)撤回旧SSV必改判断；当前原生预检与计划以 `../ga49/reports/RESULTS.md` 为准。

## 当前硬阻塞

1. 系统端TGL/HookCase/用户态栈全未部署。
2. 当前SIP/authenticated-root启用，`/` sealed只读，但Caches实际是Data firmlink，不能据此判定xe.bundle无法写入。
   GA49确认Caches root W_OK=yes；GPUBundles实际restricted且root W_OK=no，需解决该真实权限前提。
3. 原生包codesign/信任检查未做，部分上游输入已知unsigned；代码页哈希不等于可注册。
4. 常规KDK目录不存在，精确25G83符号/重建前提未确认；原生依赖解析/注册从未运行。
5. PLANES2、FMT/VALD、provider ABI、LLVM32023运行解析和legacy3802/3902加载仍无HP实测。

因此本计划**不是当前可直接执行到底的安装命令**；这些阻塞必须在下一轮逐项解决并获得对应授权。
不得通过运行原install.sh、XE_FORCE=1、复制A13、加AMFI参数、skip approval或重写驱动绕过。

## 分阶段顺序、证据和逆向动作

| 顺序 | 后续需单独批准的动作 | 完成证据/失败处理 | 逆向 |
|---|---|---|---|
| 0 | 复核机器/磁盘/版本/实际启动路径，确认独立VESA和Recovery可用 | 与本轮读回比较，任何变化先重新审查 | 无写入 |
| 1 | 新建APFS staging：仅 `/Users/Shared/GA48-preflight/` | 精确影响范围见TARGET-PREFLIGHT；原归档哈希匹配后解包 | 仅清理这个新目录，不动系统 |
| 2 | 保存系统GPU目标、AuxKC、active Preboot和全部安全/加载状态 | 新备份目录 `/Users/Shared/GA48-backup-<时间>/`，存在/不存在清单、metadata、diff、SHA256全部成功 | 保留离线可读副本；备份失败禁止安装 |
| 3 | 用原生codesign/plutil/依赖工具检查staging中的真实产物 | 逐项返回码与日志；已知unsigned/seal错误必须定位，不能自动签名掩盖 | staging可删除；无系统安装 |
| 4 | 解决签名/信任/SSV路径/KDK前提；如果确实需要任何安全变更另行精确批准 | 原生包校验、受信任加载策略、完整布局及恢复方案均有证据 | 保存每个获批改变的旧状态，先有可用逆向方案 |
| 5 | 放置HookCase及两个AppleTGL kext到L/E | root:wheel，保留正确mode/xattr；逐文件内容匹配，尚不注册 | 原存在恢复，原不存在删除新项 |
| 6 | 放置L/E五bundle、GPUBundles两bundle及xe.bundle完整编译资源 | 必须在批准且实际可写的原路径放置，不能只装EFI或一部分userland | 对上述精确Data路径做同样恢复，不默认需要SSV快照操作 |
| 7 | 注册/构建所需KC | HookCase依赖先满足，然后TGL framebuffer/accelerator；每条返回码立即检查 | 先恢复文件，再以匹配KDK修复KC/Preboot，不盲拷活动KC |
| 8 | 核实首启条件，再由用户从Ventoy选GA48 | 原生依赖/注册/签名通过，完整栈齐，回退可靠；确认bootargs Delete影响 | 从独立VESA或Recovery逆向恢复；不改内部EFI或默认项 |
| 9 | 授权启动后仅检查PCI/NG/TGL绑定 | 原生9A49、isRealTGL=1、Lilu/NG、TGL FB/accelerator依次检查 | 任一失败停止GPU工作，收集日志并回退 |
| 10 | 再分别批准MetalDevice、ShaderCompile、最小GPU工作 | 每层有真实证据，不跳步把CPU链接成功称Metal成功 | 失败保存request/reply/崩溃日志，VESA恢复，不自动重试Hang |

## 精确安装布局与依赖顺序

EFI：本轮已做Lilu1.7.2 → NootedGreen1.0.0，WhateverGreen禁用；其余HP配置保留。
系统端：HookCase8.0.1 → 两个TGL kext所需的Apple provider与KPI闭包。
HookCase没有personality也不能遗漏；它为两kext提供 `org.smichaud.HookCase` 依赖和 `_strnstr`。

从 `package/payload` 原样按相对路径复制：

```text
Library/Extensions/
  HookCase.kext
  AppleIntelTGLGraphics.kext
  AppleIntelTGLGraphicsFramebuffer.kext
  AppleIntelTGLGraphicsMTLDriver.bundle
  AppleIntelTGLGraphicsGLDriver.bundle
  AppleIntelTGLGraphicsVADriver.bundle
  AppleIntelTGLGraphicsVAME.bundle
  AppleIntelGraphicsShared.bundle
Library/GPUBundles/
  AppleIntelTGLGraphicsMTLDriver.bundle   # patched MTL17 + libxedrv
  AppleIntelGraphicsShared.bundle
System/Library/Caches/xe.bundle/         # adapter/bridge/old plugin/Gen12 IGC/6 resources
```

编译请求保持 MTLDriver → SerializedBitcode adapter → WithOptions旧plugin → Gen12/TGLLP IGC，
bridge重导出32023；不是只装kernel kext即可工作。

## 审查程序的调用契约

`tools/deployment-review.sh`、`tools/recovery-review.sh`、`tools/recovery-kc-review.sh` 是本地非可执行审查稿，
仅用 `bash -n` 检查。**本轮没有复制或执行它们。**
未来批准后需要显式phase；没有全自动“一键安装并重启”入口。
脚本要求固定staging目录、完整备份、原生签名检查、单独审查的加载/恢复前提；不会自行生成批准收据。
审查后的phase命名为backup/preflight/install-kexts/install-userland/register，恢复分restore-files/restore-kc。

- `out/PACKAGE-SHA256SUMS` 由本轮已核对归档的inventory生成，应复制到staging根目录；
  命令在 `package/` 内运行校验。原tar SHA是信任锚，不能只信目标机自生成的manifest。
- 如需经批准重新签名，保留旧文件，重新产生并审查新包哈希/manifest和原生证据；
  不要直接编辑旧manifest来“让校验变绿”。
- `GA48_PREBOOT_KC` 必须来自当次实际boot路径的只读证据；不能照抄过期UUID。
- `kmutil load --load-style match-only -p <精确kext>` 需要单独注册批准，可能更新AuxKC。
  不使用上游 `-z`；记录每条stdout/stderr及rc，非0立即退出，不继续下一kext，不重启。
- 加载命令成功仍要inspect AuxKC及active Preboot/加载状态，核实实际注册结果与完整闭包。
- GA49修正后，userland阶段检查每个真实目的父目录，不再因sealed根停止；当前GPUBundles W_OK=no仍会停止。不会自动改变保护。

KC恢复程序使用实际25G83帮助确认的 `kmutil install --volume-root ... --update-all`，
会重建集合，需匹配KDK与允许的策略；没有 `--force`、`--allow-missing-kdk` 或跳过批准。
当前无法保证它能成功，所以它是下一轮受控恢复程序，不是已验证的自动救援承诺。
详细逆向清单见 `VESA-RECOVERY.md`。
