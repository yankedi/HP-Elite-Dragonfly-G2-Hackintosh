# GA415：根因候选和可证伪边界

总体状态：**`ROOT_CAUSE_UNVERIFIED`**。已捕获真实静默像素错误，未证明桌面花屏与某一内核指令之间的因果链。

## 已排定的最早可观察边界

独立 Python Expected 和第二套不导入主比较器的 auditor 一致：

| 用例 | CPU 输入/IOSurface 前后 | source→buffer 直接 Copy proxy | shader/render→buffer | target CPU getBytes |
|---|---:|---:|---:|---:|
| A：640×100，BPR2560 | 0错 | 0错 | 0错 | 0错 |
| B：642×32，BPR2576 | 0错 | 20544错，保留0xEE | 0错 | 0错 |
| C：642×100，BPR2576 | 0错 | 64200错，全零 | 64200错，全零 | 64200错，全零 |

三例均为一次 explicit Command Buffer，status=4，无 API error。
`IOSURFACE-RESULT.json` 包含原始资源、执行顺序、时间线、逐阶段比较与 dump hash。
原始 A/B/C 在 GA414 NOAUX、PLANES2 禁用的启动期执行；新桌面配对在 PLANES2 启用后取得。
二者不构成同启动期桌面/探针资源配对。

**B 的边界是 API 路径分歧**：同一 IOSurface-backed texture 的直接 Copy 输出未覆盖初始化字节，
后续 shader 读取却正确。不能把 B 称为“已经证明 IOSurface 上传全错”。

**C 的最早错误 dump 是 source texture 的 Copy proxy**：正确 CPU IOSurface 字节到该 proxy 之间，
包括 device-cache/pageon 及额外的 texture→buffer copy。没有 raw tiled backing dump，
还不能将错误进一步压缩到单一内部 copy、纹理采样指令或渲染阶段。

## 候选排序

| 候选 | 支持证据 | 当前缺口 / 反证 | 下一条判别证据 |
|---|---|---|---|
| 直接 Copy 路径没有写入目的 buffer | B 所有有效字节保留已知0xEE，而 shader/CPU输出正确 | 不能区分 kernel未生成命令、cache/资源绑定、GPU执行或可见性 | 实际 source/destination pitch、最终 helper、同几何和时间段 |
| IOSurface↔device-cache 的 pitch/路由问题 | C 输入正确而最早proxy全零；非64对齐BPR与大图相关 | B也非64对齐且更小，呈不同失败；kernel pitch未知 | 观察实际 submitBlit 字段和COPY2D/FAST2D/COPY3D调用 |
| 上游 XE-BLITFIX 所描述的大图3D路径 | C有效像素256800B，超过0x20001；现象与上游部分相似 | IOSurface BPR不等于kernel pitch；矩形、base、分支未观测；上游目标非本机真TGL | 只观测镜像先取得实际分支，若命中再单因素移植 |
| tiling/stride/格式解释或descriptor ABI | 桌面有切片/斜切；RGBA试验具有几何相关性 | 全零/保留sentinel不提供地址变换特征；没有实测tile布局 | 非零结构化错误、resource layout和指令字段；不能以重复块猜tile |
| managed CPU readback coherence | 历史NOAUX针对旧CPU错误有FAIL→PASS | GA414后B shader/CPU一致；C CPU/GPU同错，单独CPU readback故障不足以解释 | 保留NOAUX已验证状态；检查独立冻结GPU dump |
| Core Animation/WindowServer层或截图路径 | 全屏、独立窗口均有异常且彼此不同；局部ROI随窗口移动 | 顺序采集、无正确桌面Expected，无图层资源ID | 真实资源/图层配对、后续有界capture；不是直接认定应用或合成器责任 |
| 单纯物理扫描输出 | 用户可见屏幕损坏 | 保存到内存/PNG的独立窗口图也已损坏，不能解释全部 | 不作为本轮首选解释 |

候选不是互斥的；B、C和桌面可能存在不止一条错误路径。

## 精确 donor 静态核验

Apple TGL 16.0.32 donor SHA256：
`14e21de55f2923c3c46a33731ab2f7a71e1baf472f88d1fd8c702e821c171393`。
UUID `BA3AA1C0-FE6B-33B3-9D85-73F848394E3D`。不是声称25G83 stock自带TGL驱动。

| 符号 / 字段 | 精确 donor 依据 |
|---|---|
| `IntelAccelerator::submitBlit` | VA0x2bc8e |
| source/destination pitch | params+0x08 / +0x50，2D命令生成中实际读取 |
| source/destination tiling 原字节 | +0x0c / +0x54 |
| GPU base低32位与额外offset | source +0x00/+0x2c；destination +0x48/+0x74；仅低6位用于对齐统计 |
| bytes per element / 入口selector | +0xa0 / +0xa2的bits3:4 |
| rect vector | count+0x00，data+0x10，stride0x20；只记录首项8个float原始bit |
| 普通2D / fast2D / 3D helper | VA0x30430 / 0x30970 / 0x325b6 |
| 2D source copy、fast copy实际callsite | submitBlit VA0x2c0b0 / 0x2c098 |
| 大小判定 | VA0x2c228起，0x20001；16B元素另有0x51001 |

`routeSel=0` 只是入口参数；donor仍会根据supported检查、force3D、对齐和大小选择最终helper。
既有 `XeNG BLIT ... routeSel=0` 不能验收最终2D/3D路径。

上游参考：[`df7ab78`](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/commit/df7ab78f79d08a8a792292982b46d2bcf110f052)、
[#6](https://github.com/JulioNectar/Hackintosh-XPS13Plus-IrisXe-Tahoe/issues/6)。
其 XE-BLITFIX 对不满足64B pitch条件的copy选择普通2D，描述的大图零输出值得验证。
本机当前GA414源码的BLITALIGN等位于非真TGL分支；本轮没有全开RPL xefix，也没有照搬路由修复。

## 与已修复问题的关系

- **NOAUX已验证**：GA414前CPU错误16705，后为0；不降级为未验证猜测。
- **PLANES2已验证目标panic复测**：25G83 IOSurface plane count偏移+0x98与donor旧+0xb0不兼容；
  修复前相同除零panic复现，启用后Memoji面板成功打开并完成308.619秒观察。
- **PLANES2后桌面仍花屏**。该结论排除了“仅修正这一处plane count读取即可消除现有全部花屏”，
  不代表其他IOSurface ABI均已正确。具体触发除零的IOSurface对象未转储。

## 已实现的下一步

`kernel/ga415_blit_observer.hpp` + opt-in `-ngreen415obs`：

- 只在精确HP/真TGL/25G83/NOAUX身份门槛与三个donor字节唯一匹配后安装。
- 记录入口和实际最终helper；记录pitch、tiling原字节、低位对齐、force3D/AUX、首矩形bit。
- 总共最多128条数据记录，加1条安装记录。三个饱和预算分别16/16/96，CAS最多8次。
- 每个helper保存原参数、记录后tail-jump原函数一次；不改参数、返回值、路径或资源内容。
- 新观察函数无FP/SIMD指令，无新增未解析依赖；原生ASan/UBSan CPU shim802次调用通过。
- 源码、构建、签名、镜像与USB100文件回读已独立离线审核，**内核运行尚未验证**。

局限：日志会扰动时序；tag为截断的params指针标记，可复用、非IOSurface ID；
预算可能被其他同几何copy消耗，缺日志不等于没有命令。需时间段/几何/资源证据交叉确认，
不得单凭tag或pitch谓词宣称已命中XE-BLITFIX。

后续手动启动与单例授权见 [`../BLIT-OBSERVER.md`](../BLIT-OBSERVER.md)。
