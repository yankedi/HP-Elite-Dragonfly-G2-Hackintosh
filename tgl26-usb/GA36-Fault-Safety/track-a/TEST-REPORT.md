# TrackA 实际验证与边界

## 结果

|验证|实际结果|证明范围|
|---|---|---|
|实际源码callback提取|baseline/candidate各4个Clang/GCC release、ASan+UBSan构建运行通过|真实hangThread/hangWriteRecords函数体，XNU依赖由mock替代|
|确定性原缺陷|首次CAS成功writes0/flag1；两个CAS失败者maxConcurrentWrites2且同snapshotbuffer|不是只按源码猜测；基线测试通过表示成功重现缺陷|
|源级修正|单winner、2/16线程maxConcurrentWrites1；失败flag2、后续不重试|不代表旧volatile producer已修复|
|资源清理|open/uio/addiov/write/residual/close等9路径及missinguioFree检查通过|每个成功获得vnode关闭一次；有uio必释放；vfs context释放|
|隔离Pipeline|4个编译器/sanitizer构建通过|单writer、immutable prefix、pending handoff、error终态、capacity、生命周期契约|
|高竞争|每build 120轮×16drainer；另16publisher单owner测试|外部通知可靠且输入稳定的CPU模型；非ThreadSanitizer/形式证明|
|重入/终态竞态|同线程producer重入拒绝、writer重入Busy、publication遇close/failure返回RetainedStopped/RetainedFailed|数据保留不谎称写出；不能异步强杀IO|
|重试理由|attempt1清空，2–8保留全部先前理由，新hang重新清空|独立审查F6对应纯helper；不改变THAG大小|
|真wire布局|原HangRecord从candidate header提取，Clang/GCC均assert size0xC2F8、diag0xC2A0、out0x90|原struct布局，不是184B mockrecord冒充THAG|
|CPU→实际文件→codec|3个v3记录经Pipeline写文件，两编译器输出逐字节相同，严格roundtrip；原GA32b v2 roundtrip通过|实际本地文件写出，不是实际GPU数据；不证明断电持久性|
|严格parser负例|10种空/截断/版本/size/magic/index/attempts/超容量拒绝|结构格式不等于上下文/物理真实性|
|历史parser对照|22项检查；旧parser乱序只warning，新的thag36拒绝|历史parser未改|
|freestanding|Clang交叉编译x86_64 Mach-O object通过|隔离core对象文件；完整kext未构建/链接/部署|

## A3 场景覆盖与剩余前提

- 正常/两线程/16线程/CAS成功失败：actual legacy harness及Pipeline。
- 提前退出、open失败、短写、后端返回timeout：首错误持久化、释放owner、禁止重试；**不声称能中断永不返回的VNOP_WRITE**。
- Capture重入、两次/三次hang、未完成snapshot、发布后scratch修改：producer try-CAS、complete拒绝、immutable slots和递增watermark。
- ThreadCall取消、对象销毁：CPU close/active lease/worker join模型；排队但未进入的raw callback须额外fence。真实XNU调度未实测。
- 错误恢复、重复/漏写、记录顺序：无reset API、失败终态、每prefix水位单调；通知丢失或取消后未写的记录明确retained，不能承诺所有publish必写。
- 版本不匹配/截断/序乱：原v2+精确v3 ABI/codec回归。

## 复现（在新私有副本内运行，不能改封存工件）

```sh
export CXX_GCC=/nix/store/j1938gsbvbhkyz4kbmvjk56r479mkw3s-gcc-wrapper-16.2.0/bin/g++
python3 -B track-a/tests/run.py
python3 -B track-a/tests/wire.py
python3 -B track-a/tests/legacy/run_tracka.py
python3 -B tools/make_writer_patch.py
```

如compiler路径迁移失效，用可用GCC wrapper设置CXX_GCC；actual legacy runner自行查找已安装编译器。精确命令、工具路径及结果以各logs JSON为准，不能只根据本表重建运行环境。

## 日志与已修正工具副作用

- `logs/pipeline/results.json`、`logs/wire/results.json`、`logs/legacy/tracka-results.json`；`logs/freestanding/`保存Mach-O编译命令与wrapper warning。
- `logs/pre-review-fixes-*/`保留独立审查前输入和原日志；GCC最初Werror格式失败在pipeline目录保留，已修正。
- legacy parser子进程最初缺`-B`，产生新的历史目录pycache。发现后将**本次生成件**逐字节移入`../../audit/bytecode-sideeffect/`，恢复原目录；对子进程加`-B`并禁止import写bytecode，重新执行22项parser通过。原始源码、capture及manifest哈希均需在最终seal核对。此项是已纠正的执行边界副作用，不隐瞒为“从未写过历史目录”。

## 裁定

CAS_WRITER_FIX=VERIFIED限已确认源级门控和独占/失败终态软件行为；CAPTURE_PIPELINE=PARTIAL，因为真实Hookproducer、XNU取消/卸载、O_TRUNC事务和不可返回IO仍无闭环。保持hangDump硬关闭，无新硬件backend。
