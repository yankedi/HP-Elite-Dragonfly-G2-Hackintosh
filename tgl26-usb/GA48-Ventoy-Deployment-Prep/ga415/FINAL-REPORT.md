# GA415 交付与剩余定位报告

**当前未完成花屏根因定位，也没有通过花屏修复验收。**

状态：`PARTIAL / SILENT_GPU_PIXEL_ERROR_CAPTURED / ROOT_CAUSE_UNVERIFIED`。
下一内核证据需用户手动启动已交付BLITOBS镜像并批准新单例；尚未执行。

## 本轮新增的实际进展

- 保留并重新审核A/B/C真实捕获；两套独立Expected审核对错误数一致。
- 把真实测试图dump、manifest、执行日志导出到 `captures/`，CPU fixtures和原生构建日志一并交付。
- 取得同一个设置窗口的一次(-240,0)移动；前后各有全屏和独立窗口图、窗口元数据。
- 完成ROI、通道/alpha/熵、重复行列/块、Dock/黑矩形候选与窗口坐标注册分析。
- 核验精确donor的pitch字段、入口selector与最终2D/3D helper区别。
- 实现并构建有界Blit只观测hook；原生签名、CPU ASan/UBSan、产物反汇编、镜像/USB回读已通过。
- 已交付 `HP-Tahoe-TGL-GA415-BLITOBS.img`，保留NOAUX/NOCCS3/PLANES2。
- 本次继续期间新GPU测试提交数为0；没有消耗新的A/B/C授权。

## 九项证据答复

以下按当前保留的验收范围归纳九项答复。原始九问的逐字文本未在当前保留记录中恢复，
因此**原文逐项映射尚未验收**，不以这份报告声称原GA415完整交付通过。

### 1. 是否实际开发并构建了可运行捕获工具？

是。五个指定工具见README，两个Objective-C程序在目标HP上由Apple clang21以
`-Wall -Wextra -Werror`原生编译并签名。源码/二进制与真实build.stdout hash匹配。
CPU比较器24项、捕获verifier13项adversarial检查通过。
CPU-only IOSurface八次实际采集通过；不是GPU PASS的替代证据。

### 2. 是否捕获到“命令完成但像素错误”？

是。A/B/C各只有一次真实explicit Command Buffer，均status4、无API error；
B/C却为 `PIXEL_FAIL`。每张图由独立Expected验证有效RGBA像素，排除BPR padding，
并由第二套auditor重复离线审核。实际exit0只说明捕获程序完成。

| 用例 | 几何 | IOSurface实际BPR | direct Copy错像素 | shader/GPU dump错像素 | target getBytes错像素 |
|---|---|---:|---:|---:|---:|
| A | 640×100 | 2560 | 0 | 0 | 0 |
| B | 642×32 | 2576 | 20544 | 0 | 0 |
| C | 642×100 | 2576 | 64200 | 64200 | 64200 |

### 3. 最早错误在哪个可观察环节？

B：IOSurface texture→共享buffer的direct Copy proxy未覆盖0xEE，但随后同一texture的shader读取正确。
这是明确API路径分歧，不是已证实整个源texture都坏。

C：CPU输入与锁定的IOSurface前后字节正确，首次proxy已全零；其后GPU/CPU目标也全零。
边界是正确CPU IOSurface→GPU device-cache/pageon/直接Copy proxy这一组合区间。
内部哪条copy/资源绑定/缓存操作首先失败尚未观测。

### 4. CPU/GPU一致性与NOAUX的结论是什么？

GA414 NOAUX已取得历史16705错→0错的FAIL→PASS，GPU/Expected、CPU/Expected、CPU/GPU均0错。
本轮保留这一已验证修复。
C中CPU/GPU互相一致但都不匹配Expected，证明相互一致不能替代独立真值。
`CPU_RESULT`字段表示CPU源/IOSurface正确性，不表示C的target getBytes正确。

### 5. 是否证明了tiling、stride、格式、alpha或旧帧问题？

未证明。独立affine测试用线性RGBA8Unorm、无sRGB、无blend、alpha255；
保留初始化字节和全零输出是实测，tile/stride则没有实际资源布局支撑。
legacy X/Y0变换只是离线候选；黑块/重复块也可能是正常UI。
没有已知前帧参考的桌面旧帧残留保持 `NOT_OBSERVED`。

### 6. 桌面花屏是否进入截图？是否跟随窗口/图层？

是，全屏和独立窗口PNG都含异常，纯物理扫描输出不能解释全部现象。
同ID19、同大小723×960的窗口移动(-240,0)后，Battery局部4900像素的R/G/A全同、
B统一+1，结构随窗口坐标保留；其他区域重绘改变。
全屏与独立窗口是顺序截图，不能把所有差异计成坏像素，也不能证明它们对应同一底层资源。
自编ScreenCaptureKit真正截图仍未验收，成功的是系统screencapture路径。

### 7. 是否已经确认XE-BLITFIX的触发条件及可直接修复？

没有。B/C的IOSurface BPR2576是实测；Metal内部pitch和submitBlit pitch不是它的别名。
实际kernel矩形、base对齐、最终2D/3D分支未被原A/B/C捕获。
C API有效图256800B超过上游0x20001阈值，B为82176B却也有另一种direct Copy失败。
这些支持定向调查，不证明共同根因或真TGL可直接使用上游RPL修复。
已有routeSel0日志不能判断最终helper。

### 8. PLANES2崩溃修复是否完成，是否解决花屏？

目标除零panic定向复测通过：精确25G83 KDK IOSurface的plane count是+0x98，
donor旧代码误读+0xb0。修复前实际复现同位置除零；启用后相同导航和Memoji面板打开成功，
同启动期观察308.619秒，没有新相关诊断/重启，桌面仍明显损坏。
结论是 `PLANES2_TARGETED_PANIC_RETEST_PASS`，不是长期稳定性或花屏修复PASS。

### 9. 现在交付什么、还缺什么、下一步是什么？

五工具、CPU fixtures、真实A/B/C dump/日志、四份指定报告以及本报告已形成。
另有可启动Blit观察镜像，hash：
`6aa9943242e6622bdf5f31877277c010d654f052fe5b70de825dbdb507358edc`。

已通过：Mach-O kext构建、目标Mac原生ad-hoc签名、802次CPU转发合同/ASan/UBSan、
无FP/SIMD的观察代码反汇编、100文件原生只读回读、FAT/ocvalidate和整盘hash。
未通过/未执行：观察版启动及hook安装、实际submitBlit pitch/最终分支、与桌面资源的配对，
Metal GPU Capture、长期稳定性、剩余花屏根因与修复、原始九问逐字映射。

用户手动启动观察版后先核验身份/健康/安装日志，再取得新的C一次现场授权。
只有实际观察命中候选分支，才进入单因素修复和独立Expected FAIL→PASS验证。

## 完整性和范围

- 四份报告：`reports/DESKTOP-ARTIFACTS.md`、`IOSURFACE-RESULT.json`、
  `CAPTURE-COMPARISON.json`、`ROOT-CAUSE-CANDIDATES.md`。
- 全部数据、脚本、日志hash索引：`reports/EVIDENCE-EXPORT.json`及最终交付审计。
- 本地完整桌面图和机器健康回执在`private/`，未将专有driver/SDK/KDK或凭据提交Git。
- 用户的`ga414/ISSUE-7-REPLY.md`等分享草稿保留；本轮没有代发评论或push。
- 新镜像相对PLANES2仅NG可执行文件和一个观察启动参数变化；安装系统栈及六个原镜像未改。
- 最后健康快照：同F9275286启动期、WindowServer PID197，相关诊断hash未变，无新GPU fault；
  新观察版未加载。该健康结果不认证像素正确。
