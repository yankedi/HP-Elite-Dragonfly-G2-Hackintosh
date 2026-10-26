# 12 · 新发现：命令格式也存在跨代不一致

这是 Batch 整合后的补充核验，不能沿用早期“只有ISA问题”的结论。

## 独立官方依据

Intel Tiger Lake PRM Volume2a，December2021 Revision1.0，官方附件
https://cdrdv2.intel.com/v1/dl/getcontent/703042 。本地 `reference/tgl-command-instructions-official.pdf`，14269926 B，SHA256
`f089719d408ae41004fea60a0a1b58eaa977a77be3c88c365f5a6144bce2ddd6`。
以Poppler `pdftotext -layout`提取为同目录 `tgl-command-instructions.txt`；对应原PDF印刷页码如下。

### 1. Stencil packet：Gen11五DWORD与TGL八DWORD

捕获窗口 `+0x6AB0` / GPU VA `0x426FDAB0` 原始内容：

```text
78060003 00000000 00000000 00000000 00000000
```

Gen11 Mesa继承gen8定义总长5；TGL `gen12.xml`规定总长8。更重要的是，**Intel官方PRM印刷页125**明确 `3DSTATE_STENCIL_BUFFER` 的 DW0 length=6（加bias2后共8），Body占DW1..7。因此这不是仅工具XML不一致，而是捕获的Gen11形式与TGL公开格式有真实差异。Gen12顺序decoder在该处停止，位于PS/VS设置和draw之前。

可以确认：按公开TGL规范，该packet长度与所需状态body不符。不能确认：硬件遇到此旧格式的确切处置、是否兼容/忽略某些状态、是否它先导致这次hang。不能把这个发现又直接升级为唯一根因。

### 2. 四个draw的扩展标志与长度也不自洽

`+0x6DF8 / +0x6EA4 / +0x6F50 / +0x6FFC` 的header均 `0x7B000008`：

* DW length=8→总10 DWORD；
* bit11 `Extended Parameters Present=0`；
* 后面3个附加DWORD恰为0，但不能据此称作合法扩展参数。

官方PRM印刷页2–3（text行624–632、668–680）明确：extended=false不包含XP0–2，length应为5（总7）；extended=true则length8（总10）。因此本批中“多三个零DWORD”的格式至少违反TGL文档约束。Mesa Gen11亦有单独 `3DPRIMITIVE_EXTENDED` 定义，要求bit11=1，此header未满足。

修正decoder：它可为取证**按声明长度有界走查**到END，但为这四条显式记 `length_semantics_validated=false` / `validation_level=bounded_length_walk_only`，不再把任意多长固定命令说成“合法extended”。166个packet/1089DWORD是边界走查数量，**不是166条已验证合法TGL指令**。

## Pipeline 的直接影响

* `PIPELINE_SELECT`选择3D；VS Enable/SIMD8=1；PS_EXTRA Pixel Shader Valid=1；PS的8/16/32 dispatch enable全部1。
* 因而PS的KP1 `IBA+0x200`、KP2 `IBA+0x100`不能作为无关padding丢弃。本轮已补充从这两个精确入口ICL/TGL解码、EOT/CFG、上游翻译及严格子集评估。
* KP1=440B/29条，KP2=216B/15条，均无branch、无条件EOT；三个PS合计808B/55条，旧896B切片还含88B间隙/对齐填充。
* `analysis/pipeline-snapshots.json`按四个draw packet保存22类必要状态包的最新字段；`pipeline-summary.md`展示bases/MOCS、VS/PS/WM/CLIP/SF、URB、push/constants、binding和sampler pointers。动态/结构组和实际heap内容明确未知，ModifyEnable=0的base仍继承前态未知值，不把命令内0值当已生效0。

## 对A–F假设的修订

F“其他Gen11/12状态/命令差异”现在有**具体静态反例**，不再仅为泛泛未知；A“EU ISA不等义”仍成立。两者都足以阻止“只替换Shader即可修复”的结论，但均缺排他实机因果。下一次任何翻译试验之前，必须先解决命令格式、所有启用PS入口及消息/依赖语义，而非只修PS0/VS。
