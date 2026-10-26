# GA4.11 — 上游完整渲染兼容路径核对

目标基线为GA4.10 R6；R6不是稳定版。R7封存。本阶段先做本地源码与既有像素证据核对。

- [本地审核记录](reports/LOCAL-AUDIT.md)
- `reports/LOCAL-EVIDENCE.json`：`tools/audit-local.py`从固定上游git对象、R6源码、donor及原始运行回执提取的证据。
- [像素采集协议](reports/PIXEL-PROTOCOL.md)：同图案/尺寸/格式的独立GPU、CPU expected验证。
- `reports/NATIVE-CHECK.json`：目标仍为R6 session、两个诊断源码原生严格语法检查通过；没有GPU执行。
- `reports/SYNTHETIC-VALIDATION.json`：离线dump复核器的十组人工样本验证，不是GPU运行结果。
- [GA4.10全过程总报告](../ga410/reports/GA410-CONSOLIDATED-REPORT.md)

**当前：本地审核完成，根因未定位；实机像素采集待用户批准。** 静态匹配、补丁命中、返回成功均不代替像素PASS。当前没有据本轮审核生成新的驱动补丁或实验镜像。
