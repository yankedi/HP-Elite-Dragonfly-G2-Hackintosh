# 下一步：仍是离线证据补齐

**当前不具备下一次真实Gen12 Fault采集的批准条件。READY_FOR_HARDWARE_APPROVAL=NO。** 本文件是缺口清单，不是启动、部署或新增MMIO读取的指令。

本轮已排除“还没有准确25G83驱动”的首要障碍，也推翻简单的“Apple7就是Render”注释，但mask映射不足以证明实际Hook在安全上下文。

## 按优先级的剩余研究

1. **实际dispatch与引用契约：** 证明`accelerator+0x11c0` feature位和`+0xdf8`转发函数表的选择来源/有效生命周期，追到Framebuffer实现；不能从符号存在认定当前机器选择多线程路径。
2. **电源和排他：** 追踪所有power-down/teardown/reset/interrupt/workloop入口与同一设备锁/引用关系，形成可核对的锁序偏序；证明采样期间设备active、GT不会释放、映射不会销毁。
3. **Gen12 latch：** 找到适用于Tiger Lake的权威读/clear/更新契约，确定CEC4→CEB8→CEBC是否在选点上构成同一fault；核清软件epoch与硬件更新之间的关系。
4. **精确选点：** 必须早于第一次破坏fault、在上述共同排他区域内；当前晚期mask7点与RCS mask1点均未获证。不能仅根据漂亮调用图挑地址。
5. **关联及ABI：** 建立同boot/hang/reset/context/root allocation generation协议；独立验证实际原函数trampoline与runtime-byte身份。stock入口字节/UUID不替代live patch核验。
6. **旧实现的软件缺陷：** 若未来准备复用GA3.3 writer，须在新的独立候选树修复并反例测试CAS门控、发布协议、uio失败和回调teardown。精确XNU机器码已确认CAS成功为true，而旧源码成功分支反向退出；本轮只记录，不修改旧实现。

仅在这些关键前提都证明后，才另行提出默认关闭的候选reader/observer与离线故障注入矩阵，进行独立审查。新硬件步骤须用户新的明确授权，并有单变量、有限次数、失败即停、私有取证及回退约定。

## 将来申请需携带的证据包

- 精确build/UUID/source SHA和当前loaded对应证据；Hook完整机器码/ABI/trampoline审计。
- 已证明的power/GT持有/ACK成功契约、reset/clear共同排他与锁序、latch一致性说明。
- 中断/线程上下文限制、零分配预分配缓冲生命周期、所有失败退出路径和记录关联方案。
- 默认关闭行为及mock负测、独立审查与manifest；不能以“能编译”替代上述证明。

当前不制作kext、IMG或Ventoy测试介质，不要求用户启动任何GPU实验。
