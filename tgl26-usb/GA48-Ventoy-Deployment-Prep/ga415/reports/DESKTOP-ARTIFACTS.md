# GA415：真实桌面花屏、窗口配对和离线 ROI

状态：`ACTUAL_PAIRED_SCREENSHOTS_ANALYZED`；桌面根因仍为 `ROOT_CAUSE_UNVERIFIED`。

## 实际采集

2026-10-24 18:45:44–18:45:49 +0800，在 PLANES2 + NOAUX 启动期
`F9275286-DF0B-41A8-86E7-51A6D2C55FFD`，使用已获权限的图形 Terminal
运行系统 `screencapture`。自编 `desktop-capture` 此次只采集 CG 窗口/显示元数据。
这与此前 SSH 下截图权限不足、ScreenCaptureKit 路径未完成的记录分别保存。

| 项目 | 实测 |
|---|---|
| 主显示截图像素 / CG 坐标尺度 | 1920×1080 / 1 |
| 设置页 / window ID | About / 19 |
| 窗口大小 | 723×960，前后不变 |
| 窗口位置 | (999,71) → (759,71) |
| 单次移动 | (-240,0) 像素 |
| 全屏 | `screencapture -x`，前后各一张 |
| 独立窗口 | `screencapture -x -o -l 19`，前后各一张 |
| 执行回执 | `LAYER_PAIR_COMPLETE`，stderr 为空 |

原始四图和元数据位于 `ga415/private/desktop-layer-pair-v3/pair-v3/`。
归档 SHA256：`c8c00dfc74ff3bec02bfc84a09290443875a08eacf4158a757015fa1f87e7f57`。
每张 PNG 的文件 hash、解码 RGBA hash、ICC hash 及 ROI 数据见
[`CAPTURE-COMPARISON.json`](CAPTURE-COMPARISON.json)。完整截图含机器名称和序列号，
保留在本地；公开交付包括不含这些信息的局部实图。

首次脚本假定页名为 Users & Groups，因实际已是 About 而在移动前终止。
随后脚本绑定实际页名、窗口 ID 和大小，成功完成一次移动。这不是一次失败后自动循环重试。

## 从实图能确认什么

1. 全屏 PNG 有侧栏文字缺损、Terminal 的大斜切/条纹区域等异常。
2. 独立窗口 PNG 也含缺失的 Battery 标签和显示设置按钮附近的切片异常。
   因而**仅显示链路、线缆或面板扫描输出故障不能解释所有已保存异常**。
3. 全屏和独立窗口的内容不相同：例如全屏图能看到 Battery 字样，而独立窗口对应 ROI 缺失。
   两者为顺序截图，并非同一时刻的不同观察面，不能据此断言某一个截图 API 产生了错误。
4. 同一 window ID 的像素结构至少在一个 ROI 随窗口坐标保留；其他区域在重绘后发生变化。
   尚不能将所有损坏解释为“同一块坏纹理精确跟随窗口”。

### 窗口注册后的 ROI

窗口局部坐标均为左上原点，未缩放：

| ROI | (x,y,w,h) | 窗口截图前后精确不同像素 | RGB 最大通道差 >8 的像素 |
|---|---|---:|---:|
| 侧栏 | (15,65,190,840) | 142831 | 6982 |
| 内容区 | (240,60,460,840) | 374202 | 5078 |
| Battery 标签 | (62,260,140,35) | 4900 | 0 |
| 显示设置按钮 | (550,650,145,30) | 4329 | 1421 |

Battery 标签 ROI 的 **4900 个像素全部仅 B 通道统一 +1**，R/G/A 完全相同。
这是该 ROI 像素结构随窗口移动保留的证据；精确差分的“100%不同”不能解释为“100%错误”。
其余区域的差异也可能混有颜色取整、半透明背景、重绘和截图处理。
所有差分都是描述性统计，没有独立正确桌面图，因此不输出桌面 `BAD_PIXELS` 真值。

![Battery，独立窗口移动前](desktop-roi/before-battery-label-window.png)
![Battery，独立窗口移动后](desktop-roi/after-battery-label-window.png)

同位置的全屏路径局部图：

![Battery，全屏移动前](desktop-roi/before-battery-label-full.png)

### Dock 与整图候选

在同一张真实 before.png 上离线分析 Dock 屏幕 ROI `(100,990,1720,90)`，
以及全图的通道、alpha、熵、重复行列、边界和 8/16/32/64 像素重复块。
数据在 `CAPTURE-COMPARISON.json.dock_and_full_screenshot_analysis`。
本张全图检测出的黑矩形候选包括 `(1722,864,198,109)` 和 `(360,87,640,4)`；
它们不是自动认证的坏块，也不能据此推导真实纹理 tile/stride。
此前桌面截图的 Dock 黑块统计另存于 `private/desktop-original-analysis/analysis.json`，
不把不同时间/配置的黑块合并为同一个资源错误。

## 验收限制与下一步

- 截图中存在异常不等于定位到应用绘制、图层存储、合成或截图 readback 中的某一步。
- 局部 alpha/黑块/重复块只作为候选；无前一帧参考时旧帧残留为 `NOT_OBSERVED`。
- 物理屏幕照片与截图的同帧配对、WindowServer 图层资源 dump、Metal GPU Capture 尚缺。
- 采集后与交付后均保持同一启动期、WindowServer PID 197，相关诊断未增加或变化，
  没有新 GPU hang/reset；见 `CONTINUATION-FINAL-HEALTH.json`。
- 下一步是手动启动已交付 Blit 观察版，检查实际 pitch/最终调用；不能从桌面斜纹直接启用路由修复。
