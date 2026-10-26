# GA418最终范围审计：所有驱动修复目标未达成

2026-10-26；目标`155bd26c-396b-4bcf-bf59-1452c4a9c84e`。**结果是有具体阻塞的未达成，不是“全部修好”或“所有方案已找到”。** 已交付全范围来源/候选审计；没有把完成研究文档等同完成硬件修复。

## 对照原目标逐项验收

| 原验收要求 | 实际证据 | 结果 |
|---|---|---|
| 所有已识别硬件均找到修复；未知不能计完成 | [REPAIR-MATRIX.json](reports/REPAIR-MATRIX.json)覆盖21个功能组；[PLATFORM-AUDIT](reports/PLATFORM-AUDIT.json)严格覆盖实际22个PCI功能，另含USB/I2C/PS2/ISH/EC功能。仍有未找到实现及未取得的实际资源/故障轨迹 | **未满足** |
| 区分上游声称、实际源码/二进制、HP实测；版本、依赖、最小改动、验证及回退明确 | [README](README.md)和[IO-OTHER](IO-OTHER.md)、固定来源回执、STATIC/PLATFORM报告、私有NHI/背光反汇编；候选与无候选项目逐项明示 | 研究交付满足；候选功能未冒充实测 |
| NixOS/防睡眠、全部图形基线和现用EFI/KC/NVRAM保持 | `private/linux-final-awake.json`：**09:00:16Z**同boot8b2033f0，PID5459 active/running/Transientyes及实际sleep:idle:handle-lid-switch block；本轮目标访问为有界只读采集，分析/下载写开发机 | 观测时满足；不是未来连续运行保证 |
| 来源/报告/检查持久保存并审计剩余未知 | 21功能组矩阵、22PCI覆盖、当前配置/续接/追加历史；[FINAL-CHECKS.json](reports/FINAL-CHECKS.json)记实际所需检查、报告/来源hash和二进制片段核验 | 交付检查单独记录；不能补足首行缺口 |

## 实质进展

1. **新I2C/GPIO已取得真实产物。** 官方合入后CI40157687159/artifact12584862177 SHA`71a8ad60…`与GitHubdigest相同，Debug/Release实际GPIO含TigerLakeLP defined symbols和INT34C5 personality；旧正式release同名2.9.1不能代替。GPIO175/267与本机descriptor用途核对完成。
2. **背光有两层明确门控。** GA416 realTGL早退使ngreenblmax不生效；Backlight注册被注释。现用Mach-O完整init直接AGDP引用1/Backlight0，支持源码发现；全程序部分解码/间接引用边界保留。HP历史频率不一致日志真实存在，仍缺实际PWM合同。
3. **USB不再混算控制器。** CPU9a13是1HS+4SS，PCHa0ed是12HS+4SS；PCH16个软件报告端口需按真实接线选≤15。只有内部三口的快照不能生成完整map。
4. **集成雷电有精确二进制缺口。** 25G83原生NHI两匹配均不涵盖9a1b；Type4 createNHI还按device-id选择仅8a0d/8a0f/8a17的NHIType4分支。十函数片段、真实字段来源和metaclass符号已保存；不是仅改plist可宣布支持。
5. **音频候选更具体。** AppleALC已有a0c8控制器补丁，layout71三条模拟路径与HP17→3/21→2/8→23→19重叠；Linux普通G2功放实际函数是延时100ms后coef65=0。TahoeHDA恢复、布局多余路径和真实功放仍需审验，内置SOFDMIC不是模拟layout修复。
6. **其他设备身份与传输分清。** 指纹在Linuxlibfprint支持表，但未找到macOS授权实现；十传感器走PCIISHTP，不是I2C。SMCBatteryManager的BIX支持与HP16bitEC形成候选；MicronNVMe直连且VMD另枚举，NVMeFix仅是独立功耗候选。

## 不能继续当作纯查源解决的阻塞

### A. 目标系统与物理输入缺失

当前保留NixOS，用户控制物理启动和部署。没有新候选在HP macOS上的GPIO事件、蓝牙配对、相机PROBE/COMMIT/首帧、AppleBacklight attach/PWM或音频初始化轨迹。**保持当前boot与取得另一个macOSboot的实际驱动行为不能同时实现。** 缺少这些输入时，不能判断应采用哪种条件补丁或证实它已覆盖本机失败。

完整USB map必须逐口USB2/USB3、Type-C双朝向实际插拔；雷电隧道/热插拔需真实下游设备；笔/JIS/Fn需物理动作；准确ICC需测色仪和固定SureView/亮度状态。这些不在当前无人值守现场可自行提供的输入中。本轮没有用推测表补齐它们。

### B. 完整实现仍未找到

集成TGL NHI/USB4、SOFDMIC、a0fcISHTP及其功能桥接、Synaptics指纹macOS授权、完整Intel高级Continuity功能没有本轮可核验的完整实现。这里只声明**未找到**，不推断永远不可能开发。继续开发完整transport/HAL/系统桥接是新工程工作，不能把外部教程、Linux驱动或增加device-id称为已找到macOS修复。

### C. 历史故障仍独立未知

RTC单次无报错不足以证实长期有效；MetalPOSH离线包未启用；内核Panic缺失败当时managed/PV/PTE/对象与分配历史。既有`ga417/MEMORY-NEXT-DIAGNOSTIC.md`保持有效，本轮不重跑已完成MmapDump，也不将新无线/存储候选当Panic根因。

## 检查与证据口径

- `tools/check-delivery.py`只读核验本地原件/来源/工件，并在开发机重现四个审计、执行配套仓库要求的检查。**不调用采集器，不连接目标，不构建/启用新EFI。** 实际exit/stdout、检查失败（若有）及文件hash保存为独立检查回执。
- 来源当前81个成功回执、8个失败回执；404中的误路径已通过真实子模块路径/XML原件补齐，USBToolBox HEAD限流通过GitHubMCP固定commit后raw来源补齐；评论403仍保留。失败抓取不是设备不支持的依据。
- 源码、反汇编和descriptor解析均为限定范围证据。特别是背光全程序5个部分符号片段未被默认为完整CFG；NHI十个函数片段也不是整驱动完整CFG或HP运行证明。
- 全部候选下载在开发机私有目录；source/result IMG均null。现有图形策略、独立正常镜像和现用系统未因研究而替换。

## 解除阻塞的下一步

由用户选择以后一个物理macOS窗口，先取得短小、针对实际失败的观测，然后按矩阵顺序逐个独立候选试验，保留原组合回退。完整USB/雷电/键笔/ICC观测由对应设备/仪器提供；缺实现的项目继续保留未修复状态。现有`ga417-awake.service`保持，只有用户要求解除时才停止。

本次目标的完成条件未满足；最终目标状态应为**unmet（具体阻塞）**，不能complete。研究和候选工件保留，便于具备上述输入后继续。
