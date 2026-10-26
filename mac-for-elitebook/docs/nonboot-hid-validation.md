# 离线 HID report descriptor 解析验证

## 结论与范围

使用固定上游 `libevdev/hid-tools` 的 `hid-decode` 和 `hidtools.hid.ReportDescriptor.from_bytes`，离线解析了私有 capture 中的 Synaptics 700-byte 与 Wacom 843-byte report descriptor。两份输入 SHA-256 与 manifest 一致；两份上游 CLI 命令均退出 0。解析摘要包含 Collection、Application/Usage、Report ID、bit/byte 长度和逻辑范围。

这项检查只处理 `report_descriptor` 文件；未读取设备运行时 HID reports。未 SSH、访问 USB/实机、加载或解绑驱动，也未安装或启动 macOS。Linux 上能够解析 descriptor **不能证明** macOS I2C 控制器或设备驱动可绑定、IRQ/GPIO 路由与中断投递可用、触控手势/多点触控工作、笔压感/倾斜行为正确，或任何 macOS 兼容性。

## 固定来源与复现性

- Parser：`libevdev/hid-tools` version `0.12`，commit `f4a32530ea548df2ae5efd2ebfd16d4c3e658875`。
- 固定源码归档 SHA-256：`3899284c5d45ca4e034944ef5f29f64b78159455ac62ee37f5ee4f75f645f861`；解析后的 97 个非 bytecode 源文件树 SHA-256：`277eca118b6fe0810bca68fbef21f7148c411c802f7de22801679b3d5cf91a0e`。
- 归档许可证信息有不一致：`README.md` 和源码头写 GPLv2+ / GPL-2.0-or-later，`pyproject.toml` 元数据写 GPL-2.0-only，`COPYING` 是 GPLv2 文本。manifest 保留了各自原文和 `COPYING` 哈希，不把冲突简化为单一断言。
- 固定 Python 运行依赖及 wheel SHA、许可证、完整源码/依赖树摘要均记录在 [manifest](../manifests/nonboot-hid-check.json)；当前实测环境为 CPython 3.13.15 / Linux x86_64。`hidtools` 模块没有 API 稳定性承诺；本验证将其固定在上述 commit。
- `hid-decode` 的二进制输入/退出码用法依据同一 commit 的 [man page](https://gitlab.freedesktop.org/libevdev/hid-tools/-/blob/f4a32530ea548df2ae5efd2ebfd16d4c3e658875/man/hid-decode.md) 和 [README](https://gitlab.freedesktop.org/libevdev/hid-tools/-/blob/f4a32530ea548df2ae5efd2ebfd16d4c3e658875/README.md)。

固定 capture 是 `.local/hardware/20261015T174049.365004Z`；路径、长度和预期 SHA 写在 manifest 中。执行器只接受这两条固定输入，并在解析前核验 SHA/长度。默认从 `.local/nonboot-hid/src` 和 `.local/nonboot-hid/deps` 读取已固定源码和依赖；可显式指定内容树摘要完全匹配的副本路径。

## 实测解析结果

报告中的 bit 数包含 Report ID 字节（若有）；`wire bytes` 为完整报告长度，也包含 Report ID。它们是 descriptor 声明的报告格式，不是捕获到的报告数据。

| Descriptor | SHA-256 | Collection 结构（Application / Physical / Logical / End） | 解析出的 Application usages | Reports |
|---|---|---|---|---|
| Synaptics，700 B | `0ee8e6bddf6ee6adf071cdb72983bb0970e2b20e5363ee64bcccc208762cec86` | 4 / 2 / 6 / 12，嵌套平衡 | Mouse、Touch Pad、Device Configuration、Vendor Usage 1 | Input 5、Output 2、Feature 8 |
| Wacom，843 B | `5ad4378537251bc2c6bdf43cec57b542aba7b709028ab02906a80afeb6bcc217` | 7 / 3 / 5 / 15，嵌套平衡 | Mouse、Pen、Touch Screen、Device Configuration；另有 vendor usages `0xff11:0002`、`0xff11:0011`、`0xff14:000e` | Input 8、Output 0、Feature 17 |

逐 report ID 和长度（`ID: bits / wire bytes`）：

| Descriptor / kind | ID 与声明长度 |
|---|---|
| Synaptics Input | `2: 32/4`, `3: 240/30`, `11: 496/62`, `12: 496/62`, `29: 16/2` |
| Synaptics Output | `9: 168/21`, `10: 168/21` |
| Synaptics Feature | `4: 16/2`, `6: 16/2`, `7: 2056/257`, `8: 16/2`, `13: 16/2`, `14: 16/2`, `15: 32/4`, `31: 16/2` |
| Wacom Input | `1: 48/6`, `11: 144/18`, `16: 168/21`, `19: 152/19`, `20: 144/18`, `28: 152/19`, `31: 176/22`, `255: 16/2` |
| Wacom Output | none |
| Wacom Feature | `2: 16/2`, `3: 512/64`, `4: 128/16`, `5: 72/9`, `7: 2056/257`, `8: 1088/136`, `9: 512/64`, `10: 2056/257`, `11: 512/64`, `12: 16/2`, `13: 64/8`, `14: 24/3`, `15: 64/8`, `16: 512/64`, `17: 80/10`, `18: 512/64`, `27: 2056/257` |

逻辑范围和 usage 由 parser 返回的 fields 汇总，不对 descriptor 原始字节另写 parser：

- Synaptics Mouse X/Y 为 `−127…127`；Touch Pad X/Y 分别为 `0…1273`、`0…732`。Digitizers 的 Tip Switch/Confidence 为 `0…1`，Contact Id 为 `0…5`。完整不同逻辑范围集合：`−127…127`、`0…1`、`0…5`、`0…10`、`0…15`、`0…127`、`0…255`、`0…732`、`0…1273`、`0…65535`。
- Wacom Pen 的 Tip Pressure 为 `0…4095`，X/Y Tilt 为 `−90…90`；Touch Screen X/Y 为 `0…11752`、`0…6608`。完整范围还包括 `−32768…32767`、`0…16524`、`0…29376`、`0…32767`、`0…65535`，以及 descriptor 中一个完整 signed 32-bit 范围声明。后者是字段逻辑范围，不是设备序列号值；报告 JSON 抑制了名称含 “serial” 的 usage 标签，未读取或记录任何序列号。
- 两份输入均检查 descriptor 长度一致、Collection/End Collection 有效配对、至少一个 Application 和 Input report、Report ID 范围、报告 bit/byte 对齐、非空字段以及 `Logical Minimum ≤ Logical Maximum`；均无检查错误。

## Parser 反例及真实行为

两项小型合成输入直接经固定版本的 `hid-decode` 执行，不使用本地 toy parser：

| 反例 | 观察结果 |
|---|---|
| `Usage` 后跟缺少 payload byte 的 `Usage Page` short item | exit 1，`IndexError`；parser 拒绝截断输入，但当前 CLI 暴露 traceback，而非友好的格式错误 |
| 保留的 Main item tag（后接一个非零字节，避免触发 trailing-zero 兼容规则） | exit 1，`ParseError` |

另有一个重要的上游行为：单字节 `0x00` 被该版本作为 trailing-zero compatibility case 接受并退出 0，因此没有把它伪装成非法输入反例；manifest 中使用 `00 01` 验证真正触发的非法项拒绝。上述反例只覆盖截断 short item 和保留项，不声称对所有 HID 语义错误做了全面拒绝测试。

## 命令与证据摘要

完整命令参数、各命令 exit code、stdout/stderr 长度与 SHA-256、输入哈希、脱敏解析摘要保存在私有报告：

`.local/nonboot-hid/run-20261015T234625.123764Z-65845/report.json`

报告 SHA-256：`2a4e0b347019a603ed413b9c4c0d8bbd8fae7bd1d97fbd343b31d38a54da2ee8`。

实测日志摘要（日志文件保存在同一私有 run 目录；成功解析的 stdout 是上游 descriptor 解码文本，不是设备报告）：

| 命令 | exit | stdout SHA-256 | stderr SHA-256 |
|---|---:|---|---|
| Synaptics `hid-decode` | 0 | `63ee84516e9795abb77cbf01efbc602ced3ae665290f51bc64da5fe26a4bd3da` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| Wacom `hid-decode` | 0 | `cd33e6b1c60e3e731b30b2043603b9b3c849f102f4ad4c1bfcc154b6dad9bb61` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 截断 short item | 1 | 空 stdout | `52941ee10c4e570ab869ee74ac61f255f6d4696f2850ed924da0112cc1942db5` |
| 保留 Main tag | 1 | 空 stdout | `5953562be92a1cb5917fddc3e76080607add75ba669214ed5baecb6bc1fb8d07` |

manifest 固定的两条被测输入 SHA 与上表一致。私有报告不含 descriptor 原始字节、设备序列号或运行时 HID report 数据；原始 capture 和 parser stdout 日志仍留在 Git 忽略的 `.local/` 中。

## 复跑

缓存已准备好时，在仓库根目录执行：

```sh
python3 scripts/check_nonboot_hid.py
```

也可明确指定固定内容的本地源码/依赖副本：

```sh
python3 scripts/check_nonboot_hid.py \
  --source-dir .local/nonboot-hid/src \
  --deps-dir .local/nonboot-hid/deps
```

源码归档和依赖 wheels 的固定下载 URL、SHA-256、依赖版本及许可证在 manifest 中。每次运行都会重新核验源码/依赖树和 capture 哈希，写入新的 `.local/nonboot-hid/run-*` 结果及 `latest.json`；不需要 SSH、设备访问或 macOS 环境。
