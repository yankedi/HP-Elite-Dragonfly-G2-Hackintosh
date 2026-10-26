# GA415 Blit 只观测镜像

**已制作并交付；尚未启动；不是花屏修复版。**

| 项目 | 值 |
|---|---|
| U盘文件 | `/Volumes/TARGET_VOLUME/ISO/linux/HP-Tahoe-TGL-GA415-BLITOBS.img` |
| 大小 | 1343225856 bytes |
| SHA256 | `6aa9943242e6622bdf5f31877277c010d654f052fe5b70de825dbdb507358edc` |
| NG UUID | `4C4C44A5-5555-3144-A1B8-E7727116893E` |
| 相对PLANES2镜像文件差异 | 仅NG可执行文件、config.plist |
| 启动参数变化 | 仅增加 `-ngreen415obs` |
| 保留修复 | NOAUX、NOCCS3、PLANES2 |

完整证据：`reports/BLIT-OBSERVER-{SOURCE,BUILD,SIGNED,CPU-TEST,IMAGE,DELIVERY,AUDIT}.json`。
签名为目标Mac原生ad-hoc，100文件原生只读回读与整盘hash一致，ocvalidate和FAT检查通过。
六个原有镜像及安装驱动/KC前后hash相同；没有执行自动重启或新GPU用例。

## 下一个实际步骤

1. 用户在场，手动从Ventoy选择这个BLITOBS镜像启动正常macOS。
2. 告知“已启动”，Agent先只读检查新boot session、NG UUID、启动参数、NOAUX/PLANES2/NOCCS3、
   WindowServer及GPU/诊断健康状态。
3. 必须看到 `GA415OBS install: gate=1 abi=1 hooks=1 enabled=1 ... route_changes=0`。
   若缺失或失败，保留记录并停止测试，不把镜像存在当作已安装hook。
4. 读取当前观察日志，确认针对探针几何的预算是否已被消耗。
5. 用户另行明确批准**C一次**后，在新启动期执行642×100/align16的现有探针一次，
   同时保存前后内核日志和实际pixel dumps。原A/B/C授权已经消耗，不重复使用。
6. 独立Expected和auditor检查有效像素；结合新观察判断实际pitch/最终helper。
   B是否需要新一次实验在C审计后决定，不预设自动序列。

失联、hang/reset或健康不通过时停止后续提交，保留证据；不自动重试或重启。
旧 `run-case-once.py` 绑定GA414旧启动期和已消耗claim，不能直接改claim文件绕过后复用。
新启动期的launcher应在身份核实、现场单例授权后按新证据建立。

## 实现与复核

`prepare-blit-observer.py` 从已封存GA414源码复制独立树，唯一修改kern_gen11.cpp并加入observer头。
`build-blit-observer.py` 沿用已审核交叉构建recipe，验证MH_KEXT_BUNDLE、依赖、Mach-O section和功能串。
`sign-blit-observer.py` 只对临时产物签名；不安装/加载kext。
`make-blit-observer-image.py`、`deliver-blit-observer-image.py` 和 `audit-blit-observer.py` 保存实际镜像与回读证据。

`test-blit-observer.cpp` 为CPU shim合同测试，原生Apple clang、ASan/UBSan通过：
802次转发参数不变、源数据不变、禁用/NULL观察输入不阻断原调用、128数据记录预算饱和。
产物反汇编另行核对三个wrapper各一次observer调用、恢复原参数、tail-jump原函数。
这些检查不替代新内核上的hook运行验收。

`parse-blit-observer.py LOG --output NEW.json` 可离线解码原始日志。
入口 `SUBMIT` 不视为最终路径；实际 `COPY2D`、`FAST2D`、`COPY3D` 才表示对应helper被调用。
同一lossy tag不是稳定资源ID；日志缺项可能是预算/采样，不认证命令未生成。
128条数据之外有1条安装记录；早期SOURCE报告的128指数据预算，总新增上限129。
