# RCS Hang 与 CSB 审计（任务 J/K）

## 挂死签名（三代一致）

- `IPEHR = 0x7A000004` = **PIPE_CONTROL**（6 dwords；参考项目同样识别为 batch 之后的
  PIPE_CONTROL，见 LAYER4.md §4）；`INSTDONE = 0xFFDFFFFB`（VS、CS 未完成）；
  ACTHD==HEAD；TAIL 超前；RAM 的 ring start 固定 0x402DA000/0x402BE000。
- GA3.2b 捕获的 batch（ctx5）经命令走查重建：起始于 GPU VA 0x426FD000，
  以 MI_BATCH_BUFFER_END（0x05000000）结束于 0x426FE100；`BB_ADDR = 0x426FE104`
  正是 END 之后 4 字节 → **batch 已跑完**，引擎停在 batch 之后的 PIPE_CONTROL（CS stall），
  等待 VS/CS 完成，而 VS/CS 因 shader 无法完成而永不结束。这与参考项目 GA4–GA6 的
  观察完全一致（"the render engine ran a batch, returned to the ring and stopped on the
  PIPE_CONTROL with CS stall that follows"）。
- batch 内还包含两条 PIPE_CONTROL（0x426FD000 开头、0x426FD9E0，后者紧邻 SBA），
  属驱动正常 flush，**不是** 挂死点本身。

## 分类判定（任务 J 要求区分）

- **不是 Ring command 卡住**：ring head==ACTHD 同步，batch 已完成；
- **不是 Batch 地址错误**：batch 内容完整、SBA/VS/PS 指针自洽、页表翻译成功；
- **不是显存访问错误/CCS 配置错误**（无 FAULT_REG 异常证据；gpuRestart 无 memory fault）；
- **是执行单元停滞**：VS/CS 未完成 + 捕获的 kernel 为 Gen11 机器码（本机 EU 无法执行）
  → PIPE_CONTROL(CS stall) 永不完成 → 驱动 GPU Reset。

## CSB 审计（任务 K，只读）

- `igfxtglcsb=1` 的 Gen12 六槽循环、idle/active 映射与 id 匹配检查在源码中复核；
  未再出现 `Unexpected context status buffer entry` panic（三代报告与 4 份 panic 文件
  均为 2020-01-01 时间戳的旧实验，与 GA3.x 无关）。
- 多次 GPU Reset 后仍能记录事件（参考项目 GA4/GA5 统计 65/90 事件）；GA3.2b 的
  csb 记录未启用（未设置 igfxtglcsblog），本轮无新证据 → 维持现有实现，不改 CSB。
- 残余不确定性：Reset 后事件丢失是否影响驱动的 execlist 同步，无本轮证据；标为未证实。
