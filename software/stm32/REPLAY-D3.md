# D3：三维六对特征离线回放

直接编译调用现有 `doa_solver_3d.c` 与 D2 几何校验器。Python负责严格输入解析、序列检查和报告；没有第二份 Python 逆解算法。本批不改固件、冻结接口、FPGA或动作门禁。

这是**特征级回放**：从已解包的六对 lag/峰值/邻点开始，不读取 PCM、不重新运行 FFT/PHAT，也不模拟 SPI、快照消费、实时运行时限或运动。真实三维流仍待 A 的 Profile 对齐；当前没有四面体实物或真实特征记录。

## 直接运行

在仓库根目录运行。依赖 Python 标准库及 GCC；工具通过项目现有 SS_GCC / tools.local.env / PATH 查找，不安装新软件。

```text
python software/stm32/tools/generate_replay_demo.py --out software/stm32/build/replay-d3/my-demo.jsonl
python software/stm32/tools/replay_3d.py --geometry software/stm32/config/tetra40-nominal.json --input software/stm32/build/replay-d3/my-demo.jsonl --out software/stm32/build/replay-d3/my-result
python software/stm32/tests/test_replay_3d.py
```

输入示例也可直接引用[本次实际运行输入](../../document/evidence/stm32-replay-d3-20261018/example/input.jsonl)。输出路径必须全新；重复运行选新路径，工具不会覆盖旧结果。

|输出|内容|
|---|---|
|frames.csv|每条输入一行，保留帧号、几何版本/来源、序列分类、API状态、算法原因、方向有效性、浮点角/Q8码、向量/残差/条件数、参考方向和误差|
|pairs.csv|每帧六行，保留原始七字段及 delta_q12/tau_q12/margin_q15、资格和每对拒绝原因|
|summary.json|处理完成状态、所有记录的分类统计、有效参考样本数量、均值/RMS/最大误差、几何预检与声明来源|
|input.jsonl / geometry.json|本次输入原字节副本，供重放；来源声明不由工具认证|
|build-run.log|本次实际编译/运行命令、stderr和退出码；临时工作程序随后自动清理|

退出0表示报告处理完成，不表示所有方向有效或整机通过；算法/帧序拒绝保留在报告中。结构错误、配置错配、编译/运行失败退出2，不生成完成报告。写报告中断时可能留下不完整目录，只有最后写出的 `summary.json` 含 `run_status=COMPLETED` 才是完成输出。程序错误日志会回传 stderr。

## JSONL 输入合同（主机工具格式，不是新跨板 ABI）

一行一个 JSON 对象；第一行元数据，其后1～4096帧。一份文件仅一个 session、一份固定几何。总文件≤16MiB，每行≤16384字符。不接受空行、未知/遗漏字段、重复JSON键、布尔数字、非有限数或缺失pair。

第一行包含且只包含：

- `schema` 固定 `SS_3D_FEATURE_REPLAY_V1`。
- `session_id`、`source_id`：1～63字符，由字母、数字、点、下划线、冒号、连字符组成，引用采集或合成记录。
- `source_kind`：`SYNTHETIC_FEATURES` 或 `RECORDED_FEATURES`，只描述用户提供的来源声明。
- `geometry_revision` / `geometry_source_id`：必须与输入D2几何JSON准确相同；不逐帧更换几何。ID不是内容认证，准确坐标副本随输出保存。
- `pair_order` 固定 `["01","02","03","12","13","23"]`。

每帧包含且只包含 `frame_id`、`flags`、`pairs`、`reference`：

- 帧号和帧flags为uint32。flags应来自S2的 `doa_frame_input_t.flags`，不是整个未解包快照寄存器。
- pairs恰有六个对象，每个恰含 `lag, peak, r_minus, r_plus, second_peak, mask_count, flags`。前五字段以int32存储，mask_count为0～255，pair flags为uint32、对应已解包FEATURE_0标志。
- 程序仅先检查存储范围，S25/S6、mask≤79、保留位与阶段合法性仍交原C算法判断并逐帧报告。不可为了通过测试修改原错误字段。某对不可用应保留真实字段及其资格/阶段，不省略对象或伪造合格数据。
- `reference=null` 表示没有参考；否则仅含 `kind, source_id, azimuth_deg, elevation_deg`。方位[-180,180]、俯仰[-90,90]，采用D2的+X前/+Y左/+Z上坐标。合成输入的kind为SYNTHETIC；记录输入须为INDEPENDENT，来源ID应指向独立测量，不能把本算法输出/舵机命令当真值。程序只能检查声明，不能鉴定测量真实性。

目前工具没有串口日志自动导入功能。真实数据到达后，应从S2解包帧按上述字段导出并关联真实几何/来源，不将旧二维BIST换标签当三维记录。

## 序列与误差口径

1. 首帧任意uint32编号；后续使用模2³²差值，0为重复，差值≥2³¹为倒序或歧义，其余前进。正确回绕接受；跳号记录gap，不推定硬件丢帧数量。重复/倒序不调用求解器、不改上一前进ID。
2. 结构正确但被C算法/API拒绝的前进帧仍推进观察序列。设备重启/新会话应另建输入，不自动猜测重启。此规则不是S2设备消费历史替代物。
3. `disposition` 分为 VALID、ALGORITHM_REJECT、INPUT_REJECT、SEQUENCE_REJECT。API非OK时优先解释api_status，direction_reason可能仍是原求解器初始化的SOURCE，不能误作独立故障定位。
4. CSV角度来自C的浮点角，并另外保留Q8码；误差不从Q8整数角反算。三维夹角用拟合向量与参考单位向量的 `atan2(|u×v|,u·v)`，不受Q8量化影响。方位差取[-180,180)最短差，俯仰差有符号。
5. 极点方位无效或参考位于极点时，不计算方位误差。三维向量误差仍可计算。无效帧不输出方向，避免沿用历史值；无参考的有效帧不输出误差。空值不是0°。
6. 汇总误差只使用“有效且有参考”子集，均值/RMS/max同时给count；零样本用null。总记录数和各类拒绝数完整保留，不能只引用误差而隐去拒绝率。
7. pairs中的NOT_EVALUATED与API错误必须结合看：原算法未计算时保留初始化诊断值；序列拒绝则计算列留空。来源文本若以表格公式前缀开头，CSV加单引号使其不可执行，summary JSON保留原标识。

## 本次实际结果

|检查|结果|
|---|---|
|真实CLI与错误路径|776项断言，0失败；20个负例，包括编译器不可用、结构/参考/几何异常|
|合成回放|68条：57有效、6算法拒绝、3输入拒绝、2序列拒绝；逐对408行|
|42个理想方向（上下半空间/两极点）|最大三维夹角误差0.00090219°；只是理想特征的数值精度|
|12个每对±0.05样点扰动方向|最大三维夹角误差0.50621227°；扰动是人为时差噪声，不是录音SNR|
|全部有效参考子集|56条，三维平均0.06826959°、RMS0.15864027°；方位可比较54条|
|原求解器两配置回归|二维适配2110项／三维2378项，均0失败|

六个算法拒绝分别为PAIRS、NORM、RESIDUAL、CANCELLED、SOURCE、LEGACY_BIST。一个有效帧无参考，另一个重复的同帧也无参考，所以68条中参考记录为66条；参考存在不意味着进入误差统计。

记录：[REPORT.md](../../document/evidence/stm32-replay-d3-20261018/REPORT.md)。本批只有PC软件运行，没有新增固件链接/下载、板端耗时、真实声学或两板实测；D1的Keil Lite限额和D5对齐事项继续保留。下一项D4为纯软件双轴映射，完成本批后暂停。
