# PLANES2 实机验收：目标除零 panic 未再复现，花屏仍存在

## 结论

**`PLANES2_TARGETED_PANIC_RETEST_PASS`**。
本次相同导航已从“触发同一内核除零 panic”变为“正常完成”，随后也能打开
Memoji 头像面板。修复版从导航启动起观察 **308.619 秒**，boot session、
WindowServer PID 和 MemojiPicker PID 均保持不变，没有新增或变化的 panic、
GPU restart、watchdog、WindowServer 诊断，dmesg 未匹配新的相关故障。

**这不是像素正确性通过：Memoji 缩略图和桌面仍有可见渲染错误。**
长期稳定性未验收。

## 修复前：本次新 panic 已确认

- 当前 R6 的单次导航在 **18:26:33.030288 +0800** 触发 panic。
- 新文件：`/Library/Logs/DiagnosticReports/Kernel-2020-01-01-080126.panic`。
- SHA256：`664d73bf931d8f40cb23431914675d666ce3870add03198b4d574614f4704bb6`。
- Incident：`REDACTED-SESSION-ID`。
- 进程：`AvatarPickerMemojiPicker`，PID 1510。
- RIP：`0xffffff7f96718bcd`，donor VA `0x72bcd`，`div r15d`，R15=0。
- 路径：`new_resource → newResourceWithIOSurface → deviceCacheForIOSurface →
  calculateIOSurfaceDeviceCacheVRAMBytes`。
- 文件在触发前 73 份诊断基线中不存在；panic uptime 与实际失联时间一致。
- NVRAM 7-bit 独立解码、重新打包核验通过；与诊断内容仅差末尾两个换行。

因此本次卡死已经不再只是“网络失联”或“现场感觉无响应”，而是有新 panic
和独立 NVRAM 证据支持的同一内核除零复现。

## 修复后身份

| 项目 | 实测 |
| --- | --- |
| 系统 | Tahoe 26.6.2 / 25G83 |
| Boot session | `REDACTED-SESSION-ID` |
| NG UUID | `4C4C44E9-5555-3144-A1E4-CB51FF5A72E6` |
| Apple TGL UUID | `BA3AA1C0-FE6B-33B3-9D85-73F848394E3D` |
| PLANES2 | `IOSurface+0x98: aplicado` |
| NOAUX | `postflight original=0 patched=1 verified=1 expected=0/1` |
| NOCCS3 | `retorno imediato: aplicado` |
| 启动参数 | 有 `-ngreentgltahoe`，无 `-ngreennoplanesfix`、planesxor、xefix、ccs |

修复后对已安装 Apple TGL、MTLDriver、libxedrv 的哈希检查均与已保存版本一致：

```text
AppleIntelTGLGraphics  14e21de55f2923c3c46a33731ab2f7a71e1baf472f88d1fd8c702e821c171393
MTLDriver             e3242693959408c9cef14140df81ce98ff1e04d5dd83aa9aeaddb463271ac65d
libxedrv              b274aa7293acc9ba4c00acaefa564b4c9367ed29042659371ce42b62dd651259
```

启动初期 load average 较高，执行前再次检查了健康状态：负载正在下降、无交换、
内存空闲比例 86%、无相应 GPU/panic 日志，WindowServer 可响应。

## 有界复现过程

1. 经图形 Terminal 执行**完全相同 SHA256** 的 `avatar-ui-inspect.command`，
   单次导航至 Users & Groups；输出 `INSPECTION_COMPLETE`，stderr 为空。
   MemojiPicker PID 893 已启动并存活。
2. 基于截图的一次坐标点击只命中父 group，没有打开面板；该步骤不作为头像
   面板通过证据，也未进行循环点击。
3. 读取实际 AX 树后，对 `user` 用户行的头像按钮执行一次 AX click。按钮属性
   为 position `1252,134`、size `32,32`、enabled `true`。截图确认头像面板已打开，
   Memoji 页及缩略图网格可见。PosePicker PID 1053、MemojiEditor PID 1054 已启动。
4. 最终只读检查截至 **18:38:06 +0800**：同一 boot session，WindowServer PID 197、
   MemojiPicker PID 893 保持不变；相关诊断仍为同一 74 份，哈希全部不变。

没有循环复现、自动重启、保存新头像或改动系统驱动。

## 为什么会卡死，以及与花屏的关系

### 已确定的直接机制

故障发生在内核驱动，不是只在头像应用内部。CPU 执行整数除法时除数为零，
触发 divide error，随后进入 kernel panic；整机停止正常服务，所以桌面不动、
SSH 和 ping 都失效。这与 GPU 命令执行超时的 hang 不是同一种直接机制。

### 已核实的兼容性错误

25G83 实际 IOSurface 的 `getPlaneCount()` 从对象 `+0x98` 取值，旧 TGL 驱动
却从 `+0xb0` 读取，并据此决定 plane 数量和分支。读错布局可能令后续代码
按错误的平面结构解释资源，并进入含未保护除法的路径。

PLANES2 将这一次读取改到正确的 `+0x98`。它没有简单跳过除法，也没有把所有
资源强制为非平面。CPU 实测 BGRA 的 plane count 为 0 本身合法，420v/420f
为 2；**不能把“除数为零”与“合法的非平面资源 plane count 为 0”混为一谈**。

具体导致旧版除数为零的 IOSurface 对象没有转储，不能补写其格式、尺寸、
实际 `+0xb0` 值或元数据来源。ABI 错配和这次目标路径修复得到强支持；
完整的故障对象数据流尚未直接观测。

### 与花屏的已知关系

两者处于同一图形资源栈，涉及 IOSurface/纹理资源，但不是因此就能认定
同一个 bug。当前修复版能打开 Memoji 面板而仍有花屏，已经证明修复这一处
布局读取并不足以解决现存像素错误。

- 此次 panic：资源建立/显存大小计算阶段的内核异常。
- 原 B/C 证据：输入与 IOSurface CPU 数据正确，命令完成后 Copy/采样输出
  却与 Expected 不同；其准确 kernel 路由仍未观测。
- 当前截图：文字缺损、黑块和 Memoji 缩略图渲染异常仍可见；无独立 Expected，
  不自动量化为某个已定位的 pitch/tile/CCS 根因。

结论应为：**本次目标 panic 路径实测改善，剩余花屏根因仍未确认**。

## 比较范围

本轮紧邻对比为 R6 → GA414+PLANES2，并非同一 NG 二进制的严格即时 A/B。
但更早的 GA414/NOAUX 也有完全相同的 `0x72bcd` 除零 panic；独立镜像审计
证明新镜像相对那份 GA414 只有移除 `-ngreennoplanesfix` 这一配置变化。
这些证据支持定向修复有效，但不取代长时间稳定性或更多合法资源格式验收。

## 证据入口

- `PLANES2-PRETEST.json`：新 panic、NVRAM 独立核验和修复版启动身份。
- `PLANES2-RUNTIME-RESULT.json`：完整记录的离线审核结果。
- `tools/audit-planes2-runtime.py`：核对真实回执、相同脚本 hash、诊断不变、
  进程 PID、观察时间及截图 hash，不重新执行 GUI/GPU 操作。
- `private/commands/planes2-*postboot*`、`planes2-*retest*`、`planes2-avatar-*`：
  原始 SSH 回执。
- `private/planes2-postboot/`：原始新 panic、独立 NVRAM 解码及三张实测截图。
