# 内置普通数据卷上的 Recovery 观察入口

> 此页保留最初准备方案。后续已在用户明确授权下交付到普通 NTFS 卷 **`/hpdiag`**，
> 原 `/hp` 是 OEM 目录而保留。现在的命令为 `sh /Volumes/*/hpdiag/h`，
> Wi-Fi/SSH 候选、实际交付和验证边界见 [recovery-network.md](recovery-network.md)。

## 实机结果与网上核对

用户提供的新照片显示：`ReleaseUsbOwnership=true` 后仍只有内置 512.1GB SSD 和
2.7GB Recovery 映像，**物理 Lexar 仍未出现**。本次单项对照未恢复物理 U 盘识别。
尚未取得这一版新的完整 USB registry/错误日志，不能据此补写更细的故障结论。
用户补充“触控有了”；此前已确认触控板可动但卡顿，这次是否专指触屏尚待区分。

网上查到更直接的社区匹配实现：

- [DalianSky/OS-X-USB-Inject-All 的固定 plist](https://github.com/daliansky/OS-X-USB-Inject-All/blob/ce55e00966ac90c5e2504fb39b4ecf3fcebab51a/XHCI-unsupported.kext/Contents/Info.plist)
  明确将 `8086:a0ed` 匹配到 **`AppleUSBXHCISPT`**，probe score 为 900。
- 固定 commit：`ce55e00966ac90c5e2504fb39b4ecf3fcebab51a`；该 plist SHA-256：
  `9b66b803577d7dea089bc5dc6352f25fb2f2de9c3333cb899c9a838ad7106571`。
- 本地实际 **25G83 KC** 含这个 SPT 类的 personality，但默认精确 ID 列表未覆盖 `a0ed`。
  这为“通用类已绑定但无端口”提供了可验证的下一轮匹配方向，比继续只尝试固件所有权更直接。
- 此社区 plist 没有 `9a13`；不能说它已覆盖两个控制器。它也不是本机/本版 Tahoe 已通过的证据。
  此次只核对来源，尚未给当前 USB 增加此 injector。

另参考 [OC-Little USB 说明](https://github.com/5T33Z0/OC-Little-Translated/tree/main/Content/03_USB_Fixes)
区分控制器兼容匹配与端口映射。该说明是参考资料，不代替本机 I/O 验证。
来源原件和本地 KC 交叉核对保存在 `.local/install-prep/hp-usb-research-8hpvgjut/`。

## 为什么放内置普通数据卷可行

此前 Recovery 的 `/Volumes/系统` 已出现，照片的磁盘表也能列出 Windows NTFS 分区。
计划在这个**普通数据卷**的根目录放一个 `hp` 文件夹，内含：

- `h`：短入口，运行采集后自动显示重点摘要和 I2C 中断模式；
- `collect_macos_handoff.sh`：完整观察脚本，仍只向 `/tmp` 写输出；
- 本说明：说明实际验证范围和日志去向。

部署前应在 NixOS 核对该分区身份、挂载状态及现有 `hp` 目录，保留已有文件。
这不是把文件放进内置 EFI，也不需要格式化或改分区表。
Recovery 对 NTFS 通常只读；**此方案首先解决“能读取并运行脚本”，不保证能把归档写回 NTFS**。
归档留在 `/tmp`，退出/重启前要通过另一个已验证的可写通道保存；至少可先拍自动重点摘要。

## 运行命令

文件部署完成、再次进入 Recovery 后，短命令为：

```sh
sh /Volumes/*/hp/h
```

通配符避免手输中文卷名。只有一个已核对的数据卷部署了 `hp/h` 时才使用此命令；
多个匹配将被参数检查拒绝，改用确切路径。启动器会自动定位同目录完整脚本，
运行采集并显示输入/USB/NVMe 摘要、I2C `Interrupt Mode`、磁盘列表和私有归档路径。
不必再手输长的 `ioreg` 过滤命令。

## 当前交付边界

脚本包在开发机本地准备。当前 Recovery 没有已验证的联网/SSH/文件传入通道，
原 NixOS SSH 连接尝试超时；不能宣称文件已经放上内置盘。
用户已被告知由其手动重启进 NixOS 并联网，然后再确认中转路径。
项目现行远端操作范围为只读观察；实际普通数据文件写入按用户明确授权范围安排，
不能借此写 EFI、固件、引导顺序或其他存储区域。

启动器的本地 fixture 验证不等于已在 HP Recovery 运行。
