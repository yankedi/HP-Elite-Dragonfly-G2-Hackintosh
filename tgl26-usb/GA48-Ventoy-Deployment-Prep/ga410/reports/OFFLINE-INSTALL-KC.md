# GA4.10：完整离线安装完成，首次KC调用失败

> **后续修复：** 用户明确要求继续后，已成功构建并安装AuxKC；见[KC-REPAIR.md](KC-REPAIR.md)及[KC-REPAIR-STATE.json](KC-REPAIR-STATE.json)。本文及对应收据保留首次失败时点，不代表最新KC状态。

最新证据截至2026-10-23 07:07:24 UTC；此前`STATE.json`及`RECOVERY-STATE.json`保持历史快照。

## 已实际完成

- `BACKUP_COMPLETE`：既有完整备份保留；本次在真实Recovery用新增CommonCrypto SHA256工具重新核对备份清单22项，rc0。该工具已在目标执行并与本地自身SHA256交叉核对；这不改写此前原生MD5恢复校验的历史事实。
- `KDK_INSTALLED`：精确25G83 KDK kernel再次SHA256核对为`1542ae9efea6d3a212248446d610b677d66fec02da5a5bfacf2b1a67f544b47e`。
- **`SYSTEM_COMPONENTS_INSTALLED`**：在已核实的目标Data卷离线安装全部11项原布局组件，安装事务rc0。
  源签名候选251项SHA256通过，安装目标204项SHA256通过；255条对象元数据均root:wheel且无group/world写权限。
  11个Bundle ID已记录，全部组件原生`codesign --verify --strict --deep`通过；这是ad-hoc结构验证，不代表Apple受信任加载或AMFI放行。
- 安装位置：`/Volumes/TARGET_DATA_VOLUME`下的Data实际路径；System配对卷为`/Volumes/TARGET_SYSTEM_VOLUME`，卷组`REDACTED-MACHINE-ID`、目标build25G83。
  在线对应L/E三kext及五bundle、GPUBundles两bundle、Caches/xe.bundle；驱动功能及旧LLVM依赖未修改。

## CSR判断修正

只读probe调用当前内核`csr_get_active_config`得到0；但`csr_check`对kext、fs、NVRAM、device-configuration及unauthenticated-root均返回0，对any-recovery-os返回EPERM。
这是当前Recovery的实际允许判断，不等于下一次安装系统启动后CSR3已经生效，也不等于持久关闭authenticated-root。
因此此前把`csrutil status: enabled`直接等同“Recovery无法离线安装”的推断不成立。

CSR变量普通及显式Apple GUID写入仍rc1；删除调用rc0却仍读到CSR0。
同build KDK AppleEFINVRAM UUID与实际加载UUID均为`7E2D300F-3D59-35BF-879C-EA5F7C54D47B`；反汇编显示变量缓存权限与EFI属性有关，与`WriteFlash=false`产生的易失变量只读现象吻合。
这是有二进制依据的原因判断，尚未读取运行时内部缓存标志，不宣称已完全证实固件或唯一拦截路径。
独立VESA CSR3镜像仍未启动，**`POLICY_APPLIED`未完成**。

## 唯一一次真实KC调用

```sh
/usr/bin/kmutil install \
  --volume-root "/Volumes/TARGET_SYSTEM_VOLUME" \
  --kdk "/Volumes/TARGET_DATA_VOLUME/Library/Developer/KDKs/KDK_26.6.2_25G83.kdk" \
  --variant-suffix release --arch x86_64 \
  --update-all --update-preboot --verbose
```

实际rc **71**。原始stdout/stderr及命令时间均保存在`ga410/private/commands/recovery2222-kc-register-first-attempt.json`。
关键输出：

```text
Warning: kmutil install's usage of --update-all is deprecated. Use kmutil create --update-all instead
Warning: com.apple.driver.KextExcludeList was not found!
rebuilding release collections:
    boot kernel collection
    system kext collection
failed to build release collection:
    Error Domain=NSPOSIXErrorDomain Code=30 "Read-only file system"
```

本次命令范围过宽：`--update-all`触发了Boot/System KC重建，在只读System卷写入时失败。
这是实际命令选择及离线目标写入错误，**不能据此证明TGL符号/C++ ABI链接失败，亦不能据此认定必须关闭SSV**。
输出还提示KextExcludeList缺失及两项KDK扩展UUID差异；这些需在后续获准的新尝试前处理目标/repository及重建范围，不能隐去。
本次没有获得三项目标kext成功纳入AuxKC的证据，**`KC_REGISTERED=false`，`INSTALL_READY=false`**。

## 失败后现场与停止边界

- 按既定约束，KC失败后没有自动重试、扩大CSR或关闭authenticated-root，也没有继续TGL首启准备。
- 原有System、Library和Preboot的16项KC相关文件SHA256全部仍匹配备份；AuxKC及Preboot文件列表已复核。
  未产生经过验证、可用于首启的新KC；不把内存中链接过程输出当作注册成功。
- 完整11项组件保留在Data卷，未出现复制事务半安装；旧KC未改变，无KC需要回写。完整原状态备份及恢复工具仍保留。
- 未执行重启、关机或GPU测试；失败后的SSH核验命令仍rc0。内部EFI和原GA48/VESA镜像未写入。
- 未来再启动准备前必须解决KC目标映射/重建范围并取得真实注册证据，核实实际引导策略和匹配TGL配置；当前不要把任何GA48镜像当作已就绪的加速首启。

## 证据与恢复

机器可读摘要及主要日志SHA256见`OFFLINE-INSTALL-STATE.json`。本次工具本地提交：`512e4f5`（只读CSR与SHA256）、`9072ff8`（事务安装）；未push。
原完整恢复归档`GA410-backup-20261023-0830-complete.restore.zip`及USB上的`restore-recovery-native.sh`/映射表保留，恢复前仍需重新识别卷组和挂载映射。
本次未执行破坏/恢复演练。旧“无需撤销GPU文件”的记录已不适用于当前完整安装现场。
