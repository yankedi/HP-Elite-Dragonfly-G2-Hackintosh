# GA4.1 唯一推荐目标：i915/XNU 的真实设备探测与 GEM 内存对象闭环

**继续原生Intel主线，优先解决真实内核设备/内存合同。** 不再做一轮广泛Gen11→Gen12数值审计，也不先把WindowServer/完整Render作为单步目标。

GA41建议命名：**Tiger Lake i915/XNU Probe & GEM Foundation**。这是下一轮实施建议，本轮没有开始或授权它。

## 单一验收闭环

`可信设备身份/Query → GEM创建 → 合法CPU映射 → 写入/回读 → unmap/close → 对象与页所有权完整释放`。

它不是GPU提交目标；必要的render节点、libdrm/PCI shim和真实query是该闭环前提，不是假造驱动名绕门禁的手段。NMDRM通用VERSION返回nmdrm是正确表达未实现状态；必须具备实际后端再讨论i915身份。

## 先后顺序

1. 在独立新目录建立Darwin用户/内核共享的精确wire ABI与构建环境，固定XNU/SDK/编译器版本。保留Linux/BSD方向位差别、顶层与嵌套指针copyin/out规则；不直接把Linux request number硬塞给Darwin。
2. 在CPU上实现受控内存提供者与严格错误路径，覆盖每个真实资源所有权步骤；Mock明确标记，不能宣称内核/GPU支持。
3. 提供可编译但默认拒绝的Darwin transport与i915接口，绑定真实后端前任何query不足、GEM不足、mmap不足均应失败；用原始负例验证拒绝，不用Fake Success过ANV。
4. 对真正的XNU物理页/GEM实现做局部移植与代码审查。PCI/页固定/映射/缓存/对象回收所需实机条件必须另列，并等待用户明确许可。
5. 即使完成内存闭环，也不升级为可提交。GPU VA/页表/context/engine初始化、同步/IRQ/reset/PM仍是下一阶段独立工作。

## 必须保留的负例

未知request、wrong size/方向、padding/extension、synthetic/真实指针混用、未授权嵌套指针、越界/对齐/溢出、跨会话与stale handle、映射失败、部分成功清理、close与并发、未完成Fence不得成功、无提交时readback不能冒充GPU结果。

## 进入真实硬件前的必要条件

真实PCI所有权与Apple驱动竞争方案、内存所有权和可审计回收、映射与缓存合同、明确的恢复/断路策略，以及新的用户授权。当前 `READY_FOR_HARDWARE_APPROVAL=NO`；本计划不批准部署、内核加载、MMIO、Batch、重启或修改任何安全门禁。

## 为什么选这个目标

GPU原生编译的价值必须依靠真实内存对象/映射来承接。继续增加CPU Mock功能或继续扩大helper复用都不能替代该缺口；反过来先做真实Batch而没有GEM/VM/同步基础会直接制造不可靠成功或Hang风险。该闭环把下一轮工作限制为一项可明确验收、可失败、可停止的工程目标。
