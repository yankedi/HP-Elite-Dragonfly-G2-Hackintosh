# GA32 ISA Lab

本机 GA3.2b 捕获的 **纯离线** EU ISA、Batch 与严格翻译子集研究。

主报告：[`reports/FINAL-REPORT.md`](reports/FINAL-REPORT.md)，逐一回答22问。
关键结果：ICL PS0 152B/11条、KP1 440B/29条、KP2 216B/15条、VS288B/24条完整解码；相同比特TGL不等义；严格原型31个独立单位往返，完整shader拒绝。另有stencil/draw命令长度与官方TGL规范不符，详见报告12。GPU Hang排他根因仍未证实。

## 目录

* `analysis/`：独立提取、四份ASM、逐条差分/CFG、命令/状态/原始ring、上游与严格子集结果。
* `tools/`：固定IGA构建、隔离Mesa adapter、提取/解码/审计驱动。
* `translator/`：离线解码—白名单—编码—目标验证—round-trip；无GPU路径。
* `tests/`：正/负/未知、官方与参考样本、25类覆盖及故障注入。
* `logs/`：实际构建/运行stdout、stderr和测试回执，含预期失败。
* `reference/`：固定参考源码、官方PRM、Linux fault寄存器定义与来源hash。
* `inputs/`：原ZIP的安全解包副本与12份历史gpuRestart私有副本；原始THAG仍在既有GA32目录。
* `manifest.json`、`manifest.sha256`：关键工件、完整私有交付文件清单和固定依赖；不纳入build缓存。

这些文件含私有GPU捕获/Shader及其派生字节，保留本地，迁移应私下连同输入和manifest传输。

## 复现

当前开发机已有 `python3`、Clang21、CMake、Ninja与git。固定IGA `c36a504a4e6c68030c3302646aa396b8b59b22cb`、Mesa23.3.6 `863338275d915e867319c3690ffd3272b06303c3`。报告02给出API和平台细节。

从本目录运行：

```bash
bash tools/iga/build.sh
bash tools/mesa-eu/build-adapter.sh
python3 tools/isa_analyze.py
python3 tools/rcs_evidence.py
python3 tools/batch_decode.py
python3 tools/pipeline_reconstruct.py
python3 tools/evaluate_upstream.py
python3 tools/verify_mesa_sources.py
python3 -m unittest discover -s tests -v
python3 tools/archive_lab.py
```

`archive_lab.py`默认**只校验**；复现会改变运行日志/测试manifest的时间或路径，需先保留原交付树，再在副本运行。重新封存副本用 `python3 tools/archive_lab.py --create`。manifest自hash也可用 `sha256sum -c manifest.sha256`。

输入独立重提取（输出必须是新目录）：

```bash
python3 tools/extract_capture.py \
  --capture ../GA32/capture/tgl-hang-GA32b-crash-20261018.bin \
  --zip ../GA32b-offline-analysis.zip \
  --outdir analysis-new-extraction
```

严格原型的真实PS/VS示例：

```bash
python3 translator/offline_translate.py analysis/ps-bounded.bin analysis-new-ps
python3 translator/offline_translate.py analysis/vs-bounded.bin analysis-new-vs
```

以上两条**预期exit1**：完整输入有不支持指令，report.json明确拒绝；独立成功单位以segment保存，绝不拼接为shader。每个segment源/目标长度、源offset和目标offset映射、SWSB drain、IR与往返结果均有报告。

## 额外构建矩阵

GCC构建使用独立Nix shell（只提供工具，不改系统配置）：

```bash
nix-shell -p gcc --run 'cmake -S tools/iga/source/visa/iga -B tools/iga/build-gcc -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ && cmake --build tools/iga/build-gcc -j4'
cmake -S tools/iga/source/visa/iga -B tools/iga/build-sanitize -G Ninja \
  -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_C_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer' \
  -DCMAKE_CXX_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer' \
  -DCMAKE_EXE_LINKER_FLAGS='-fsanitize=address,undefined'
cmake --build tools/iga/build-sanitize -j4
EXTRA_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer' OUT=build-sanitize bash tools/mesa-eu/build-adapter.sh
nix-shell -p gcc --run 'CC=gcc OUT=build-gcc EXTRA_FLAGS="-std=gnu11 -include unistd.h" bash tools/mesa-eu/build-adapter.sh'
python3 tools/native_matrix.py
bash tests/samples/run-smoke.sh
```

`native_matrix.py`对四入口及合成样本共64次调用做正样本成功/原Gen11在TGL拒绝/跨编译器stdout相同及sanitizer无诊断断言；20组跨build摘要相同。IGA对某些truncated/illegal输入exit0的实际行为保留，Pythonframing负责强制拒绝截断。完整unittest为79项，25类需求映射在报告10。

若迁移时未带Mesa源码，按报告02的公开URL克隆 `mesa-23.3.6` 至 `tools/mesa-eu/source`，校验完整commit，再启用稀疏路径 `src/intel/compiler src/intel/dev src/intel/genxml src/intel/common src/util include src/compiler src/mesa/main src/c11`。adapter副本与pristine源码分开保存。

## 解释结果

解码成功、validator通过、目标往返和单测绿灯都不是GPU执行正确的替代品。NF/acc、debug Switch、message/payload、完整SWSB仍是语义阻塞。当前 `READY_FOR_NEXT_HARDWARE_EXPERIMENT=NO`；所有实机后续均等待明确单独授权。
