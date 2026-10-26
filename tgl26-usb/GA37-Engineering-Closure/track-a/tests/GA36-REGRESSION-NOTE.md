# GA36 原样回归发现：bounded lease refusal 并非永久关闭

`ga36_pipeline.cpp` 初始逐字节复制实际 GA36 `pipeline.cpp`。第一次 Clang Debug/Release/ASan+UBSan 通过；GCC因新 executor 测试的误导缩进触发 `-Werror`，仅修复缩进。

第二次运行保留 `logs/20261018T162019Z/clang-debug-ga36_pipeline-run.txt`：原样 stress 在第149行 `publish==Accepted` 断言失败。原核心 `enter()` 有32次CAS预算，16个drainer同时增减lease可以耗尽预算，`publish` 返回 `Stopped`，即使并未 `close()`。这不是buffer被覆盖，也不证明真实XNU故障；暴露原宿主stress假定“无关闭必定成功”过强，且API将暂时refusal与shutdown合并。

不改历史、不改核心的wire/Writer协议；后续适配回归必须显式接收未发布的暂时refusal并由宿主有限重试，原样测试及失败日志继续保留。executor在自身门控确认Running时把该Stopped映射为Busy，不能把一次lease竞争当成对象已经释放的证据。
