# 测试与证据矩阵

这些检查验证离线实现和证据边界；未运行GPU/驱动/实机采样。最终实际结果在`logs/lab-check.txt`、各native-results及`logs/determinism.json`。

## Python：104项方法

|范围|方法数|主要正例|主要反例/边界|
|---|---:|---|---|
|原命令suite|31|THAG166边界/raw、SBA已知继承、普通/extended长度、显式typedBBS、NOOP变长/跨页|旧stencil/draw、UNKNOWN继承、heap缺失、unknown opcode、truncation/overflow、alias、间接/谓词/BBS payload、packet/depth界|
|独立初审回归|20|Gen11第二级chain、已知nested3层、保持fallthrough、逐field pipeline mask、lastVA DWORD|未知target模式、循环、模式路径不合、改变fallthrough目的、初始payloadentry、条件结束、非法selector mask、END/BBS MBZ、半LRI组、扫描work超限|
|Normalizer/复审回归|13|官方独立pack的8DWNull/Depth拷贝、四draw A/B与next边界、两研究样本总长、非Null编码仅syntax级UNKNOWN、条件XP缺省|资源存在/未知/状态缺失、MOCS/stepping/depth未知、nonzeroXP/indirect拒绝、R01七DW不误要求XP、R02 checkeropcode/mode/envelope、R03 VA边界、R04 frozen provenance/矛盾state拒绝|
|关联模型|40|Batch/Shader/Surface/PostSync候选、完整identity、sample-only、hang-through-sample、GGTT、lastVA byte|valid0、clock/time/seq/epoch/context/PML4未知或冲突、string-false proof、allocationclock/epoch/lifetime/identity/generation缺失、post-hang replacement、alias、malformedcandidate继续、半开区间溢出|

`track-a/tests`共64，`track-c/tests`共40。方法数不是所有内部数据组合数。没有把旧31+15绿灯当安全证明：初审14问题22反例与后来4+2发现均保留独立证据，修复后的新增回归另列。

## Native core

Clang21.1.8与GCC16.2.0，每个compiler均为Debug`-O0 -g3`、Release`-O2 -g -DNDEBUG`，plain及ASan+UBSan，各4executable，共8。freestanding Debug/Release每compiler2object，共4；未解析依赖只允许编译器memory primitives。核心测试组数以最终receipt为准，修复borrowed-input alias后重新实构建，不复用旧binary充新结果。

|问题域|实际覆盖|
|---|---|
|decode/VA|valid0/1、PPGTT/GGTT、32768engine/source/type组合、DATA1全部512合法低9位组合/每个高MBZ位、36bit页→48bitVA界|
|失败与时序|三个read位置逐一失败立即停、42次guard边界的epoch/token/reset/power/GT/ACK注入、稳定/回退/缺失时间、caller身份、重入、borrowedRequest/Callbacks alias回归|
|有界存储|fixed8、失败也占slot、满不覆盖首条/无回调、序号UINT64_MAX/zero seed、计数饱和|
|codec|108种truncation、magic/version/size/reserved/enum/validity/status/readCount不可能组合、事务性拒绝、rawinvalid保留、每build20000mutation roundtrip|
|静态范围|无真实MMIO backend、无clear/reset/allocator/文件IO/threadcall、原GA33副本hash、未接入patchcheck|

独立fault审查另外有10725codec状态组合oracle与24reachable结构态、9431scanner检查；TSan用于证实**未支持并发调用确实race**，不是声称thread-safe。真实锁/ACK/power、callback真实执行时长与context生命周期未由CPU测试证明。

## 独立上游pack与样本

另8个Clang/GCC Debug/Release plain/ASan+UBSan上游pack executable，实际输出匹配`reference/track-a/pack-proof.log`。Release测试仍保持pack-check assert有效，避免NDEBUG取消测试；core使用独立CHECK，不因Release取消断言。

boottext scanner 24正负case和五个108B wire sample另外由ClangASan+UBSan编译执行，真实Collector/codec落盘回读、sample hashes留档。它们是合成数据；context/PML4均unknown。alias修复后新run与旧sample bytes比较，旧sourcehash/receipt不覆盖。

## 确定性和来源

13分析工件两次完整再生成逐byte/hash一致；native8core+8pack共16binary及对应tested sourcehash核对，两个独立跨8build stdout组一致。不是跨compiler二进制逐byte相同，也不证明GPU行为确定。

`tools/verify_history.py`只读验证旧ISA-Lab559本地文件+2外部输入、2个clean pinned源码、4个GA33副本。Lab和仓库根makecheck分别执行，来源审计脚本重新检查Linuxoffset/domain/公式/clear/MOCS及官方DATA1。完整封存由manifest验证，不用重封掩盖变动。
