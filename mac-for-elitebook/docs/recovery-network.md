# Recovery Wi-Fi 与 SSH 调试候选

## 当前实机结果

**用户已确认 Wi-Fi，代理已实际通过专用公钥连接 Recovery root SSH，执行命令并用内置 SFTP 取回完整观察归档。**
当前版本为 26.6.2/25G83，实际加载 AirportItlwm 2.4.0；内置 NTFS 脚本读取也已验证。
归档及补充日志在 `.local/install-prep/hp-recovery-live-hlhn8fro/`，
证据见 [`hp-recovery-runtime-check.json`](../manifests/hp-recovery-runtime-check.json)。
局域网连通已验证，Internet/TLS、网络长期稳定性、睡眠恢复和安装器下载没有验收。

照片中的缺 PID 提示是入口过早检查造成的假失败：后续实际 PID 文件和 listener 存在，SSH/SFTP 正常。
本地 `start_hp_recovery_ssh.sh` 已增加最多 5 秒等待，延迟 PID 对照复现旧入口退出 1、新入口退出 0；
该新源码尚未重新交付，当前运行中的 SSH 保持原状。

## 候选与已执行的启动流程

原 Recovery 没有加载 Intel Wi-Fi kext；本机 AX201 `8086:a0f0` 不能因为 Recovery 自带 Wi-Fi 菜单就自动工作。
已准备并交付独立 **`ISO/linux/HP-Tahoe-VESA-WiFi.img` → `HPRECOVERY (dmg)`**：

- IMG SHA-256：`8ff91489c5c533644af60eee9ed5cd245fa805e6065263b4562992586845c54c`。
- 只向已交付的所有权版追加 Tahoe AirportItlwm；保留其余配置、42 个已有 IMG 文件及私有身份。
- 同版 OpenCore 1.0.8 `ocvalidate=0`；11 个 kext 原生 KC 注入通过，Wi-Fi 真实导入符号损坏的负对照退出 255。
- 此后实际连接与 SSH/SFTP 已通过；离线检查本身仍不等于功能验收。

用户已手动进入 NixOS，原 SSH 恢复，Linux Wi-Fi 已联网。不能沿用 NixOS 的 Tailscale 地址来访问 Recovery；
连接 Recovery 时采用其实际局域网 IPv4。开发机需要能到达该网络，不能选用隔离客户端的访客 Wi-Fi。

## 固定 Wi-Fi 来源

[laobamac/itlwm 固定 README](https://github.com/laobamac/itlwm/blob/bbe368ec7d55a5395d08c729e88eeaabebae8255/README.md)
自述支持 Tahoe 26.x x86_64 原生 Wi-Fi；这是社区 alpha，不是本机 Recovery 的实测结论。
与需要 HeliPort 或预填网络配置的普通 `itlwm` 相比，选用原生菜单的 `AirportItlwm` 更适合此处的连接流程。

| 项目 | 固定值 |
| --- | --- |
| 源提交（asset 文件名及 release body 指向） | `bbe368ec7d55a5395d08c729e88eeaabebae8255` |
| Release / asset ID | `v2.4.0-alpha` / `643799488` |
| Asset | `AirportItlwm-Tahoe-v2.4.0-RELEASE-alpha-bbe368e.zip` |
| Asset SHA-256 | `f47b8320f90b71c25d1bf3d37e471c6e50c016e2e70c1eb7069e599b22dc6878` |
| 二进制 | x86_64 Mach-O kext；原 release 字节，无本地修改 |
| Darwin 限定 | `25.0.0–25.99.99` |

下载后与 GitHub asset digest 核对一致。Alpha tag 可移动，不能只用 tag 作为复现身份；
release 的 `target_commitish` 也不等同于这个现有 asset 的构建提交。
实际 25G83 KC 已包含它声明的 IO80211Family、IOSkywalkFamily、corecapture 等依赖。
注入检查使用已固定的 link-only OpenCore host 工具，没有运行 XNU/VM，也未部署其生成 KC。

按该 fork 的说明，本轮先用 **WPA2-Personal**；Wi-Fi 6 默认关闭，未追加 HE 参数。
WPA3-only、强制 PMF、AWDL/AirDrop 不受该 fork 支持。
上游[常见问题](https://openintelwireless.github.io/itlwm/FAQ.html)解释了普通 itlwm 与 AirportItlwm 的界面差异；
上游旧版支持表不能证明本次 Tahoe Recovery 兼容。

## 内置脚本已交付

用户通过工具明确允许 NixOS SSH 上的有限普通数据写入后，已核对内置 Windows NTFS“系统”卷并部署：

```text
/hpdiag/h                         采集与重点摘要
/hpdiag/collect_macos_handoff.sh   完整观察助手
/hpdiag/s                         启动 Recovery 自带 sshd
/hpdiag/ssh_host_ed25519_key       此次专用服务端身份
/hpdiag/ssh_host_ed25519_key.pub
/hpdiag/authorized_keys           开发机专用公钥
```

已有 `/hp` 是 OEM 目录（`bridge`、`HPQWare`）；初次检查拒绝覆盖，改用原先不存在的 `/hpdiag`。
六个文件在重新**只读挂载**后逐一 SHA-256 核对通过，卷已卸载。
首次复制后普通用户无法 `cd` root-owned 目录，导致验证退出；保留失败日志，以 sudo 只读回读完成验证，未重新覆盖文件。
没有强制挂载或修复，也未写 EFI、固件、NVRAM 或分区表。

若 Recovery 自动挂载了该卷，连上 Wi-Fi 后只需：

```sh
sh /Volumes/*/hpdiag/s
```

该入口复制专用服务端身份和授权公钥到 `/tmp`，校验配置，再启动端口 **2222** 的临时 sshd，
输出 IPv4、日志目录和停止命令。启用公钥认证及内置 `internal-sftp`；专用客户端私钥仅留开发机。
Recovery 下的实际 root 公钥认证、会话和 SFTP 现已连接验证；启动器打印 PID 本身仍不等于握手成功。
未通过系统 Remote Login 设置持久化 SSH，也未读取或修改 NixOS SSH 配置。

当前实际 BaseSystem 的文件目录确认有 `sshd`、`sshd-auth`、`sshd-session`、`ssh` 和 Wi-Fi 服务；
没有独立 `ssh-keygen`、`sftp-server`。因此提前生成专用 host key，文件传输用内置 SFTP，
无需给 Recovery 塞入另一个 SSH 服务端二进制。
启动器通过 shell 语法、Linux 拒绝、隔离成功/校验失败/启动失败/缺文件控制流检查；
生成的配置经本机真实 Linux `sshd -t` 退出 0。后续还进行了 Linux 本机回环 SSH 和内置 SFTP 实测，均通过，临时监听器已结束。
该实测使用当前 Linux 用户及随机回环端口，不能代替 Recovery root 的实际认证/会话验证。

最终审阅发现临时授权公钥所在的 `/tmp` 祖先会触发 OpenSSH StrictModes 目录检查；
最终入口在其专用临时配置中设 `StrictModes no`，mktemp 子目录仍为 root-only、文件仍为 0600。
修订版已替换本次自己交付的 `/hpdiag/s`，重新只读挂载核对六个摘要；USB 私有调试包及摘要表也已同步并安全卸载。
修订证据在 `.local/install-prep/hp-ssh-tempkey-fix-fiejno1d/`；前版收据保留。

网络不通也可运行：

```sh
sh /Volumes/*/hpdiag/h
```

若找不到脚本，先用短命令 `ls /Volumes` 确认普通 NTFS 卷是否仍挂载；
不能把 NixOS 的挂载成功直接当成 Recovery 可读取成功。
NTFS 在 Recovery 通常只读，观察归档仍保留在 `/tmp`，不要先重启丢失现场。

## 开发机连接信息（私有文件）

私有目录 `.local/install-prep/hp-recovery-network-2lk4c8rz/` 保留：

- `client_ed25519`：专用客户端私钥；未交付到 HP 或 USB 包。
- `known_hosts`：以 `hp-recovery-20261016` 为 alias 固定服务端公钥。
- `ssh-package.json` / `internal-delivery.json` / `usb-delivery.json`：包、内置卷和 USB 收据。
- `native-link/` / `native-negative/`：原生 KC 注入证据。

最新 SSH 包为 `.local/install-prep/hp-ssh-tempkey-fix-fiejno1d/HP-Recovery-Debug.tar.gz`，
SHA-256 `5ba9ebcba26b8fe74b7611fe7394a316b79f3102c9ba5bfadd889c12aebf6c0f`；
服务端身份、授权公钥、开发机私钥和 host alias 均沿用同一组。

有实际 Recovery IP 后，在开发机使用 `-p 2222`、上述 identity 和 known-hosts，
`HostKeyAlias=hp-recovery-20261016`、`IdentitiesOnly=yes`、`StrictHostKeyChecking=yes` 连接 `root@<Recovery-IP>`。
后续已按该流程连接成功；真实地址仅保存在私有运行态证据中。

## USB 与上轮原件

USB 四个新增普通文件（Wi-Fi IMG、私有调试包、说明和摘要表）完整回读通过，已安全卸载；
218 个已有文件大小/mtime 保持，原实测 ownership IMG 内容摘要保持，Ventoy 配置与分区布局保持。
19.9GB 离线数据写入前完整摘要仍为 `75f6cab00020ad6c2124579bc4641ca0f9029ad0ff23cf3d8112d01211523c92`，
本次未写该文件。

上轮完整 IMG 与全部 44 个 FAT 文件保存在 `.local/install-prep/hp-usb-ownership-capture-rorpjbsx/`：
IMG SHA `5ac0710d67dc339a9f5015c9794a6e67de8f5ac9f53f3235183c08d1fddde6d9`，配置仍为所有权版。
新增 `opencore-2020-01-01-000055.txt`（日志名时间不是可靠现实时间）到达 EXITBS，没有旧 MM.AKM/STOP。
物理 Lexar 仍缺失来自用户照片，不能从这个 booter 日志推断 XNU USB 根因。
新 Wi-Fi IMG 基于上轮启动前已固定交付原件，原实测日志单独留存在原 IMG/采集目录。

结构化证据见 [`hp-recovery-network-check.json`](../manifests/hp-recovery-network-check.json)。
