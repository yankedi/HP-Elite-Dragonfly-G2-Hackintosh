# GA4.10 下一次物理启动：唯一当前操作入口

> **实测更新：已迭代至R3的CCS resolve写页故障。下一次入口见[R4启动说明](R4-NEXT.md)。以下保留首次启动前的安排。**

## 启动前准备状态

当前系统组件、AuxKC、实验镜像、独立Recovery镜像、一次性日志collector和恢复工具均已准备。
镜像及实际交付SHA256见`FINALPREP-DELIVERY.json`，总收据见`FIRSTBOOT-STATE.json`。
**PREBOOT_PREP_COMPLETE仅表示启动前可做的准备完成，不代表POLICY_APPLIED、驱动已加载或Metal通过。**
本轮没有重启/关机，没有改内部EFI或默认启动项。

## 正常首次实验启动

由用户安排下一次物理启动时：

1. Ventoy选择 **`ISO/linux/HP-Tahoe-TGL-GA410-CSR203-AMFI.img`**。
2. 在OpenCore选择**已安装的Tahoe 26.6.2 / 25G83系统**，不是Recovery/dmg条目。
3. 保持网络；显示正常时留在桌面，不启动额外GPU测试。代理使用`SSH-ACCESS.md`中的普通22端口连接取证。

新镜像沿用GA48的HP完整实现、ACPI/USB/网络/设备属性和GPU参数，明确携带：

- `csr-active-config=<03020000>`，即`0x203`。
- `amfi_get_out_of_my_way=1`。
- Lilu→NootedGreen的注入顺序，WhateverGreen不同时启用。
- HookCase/FB/accelerator从已安装AuxKC提供，没有重复放入EFI/Kernel Add。
- `-ngreentgltahoe`与原`-ngreennoplanesfix`保留；未改驱动功能或重新启用未经验证的planes偏移。
- 原`debug=0x100`、ApplePanic和OC文件日志保留；没有自动重启安排。

两份新镜像都明确Delete/Add boot-args及CSR，保留WriteFlash=false。
Delete仍可能删除原持久变量；不能认为“USB引导、WriteFlash=false”就没有NVRAM影响。
实验参数完整192字节，已有平台boot-args长度范围内；没有关闭authenticated-root或设置AppleInternal。

## 自动取证的范围

`/Library/LaunchDaemons/com.ga410.firstboot.plist`仅RunAtLoad一次，KeepAlive=false，没有定时重复任务。
collector有一次性marker`/private/var/db/ga410-firstboot-once`，一个15秒有限延迟，命令均有超时和输出上限。
记录CSR/boot-args、loaded kext、PCI、framebuffer/accelerator registry、内核消息、kernelmanagerd日志、网络、进程、KC哈希和近期panic文本。
**不调用Metal API，不请求加载kext，不运行GPU工作负载，也不修改电源或触发重启。**

目标结果目录：`/Users/Shared/GA410-firstboot/`。
启动前只做了原生语法/路径预检，没有把当前Recovery记录伪装成首启结果，也没有创建一次性marker。
若系统在launchd之前挂住，collector不会有结果；使用屏幕照片及独立Recovery取回可持久化的panic/OC日志。
镜像内原继承的`opencore-*.txt`是历史日志，只有新生成的差异文件才可作本次引导证据。

首轮验收顺序：实际CSR/boot-args→PCI8086:9A49→Lilu/NG/HookCase/FB/accelerator→显示与SSH。
这些通过后再手动逐层做MetalDevice→ShaderCompile→小规模GPUCompute；本轮没有自动运行它们。

## 黑屏、panic或无法连接时

进入下一次Recovery时：

1. Ventoy选择 **`ISO/linux/HP-Tahoe-Recovery-GA410-CSR0.img`**。
2. OpenCore选择其内置 **Recovery / HPRECOVERY (dmg)** 条目，**不要把已安装Tahoe当作干净回退系统**。
3. 该镜像携带原VESA boot-args、CSR0，无实验AMFI参数；内置BaseSystem/Chunklist与原GA48中已验证的独立Recovery字节相同。
4. 联网后用现有`sh /Volumes/系统/hpdiag/s`重开SSH；其余普通命令由代理执行，完整连接命令已写在`SSH-ACCESS.md`。

新Recovery镜像尚未物理启动验证；文件/配置/内置Recovery载荷已原生核对。
它本身不会撤销目标系统驱动，必须在独立Recovery中操作目标Data。

工具目录默认：`/Volumes/TARGET_VOLUME/GA410-FirstBoot-20261023`。卷名改变时使用该目录的实际挂载路径。

```sh
# 仅完整恢复预检：已在本机当前真实Recovery执行成功
bash /Volumes/TARGET_VOLUME/GA410-FirstBoot-20261023/restore-firstboot-recovery.sh --verify

# 仅保留现场；不要求AuxKC仍等于首启前版本
bash /Volumes/TARGET_VOLUME/GA410-FirstBoot-20261023/restore-firstboot-recovery.sh --collect

# 确需回退时执行：先保留现场，再撤销11项GPU组件并恢复原KC
bash /Volumes/TARGET_VOLUME/GA410-FirstBoot-20261023/restore-firstboot-recovery.sh --restore
```

恢复工具以固定卷UUID识别Data/System/Preboot及卷组，适应设备编号、挂载名变化；校验原备份和当前组件，保留实际返回码。
原完整备份在目标Data、Ventoy、NixOS三处保留；目标上的原备份目录已由新工具再次真实SHA256核验。
实际破坏/恢复未执行；`--verify`的通过不宣称完成过真实恢复演练。
恢复后先验证原状态，再用原VESA系统引导；不要Reset NVRAM，不盲恢复整个变量字典。

## 所有记录的位置

- 工程：`ga410/reports/`及忽略的`ga410/private/commands/`。
- Ventoy：`GA410-FirstBoot-20261023/`，含本说明、SSH方式、工具、收据、SHA清单和操作证据归档。
- 目标Data在线路径：`/Users/Shared/GA410-work-20261023-0820/firstboot-prep-20261023/`。

历史`RECOVERY-NEXT.md`、CSR3维护镜像与早期“回VESA后再安装”的指引不再是当前启动安排。以本文件为准。
