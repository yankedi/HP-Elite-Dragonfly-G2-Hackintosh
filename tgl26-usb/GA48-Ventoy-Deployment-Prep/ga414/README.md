# GA4.14 — Native HP Tiger Lake XE-NOAUX

从封存 R6 独立构建，只开放 **HP 8086:9A49 / subsystem 103C:8716 / CPU 0x8C / Tahoe 25G83** 的原版 XE-NOAUX。完整目标为确认相同 R8 Managed RT 用例的 CPU getBytes 能否从 16,705 错误像素变为 0。

**实机结果已取得：[FINAL-REPORT.md](FINAL-REPORT.md)。NOAUX 真实命中，唯一原 GA4.12 R8 三组比较均0错，CPU从16705错到0；用户仍报告桌面花屏，长期稳定性未验证。** 构建／交付报告保留当时的 `BOOT_NOT_TESTED` 时点状态。

## 实验边界

- `static const uint8_t f_noaux[] / r_noaux[]` 保持作者原字节；唯一补丁是 `75 0b → 90 90`，未重实现函数。
- NOAUX 独立放在 NOCCS3 邻近位置，单一 apply 点；非 native 保留上游条件，native 需精确身份／build 门槛。
- native 原 pattern 必须唯一，原／替换计数必须 `1/0 → 0/1`，原子 once 防止重复应用。失败不记成功。
- `-ngreenccs` 原禁用含义不变，镜像不携带此参数；不启用整套 xefix。
- 保留 R6 的 R2/R3/R5/R6、NOCCS3、XE-FMT 和整个系统端栈；不带 R7。
- **native NODEPTH 保持 R6 的未启用状态**，这是相对作者“keep NOCCS3/NODEPTH”建议的明确差异，避免第二个功能变量。

## 交付与证据

- [GA414-NOAUX-vs-R6.patch](patches/GA414-NOAUX-vs-R6.patch)：完整相对 R6 diff。
- [SOURCE-AND-DONOR.json](reports/SOURCE-AND-DONOR.json)：27 源码文件范围、实际 25G83 donor、唯一 pattern／函数、原 kernel build 符号。
- [GUARD-TESTS.json](reports/GUARD-TESTS.json)：22 项 CPU-only 身份／数量／实际构造函数测试。
- [BUILD.json](reports/BUILD.json)：真实 cross build、必要符号、UUID、功能段和无新增未解析依赖。
- [NATIVE-SIGNATURE.json](reports/NATIVE-SIGNATURE.json)：实际 macOS ad-hoc 严格签名验证。
- [IMAGE-LOCAL.json](reports/IMAGE-LOCAL.json)：R6 副本、仅 NG 文件变更、OC1.0.8、Enabled 依赖、FAT／MBR／文件回读。
- [DELIVERY.json](reports/DELIVERY.json)：实际 USB 同步、整镜像哈希和原生只读回读已完成。
- [BUILD-REPORT.md](BUILD-REPORT.md)：构建交付结论、限制与下一阶段。
- [FINAL-REPORT.md](FINAL-REPORT.md)：实际 NOAUX 命中、唯一 R8 PASS、用户仍花屏与截图限制。
- [REQUIREMENTS-AUDIT.md](REQUIREMENTS-AUDIT.md)、[FINAL-AUDIT.json](reports/FINAL-AUDIT.json)：完整需求到实物证据映射与最终离线审计。
- [BOOT-HANDOFF.md](BOOT-HANDOFF.md)：用户手动启动及运行验收边界。

源码构建目录、真实 signed kext、镜像和原始回执分别位于 `private/source/`、`private/native-signed/NootedGreen.kext/`、`private/HP-Tahoe-TGL-GA414-NOAUX.img`、`private/commands/`，忽略提交；diff 与证据摘要正常提交。

## 离线复核

```bash
python3 ga414/tools/audit-source-and-donor.py
python3 ga414/tools/audit-runtime.py
```

`build-kext.py`、`native-sign.py`、`make-image.py`、`deliver-image.py` 是本次独立产物的生成配方，采用新文件／目录与留存回执，不应当作可无限重跑脚本。它们不安装／加载驱动，不重启，也不执行 Metal 探针。

## 作者依据

已保存 [作者原回复](reports/UPSTREAM-ADVICE.json)，对应 Issue #7 / comment 6380149624。用户补充的新说明见 [AUTHOR-TEST-STEPS.md](AUTHOR-TEST-STEPS.md)，特别强调 `const` 数组、真实 NOAUX 启动日志及相同 R8 复测。
