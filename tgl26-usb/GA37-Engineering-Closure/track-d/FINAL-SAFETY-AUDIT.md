# GA37 最终安全审计整合

三个独立源码审查的必修发现均已修复并独立重放；本整合结论限下述宿主／离线契约。最后的字节完整性以交付audit与seal回执确认。

## 审计方法与证据边界

主代理负责系统集成和最终准入结论，三份源码审查由独立代理完成，初审`AUDIT.md`保留，修复后另写`FINAL-CLOSURE.md`。简单来源/历史索引和GA38路线证据审查按用户偏好交DeepSeek。测试是实际CPU/文件系统/codec运行，硬件安全不以测试数量升格。

|领域|实际代码／独立证据|处置|
|---|---|---|
|CAS成败/Writer独占/错误发布|GA36候选原函数提取，legacy-regression8组合；源文件62e3abf2…|已确认的源级缺陷修复保留，baseline反例仍可重现；不是运行kext认证|
|Release/Acquire、不可变prefix/共享buffer|原GA36core7771dfb4…；原函数与核心测试，实际THAG集成|slots仅append；唯一snapshot writer；pending握手/水位/失败终态；旧volatile Hook未混入|
|排队/active/publish寿命|owned_executor c1e89ee6…，executor-review/FINAL-CLOSURE|Control强引用/Client/uniqueTicket、publishing栅栏、recursivegate、same-ticketRetry；宿主条件下关闭|
|取消/超时/异常退出/代码卸载|A协议与ThreadCall reference及Apple公开API交叉核对|cancel_wait不是禁新提交栅栏；timeout不可free activeIO；callback必须正常返回；真实XNU/模块卸载继续BLOCKED|
|事务文件/恢复/权限|TrackB源码865b609f…与writer-review/FINAL-CLOSURE|prefix symlink拒绝、post-publish allocation不确定终态与无分配保留、旧/新revision保全，原反例独立重放关闭|
|C++ callback名义ABI|实际集成constexpr Capture36::Write及callback_adapter，B独立static_assert与运行|准确类型已验证，文档已澄清default是名义不同的shape接口，真实GA36必须adapter，不能强转|
|v1/v2 wire/内存安全|codec c3cff699…，codec-review/FINAL-CLOSURE|初版伪VA/range/MBZ/flag/roundtrip遗漏已修；原负例重放拒绝；旧108B header/hash不变|
|原始与推导数据分层|C canonical raw-derived与12/10独立域|内部一致不等于观察者真实；unknown/raw可保留但不可冒有效VA；身份不得由范围/epoch猜出|
|路径/权限与资源寿命|逐component no-follow/受控dirfd/lock/暂存64残留上限；B独立清理反例|未知、权限不符或hardlinked资源保留且拒绝危险清理；published revision保留，文件和目录sync分离；整改独立关闭|
|Data race/Pointer ownership|A12矩阵+2TSan、独立重放；B序列化callback契约|有效Client/单ownerTicket和稳定input是API前提；同对象并发销毁或强杀不是受支持用法|
|HookABI/PM/GTACK/reset/clear|既有24函数、五问题有界补证及剩余缺口|未证明live patched instructions/receiver/active-power/same-request ACK/共同排他；不放行|
|默认关闭/物理内存门禁|旧候选hangDump强制0，新reader/backendNONE|没有bootarg接入或真实MMIO；未放宽pmap/TSEG/stolen等门禁|
|加速路线|TrackE唯一方向与roadmap-review13/13|输入/四无branch程序/31unit边界/资源缺口核验；只计划未启动GA38|

## 必须保留的条件

1. `EXECUTOR_LIFECYCLE=VERIFIED`只指有主宿主协议；真实ThreadCall coalescing/rearm/param引用、入口撤销与代码卸载栅栏未实现。`quiescent`不覆盖排队裸回调，ASan反例是实际失败证据。
2. `TRANSACTIONAL_WRITER=VERIFIED`须限定用户态受控本地FS与序列化单对象调用；跨对象/进程由同一parent lock协调。不能外推APFS断电耐久、网络FS、内核vnode或不可取消IO。
3. `FAULTRECORD_V2=VERIFIED`只证明格式/内存边界/一致性检查；provenance与caller字段是未自认证claim。raw/derived数学一致仍不证明tuple同事件或根因。
4. `CAPTURE_PIPELINE=PARTIAL`，宿主实际链接通不等于Hook→GPU producer→XNU scheduler→目标磁盘全链接通。
5. `DIAGNOSTIC_ENGINEERING=CLOSED`表示本轮授权离线工程已完成、必修发现已独立关闭；不以此替换硬件访问证明。

## 独立复核的最终绑定

* Executor `c1e89ee680b40e1e27b34ed9d015ba70e8a81eca5e87c060b4b490587010f84f`：宿主所有权协议条件通过，真实XNU代码卸载阻塞。
* Writer `865b609ffda438d0a5d776ffcb9f5dfbf812e4faa371f6f3ab3d8979816df820`：受控目录、单实例序列化、普通本地LinuxFS范围CLOSED PASS；8×73案例及独立旧反例/Clang和GCC重放。
* Faultv2 codec `c3cff69976223772c617f7f8fbba33e28e3384d2cf4fe829e3e525c5795f10bb`：原P1/P2负例独立重放拒绝，140codec/71gate与8matrix通过。

初审报告与修复前可执行文件/日志/结果/SHA回执保留；B检查点12件、C检查点92件已重算匹配原归档回执。没有将源级错误、故障注入、宿主崩溃或reference规范描述成目标GPU现象。

## 硬件准入结论

```text
READ_SAFE = BLOCKED
FAULT_DATA_COHERENT = UNKNOWN
REAL_MMIO_BACKEND = NONE
READY_FOR_HARDWARE_APPROVAL = NO
```

磁盘KC fbab2d48…及loadedmetadata不等于live patched bytes认证；SafeForceWake正常return不等于same-requestACK；spinrelease不等于引用必有效或必失效；softwareepoch稳定不等于硬件tuple原子性。旧4094不能排除Gen12 CEC4 Fault。最低额外证据见`REMAINING-BLOCKERS.md`。

本轮没有SSH改机、MMIO/GPU实验、kext部署、IMG/EFI/系统/固件/物理门禁写入，没有自动实机批准，也不需要用户现场配合。新真实访问仍需新明确授权与安全前提证明。
