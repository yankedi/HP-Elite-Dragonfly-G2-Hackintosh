# HP 25G83 备份与故障恢复清单

## 当前已只读保存的基线

- 十一个未来安装目的当前全部不存在，逐项命令/rc见DESTINATIONS.json。L/E存在，GPUBundles存在但restricted；Caches为Data firmlink。
- NVRAM XML、kern.bootargs、SIP/authenticated-root、mount、APFS卷组/快照、kmutil showloaded和inspect原始输出在`ga49/private/readonly/`。
  当前加载Lilu1.7.2、WhateverGreen1.7.1，无HookCase/TGL/NG；这与未来GA48禁用WEG、注入NG的状态有区别。
- 当前根卷信息重新确认卷组`REDACTED-MACHINE-ID`；不用旧UUID未经确认地推断活动Preboot。
- AuxKC：917,504字节，SHA256 `5d6170588133eae3fe1d4f0024f67960f0ce6aeb6d2f3266e9865d96ddfa8fcd`。
- 对应Preboot `boot/System/Library/KernelCollections/BootKernelExtensions.kc`：67,584,000字节，
  SHA256 `c80161fa3065883753fc285339281361a8469cbb6fb27653c88e2a22eb4807a4`。
- 两个KC均通过SSH只读cat回取到`ga49/private/kc-baseline/`，本地完整hash匹配；原Preboot目录含elides/im4m，目录清单已保存。
  **这些字节副本不是元数据完整的目标备份，更不是已验证的KC还原。**
- VESA、GA48本地/USB、旧eDP、GA32a共五个文件本轮hash均与GA48收据相同。VESA配置新回读有`-igfxvesa`且无NG条目；不依赖GA48。
  本轮没有物理重启测试VESA，也没有宣称它能避开所有系统端KC故障。

## 未来安装前必须创建的完整备份（未获执行授权）

新建且不覆盖的APFS目录，例如`/Users/Shared/GA48-backup-<时间>`，chmod700；保存到外部独立可读介质并hash验证。
只有获备份写入授权后才执行，不占用获批preflight目录来冒充安装批准。

| 对象 | 备份内容 | 恢复要求 |
|---|---|---|
| DEPLOYMENT-PLAN中的11项 | 每项存在/不存在、lstat、owner/group/mode、ACL/xattr/flags、符号链接目标、文件hash；若存在用ditto保留元数据完整复制 | 原不存在仅删除本轮确知新增的精确路径；原存在恢复内容和元数据。不通配删其他驱动 |
| `/Library/KernelCollections` | 整目录、AuxKC、附属元数据、native inspect/UUID及hash | 结合恢复后文件重建/核对；不能在线盲盖活动KC |
| 当前卷组对应Preboot KC目录 | 整目录含BootKC、elides、所有im4m等；实际路径由当轮根卷组确认 | 保存精确build/UUID/对应关系。更改前审定原生同步或离线还原办法，不只复制一个kc |
| 系统Boot/System KC | 当前路径/内容hash、inspect/UUID、与Preboot关系；若某项不存在记录不存在 | 重建前后对应比较，不能因AuxKC恢复就假定所有KC恢复 |
| NVRAM/安全 | `nvram -xp`原值、CSR、boot-args、SIP/authenticated-root、外置与内部OC设置读回 | 仅恢复批准过的变量/策略，不全局Reset或改BootOrder；不回写内部EFI |
| 运行状态 | 版本/kernel、showloaded、iostat/IORegistry必要身份、mount/APFS卷组和快照清单 | 同一目标卷组/版本上核对；不要在错误Data卷删除同名文件 |
| 引导/Recovery | 独立VESA/Recovery及当前ESP只读副本/原哈希；SSH与物理恢复步骤 | 不覆盖内部EFI或现有IMG，故障时能物理选择Recovery；本轮不通过首启测试替代授权 |

每次备份命令非零立即停止。所有对象复制、元数据和hash对比后才写BACKUP-COMPLETE；
单个receipt文件不是备份完整的充分证据。备份到本机之外并确认Recovery可读取。

## 故障恢复顺序（均待授权）

1. 保存失败日志与当前文件/KC/NVRAM状态，不盲目循环重启。若同系统VESA可进维护环境，先确认当前未加载实验栈；否则使用独立Recovery。
2. 核对备份hash、原存在清单和目标卷组。逐项恢复11目的路径。Caches仍按Data实际后端处理，不因根read-only跳过，也不为它改SSV。
3. **离线Recovery特别限制：**目标System/Data可能分开挂载且firmlink不自动合成。先用diskutil卷组确认配对；
   L/E及GPUBundles落在目标Data的Library，xe落在目标Data的System/Library/Caches。
   对照逻辑路径与实际Data路径映射后才操作，绝不能把`/Volumes/<System>`简单前缀当作正确Data目的。
   现有review脚本仅支持在线VESA维护根`/`且核对Caches同inode；对离线目标硬停止，另审定映射和命令。
4. 文件恢复后单独批准KC修复。依据精确25G83 KDK和目标kmutil工作流重建/同步，比较AuxKC、系统KC及Preboot的ID/UUID/hash。
   `--update-all`可改变多个KC；不加`-z`/missing-KDK绕过；任何非零停止。若无法重建，需要先批准完整离线KC/系统还原方案。
5. 若后续确实获批改过策略，先确保文件/KC回到正常状态，再按原记录恢复CSR/boot-args/相关AMFI配置；
   核对外置OC是否再次注入。没改变过SSV就不执行SSV快照恢复；有独立快照变更则按其单独恢复计划处理。
6. 原生inspect和文件hash确认正常，确认原有非GPU kext未受影响；用户另行批准重启验证。

`tools/recovery-review.sh`与`tools/recovery-kc-review.sh`只是未执行的审查材料；通过bash语法不等于Recovery现场可用。
**VESA负责提供一条独立引导选择，完整备份+正确Data映射+可用KC恢复才构成系统回退。**
