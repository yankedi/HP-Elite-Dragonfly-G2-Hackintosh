# 下一步：一次物理 Recovery 操作

> **后续实测更正：** 用户已进入25G83 Recovery并启动`hpdiag/s`的2222 SSH。
> 已找到原专用密钥并实际以root连接；无需密码或新增公钥。
> 下列`csrutil`命令已由代理执行，rc69：`failed to set csr-active-config`；
> 原生`nvram`写同一个CSR3也返回rc1、`(iokit/common) not permitted`。
> 因此不要再手动重复下面的旧命令。当前CSR仍0，策略未生效。
> 最新衔接见[RECOVERY-SSH-NEXT.md](RECOVERY-SSH-NEXT.md)。
> 按用户最新要求，EliteBook保持开机和SSH，不执行关机或重启。

当前已实际完成 `BACKUP_COMPLETE`、`KDK_INSTALLED`；实验签名副本已准备。
当前为 `BLOCKED_PHYSICAL_RECOVERY`，不是 `INSTALL_READY`。系统驱动11路径尚未写入，KC注册尚未尝试。

## 原拟操作（历史记录，CSR写入已实测失败）

1. 将含VESA和备份的Ventoy介质接到HP。正常结束当前macOS会话并手动重启。
2. 从Ventoy选择 **HP-Tahoe-VESA-XHCI-RHUB.img**。在其OpenCore选择器中选择目标 **macOS Recovery / Recovery 26.6.2**；必要时按空格显示辅助项。
   对应Recovery来自当前卷组`REDACTED-MACHINE-ID`，本轮已只读验证BaseSystem为25G83且工具可读。
   不选GA48/旧TGL镜像，不使用Reset NVRAM，不更改默认启动盘。
3. 进入Recovery后打开“实用工具 → 终端”，执行：

```sh
csrutil enable --no-internal --without kext --without fs
csrutil status
csrutil authenticated-root status
```

目标是仅允许未受信任kext与受保护文件系统写入，预期CSR掩码`0x3`；
`--no-internal`避免csrutil默认附带AppleInternal位。目标工具字符串已确认这些选项存在，部分配置可能打印unsupported configuration警告。
只接受命令成功，authenticated-root仍为enabled；如报未知选项、执行失败或authenticated-root不是enabled，停止并提供屏幕原文，不换成全局disable。

**不要执行 `csrutil authenticated-root disable`，不添加AMFI全局参数，不放宽kext用户批准位。**
若Recovery中status显示当前会话旧值，实际是否生效以重启回维护系统后的CSR原始值和分项状态为准。

4. 手动重启，再从同一 **VESA** 镜像进入已安装的25G83 macOS，保持网络/SSH可用。然后通知代理“已返回VESA”。
   此时仍不要启动GA48；代理将通过SSH核实新CSR/权限、安装完整组件并执行一次原生KC流程。

## 为什么无需改现有IMG或内部EFI

既有VESA和GA48的NVRAM Add含CSR0，但Delete不含csr-active-config。
OpenCore的Add只为不存在的变量提供默认值，故不覆盖Recovery持久写入的CSR；实际值必须回到VESA后确认。
另已生成通过ocvalidate的新配置副本，显式移除CSR0默认项，尚未应用到任何EFI/IMG。
现有GA48仍有boot-args Delete/Add：首次实际实验前保存原值，明确其可能影响持久变量；WriteFlash=false不是无NVRAM影响保证。

## 备份与恢复入口

- 目标完整备份：`/Users/Shared/GA410-backup-20261023-0830`。
- 可移植完整归档：`GA410-backup-20261023-0830.restore.zip`。
- 介质位置：Ventoy exFAT卷根目录的`GA410-Recovery/`。
- SHA256：`0022a9627ddb3eddc2b1cc47b7d20e9a3727bec6bc9030c01c8384f7fd68d86c`。
- NixOS副本：项目`ga410/private/`同名归档。
- 恢复工具：介质`GA410-Recovery/restore-recovery.sh`。**当前不需要运行恢复工具**；本轮未安装系统驱动或变更KC。

若后续注册/启动失败，先保存日志，从Recovery挂载并确认同卷组Data和Preboot，校验归档后用原生ditto解包。
恢复脚本接受明确的Data根、Preboot根和解包后的备份目录，不把只读System前缀当Data。
它仅适用于本机11路径原来全不存在的真实基线，删除实验新增项并恢复完整Data/Preboot KC归档与元数据、逐文件hash验证。
恢复后仍要核对sealed System KC、NVRAM/安全基线，再决定是否启动；脚本不自动重启、重建KC或批量回写NVRAM。
恢复工具本轮做了语法检查，尚未在真实Recovery执行，不能冒充已完成恢复演练。

若要回到本轮前CSR0，应在文件/KC恢复正常后从Recovery使用`csrutil enable --no-internal`，保留authenticated-root启用。
精确25G83 KDK是独立已安装开发组件，不作为GPU栈注册成功的证据；系统回退不要求盲删其收据。
