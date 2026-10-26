# Tahoe 25G83 签名与加载路径研究

状态：`DEPLOYMENT_BLOCKED`（未证明符合当前约束的合法路径）。
本轮没有修改 SIP、SSV、AMFI、Secure Boot，也没有加载/安装任何组件。

## 1. 已知事实

- 目标为 macOS 26.6.2 / 25G83；目标 CLT 存在，但未发现
  `/Applications/Xcode.app`。
- donor AppleIntelTGLGraphics 16.0.32 具有 `LC_CODE_SIGNATURE`（Apple 签名）；
  GA4.5 生成的 dylib **没有** `LC_CODE_SIGNATURE`，未签名。
- `AppleIntelTGLGraphics.kext` 是 Apple 私有 kext，不是本项目源码构建的
  第三方 kext；修改后的二进制不能保留 Apple 原始签名。
- 参考项目使用 `amfi_get_out_of_my_way=1`；本任务明确禁止。
- 目标系统卷受 SSV/SIP 保护；`/Library/Extensions` 和 kernel collection
  的加载还受 AMFI、kext consent、签名/公证和 Apple 私有 entitlement 约束。

## 2. 不能据此宣称的路径

1. **Developer ID 签名自己的 NootedGreen** 可能满足普通第三方 kext 的
   Developer ID 要求，但本机没有可用签名身份/证书，也没有证明它能修改或
   注入 Apple 私有 GPU 驱动。
2. **ad-hoc `codesign -s -`** 不能保留 Apple 签名，也不能证明 AMFI/
   WindowServer/MTLCompilerService 接受；没有在目标验证。
3. **替换 `/System/Library/Extensions` 或 `/Library/GPUBundles`** 会改动
   系统/受保护位置，明确禁止。
4. **`amfi_get_out_of_my_way=1`** 是参考实现的绕过，明确禁止。
5. **Apple 私有 MTL driver 的 `LC_LOAD_DYLIB` 注入**：即使 dylib 有合法
   Developer ID，也不能假定 library validation/Team ID/entitlement 会接受
   旧 driver；没有目标运行时证据。

## 3. 结论

- 当前没有证据证明“不修改 SIP/SSV/AMFI/Secure Boot”即可让修改后的
  Apple 私有 GPU 驱动被 WindowServer/MTLCompilerService 接受。
- 因此本阶段的部署/加载状态是 **`DEPLOYMENT_BLOCKED`**，不是“待测试”。
- 合法路径需要用户提供开发者签名身份/Apple 允许的加载方案，或明确改变
  安全策略的单独授权；本轮没有该授权，也没有执行。
- 这不影响离线 dylib/对象构建；只阻止实机安装/加载。

## 4. 下一步需要的外部输入

1. 合法 Developer ID/公证身份与对应密钥（若走第三方 kext 路径）；
2. 或者 Apple 书面/系统机制允许的 GPU bundle 加载方案；
3. 目标 25G83 的运行时 ABI 探针授权；
4. 一次明确的受控实机实验授权。

在以上任一项缺失时，保持 `DEPLOYMENT_BLOCKED`，不进入安装/加载。
