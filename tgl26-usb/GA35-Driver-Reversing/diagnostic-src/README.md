# GA35 隔离诊断核心

这里是GA34最终405行核心、boot-text离线scanner、mock测试和sample源码的逐字节私有副本。保留namespace/版本/文件名以明确基线，未连接任何Apple Hook或MMIO backend，也未创建新kext project。

新取得的25G83二进制尚不能建立active power/reset排他/latch一致性契约，因此本轮不开发真实接入。`Request::enabled=false`，默认拒绝而不调用callback。`-igfxtglfault34`只作离线文本识别；没有接入真实启动参数。

独立GA35构建和回归在`../audit/ga34-review/`：8种Clang/GCC Debug/Release×plain/sanitizer、224组core、4个freestanding和4个alias审查构建、5个108B wire。该目录保留实际源码副本与tested-source hash；交付副本由最终审计核对逐byte一致。

本地最小重编译示例（所有输出留在GA35新目录）：

```sh
mkdir -p diagnostic-src/local-build
clang++ -std=c++17 -Wall -Wextra -Werror -O2 diagnostic-src/test_tglfault34.cpp -o diagnostic-src/local-build/core
diagnostic-src/local-build/core
```

完整矩阵复现入口见根`TEST-REPORT.md`。不要运行GA34原地build脚本覆盖历史。

注意三套domain数值不同：核心本地GT=1/Render=2/Media=4；精确Apple多线程分支的Render=1/Media候选2/GT=4。不能把Apple mask直接填入core的单域字段，不能从mask请求推导ACK或电源状态。
