# GA37 Track E · 修正说明（CORRECTION-NOTE）

本文件保留 rev1 的原始回执，并记录主代理评审后的 4 项修正。修正只改本目录
（`GA37-Engineering-Closure/track-e/evidence/`），未 SSH、未接触硬件、未部署、未改 IMG/EFI/固件、
未执行上游代码、未写 GPU 命令/shader、未做公开检索、无 Python import/pycache。`SOURCE_IMG/RESULT_IMG = null`。

## rev1 原始回执（保留，未删除）

| 工件 | SHA-256 | 备注 |
|---|---|---|
| `INPUTS.json`（rev1） | `11b2402b6d45fe41ce09c3c201727b20c628cc120658bfde1498643f3b592b61` | generated_at `2026-10-19T00:21:07+08:00`，144 项 |
| `EVIDENCE-MATRIX.md`（rev1） | `98ede6ee3af005564c127b1493834e5aab60eecbbc356a812eff347ea63be354` | — |
| `build-inputs.sh`（rev1） | `c1b03a87806630be10314a195fdefa3fa36edcc1efef1a82fa5e36c26bfb7ea8` | — |
| `assemble.jq`（rev1） | `7b8d3e090ab6ac1ed425eb4921169b795f43cf9c02f88f3f4c6f2fa01b5cddda` | — |

rev2 的 `INPUTS.json` 内含 `revisions[]`，记录 rev1→rev2 的 supersede 关系与本次改动清单。

## 主代理评审的 4 项修正

### 修正 1 —— exact 25G83 二进制可用；阶段区分
- **事实**：exact Apple 25G83 KC **当前可用**（GA35 原件 + GA36 复用）。
- GA34 报告“Exact AppleIntelICLGraphics 25G83 binary/disassembly not located”是**GA34 当时阶段的历史状态**，
  不是当前状态。
- **区分**：缺失项是 **raw heap / MOCS 编程 / 运行态认证**，
  与**已可用的 25G83 binary** 分开陈述。
- 改动：`INPUTS.json` 增 `stage`、`available_apple_binary`、资源表新增 `exact_apple_25g83_kc` 行；
  新增 19 个 GA35/GA36 源锚（`ga35_kc`/`ga35_analysis`/`ga36_evidence`）。

### 修正 2 —— THAG 哈希是整文件哈希
- **事实**：`1622ecc2aecdcc85ae45dcf86e4219338f6e41e0243b27d5e7128a9999f13333` 是 **99648 B、两条 v2 记录的整文件**
  SHA-256，**不是记录 1 的 SHA-256**。
- 记录 1 派生的字节（batch 8 页 / VS 窗口）可用，但**分开标注**。
- 改动：`frozen_baselines.raw_thag_sha256_whole_file`、`thag_validity`、`files[]`（THAG 两条）标签更正；
  `EVIDENCE-MATRIX.md` §4 更正。

### 修正 3 —— 两套 A–F
- **历史根因假设**（原稿所用）现显式标为 **H-A..H-F**（`historical_rootcause_hypotheses_H_A_F`）。
- 新增**用户请求**的 **USER A–F** 工程方向矩阵（`user_task_matrix_A_F`）：
  A 整 4-shader 翻译 / B 命令状态变换 / C resource ABI / D 上游翻译器修复 /
  E 已知简单原生 TGL pipeline / F 完整原生 TGL 驱动-编译器；
  8 维度：**code-distance / offline-proof / extra-data / Fault dependency / difficulty / memory-safety /
  acceleration-benefit / small-intermediate**。
- 改动：`assemble.jq`、`INPUTS.json`、`EVIDENCE-MATRIX.md` §5A/§5B。

### 修正 4 —— 去掉过度声明
- **不**再声称 4 shader 静态数据即可证明 full URB/RT 消息 payload ABI 等价。
  改为：可建模 **raw 消息 descriptor + 参数化契约**，并显式保留 **UNKNOWN payload**，不构成具体可执行语义。
- 当前 4 程序**无分支**，故 **GA38 branch relocation 对实际语料非必需**，显式延后为未来项（支持范围外）。
- 去掉“A 唯一可完全闭合”的措辞；USER-A 仅在**静态 ISA 部分**最 grounded，消息 ABI 部分不可由静态数据闭合。
- 改动：`shader_totals.branch_note`、`strict_units.branch_scope_correction`、
  `user_task_matrix_A_F.recommendation_corrected`、`proved_vs_unknown`；`EVIDENCE-MATRIX.md` §2/§5B。

## 复现

```
cd GA37-Engineering-Closure/track-e/evidence
bash build-inputs.sh          # 只读历史, 仅写本目录; 需 bash/sha256sum/stat/jq
```

## 边界

- 本修正不实现任何 GA38 代码（无 translator/executor），不做公开检索。
- 既有有效 THAG（整文件 `1622ecc2…`）保持原状；GA31–GA36 历史只读。
- 最终 GA38 唯一方向选择归主代理。
