# 无 VM 的完整安装输入组装

本地组装目标是让 Recovery 可以挂载、读取完整的 Apple 安装 app。
**这不是 `createinstallmedia` 的替代验证，也尚未在 HP 开始正式安装。**
HP 的启动错误与下一次单项重试见[实机交接](install-handoff.md)。

## 后续实机验证：网络只读附加与完整载荷读取

2026-10-16，已有 Wi-Fi/SSH 后，使用开发机上的同一份 HFS 数据映像，
通过 HTTP byte ranges 和现有专用 SSH 的 loopback reverse tunnel，在真实 Recovery 完成：

1. `hdiutil attach -readonly -nobrowse -noautoopen -noautofsck -insecurehttp
   -imagekey diskimage-class=CRawDiskImage` 附加网络 HFS；实际挂载为只读。
2. 只读附加 app 内完整混合 UDIF `SharedSupport.dmg`，原生识别其 GPT/HFS。
   此有界试验跳过嵌套 UDIF 整盘校验；源 HFS 在服务启动前完整核对 SHA-256。
3. 从实际嵌套挂载点取回 catalog，原 SHA-256 完全一致；选择到 26.6.2/25G83。
4. 从 Recovery 将完整 **18,356,020,461-byte** 主载荷经 SSH 流回开发机，
   SHA-256 `0b44a71bd6a721f5ddfb46f8dba39b09ee46bf9678a1c3100b978f512acfc07c`
   与原 Apple catalog 一致。用时 1041.708s，平均 16.805MiB/s；没有在 HP 内置盘或 tmpfs 存整份载荷。
5. app 的 `startosinstall --usage` 退出 0；`startosinstall` 与 `InstallAssistant` 的独立 Mach-O
   原生 codesign 校验通过。**整个 app/default/deep-strict 校验仍因 custom omit rules 报 obsolete resource envelope**。
   入口、CLI 和 CodeResources 与已验证 Apple 包原字节一致，没有修签；GUI/安装接受性仍未通过。

直接 LAN HTTP 的首次 curl 超时退出 28，随后改用已有 SSH 的反向转发成功，没有改防火墙。
只读服务 [`serve_hp_offline_image.py`](../scripts/serve_hp_offline_image.py) 在启动前固定核对
源文件大小/完整 SHA-256，仅提供单个随机路径，支持 HEAD 和单字节区间范围，没有目录列举或写入入口；
13 个真实本地 HTTP 正负对照通过。具体命令、临时路径和日志在私有证据中。

本轮两层映像已正常卸载，实验服务和专用 reverse tunnel 已停止，原 Recovery SSH 继续保留。
该通道已证实可重建，**资源读取不再依赖物理 USB 恢复**。没有创建 APFS 或正式启动安装；
原来的远程只读、内置 EFI/NVRAM 和重启限制仍适用。
证据索引：[`hp-network-installer-check.json`](../manifests/hp-network-installer-check.json)。
以下保留最初构建与 USB 交付时的验证边界。

## 已验证的 Apple 输入

- 来源：Apple CDN 的
  [`InstallAssistant.pkg`](https://swcdn.apple.com/content/downloads/37/33/140-93587-A_GRFFH93NOL/f944yaqo1cjhh2m0kxrl0zhcpg9yb9qphv/InstallAssistant.pkg)。
- 长度：18,384,624,402 bytes。
- SHA-256：`376923d7494cfa32b69f383bcfdce46aeedb609fe6a242ea12a6e015bfb77ba4`。
- XAR TOC 签名、固定 Apple Root CA 证书链、五成员的压缩前后摘要通过；签名篡改负对照失败。
- 包内 MobileAsset catalog：26.6.2 / 25G83，`SUDocumentationID=PreRelease`。
  当前 `MacBookPro16,2` 的 board 对应记录存在；这只是 catalog 匹配，不是 HP 兼容性结论。
- 主资源 ZIP：18,356,020,461 bytes，SHA-256
  `0b44a71bd6a721f5ddfb46f8dba39b09ee46bf9678a1c3100b978f512acfc07c`，
  与包内 catalog 的二进制摘要字段一致。

包扩展名不足以判断格式：该输入同时有 XAR 包头与合法的 UDIF `koly` 尾部。
包的 postinstall 将整个包链接为 app 的 `Contents/SharedSupport/SharedSupport.dmg`。
因此不能只把 XAR 中名叫 `SharedSupport.dmg` 的成员当成最终完整 DMG，
也不应因为它叫 `.pkg` 就认定它无法按 DMG 读取。

## 复现顺序

所有脚本仅在 `.local/install-prep/` 新建普通文件。准备约 40GiB 临时空闲空间；
输入包、最终数据映像与独立解码的临时 HFS+ 分区各约 18–20GB。
早期 `qemu-img convert` 仅作文件格式转换，因 DMG chunk 超过该工具的实现上限被拒绝；
后续改用固定 7zz 解码。此处没有运行 QEMU 虚拟机。

```sh
python3 scripts/fetch_install_assistant.py --help
python3 scripts/verify_install_assistant.py --help

# 验签后，用实际 verification-<run>/report.json 替换以下路径。
python3 scripts/inspect_installer_support.py \
  --verification .local/install-prep/full-installer/verification-<run>/report.json \
  --sevenzip /path/to/pinned-7zz

python3 scripts/reconstruct_installer_app.py \
  --verification .local/install-prep/full-installer/verification-<run>/report.json
```

`inspect_installer_support.py` 固定校验 7zz 26.04 二进制 SHA-256：
`3e3a0fa5d764701c81076b1574012b7ecb1563b24439d548eb5da498e6875d6f`。
它实际解码混合 DMG 中的 `5.hfs`、读取 catalog 并流式校验主 ZIP，最后删除其临时大分区。
`reconstruct_installer_app.py` 只解包验签 Payload、恢复模式与相对 symlink，
并硬链接完整包为 SharedSupport；不执行 postinstall。

## HFS+ 大文件工具修正

初次使用 xpwn 0.5.8 的 `hfsplus` 写入完整 SharedSupport 时发生 `BTree inconsistent!`。
该固定源码的 `allocate()` 使用两个 `uint32_t` 相乘计算零填充的物理偏移，
超过 4GiB 后会回绕。已添加单行 `off_t` 提升补丁：
[`xpwn-large-volume-offset.patch`](../patches/xpwn-large-volume-offset.patch)。

上游：[planetbeing/xpwn](https://github.com/planetbeing/xpwn/tree/20c32e5c12d1b22a9d55a59a0ff6267f539b77f4)，
commit `20c32e5c12d1b22a9d55a59a0ff6267f539b77f4`，GPL-3.0-or-later。
本地使用的完整源码 NAR hash：`sha256-wOSIaeNjZOKoeL4padP6UWY1O75qqHuFuSMrdCOLI2s=`。
只构建 HFS 子工具，编译方式如下（`SRC` 必须是可写的固定源码副本）：

```sh
patch -d "$SRC" -p1 < patches/xpwn-large-volume-offset.patch
cc -O2 -fcommon -Wno-implicit-int -Wno-incompatible-pointer-types \
  -I"$SRC/includes" -I"$ZLIB_INCLUDE" \
  "$SRC"/hfs/{hfs,btree,catalog,extents,xattr,fastunicodecompare,flatfile,hfslib,rawfile,utility,volume,hfscompress}.c \
  "$SRC"/common/{abstractfile,base64}.c \
  "$ZLIB_LIBRARY" -Wl,-rpath,"$(dirname "$ZLIB_LIBRARY")" -o "$OUT/hfsplus"
```

构建数据映像还使用 hfsprogs `627.40.1-linux` 的 mkfs/fsck，源码固定于
`glaubitz/hfs@a9496556b0a5fa805139ea20b44081d48aae912a`（APSL-2.0）。
Linux fsck 的块设备大小 ioctl 对普通文件失败，因此单独提供
[`hfs_regular_ioctl.c`](../scripts/hfs_regular_ioctl.c)：仅对普通文件的大小查询返回
512-byte 逻辑块与真实文件长度，其他 ioctl 透传。它不修改卷内容或 fsck 的完整性判定。
该适配器已对有效 64MiB 探针卷校验成功；对前述损坏映像仍报
`Invalid B-tree node size`、退出 8。

```sh
cc -shared -fPIC -O2 -Wall -Wextra -Werror \
  scripts/hfs_regular_ioctl.c -ldl -o "$OUT/hfs_regular_ioctl.so"

python3 scripts/build_offline_app_volume.py \
  --app-report .local/install-prep/offline-app-<run>/report.json \
  --hfsplus "$OUT/hfsplus" \
  --mkfs /path/to/mkfs.hfsplus \
  --fsck /path/to/fsck.hfsplus \
  --sevenzip /path/to/pinned-7zz \
  --fsck-preload "$OUT/hfs_regular_ioctl.so"
```

构建器显式写入目录、文件模式与 symlink，不使用会解引用链接、丢失执行权限的
`hfsplus addall`。它随后运行只读 fsck，再用独立 7zz 解码 app，比较普通文件摘要、
执行权限和链接目标，并流式回读完整 SharedSupport。

实际生成结果：**19,922,944,000 bytes**，SHA-256：

```text
75f6cab00020ad6c2124579bc4641ca0f9029ad0ff23cf3d8112d01211523c92
```

fsck 退出 0，695 个普通文件、26 个链接、所有普通文件权限及完整嵌套包摘要通过。
首次回读曾因父进程 `umask=077` 导致解码副本变为 0600/0700，而映像内记录正确；
改为仅在私有输出目录内让独立解码器保留原权限后，使用 `--verify-image` 对同一映像
完成验证，没有为了消除该检查错误而改写安装 app 或重新生成大映像。

## Recovery 接入边界

最终 `.hfs` 是可挂载的**数据卷映像**。它不包含新的 OpenCore 或身份，不能代替
`HP-Tahoe-VESA-Recovery.img` 启动。现已作为普通文件放入现有 exFAT 的
`/ISO/linux/Tahoe-26.6.2-Offline-App.hfs`，完整回读摘要通过，USB 已安全卸载。
交付证据为 `.local/install-prep/usb-offline-delivery-38vmry8y/report.json`。
后续由 Recovery 的 DiskImages 栈只读附加。

进入 Recovery 后，可在 Terminal 使用手动接入助手：

```sh
# 将 <volume-name> 替换为 diskutil list 和 /Volumes 中实际显示的物理 exFAT 卷名。
sh "/Volumes/<volume-name>/ISO/linux/collect_macos_handoff.sh" --save-usb
sh "/Volumes/<volume-name>/ISO/linux/attach_hp_offline_installer.sh" \
  "/Volumes/<volume-name>/ISO/linux/Tahoe-26.6.2-Offline-App.hfs"
```

[`attach_hp_offline_installer.sh`](../scripts/attach_hp_offline_installer.sh) 检查映像长度，
显式使用 `CRawDiskImage` 只读附加到唯一的临时挂载点，打印完整 app 路径和卸载命令。
助手不启动 app；其 Darwin 执行与实际映像附加仍待 HP Recovery 验证。
Linux 上的交付摘要校验不依赖 Recovery 是否带有 `shasum`；不能用映像长度检查代替摘要校验。

必须先在 HP 验证：Recovery 真正启动、USB/XHCI 正常、物理 exFAT 卷可见、
数据映像可挂载、Apple app 及 SharedSupport 被安装器接受。
UEFI/Ventoy 的虚拟 Block I/O 可用不保证进入 XNU 后仍能访问同一虚拟磁盘。
因此离线资源齐全与实机完全离线安装成功是两项不同证据。

当前不自动运行安装器或选择目标盘。候选 APFS 区仍是 p6/p8 之间的
107.94140625GiB 连续未分配空间，须在 Recovery 按偏移、大小重新核对。

本地交接集可用 `scripts/stage_hp_handoff.py` 从通过检查的重试报告与数据映像报告
生成，包含两张普通文件映像、观察脚本及 `SHA256SUMS`。它再次核对输入摘要并使用
本地硬链接，不自动挂载或写回 USB，也不修改 Ventoy 配置。
