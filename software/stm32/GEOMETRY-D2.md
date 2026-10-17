# D2：三维阵列几何配置

本模块提供坐标配置、通道对应和运行前校验。二维默认目标、冻结 SPI/S1 接口和数值求解公式不变。没有真实四面体测量；当前 JSON 为设计标称值，不能据此打开三维流或动作。

## 配置内容

入口：[tetra40-nominal.json](config/tetra40-nominal.json)。另存自己的配置再编辑，不把实测值追写成旧标称结果。

|字段|定义|
|---|---|
|schema / revision|格式版本固定 1；配置修订号为非零 uint32，由使用者维护，坐标或通道变化应增加修订号|
|provenance|NOMINAL 标称／MEASURED 声明实测／SYNTHETIC 合成；声明不等于已完成校准|
|source_id|1～63 个非空白可打印 ASCII 字符；引用测量记录或设计记录，非文件自动认证|
|microphones|正好 4 行，每行 channel 为不同的 0～3；xyz_mm 是该实物声孔中心的三坐标|
|坐标约定|毫米，+X 阵列前方、+Y 左方、+Z 上方，右手系。标称原点在质心；整体平移不改变方向|
|sample_rate_hz|现有配置固定 48000；其他采样率需要先与 FPGA 组对齐|
|sound_speed_m_s|300～380，默认 343；实际条件待测，不由程序自动标定|
|position_error_mm|每个声孔坐标的**径向误差上界**，不是标准差；-1 为未知。MEASURED 必须给正值|

40 mm 正四面体：底面通道 0/1/2，顶点通道 3。mic0 在 +X 方向；精确标称值在 JSON。任意实物通道排列用 channel 字段表达，程序将坐标排到线协议通道顺序，**不重排六对特征**。六对保持 01、02、03、12、13、23，lag = t_a − t_b。

## 生成与安装

在仓库根目录运行（GCC 通过 SS_GCC、tools.local.env 或 PATH 查找）：

```text
python software/stm32/tools/prepare_geometry.py --input software/stm32/config/tetra40-nominal.json --out software/stm32/build/my-geometry/ss_geometry_selected.h
```

严格拒绝未知/遗漏字段、重复 JSON 键、布尔数字、NaN/Inf、通道重复和不合格几何。程序编译并执行**固件同一份 C 校验器**；通过后才生成头文件，已有输出不覆盖，需选择新路径。生成头文件含常量 `ss_geometry_selected`，不含硬件操作。临时校验可执行文件自动清理。

在三维应用中可以选择以下一种接入方式：

1. 加入生成头所在目录的 include path，并定义 `SS_GEOMETRY_HEADER="ss_geometry_selected.h"`；`ss_app_init` 会安装并再次校验该配置。此路径已做 GCC 运行和 AC5 对象编译。默认未定义此宏，仍使用原 40 mm 标称配置。
2. 应用代码 include 生成头后，在 `ss_app_init` 成功且尚未启动或访问设备时调用：

```c
doa_geometry_report_t report;
ss_status_t status = ss_app_set_geometry(&app, &ss_geometry_selected, &report);
if (status != SS_OK) {
    /* 停止启动；报告错误，不继续拿旧配置当本次配置。 */
}
```

仅允许刚初始化的冷状态设置，配置接口不发 SPI。坏候选不会覆盖已安装记录、配置和报告；开始运行、STOP、discard、recover、ackstop 后锁定本会话配置，恢复到 IDLE 也不解锁。结构体成员为只读诊断，调用者不应直接修改，也不能通过重新 init 绕过锁定或清除帧历史。新几何用于新会话前，应在双方确认的流程中清空旧生产帧并完成通道/Profile 对齐。

`report` 用独立局部变量；仅在返回 SS_OK 或几何校验失败的 SS_ARGUMENT 时读取相应几何报告，SS_BUSY 不生成新报告。`app.geometry` 保留修订号与来源，`app.geometry_report` 保留已安装结果，后续 D3 可引用，当前不新增线协议字段。

## 校验范围

- 坐标有限且各分量在 ±1000 mm，四个通道完整且唯一。
- 六对非重合；计算全部六对的矩阵秩及无穷范数条件数，条件上限沿用 100。
- 六对中心搜索范围仍为 ±{6,8,6,6,8,6} 样点；标称最大时差为 `distance_mm * Fs / (1000*c)`。
- 已知每麦误差上界 e 时，再以 `(distance_mm + 2*e) * Fs / (1000*c)` 检查窗口。未知误差的 `bounded_delay_samples=-1`，不能看作零误差保证。
- 测量误差窗口检查不是误差范围内秩/角度精度保证，也不包括声速误差。整六对预检不能证明每种丢对子集可解；原求解器仍逐帧检查有效对数、秩、条件数、残差和范数。
- 不验证声孔实物位置、通道实际焊接、测量方法或声学精度，不授予运动许可。

## 本批实测（PC）

|输入|预期|PC结果|
|---|---|---|
|标称 40 mm|六边 40 mm；条件数 1|40.000000 mm；1.000000；最大时差 5.597668 样点|
|每麦误差上界 0.5 mm|窗口通过|5.737609 样点，通过|
|每麦误差上界 2 mm|至少一个 ±6 窗口不够|pair01 拒绝；理论上界约 6.157434 样点|
|原配置、通道0/3交换、整体平移、微扰坐标|+45°/+30° 和 -70°/-25°|8 组合成特征均在 0.04° 测试容差内；本次 Q8 输出恰与目标一致|
|共面、近共面、超窗、通道/来源非法等|拒绝|全部在对应配置错误处拒绝|

D2 829 项断言与 18 个导入场景通过；D1 8072 项及四个三维主机模型通过；二维 P3 3070/3283、S1 4705、S2 15980 和五自检模型通过。AC5 新几何模块/配置选择应用对象编译通过，二维 Template 完整构建 0 错误 0 警告，Code29326/RO1994/RW48/ZI10080。

三维完整链接仍受本机 MDK-ARM Lite 32 KiB 限额阻断。D1 的 33936 字节是旧候选大小；D2 没有重新完整链接，不把旧大小当 D2 大小。当前无已验证 D2 三维 HEX，板端耗时/栈也未测。

```text
python software/stm32/tests/run_geometry_tests.py --armcc <armcc.exe>
python software/stm32/tests/run_spatial_app_tests.py
python software/stm32/tests/run_app_tests.py
python software/stm32/tests/run_host_tests.py
UV4.exe -r software/stm32/keil/soundsight_f407/Projects/MDK-ARM/atk_f407.uvprojx -t Template -o <log>
```

[实际日志与首错](../../document/evidence/stm32-geometry-d2-20261018/REPORT.md)。下一步 D3 离线回放与误差诊断；完成 D2 后暂停。实物坐标、合法可用工具许可和 A 的三维 Profile 对齐分别保留待办。
