# Intel 原生命令生成的最小离线验证

固定输入是 Mesa26.2.3 / `31e9a6b2e95e30d84bf3177d1f497d063e59b6b2` 的 `src/intel/genxml/gen120.xml`、原样 `gen_pack_header.py` 及其同树 imports。实际执行：

```sh
python3 -B tools/native_packet_probe.py
```

证据 `logs/native-pack-020/receipt.json`、`build/native-packet-probe/receipt.json`：生成器、C 编译、CPU pack 运行全部 exit0。Mesa 生成的 `GFX12_MI_NOOP_pack` / `GFX12_MI_BATCH_BUFFER_END_pack` 产生两个 DWORD `[0x00000000,0x05000000]`，总8字节；C 程序以独立固定期望核验格式。产物明确标 `NOT_FOR_HARDWARE_CPU_PACK_ONLY`，不带 GPU 地址，没有执行/提交入口。

这验证的是 **Gen12 原生命令打包的极小子集**，不是 ANV 完整 command buffer、draw、compute dispatch、合法初始化序列、shader binding、资源重定位或同步完成证明。完整 ANV 在实际设备合同下生成 workload 的链路仍需用户态/内核实现；不能把空命令流当作加速成功。

复用了 Mesa 原生成器而非从旧 Apple Gen11 stream 翻译字段；它与 `intel/GEN12-COMPILER-REPORT.md` 的 shader 编译里程碑独立。两者都通过也不等于二者组成可提交的工作负载。复现请在私有副本使用新 build/log 输出路径，原执行工件不可覆盖。
