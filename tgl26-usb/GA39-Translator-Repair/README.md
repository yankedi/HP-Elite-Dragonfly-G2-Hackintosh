# GA3.9 — Translator Repair & Semantic Proof

纯CPU离线工程。所有新增文件在本目录，GA32–38封存只读。**最终工程报告已交付，三轨必修已独立闭环；完整性结果见`logs/seal-verification.json`，硬件批准NO。**

本工程实现默认Strict的转换准入、一个实际有限整数MOV codegen、独立scratch may-liveness、NF/ACC携证拒绝、Debug/Switch门禁以及SEND字段/完成事件审查。没有把旧候选的decode/roundtrip成功提升为语义证明。

## 两个转换入口

在本目录运行，所有输出目录必须是不存在的新目录。

```bash
export PYTHONDONTWRITEBYTECODE=1
# 默认Strict：真实四程序仍含必要UNKNOWN。拒绝exit=2，输出原bytes与逐节点义务，不输出目标shader。
python3 -B translator/driver.py --shader PS0 --output runs/my-strict-PS0
# 显式Research：独立重建的上游生成器；生成完整离线候选、 fresh GA38 review及exact roundtrip。
python3 -B translator/driver.py --shader PS0 --mode research --output runs/my-research-PS0
# 严格有限接受的正例：整数MOV孤立片段，不是可执行shader。
python3 -B tools/run_positive_fragment.py runs/my-integer-mov
```

其它真实ID：`PS-KP1`、`PS-KP2`、`VS`。Research产物路径及sidecar均带`NOT_FOR_HARDWARE`。报告区分“生成了完整研究程序”和“接受了已验证可执行程序”；后者目前始终否。`translate_unit.py`仅接受无NF/ACC/SEND/Debug的有限NoMask SIMD8连续DWORD整数MOV域，不能把孤立片段拼成完整shader。

## 证据与来源

- `reference/inventory/`：实际GA38/37 seal核验、原捕获与IGA/Mesa/Translator完整pin、87项身份；GA38manifest固定`db30c52513df69b6aede0cab767861de137ed669a26d88cbfee61ceddbe326f8`。
- `validator/ga38/SNAPSHOT.json`：按封存manifest逐文件核验复制的独立基线；语义核心不改。路径/输出范围和测试scopefixture适配diff在`translator/patches/ga38-adaptation-012/`。原失败009与47项重放010均保留。
- `translator/source/native/`：归档13blob的translator和必要Mesa adapter/header子集、五新构建及复现脚本。不是完整原上游worktree。GCC首次C23/once_flag构建失败与gnu11适配均保留。
- `reference/numeric-debug/`：ICL PRM的NF格式及Switch实际作用。NF格式轮廓已知但66/67bit冲突，位精确算术仍UNKNOWN；VS为普通FACC。
- `numeric/scratch-liveness/`、`numeric/proofs/`、`debug/switch-elimination/`：已知GRF投影、逐转换义务和默认拒绝。
- `messages/`、`scheduling/`：独立消息字段与五种完成事件；旧14+6及第三轮四项已独立关闭，第四轮修补与final4保留；最后N15分类优先级最小修补在`reference/message-scheduling/repairs-005/`，独立final5另存。旧默认输出已逐轮封存在`superseded-defaults/`，当前指针在各`CURRENT.json`。
- `tests/historical-regression/`：31历史单位、8程序、640 native调用和21旧mutant的真实重放；Python未声称ASan覆盖。
- `candidates/delivery/final-I-072/`与`final-J-074/`：冻结driver053/message005源码后两套全新目录，各重提取79源+79候选、20SEND、948评价；四程序Strict拒绝、Research实际重生/GA38再验证/往返，双模式附semantic-bundle。`candidates/comparisons/final-determinism-075/`要求108项必需语义/二进制工件并通过比较；只规范化运行根路径及指定JSON路径耗时，保留嵌套同名语义键；键序/空白规范化明示。旧A–H均保留。当前bytes及948评价仍627有前提核对、0子集确定反例、321UNKNOWN，Strict拒绝不减少UNKNOWN。
- scratch当前`run-031`；Strict/正例当前优先看final-I内，旧`strict-032`/`positive-fragment-033`是数值修补后中间回执。修前004/007/019及Research014/semantic023均保留；不冒充最新集成产物。数值终审224探针、新鲜度刷新115探针通过；005源码后current bundle已由I/J重生，076核原码/计数，最终来源绑定见state。

## 一次完整离线重放

```bash
python3 -B tools/run_delivery.py run --output runs/my-fresh-A
python3 -B tools/run_delivery.py run --output runs/my-fresh-B
python3 -B tools/run_delivery.py compare --left runs/my-fresh-A --right runs/my-fresh-B --output runs/my-determinism
python3 -B -m unittest discover -s tests -v
env -u GA38_RUN python3 -B -m unittest discover -s validator/ga38/tests -v
```

重放会增加Lab文件；最终封存后的原件只做`python3 -B tools/seal.py verify`，重放需先私下复制完整Lab/外部依赖，在副本的新目录运行。所有命令只使用CPU，Strict预期拒绝不表示重放失败。Research失败不发布成功候选，保留`rejected-NOT_FOR_HARDWARE`与结构化失败报告。

## 固定依赖

Python标准库，native IGA与C/C++工具由来源回执固定：IGA `c36a504a4e6c68030c3302646aa396b8b59b22cb`，Mesa `863338275d915e867319c3690ffd3272b06303c3`，Translator `1010490d3421628c9d6fd0bd518b6c4b6f8ee33c`。实际binary/shared-library SHA每次IGA调用前核验。native研究生成器在`translator/research-mode/generator.json`固定；新构建命令见`translator/source/native/README.md`。

## 边界与迁移

`READY_FOR_HARDWARE_APPROVAL=NO`。NF模型、资源Heap/thread payload ABI、null-response `.dst`、SBID复用和EOT全局可见性仍有未证义务。未访问真实GPU/MMIO/SSH、未部署或改IMG/EFI/固件/门禁；不声称Metal成功。GA40只规划。

包含私有捕获派生物、源码、构建与失败证据，不进Git或公开上传。迁移须私下转移完整Lab和最终manifest列出的外部来源，并核SHA；仅仓库不足复现。`state.json`、追加`history.json`和`continuation.md`记录当前进度，最终结论须以封存后的FINAL-REPORT和实际审计回执为准。

外部来源含绝对路径，`trust.py`也要求同父目录下的认证GA38副本。迁移/重放应保留原路径布局（可在另一台机器的相同路径建立私有副本）并核对依赖；单独移动GA39目录不能保证重放成功。改路径属于新的适配实验，应在副本保留diff并重新验证，不能改已封存原件。seal覆盖历史manifest列出的文件/链接文字，未列的新目录成员不在其范围；manifest pin的独立锚为最终会话交付回执。

复现环境另需可运行的Git/Python及同ABI的IGA/native运行时；IGA校验实际执行固定来源树的`git rev-parse HEAD`，因此须一并私下保留匹配checkout及必要Git元数据，不能只复制`iga64`。manifest的文件完整性闭包不等于可迁移的完整Linux系统镜像，符号链接目标与宿主运行库仍须独立满足。
