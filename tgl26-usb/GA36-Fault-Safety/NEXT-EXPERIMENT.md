# 下一轮最小方案与证据回退

## 当前判定

**READY_FOR_HARDWARE_APPROVAL=NO。现在不申请读CEC4/CEB8/CEBC的实机实验。** 没有可审计的采样点；多一次真实读无法替代PM/ACK/reset排他与tuple安全证明。

## 先做的最小离线增量

1. 只在新私有目录开发publisher→可靠executor的XNU适配设计：先fence所有capture/worker提交入口与执行中的Hook，再证明cancel/wait/free的后置条件、无新enqueue、无queued raw callback、无active IO。上游公开XNU12377.121.6不是25G83的12377.161.14，不能把参考契约称为目标实测。
2. 将legacy O_TRUNC改造为可审计的完整文件commit策略：唯一临时文件、短写/close/sync失败保留旧证据、原子替换及目录持久性分别记录。先离线故障注入，不直接在内核增加vnode/rename调用。
3. 保持三读backend为空。对已经找到的`populateAccelConfig`→flags、callbacktable→receiver和PM/reset ownership分别补足**一个最小契约**：实际分支、对应GT引用owner、same-request ACK后置条件、reset/clear/lifetime共享排他；不能把独立token声明当证明。
4. 查到适用于本stepping的设备级fault latch/clear代际规范后，才定义三寄存器tuple判据。重复读取CEC4相同不能排除ABA；不得为了“确认”擅自增加真实读。

## 未来实机提案的最低格式（本轮不执行、不批准）

- 固定diskKC及运行patched bytes/trampoline身份、接入ABI、对象和MMIO映射生命周期。
- 九条件各自证据全部VERIFIED；证明同一power/ref/ACK/epoch覆盖全部读，排除reset/clear并发，且不扩大Apple锁范围或改变恢复流程。
- 实验唯一变量为已审计的默认关闭只读采样点；固定一次有界记录/超时预算/停止条件，禁用GPU写/clear/命令与shader修改。
- 先审批方案再由用户物理控制启动；任何关键条件缺失均保持NO，不将条件计划当授权。

## 回滚与保存

本轮没有部署、IMG/USB/EFI/系统卷/固件变化，故无需硬件回滚。软件回退只需丢弃新候选工作副本，历史GA31–35仍按原manifest。不要删除原捕获、失败日志或initial审查，GA32b真实THAG有效性不受GA33源码CAS缺陷否定。

封存复制包括本目录、manifest/selfhash、GA35准确KC和独立输入的哈希；跨机必须私下传输并两端verify，不公开Apple专有bytes或私有身份。新的失败或结论追加在新的实验目录与history，不改写本封存为事后成功。
