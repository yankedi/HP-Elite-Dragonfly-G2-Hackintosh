# 内置 OpenCore 与旧 Debian 引导清理

2026-10-17：用户明确授权新增内置 OpenCore／启动菜单，并要求备份后删除旧 Debian。
已完成写入和独立完整回读；**内置链式启动及 macOS 接力阶段尚待用户实机启动验证**。

## 当前启动路径

1. 用户手动重启，经现有 **Linux Boot Manager** 进入 systemd-boot。
2. 选择 **macOS (OpenCore)**，由 `/boot/loader/entries/macos-opencore.conf`
   加载 `/EFI/OC/OpenCore.efi`。
3. OpenCore 中选择硬盘上的 **macOS Installer**；这是已有暂存流程的接力入口。
   后续系统安装完成后再选择 **Tahoe**。

`bootctl list` 已识别新菜单和目标路径。新菜单位于很多旧 NixOS 条目之后，需向下查找。
当前默认仍是原 NixOS；没有添加固件 OpenCore Boot#### 项。
USB 上实测 RHUB IMG 和开发机原件均保留；当前内置 OC 配置／驱动／kext／身份均来自该实测原件，未修改。

## 已核验的精确变更

- 第一 ESP：`nvme0n1p1`，PARTUUID 已从公开副本脱敏，
  新增 `EFI/OC` 内41文件和1个 systemd-boot 菜单文件。
  214个既有文件摘要全部保持；42个新增文件完整读回开发机，与源逐字节摘要一致。
- 安装后回读的配置通过同版 **OpenCore 1.0.8 ocvalidate**；这是静态校验，不是新启动路径通过证明。
- 第二 ESP：`nvme0n1p6`，PARTUUID 已从公开副本脱敏，
  删除 `EFI/debian` 的6文件，以及 `EFI/BOOT` 的4个已验证同字节 Debian shim/grub/mm/fb 副本。
  这两个空目录随之移除。ESP分区及其他目录保留，操作后已卸载。
- 删除固件 `Boot0007 debian`，其路径原为第二ESP `\EFI\debian\shimx64.efi`。
  BootOrder 从 `0001,0007,0003,0006,0000,0002,0004,0005`
  变为 `0001,0003,0006,0000,0002,0004,0005`；其余Boot变量字节保持。
- GPT JSON前后字节相同，`sfdisk --verify`退出0；Tahoe前16MiB摘要保持。
  原 Debian 数据区此前已经改为 Tahoe；本轮没有删除任何分区。

## 备份与回退依据

私有目录：`.local/install-prep/hp-internal-boot-20261017/`。

| 路径（相对该目录） | 内容 | SHA-256 |
| --- | --- | --- |
| `backup-stable/esp1-before.img` | 第一ESP完整314572800字节原始映像 | `b2d152eb5c04512fba58b9e7b0b5c4db867de38504d3c3142d68af0f0c27f691` |
| `backup-stable/esp6-before.img` | 第二ESP完整1024458752字节原始映像 | `440b851cecc5ef17887afac6f3a2e6ceac0dae1bc9cfebca04aabe89525955bc` |
| `backup-stable/backup-report.json` | 两映像源前／源后／本地完整摘要一致的收据 | `fabe8953f565a6228a8342844ef24bf932ed530cc3a7276e695bcca9489171d1` |
| `prepare-report.json` | 原41个OC文件、新菜单及10个旧Debian文件摘要 | `5389b44e316145ff0797c7caf9ce326a6bd7edc16d429c2bb75effe1f3ae47ae` |
| `delivery-report.json` | 独立回读、原文件／Boot变量／GPT保持证据 | `d4baeb831fe933200f9c4b694967e5e6543d3f4fd616571457392de2151252d6` |

另有 `backup-stable/boot-vars/` 每个原始Boot变量（含属性头）、
`esp6-files-before/` 逐个提取的旧Debian文件、`installed-readback.tar` 以及原文件摘要清单。
首次在线ESP1复制时摘要变化，原尝试已保留；它不是上表中的可靠备份。
刷新原有待写FAT状态后重新采集的 `backup-stable/` 才通过稳定摘要门禁。

若需要回退，先核对实际挂载设备与上述PARTUUID，再用清单限定恢复范围：
撤销本轮新增的 `EFI/OC` 与单个菜单即可还原第一ESP原有文件集；
恢复Debian时使用已提取的10文件和保存的原始Boot变量／原BootOrder。
任何恢复操作应另行取得明确指令，不能把原始ESP映像直接覆盖到仍挂载的分区。
这些私有映像／变量／生成身份不进Git，迁移开发机时须另外传输并核对摘要。

证据索引：[`hp-internal-boot-check.json`](../manifests/hp-internal-boot-check.json)。
