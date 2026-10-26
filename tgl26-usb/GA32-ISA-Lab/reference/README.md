# GA32-ISA-Lab / reference

离线、只读的 Gen11→Gen12 EU 翻译器**参考资料与来源固定**归档。
不含构建产物、不含实机产物、不含私有身份；未改动 `/tmp/opencode/ga33`、HP 或任何介质。

## 内容

| 目录 | 内容 | 来源 |
| --- | --- | --- |
| `upstream-holdmysocks-1010490/` | 参考项目 `LAYER4.md`、`0004-tgl-accelerator.patch`、`tgl-xlate/` 源码与 `xlate-GA11.txt` 日志 | `github.com/holdmysocks/latitude-7320-detachable-hackintosh` @ `1010490d3421628c9d6fd0bd518b6c4b6f8ee33c`（逐 blob 校验一致） |
| `project-analysis/` | 本项目 GA3.2b/GA3.3 离线笔记（ISA/页表/内存安全/CSB/watchdog/记录格式） | `/tmp/opencode/ga33/research`（只读复制） |
| `PROVENANCE.json` | 机器可读的来源/摘要清单，含上游 commit 与每个文件的 git blob SHA-1 | 本目录 |

## 校验方法

- 上游 commit 用 `git ls-remote` 与 GitHub tree/blob 比对确认；
- 归档文件的 **git blob SHA-1 == 上游 tree 中同路径 blob**（即字节一致），另附 SHA-256；
- Mesa 依赖固定为 tag `mesa-23.3.6` → `863338275d915e867319c3690ffd3272b06303c3`；
- 复核：`jq -r '.files[]|"\(.git_blob_sha1)  \(.path)"' PROVENANCE.json` 后逐个 `git hash-object` 对比。

## 相关审计

- [`../reports/08-upstream-source-audit.md`](../reports/08-upstream-source-audit.md)：翻译规则/缺口、SEND/SWSB/compact、分支重定位、边界/缓存/跨页、Machine Check 与 fail-open 分析，以及 GA4–GA11 实机失败与"无稳定桌面"的归因。

## 已知缺口（详见 PROVENANCE.json `known_gaps`）

- 上游 `tgl-xlate/` 的 `eu-stubs/`、`kshim/`、`kruntime.c`、`stub/`、`fzbuild.sh`、`a1_3src_helpers.h` 未在本归档内（上游存在；本地 Linux 适配副本见 `GA32-ISA-Lab/tools/tgl-xlate`）。
- 上游未在仓库内标注固定 commit；此处固定的是当前 public main HEAD，且所有已比对 blob 与之相符。
- 参考项目的运行日志 `xlate-GA7..GA10`、hang/csb/panic 文件未归档。
