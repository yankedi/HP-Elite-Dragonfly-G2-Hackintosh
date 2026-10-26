# GA4.10 实际执行结果

> **最新KC修复：** [KC-REPAIR.md](KC-REPAIR.md)。一次明确修正后的aux-only构建rc0，三项驱动和原三项均已安装到目标AuxKC，原Boot/System及Preboot未变；运行时认证与策略引导尚未验证，未重启。

> **最新现场：** [离线安装与首次KC结果](OFFLINE-INSTALL-KC.md)及[机器可读收据](OFFLINE-INSTALL-STATE.json)。
> 11项系统组件已实际安装并核验；首次KC调用rc71（只读文件系统），失败后16项KC/Preboot基线仍一致，未自动重试。
> 以下各轮结果保留历史时点含义，不再代表当前“未安装/未尝试KC”的状态。

> **后续Recovery实测更新：** 已使用原hpdiag专用密钥登录2222/root并实际执行SIP命令，
> `csrutil`返回69、原生`nvram`返回not permitted，CSR仍0。
> 原“进入Recovery即可执行”步骤已被实证纠正；见[最新衔接](RECOVERY-SSH-NEXT.md)。
> 已准备新的独立VESA策略副本以供后续物理引导验证，当前没有策略生效或系统安装成功声明。
> 按用户要求保持EliteBook开机及SSH，不执行关机/重启。下文为上一轮封存执行结果。

## 已完成的状态

- **BACKUP_COMPLETE**：目标独占APFS完整备份，含11目标原状态/父目录与对象元数据、整Library及System KernelCollections、当前Preboot完整KC目录、NVRAM/安全/卷组/快照/挂载/加载清单。
  原生pax保留ACL、xattr、flags及AppleDouble；16个原有文件经过原生内容解包和本地再次hash核对。
  完整restore.zip在目标、NixOS和Ventoy介质三处SHA256一致。详见BACKUP.json。
- **KDK_INSTALLED**：仅使用原有精确25G83 KDK；源/目标SHA256一致。DMG checksum VALID但自身未签名，未伪称签名通过；
  真正安装源`KernelDebugKit.pkg`原生pkgutil返回`0 / signed Apple Software`，链到Apple Root CA。
  installer实际rc0，标准`/Library/Developer/KDKs/KDK_26.6.2_25G83.kdk`及Apple安装收据存在；
  kernel SHA256 `1542ae9efea6d3a212248446d610b677d66fec02da5a5bfacf2b1a67f544b47e`与包内一致，
  Darwin25.6.0、xnu12377.161.14~5，UUID`39CC2C26-3F72-3565-89C4-94DFE36DFDF2`与运行内核相同。

## 当前停止状态

**BLOCKED_PHYSICAL_RECOVERY**：root对GPUBundles的W_OK仍为no，目录restricted/rootless；SIP和authenticated-root仍enabled。
目标csrutil原生usage明确enable/disable仅Recovery可用。必要安全变更已获授权，但不能经SSH假装Recovery操作完成。
最小拟用配置为CSR0x3：kext+fs，保持AppleInternal、其他SIP分项及authenticated-root保护；
未采用上游0xA13或全局AMFI参数。精确物理步骤见[RECOVERY-NEXT.md](RECOVERY-NEXT.md)。

以下状态**没有完成**：`POLICY_APPLIED`、`SYSTEM_COMPONENTS_INSTALLED`、`KC_REGISTERED`、`INSTALL_READY`。
11系统目标尚未写入，KC注册未尝试，不需要为此撤销系统驱动文件。没有无人值守重启或GPU程序。

## 已准备的实际组件

- 已校验原staging后，创建全新`/Users/Shared/GA410-work-20261023-0820/package-signed`，未改原staging。
- 31个Mach-O与13个bundle全部原生ad-hoc签名并严格deep验证通过。保留可读取的原identifier/entitlements/flags，
  不沿用Apple锚定requirement，不冒充Apple或Developer ID受信任签名。
- 独立回读逐个比对全部31 Mach-O原sections与非签名/非segment load commands；全部一致。
  198项非签名资源及Plist字节也不变；libxedrv、Adapter、LLVMbridge、旧Gen12/TGLLP IGC及资源均保留。
- 签名只准备了候选，实际加载仍需获授权策略及KC条件。EFI Lilu副本虽已签，原IMG未替换；原EFI注入不等同AuxKC加载。
- 旧LLVM3802/3902五条强依赖仍原样保留，不以尚未证实的动态可达性阻止此次签名/KDK工作；若实际加载器报缺依赖必须处理。
- 创建新私有OC配置副本，删除CSR0 Add默认值，ocvalidate通过；未应用到任何EFI或IMG。
  既有GA48/VESA的Add不覆盖已存在CSR且Delete不含CSR，回到VESA后须验证实际持久值。

## 记录与真实错误处置

所有目标命令的实际命令/时间/rc/stdout/stderr在`ga410/private/commands/`，凭据不写入文件。
首次ditto复制KernelCollections遇Operation not permitted即停止，没有半安装；失败目录保留，改用pax归档后成功。
`pkgutil --pkgs=<不存在收据>`的rc1与csrutil不存在help子命令的rc64都保留，没有当成功；之后用独立存在检查、全收据列表及原生usage定位。
签名后首个未压缩回传超时，部分本地tar保留；已成功的44次签名不重复，改为压缩只读回传后验证成功。

原内部ESP实际只读SHA256仍为`14f9cb981688bebea8e592f85fdc0a55d2f96db3ca4448b9ca3e62f13c51ff15`。
既有GA48/VESA不覆盖；新增文件仅备份/工作/开发KDK/实验签名候选/私有配置与日志。
本轮不以静态准备冒充完整系统安装，下一步是[物理Recovery操作](RECOVERY-NEXT.md)，随后回VESA由SSH继续安装/KC。
