# 07 · RCS Hang：证据与竞争假设

## 实际 ring 证据

`python3 tools/rcs_evidence.py` 读取 GA2/GA31/GA32 的 **12 份** gpuRestart（排除 AppleDouble `._` 资源文件），每份路径/摘要/原始 ring/寄存器归于 `analysis/rcs-evidence.json`。共同签名 `IPEHR=0x7A000004`、`INSTDONE=0xFFDFFFFB`；报告的 VS/CS 未完成解释来自 Apple 驱动，对 TGL 的细分 EU/保留位解释不能全盘采信（原报告已有 reserved bits unreliable 警告）。

| 历史代 | 报告时间（文件名） | context顺序 | HEAD顺序 | PC后写值顺序 |
|---|---|---|---|---|
| GA2b | 230328 / 230348 / 230349 / 230358 | 6 / 5 / 6 / 5 | D4 / 14C / 244 / 16C | 4 / 5 / 9 / 10 |
| GA3.1b | 015324 / 015344 / 015345 / 015354 | 6 / 5 / 6 / 5 | D4 / 14C / 244 / 16C | 4 / 5 / 9 / 10 |
| GA3.2b | 040321 / 040341 / 040341-1 / 040351 | 6 / 5 / 6 / 5 | D4 / 14C / 244 / 16C | 4 / 5 / 9 / 10 |

三代head PC均为同一控制位组合 `7A000004 00104598 40001040 0 <值> 0`，是跨启动相似的等待/重置序列；context和后写值一致不证明同一物理资源或同一EU故障原因。12份原报告已私有复制至 `inputs/gpuRestart/`，receipt保存原路径与摘要，避免迁移时只带派生JSON无法复现。

Record1 对应 GA32 ctx5，`Kernel_2026-10-18-040341_host.gpuRestart` SHA256 `42391262698c263d0ab6c6bfc28948a3bca5da94cf6f9f432ad454b0ca789d63`：

* 第333–335行 ring `+0xC4` = `18800101 426FD000 00000000`，**MI_BATCH_BUFFER_START**，PPGTT、无 predication，目标 `0x426FD000`。由同context/寄存器签名的原始 ring 补得可信提交入口（捕获窗口 +0x6000），强于仅扫描 SBA 的证据。ring日志与THAG仍不是原子同步快照；没有allocation-generation ID，故地址复用/时间一致性不能无限提升为独立执行轨迹。
* `RING_HEAD=ACTHD=0x14C`，TAIL=0x168。报告第367–372行 head 起六 DWORD：
  `7A000004 00104598 40001040 00000000 00000005 00000000`。
* 6 DWORD = (header length4 + bias2)，是 **PIPE_CONTROL**，不是 MI_BATCH_BUFFER_START。
* DW1：CS Stall=1，Post-Sync=Write Immediate Data，地址 PPGTT `0x40001040`，立即数据5；constant/VF/texture cache invalidate、Pipe Control Flush、Notify=1；depth/DC/RT flush=0；instruction cache invalidate=0、TLB invalidate=0、LLC flush=0。
* 前一条 `+0x134` PC 是 `7A000004 10105021 40000000 00000000 00000000 00000000`。两个 PC 的用途不同，不能把所有 flush 归到同一命令。已按 Gen11 与 Gen12 XML **分别**解码：前一条DW1 bit28在Gen12是 `Tile Cache Flush Enable=1`（Gen11表不定义该field）；新代header HDC/L3 invalidate位在这两条为0，head PC的tile flush亦0。这是额外跨代状态差异线索，不足以独立判非法。
* 报告标记箭头 +0x148 是 **Adjusted to previous instruction** 的 dump 标记，不是实际 RING_HEAD；真正寄存器是+0x14C。

Intel 官方 TGL PRM Vol8（2021-12，官方 PDF 与镜像逐字节相同，SHA `8f69aa40…`）说明 stalling PC + post-sync 是 non-posted、等待先前 posted writes 达到 GO 点。因此前序 shader、cache、memory 依赖不完成都可能表现为此处停滞。**不得删除同步命令规避。**

## 一个关键证据缺口：原 fault 地址不是 TGL 的实际地址

固定 Linux `v6.18/drivers/gpu/drm/i915/gt/intel_gt_regs.h`：`GEN8_RING_FAULT_REG=0x4094`，而 **`GEN12_RING_FAULT_REG=0xCEC4`**，Gen12 fault address 寄存器是 `0xCEB8/0xCEBC`。Apple 报告打印旧 `0x4094=0x36`（且 valid bit0=0），没有真实 `0xCEC4` 捕获。

故“没有显著 fault 证据”只能说**没有捕获到可靠的新代 fault 证据**，不能说“已排除 GPU 内存错误”。本轮仅源码/离线观察，不修改任何现有 Hook；后续若需要这三寄存器，须另行授权独立诊断版本。

## 竞争假设矩阵

| 假设 | 支持 | 反对/约束 | 未知 | 离线可验证 | 还需要什么 |
|---|---|---|---|---|---|
| A EU ISA 不兼容 | 本机 PS/VS 双解码，compact MUL 的 SIMD8→16/寄存器改变、MOV→SYNC、SEND 非法 | 尚无逐线程执行轨迹；同一 hang 可能多因素 | 真正 dispatch 的 kernel、首个出错指令、转换后能否退休 | 已确认**编码不等义**；可验证转换字段/round-trip | shader/payload/SWSB/message 的完整静态证明，之后才是授权最小执行对照 |
| B Kernel/Batch 地址 | 原始 PTE 未保存，BB状态是瞬时快照 | ring 有可信BBS入口，Batch顺序长度可核验，捕获页成功，入口有效ICL代码 | GPU PTE flags、cache alias、时序重用 | pointer位布局/捕获metadata/顺序边界可验证 | 原始PTE及当时mapping identity；不放宽读取门禁 |
| C Surface/Memory state | state heaps不完整；sampler/RT SEND实际存在 | 本轮未找到可直接确证的越界指针 | surface格式/tiling/pitch/binding/sampler/payload | 已有命令字段可解析，堆内容不足 | 最小相关surface/binding/sampler/constant heap捕获 |
| D Cache/CCS/Resolve | Gen11/12 cache/aux差异；参考项目有独立resolve hang（上游声明） | 本机没有确认该draw是CCS resolve的证据 | aux-map/CCS/fastclear、PC目的地PTE、flush依赖 | 只能审查命令与已有状态 | 相关aux/CCS/resolve状态及Gen12 fault寄存器 |
| E CSB/Execlist | 现有适配并非完整Gen12原生driver；Reset后事件完整性未知 | 无旧CSB panic，能记录ctx切换与hang | CSB事件缺失/重排，reset时同步 | 源码与已有事件可审，不足证全正确 | 有界CSB/execlist时间序列，不能把无panic当正确性证明 |
| F 其他跨代状态/命令 | **具体反例**：+0x6AB0 stencil为5DWORD而TGL PRM要求8；四draw扩展flag=0却总长10（PRM要求7） | 顺序声明长度链可走，不代表TGL合法；硬件实际处置未知 | 是否在shader dispatch前已出现command/state故障；URB/payload/WA | 已对照官方PRM页125、2–3确认格式差异，见report12 | 先解决命令格式与启用的全部PS入口，不能仅做ISA写回 |

## 修正旧结论

历史 GA33-research/RCS-HANG.md 曾断言“不是Ring/显存/CCS错误”“shader无法完成是根因”。新证据能证明**ISA编码不等义**和**停在stall PC的寄存器快照**，但不支持排除C–F，也不能凭BB_ADDR紧随END证明整个绘制已完成。Batch fetch/control-flow完成与EU工作退休是不同事件。

**GPU_HANG_ROOT_CAUSE = PARTIAL**。ISA与command格式现在都有静态不等义/不一致的具体证据，仍未区分首个故障及排他因果；当下不具备Shader写回实验条件。初稿中“尚未发现明显状态错误”已被report12的新证据修订。
