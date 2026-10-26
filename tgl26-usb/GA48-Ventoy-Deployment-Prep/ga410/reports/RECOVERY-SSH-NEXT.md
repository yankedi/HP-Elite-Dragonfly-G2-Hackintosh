# Recovery SSH：实际命令与下一次引导准备

> **最新KC现场：** [KC-REPAIR.md](KC-REPAIR.md)。目标已装入包含三项TGL/HookCase条目的新AuxKC；旧“直接回维护系统再安装”的指引已过时。当前保持Recovery开机，后续引导须先核实策略与回退方式。

> **后续更新：** [OFFLINE-INSTALL-KC.md](OFFLINE-INSTALL-KC.md)为最新现场。
> 已测得Recovery实际CSR接口允许离线安装，11项组件已安装；首次KC注册rc71，未重试，原KC/Preboot哈希未变。
> 本文及`RECOVERY-STATE.json`保留此前时点；“系统目标尚不存在/KC未尝试”已由新收据取代。

## 当前现场

- 用户已通过`sh /Volumes/系统/hpdiag/s`启动Recovery临时sshd，端口2222。
- 在旧工程`docs/recovery-network.md`找到了专用客户端密钥及固定host alias/known_hosts。
  专用密钥实际root认证成功，**无须密码或另加公钥**；私钥字节未复制或提交。
- 实际根为25G83只读macOS Base System，目标System/Data同属
  `REDACTED-MACHINE-ID`，完整备份及Ventoy介质在真实Recovery中可读。
- **按用户要求保持EliteBook开机，保留SSH；未执行关机或重启。**

## 必须保留的真实失败

```text
csrutil enable --no-internal --without kext --without fs
return code 69
csrutil: failed to update system integrity configuration: failed to set csr-active-config

nvram 'csr-active-config=%03%00%00%00'
return code 1
Error setting variable - 'csr-active-config': (iokit/common) not permitted.
```

这已经是Recovery内root执行的结果，不能再说只需要用户进入Recovery重复命令。
CSR最终仍`00000000`，SIP和authenticated-root仍enabled；未把失败记成`POLICY_APPLIED`。
错误定位到当前Recovery/引导环境拒绝CSR的NVRAM写入，具体内核/固件拦截层尚未证实。
本地GA48配置的DisableVariableWrite=false，不据此推断本次实际引导全部设置相同或硬说是固件故障。
没有改用全局disable、扩大CSR掩码、关闭authenticated-root或放宽AMFI来掩盖错误。

Recovery缺少shasum、diff和可读的logd store，相关127/65失败日志保留。
使用现有原生md5核对Recovery介质上的完整备份及原GA48与本地留存副本一致；
不把MD5写成SHA256。最终新镜像的完整SHA256由SSH流式回读到NixOS计算。
普通hdiutil自动mount失败后，使用明确raw attach及原生mount_msdos处理已识别的镜像分区，未挂载内部EFI。

## 新的独立维护镜像

Ventoy路径：`ISO/linux/HP-Tahoe-VESA-GA410-CSR3.img`。
它从原`HP-Tahoe-VESA-XHCI-RHUB.img`全字节复制，写入前原生MD5与原镜像一致。
只改配置中的两处：

1. `NVRAM/Add/.../csr-active-config`：`00000000` → `03000000`。
2. `NVRAM/Delete/...`：加入`csr-active-config`，以免旧的CSR0优先于Add。

保留原VESA boot-args和全部驱动、Recovery资源；没有NootedGreen或TGL系统栈注入。
保留`WriteFlash=false`、SecureBootModel Disabled，未添加AMFI参数。
配置通过ocvalidate与原生Plist校验；全部原有非配置文件MD5一致。
原生挂载在新镜像额外生成了`.fseventsd/fseventsd-uuid`，该附加文件明确记录，未冒称文件清单完全相同。
全清单、哈希和精确配置回读结果见`RECOVERY-SSH.json`。
旧VESA镜像、GA48和内部EFI均未覆盖。

新镜像大小：1,343,225,856字节；完整SSH回读SHA256：
`279dbdbd50f0068e33a0dd46bd7ba33e81e3e11b74fa2995f98668f1ee75323b`。

**重要的生效范围：** Delete仍可能删除持久变量；WriteFlash=false不保证CSR3跨其他引导链持久。
新镜像明确携带CSR3，只有真正用它启动后才可验证当前系统策略；不能保证原GA48随后自动沿用CSR3。
后续真正TGL首启也必须使用匹配CSR3的新配置/独立镜像，完成全栈/KC后再准备，不能直接宣称原GA48已INSTALL_READY。

## 接下来

当前不需要用户输入命令，也不触发任何关机或重启。
当用户后续决定进行下一次物理启动时，从Ventoy选择**新的VESA-GA410-CSR3镜像**，
然后进入已安装的25G83 macOS，保持网络与普通SSH可用。
代理将核实实际CSR为3、authenticated-root仍启用、GPUBundles权限满足，再继续完整安装和KC流程。

新镜像尚未物理启动，不记作策略生效。当前结果仍是`BACKUP_COMPLETE`、`KDK_INSTALLED`，
以及本次真实的CSR写入错误`BLOCKED_REAL_ERROR`；后续新策略引导仍需物理操作。
`SYSTEM_COMPONENTS_INSTALLED`、`KC_REGISTERED`、`INSTALL_READY`均未完成。

旧`STATE.json`是上轮封存快照，其文件hash不随本次文档/工具变更重写；本次另有独立收据。

## 恢复工具的现场修正与验证

实际Recovery没有`/usr/bin/shasum`，已修正恢复工具：有shasum时继续SHA256；
否则用本机原生`/sbin/md5`，对照从已验SHA256原始备份派生、且脚本固定摘要的映射表。
明确是MD5回退核对，不冒称Recovery原生SHA256。USB上为`restore-recovery-native.sh`和`recovery-checksums.tsv`。

另发现旧portable ZIP生成早于目录末尾的`SHA256SUMS`及完成标志，虽然源文件/元数据完整，
但不足以直接运行原恢复脚本。因此保留旧归档，并从已完成目录生成新的自包含归档：
`GA410-backup-20261023-0830-complete.restore.zip`。
新归档SHA256为`95cc69b3cc94963ba370e2103a4781d49d359df7512fd0ae856b5137717f1a33`，
包含SHA清单、backup.rc=0和完成标志；所有原始源文件及pax元数据再次在NixOS验证。
已在真实Recovery中原生解包到新tmp目录，并实际运行新工具`--verify-backup`成功，未执行文件/KC恢复。
本轮没有完整破坏/恢复演练、没有安装系统GPU组件或修改KC，不扩大这一验证的成功范围。
