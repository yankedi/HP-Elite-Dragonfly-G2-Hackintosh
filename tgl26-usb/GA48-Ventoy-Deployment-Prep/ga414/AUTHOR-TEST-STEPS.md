# 作者最新测试说明（用户转述）

用户在本轮实现期间提供下列作者新回复。这里保留原文并将其作为当前 GA4.14 的实施约束；此转述没有另行推定 GitHub comment ID。

> Concrete steps for the test, since your tree differs from ours:
>
> 1. In `src/NootedGreen/kern_gen11.cpp`, the NOAUX patch is the `patchNoAux` block (search for `XeNG NOAUX`). In this repo it sits inside the `if (!NGreen::callback->isRealTGL)` branch next to NOCCS3, so a native-TGL build skips it. Move that block (and its `f_noaux` / `r_noaux` arrays) so it also runs on your native branch, **wherever you apply NOCCS3**. Keep the arrays `const`: a writable `uint8_t[]` silently picks the wrong `LookupPatchPlus` constructor and the patch fails.
> 2. Rebuild, put the kext on your EFI, reboot. The boot log should show `XeNG NOAUX: fillSurfaceStateAuxInfo sempre AUX_NONE: aplicado` (`log show --last boot --predicate 'eventMessage CONTAINS "NOAUX"'`).
> 3. Rerun the same R8 → RGBA8 Managed capture and your verifier.
>
> Expected: CPU `getBytes` now matches the GPU copy and the expected image (0 bad pixels). Please post the verifier table, and whether the desktop artifacts and the PIPE_CONTROL +0x7e4 hangs change over a normal session.

## 本轮落实

1. const 原数组、原补丁字节与单一 `patchNoAux` apply 点移出 RPL-only 分支，放在现有 NOCCS3 之后。
2. native 开放范围严格小于“全部 native TGL”：仅当前 HP CPU／实际 PCI／subsystem／确切 `25G83`；`_osversion` 无法解析时 fail-closed。没有增加 ABI hook。
3. 新镜像只替换 NootedGreen 二进制；保留原成功日志，并新增 native 前后 pattern 计数和失败日志，用于分清静态构建与实际应用。
4. 新镜像交付后由用户手动从 Ventoy 选取；不写内部 EFI，不自动重启。
5. 只有实启后才确认 NOAUX_RUNTIME_CONFIRMED；再运行一次原 GA4.12 legacy R8 和 verifier，不能把作者预期写成实测。
6. native NODEPTH 保持 R6 未启用状态，单因素差异公开；不同时移植作者提到的其他补丁。
