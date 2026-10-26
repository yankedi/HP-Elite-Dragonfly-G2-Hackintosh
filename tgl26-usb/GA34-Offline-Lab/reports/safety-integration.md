# 独立安全审查整合

结论等级：**CONDITIONAL（离线实现），真实MMIO接入BLOCKED**。没有安全门禁放宽、GPU写回、原hook修改或硬件实验。

## 审查链与证据保留

1. `track-a/reports/independent-parser-audit.md`：14distinct发现、22实际反例，10P1/4P2；A01–A08/C01–C05/X01。旧31命令+15关联suite绿灯未覆盖这些问题，原reproducer/results/source hashes保留。
2. `track-a/reports/repaired-command-review.md`：13原A反例修复或拒绝，新增26观察，未重现strict Shadow错误成功；另发现R01–R04四项P2。旧snapshot与错误candidate receipt作为历史证据保留。当前实现修复条件XP、checker envelope/opcode/mode、studyVA及exact frozen provenance，closure单列。
3. `track-c/reports/correlation-fix-receipt.md`：C01–C05和C侧X01修复，40测试、9原输入与18新场景，identity从页范围/未知epoch/错误根地址/异域lifetime/替换allocation中降级；sample身份与hang连续性分开。
4. `track-b/reports/independent-fault-review.md`：独立codec oracle、scanner/wire核验及TSan边界；发现R1/R2两项条件borrowed-input alias问题（request基准漂移、callback指针被改导致crash）。实现采用入口descriptor值拷贝并新增回归；`fault-alias-closure.md`独立确认原R1变为ResetRace/1read/2guards、原R2不再crash且固定3read/6guards；63descriptor+3request变体在两sanitizer模式通过，191protected文件不改，三路10sample artifacts相同。原失败样本不删。

## 已控制的离线错误域

|域|控制/证据|
|---|---|
|错误命令控制流|legacy二级chain、显式Gen12mode、最多3层、条件结束拒绝、entry/BBS边界、每dynamic occurrence映射及返回/fallthrough核对|
|reserved/conditional字段|canonicalEND、BBS地址MBZ、pipeline逐fieldmask/非法mask、完整动态组、条件XP default0；XMLnonzero不滥当普遍硬件限制|
|范围/工作预算|source/target alias、48bit半开区间、input segments/bytes、packet/decode-scan budget、MAX_BYTES输出、frozen研究输入与typed refs|
|不完整成功|strict converter资源未知即拒绝、无partialbyte发布；完整A/B研究强制PARTIAL/GPUunproven/deploymentfalse，opaque资源未重定位|
|故障/record|GT和ACK分开、power/reset/exclusion门禁、fail-stop read/observer、fixed8append、sequenceoverflow、codec事务性校验、raw/derived有效性分层|
|callback输入alias|借用descriptor在入口冻结，callback不能通过修改原Request/表改变当前采样基准；callback context生命周期仍是caller义务|
|错误关联|typedknown epoch/strictbool、有效root/clock/sequence/lifetime、identity/generation/receipt、aliasambiguous；identity从不等同hang因果|

## 必须保留的真实接入阻塞

* current25G83 exactbinary/反汇编、Apple domain7映射、GT ACK/active-power/refcount、reset/clear互斥及锁顺序未证。
* core的bool/token/epoch由caller声明，值拷贝不建立锁；observer必须coherent，callbacks有界nonthrowing/不阻塞，context必须有效。collector不支持多线程并发，busy只防同线程reentrant；TSan证实并发不在契约内。
* 3个raw寄存器顺序读与6个guard不证明原子fault latch、同次hang、无ABA/clear。Complete表示协议完整，不是硬件coherence。没有二次fault读/设备前后clockpair。
* 原GA3.3共享flags/buffer/thread_call的同步和lifetime未在本轮证明；新core不接它。未实际试验MMIO读副作用、panic/machinecheck；无真实backend，因此CPU测试不能把这些降为PASS。
* heap/allocation generation/shader payload、MOCS及stepping/flushworkaround仍缺；NULL与draw局部合法不等于完整Batch合法，也不等于Metal。

初审14+第二轮A4+B2共20distinct发现已修复；闭环回执分别见A的`r01-r04-closure.md`、C的`correlation-fix-receipt.md`、B的`fault-alias-closure.md`。修复完成以这些新closure和最终sourcehash/测试收据为准；不修改前次审查报告来冒称当时已经修复。最终manifest收录整条证据链。该闭环不关闭上节真实平台/资料缺口。
