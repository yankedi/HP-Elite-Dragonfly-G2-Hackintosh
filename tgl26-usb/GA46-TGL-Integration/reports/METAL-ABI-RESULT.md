# Metal373.7 / libxedrv 与只读探针审查

## 实际修复

旧libxedrv有644行混合RPL实验逻辑，除descriptor转换外，还默认截取hash-map
释放但不释放对象、TLS256项循环缓冲（返回指针可在重入/持有后复用）、无析构
堆buffer、未同步lazy globals、进程signal日志（调用非async-signal-safe函数）、
默认stencil heap重分配，以及对Buffer Copy等私有路径的固定偏移读取。
这些不是25G83已验证的native-TGL适配，现已从本轮实际dylib移除，历史完整源码
保存在baseline提交。Apple原生compression/AUX/heap/context/提交不被替代。

新libxedrv是明确的**隔离构建**：不做未知descriptor转换；只在实际donor image
的initWithAcceleratorPort:方法（@返回、I参数、3参数编码）上返回nil，阻止暴露
未经验证的device。使用pthread_once，检查方法归属，继承方法用class_addMethod
覆盖，不原地修改framework父类。若类注册/初始化次序不符合条件，加载立即
失败即停，不用轮询或延迟重入去猜测。没有环境开关能绕过缺失的ABI证明。
这不是可用于WindowServer的兼容driver，不宣称Metal ready。

## 新的CPU观察逻辑

`metal/runtime-preflight.h`与metal-abi-probe共用：实际class/ivar encoding、
NSGetSizeAndAlignment、offset/size/alignment及溢出界限；先校验selector签名，
再在新建descriptor上验证实际class与inline _private地址一致，才读已界定范围。
通过公开property写入sample=4/vertex descriptor，读取对应候选字段进行对照。
异常只处理Objective-C解析/属性异常；没有SIGSEGV恢复。观测全部吻合也仅是
候选证据，不会把logicOp、附件bitfields、ownership和private ABI自动标为通过。

## 尚未确认

Metal373.7 class size不证明完整descriptor schema；LogicOp 27→32映射、
color-attachment启用位、enum编码、Vertex Descriptor ownership、pipeline
metadata和resource binding仍ABI_UNVERIFIED。修复后的纯C边界检查有负例；
Objective-C行为只能在授权目标CPU探针中验证，本机只交叉编译和检查导入。
Library Validation/LC_LOAD_DYLIB路径参见签名报告，不因能链接即判可加载。

## 两个探针的精确行为与待授权方案

本轮未在目标macOS执行任何新程序。离线构建产物在最终staging清单中。
以下为**下一阶段需要单独批准**的目标命令示例，不是已执行记录：

```sh
./metal-abi-probe
./compiler-runtime-probe
# 只有另行明确批准加载Apple系统image及其initializers后：
./compiler-runtime-probe --open-system-images
```

- metal：加载Apple Foundation/Metal，查询元数据，新建CPU descriptors并在其
  自有内存上设置/读取字段，释放；不创建MTLDevice、queue、library或GPU工作。
- compiler默认：仅精确两个system install names的RTLD_NOLOAD，dlsym和dladdr，
  输出NDJSON；不加载donor/plugin，不创建context/compiler，不编译shader。
- open模式：dlopen Apple GPUCompiler32023 libLLVM和MTLCompiler(Current)，
  可能执行系统image initializers，随后只查符号。它不是纯NOLOAD，因此与默认
  模式分列授权；不接受任意路径，不搜索bare libLLVM。

NOLOAD失败并不证明shared-cache install name不可dlopen；open成功也不证明
getSerializedModule私有签名或请求ABI。本阶段无任何运行授权被扩大。
