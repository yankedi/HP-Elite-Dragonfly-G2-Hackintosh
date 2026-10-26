# CALLGRAPH：TrackB 有界调用图

## 证据规则

来源 SHA `fbab2d48bf1470fb0ec15dd62a6bb90c39d8bb45ed68240d3c73f1e43e770dee`；SystemKC 内 ICL UUID `REDACTED-MACHINE-ID`，Framebuffer UUID `REDACTED-MACHINE-ID`，IOAccelerator UUID `B77A42EC-6B0C-3A8D-89A2-B8F4CDBAC8C9`。全部坐标为 KC 未滑动坐标。`analysis/focused-fragments.json` 是本轮 24 个有界函数的机器可读证据；caller 计数若截断会显式标记。静态 call/vtable target 不表示 live receiver。

## 主链

```text
IntelAccelerator::start
  ├─ [this+0x1468] = allocated lock/context
  └─ [this+0x11c0] = 0; later config may set flags
        └─ populateAccelConfig
             ├─ bit11 = config bit << 0xb
             └─ bit12/15 path: clear mask, OR 0x9000

SafeForceWake(bool,mask)
  ├─ mask==0 || flags.bit12 → ret
  ├─ flags.bit11==0 → [[this+df8]+8](bool,mask) tail-jump
  └─ flags.bit11==1 → lock [this+1468]
       ├─ refcount transition absent → unlock/return
       └─ SafeForceWakeMultithreaded → ACK loops / panic → unlock only on normal path

IntelAccelerator::setPowerState
  ├─ [this+df8]+0x30(3,0/1)
  ├─ lock_busy / unlock_busy
  └─ other vtable PM calls

systemWillSleep / IOGraphicsAccelerator2 PM paths
  └─ scheduler/display/interrupt vtable calls; no common +1468 proof

IOAccelFIFOChannel2::restart
  ├─ vptr+0x208 → static ICL diagnosis candidate
  ├─ reportGPURestart
  └─ vptr+0x200 → static ICL resetHardwareAndReplay candidate
       └─ resetGraphicsEngine / doSchedulerReset / processGPUReset
            ├─ beginReset
            ├─ old 941c reset loop + 4094 clear
            └─ endReset / SafeForceWake(false,7)
```

## 24 个有界函数

|函数|entry–end|B|raw SHA 前缀|关键关系|
|---|---|---:|---|---|
|SafeForceWake(bool,unsigned)|`13ec39f6–13ec3c72`|636|`70310acad78445a1`|flags/forward/local lock/refcount/release|
|SafeForceWakeMultithreaded|`13ec7d7a–13ec8198`|1054|`ec3de670b2d19fee`|request writes, ACK loops, IOPause/panic|
|SafeForceWakeInterrupt|`13ec8198–13ec81e2`|74|`f4cad0fe1c0b1e54`|forward or direct shift=2|
|populateAccelConfig|`13ec23bc–13ec3102`|3398|`e2fb4ac2934537bb`|flags bit11/bit12 assignments|
|start|`13ebf09e–13ebfb38`|2714|`4d698c82641c100d`|initialize +1468/+11c0|
|stop|`13f211b6–13f2157c`|966|`726be59d8179d3f4`|clear df8/1468 after async calls|
|free|`13ebee74–13ebee98`|36|`431726549b508f0e`|destructor tail only|
|setPowerState|`13ec5524–13ec56bc`|408|`cb1a235739e60b30`|forwarding PM calls + busy lock|
|IntelAccelerator::systemWillSleep|`13ec36de–13ec3742`|100|`10b6afbf74a7fb2e`|telemetry/scheduler/interrupt sleep|
|initLocalCallbackSupport|`13ec537a–13ec5420`|166|`29bca3d4352fefe7`|write df8 and handler table|
|cleanLocalCallbackSupport|`13ec21a6–13ec21d0`|42|`f0347ea2bc78fcd5`|free/clear df8|
|PowerWell::init|`140274ba–14027508`|78|`a72d8c31479a12ee`|controller and PG state|
|PowerWell::enablePowerWellPG|`14028cbe–14028d3e`|128|`32aa2805840e966a0`|PG counters/state|
|PowerWell::disablePowerWellPG|`1402861e–140286dc`|190|`87a923aafd3c2aef`|PG counters/state|
|IOGraphicsAccelerator2::systemWillSleep|`145c2e06–145c2f96`|400|`344ad0cc79aaca1f`|sleep traversal/vtable calls|
|IOGraphicsAccelerator2::system_will_sleep|`145c3098–145c32f4`|604|`6344a1da9d32a76e`|PM state and progress timer|
|IOAccelEventMachine2::hardwareErrorEvent|`145943e6–145946ba`|724|`d9c36065eeb7503a`|IOLock/busy/restart caller|
|resetGraphicsEngine|`13edcaa6–13edcd92`|748|`35be8e2cc173c304`|reset bypass/4094 clear|
|doSchedulerReset|`13edca80–13edcaa6`|38|`0c4f124c36135b7c`|vptr+190 tail jump|
|doHangAnalysis|`13edcdd2–13edcece`|252|`f0df2af3904b29b2`|late mask7 wake; callers debug/diagnosis|
|beginReset|`13f13832–13f1390c`|218|`d8631abb6c818ab4`|context reset state|
|endReset|`13f1390c–13f13916`|10|`0be6f3d7b2dfea06`|tail jump cleanup|
|processGPUReset|`13ed3c92–13ed3e38`|422|`7c8d14b2194256c4`|begin/ring/end reset chain|
|IOAccelFIFOChannel2::restart|`145869fe–14586d50`|850|`08a9dae1c2c7555e`|diagnosis/report/reset ordering|

完整 raw SHA、bytes、callers 和 basic-block 信息以 JSON 为准，不以本表前缀代替。

## 静态 caller / vtable 事实

- SafeForceWake 有 96 个 direct call/jmp edge；JSON 保留前 30 并标 `caller_count_total=96`，其余不丢失结论但不展开。SafeForceWakeMultithreaded 有 wrapper call `13ec3c06` 和 interrupt tail `13ec81dc`。
- SafeForceWakeInterrupt 的 direct callers 包括 `processContextStatusBuffer@13ed4b5f/4c74/4c80` 与 `IGInterruptBridge::{enable,disable}` 的若干 callsites；这说明它是不同上下文入口，不能套普通 lock。
- `doHangAnalysis` callers：`debugGraphicsEngine@13edcd9b`、`getHardwareDiagnosisReport@13ee5e64`。
- `beginReset` callers：`IGGuC::processGPUReset@13eb7f2e`、`IGHardwareCommandStreamer5::processGPUReset@13ed3d21`；`endReset` 对应 `13eb7ffe`、`13ed3dde`。
- 已验证 format-11 static candidates：`__ZTV20IGHardwareRingBuffer+0x168 → resetGraphicsEngine`；`__ZTV12IGScheduler5+0x190 → processGPUReset`；`__ZTV18IGAccelFIFOChannel+0x200/+0x208 → resetHardwareAndReplay/getHardwareDiagnosisReport`。IOAccelFamily2 对应 slot 可为 pure virtual；所有 live receiver 仍 unresolved。

## 锁/等待/异常

|站点|静态调用|安全含义|
|---|---|---|
|SafeForceWake|`0xc222` lock、`0xc228` unlock|只覆盖 local wrapper 正常路径；early/forward/interrupt 不同。|
|SafeForceWakeMultithreaded|`0xcac2` IOPause；cold `0xc342` panic|ACK loop 有等待/异常；不返回 bool。|
|setPowerState / IOAccel PM|`lock_busy/unlock_busy` 与 vptr lock calls|不能与 +1468 spinlock 自动合并。|
|resetGraphicsEngine|`0xc318 assert_wait_timeout`、`0xc366 thread_block`、`0xc02a IOSleep`|reset 可阻塞；禁止在未知上下文新增 MMIO/等待。|
|hardwareErrorEvent|IOLock lock/unlock、trylock、`lock_busy/unlock_busy`|只证明局部静态调用点，未建立全局锁序。|

结论：调用图已向生命周期/PM/reset 前后推进，但没有实际硬件安全点；保持 BLOCKED。
