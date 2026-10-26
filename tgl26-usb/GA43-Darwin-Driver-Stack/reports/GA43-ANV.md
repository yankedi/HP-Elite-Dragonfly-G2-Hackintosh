# GA43 ANV Darwin 构建状态

固定Mesa、三份GA42 patch及编译器功能保持；未重复Linux ANV构建。
用户要求先完成最小真实链接；当前严格探针缺libSystem及现代Mach-O linker，
所以完整ANV仍BLOCKED，无 `libvulkan_intel.dylib`，无可交付 `intel_icd.json`。

本轮实际改进 `tools/anv-darwin-attempt.py`：

- 无真实完整用户SDK和SDK匹配的八个编译/链接结果时，在复制/配置前拒绝。
  不再重复 `/nonexistent` sysroot 的完整Meson调试。
- 不采用kernel headers、Linux头或允许任意未解析符号的诊断dylib作为gate成功。
- 明确Darwin linker与llvm-ar/llvm-strip，C++使用libc++；sysroot保留真正标准头搜索。
- 从固定commit `git archive`，隔离ignored下载缓存，强制patch `--fuzz=0`。
- `--wrap-mode=nodownload`，禁止强制fallback；cross pkg-config目录显式给定，
  默认空列表，避免host ELF依赖意外进入Darwin链接。
- 不运行target程序，`needs_exe_wrapper=true`；无网络操作。

实际 `logs/anv-prerequisite-gate-001` exit2：缺DARWIN_SDK/DARWIN_LD/
DARWIN_PROBE_RESULT，未运行Meson；脚本语法检查exit0。
这是fail-closed构建工程改进，不是ANV编译或链接PASS。
GA42最后编译/链接错误仍如实继承：GNU linker和缺 `sys/stat.h`；
本轮更早阻塞由真实五步探针具体定位为缺stdlib/string/libSystem/c++与旧LLD限制。
完整交叉配置路径需合法输入后实际验证，未执行部分不作成功声明。

独立审查F3后进一步修复：**不再读取或信任`DARWIN_PROBE_RESULT`**，在真实SDK/工具
初检通过后，使用本次Clang/linker/LLVM/SDK、当前probe代码，直接运行唯一label的
fresh probes；只有新生成v2输出/import/LLVM合同全部通过才复制Mesa和配置。
CC/CXX必须解析到同一已验证Clang binary，避免probe与实际编译器错配。
`anv-reviewed-gate-001`即使指定旧/伪success JSON也不会读取，仍因缺SDK/工具exit2。
这是缺合法输入时的负向gate证据，不是完整正向Darwin构建验证。
原TU命令由syntax-only改为实际`-c -o`，移除错误禁用真SDK头搜索；未来输出需查Mach-O，
当前依然未运行该阶段。最终模块/ANV状态不变：BLOCKED。
