# GA48 OpenCore 配置与镜像检查

## 母版证据

本轮经 SSH 只读 `diskutil info -plist disk0s1` 确认内部 EFI 分区、未挂载、大小
314,572,800 字节后，用 `sudo dd if=/dev/rdisk0s1` **仅向本地**回取。
未在目标挂载 ESP。原始读回 SHA256：
`14f9cb981688bebea8e592f85fdc0a55d2f96db3ca4448b9ca3e62f13c51ff15`。

当前 `EFI/OC` 的 **41 个文件全部**与 10 月 17 日 installed-readback、现有独立 VESA IMG
中的 OC 逐字节一致；当前 config SHA256：
`efc18fb4cbd93688295c8ceaa74a044698afa2b1b1219a1f82a14b1d27313a6e`。
整个内部 EFI 还有 Microsoft/HP/Linux/systemd 文件，未复制它们到实验镜像，未改写它们。
内部 `EFI/Boot` 是另一引导链，不能用它取代外置 OpenCore bootstrap。

IMG 使用现有 HP VESA 介质的已验证布局与外置 OpenCore bootstrap，OC 子树取自本轮当前读回。
OpenCore.efi 与 BOOTx64.efi 均逐字节匹配固定的 OpenCore 1.0.8 RELEASE ZIP；
ZIP SHA256 `2011e8b7216ecb2645d97ea710df965947edd406846e92050b9bc4190be6d27b`。
没有使用 Dell 整份 EFI。

## 精确差异

完整机器可读值见 `IMAGE.json/config_delta`；只有四处结构路径变化：

1. `DeviceProperties/Add/PciRoot(0x0)/Pci(0x2,0x0)`：
   `AAPL,ig-platform-id=<0000499a>`。不注入 `device-id`，不伪装 8A5A。
2. `Kernel/Add`：禁用 WhateverGreen，Lilu 后加入 NootedGreen，保持其他条目的内容与相对顺序。
   Lilu 使用 GA47 审计的 1.7.2；NootedGreen 使用 GA47 最终真实产物。
3. `NVRAM/Add/.../boot-args`：由 VESA 切至下列候选。
4. `NVRAM/Delete/...`：仅加入 `boot-args`，保证已有 `-igfxvesa` 值不会令 Add 失效。

```text
-v keepsyms=1 debug=0x100 slide=0 -vi2c-force-polling -ngreentglwithgfx ngreenSched=3 ngreen-dmc=tgl -ngreentgltahoe -ngreenfixbootmode IGLogLevel=3 -ngreennoplanesfix
```

167 ASCII 字节，含 NUL 为 168，低于 1024 字节界限。没有 GA32b Hang/ICL3D、ADLP DMC、
Dell RPL spoof、`-disablegfxfirmware` 或 `amfi_get_out_of_my_way=1`。
GA47 候选中的 AMFI 参数本轮移除，CSR 仍为 `<00000000>`。

ACPI、Booter、PlatformInfo/SMBIOS、UEFI、Misc（包括扫描、默认项设置、SecureBootModel）、
Kernel 的 Block/Patch/Quirks/Emulate/Force/Scheme 保持当前 HP 值；相关断言已实际运行。
HP 当前母版没有额外音频 kext，本轮保留实际状态，没有替换为 Dell 音频配置。

### NVRAM 行为不能忽略

OpenCore 1.0.8 手册规定 Add 不覆盖现存变量，需先 Delete。
保留 `WriteFlash=false`；但它只控制**新加变量**的非易失属性，不能承诺 Delete 对原有
持久变量毫无影响。今后批准启动 GA48 时，须同时批准该 boot-args 替换行为并保存原值；
必要时在独立 VESA/Recovery 下恢复备份原值。**本轮没有运行这套 EFI，也没有执行 NVRAM 写命令。**
不删除 CSR、安全变量、BootOrder/BootNext；`AllowSetDefault=false`、`LauncherOption=Disabled` 保留。

## Kernel/Block、ICL 与失败行为

- 当前 HP、GA48、VESA 的 `Kernel/Block` 都为 `[]`，没有误挡 TGL 的规则。
- 本轮读取 stock ICL accelerator personality，只有 FF02/FF05/8A50…8A71 等 ID，**不含 9A49**。
  未注入 8A5A，因此不添加无依据的 ICL Block。ICL 在 stock KC 中存在，但当前 `showloaded`
  没有 ICL accelerator。详细匹配见 `DEPENDENCIES.json`。
- EFI 注入顺序 Lilu → NootedGreen → 其余 HP kext；WhateverGreen 条目禁用，文件保留。
- 系统端 HookCase → TGL framebuffer/accelerator 依赖闭包由原生 KC 解析；HookCase 不注入 EFI。
- OpenCore 注入不保证依赖失败时自动切 VESA；缺系统驱动、签名拒绝、ABI 错误可导致无加速、黑屏或 panic。
  任何依赖/注册失败立即停止，不能以 EFI 校验通过继续启动加速测试。

## PLANES2 分项回退

`out/config-variants/` 三份完整私有候选均通过 ocvalidate，不是已部署配置：

| 文件 | FMT | PLANES2 | 用途 |
|---|---|---|---|
| `fmt-only-default.plist` | 开 | 关（`-ngreennoplanesfix`） | IMG 默认；FMT 自身仍未实测 |
| `fmt-planes-off.plist` | 关 | 关 | 移除 native opt-in；不是自动恢复系统文件 |
| `full-ga47-planes98-UNVERIFIED.plist` | 开 | `+0x98` | 恢复 GA47 候选行为，须另行授权与运行证据 |

现有实现的 FMT 和 native opt-in 共享 gate，**没有独立 FMT-off/PLANES2-on 开关**。
上述表准确表达已有能力，不增加驱动代码。没有选择把所有 surface 强制单平面的 `-ngreenplanesxor`；
VALD 保留上游共同路径，不受这两项开关关闭。分项关闭不等于 25G83 全部 ABI 已安全。

## 介质验证

- 大小 1,343,225,856 字节；原 MBR/active EF 分区，start=2048、size=2621440 扇区，FAT32。
- 第一 MiB 与源介质完全相同；沿用既有 Ventoy IMG 结构，没有重分区物理 U 盘。
- 匹配的 Linux ocvalidate 1.0.8：主配置、三候选、VESA 全部 rc=0。
- 每个 Enabled kext 的 BundlePath、ExecutablePath（允许 codeless 空值）、PlistPath、真实 Mach-O、
  CFBundleExecutable、唯一 ID 和包内依赖先后均检查；ACPI/UEFI/Tools Enabled 路径也检查。
- mtools 提取后，另用 udisks 建立**只读** loop 并内核挂载；99 个文件全部回读哈希，85 个在 EFI。
  其余 14 个文件与原 VESA 介质保持相同。两套 FAT 分区独立副本 `fsck.fat -n` 均 rc=0。
- U 盘已挂载 `/dev/sdb1` exFAT、空间足够，目标不存在，以 exclusive create 新建；fsync/sync 后哈希匹配。
- 挂载和 loop 映射已清理。`IMAGE.json`、`MEDIA.json`、`*-fsck.log` 是实际收据。
