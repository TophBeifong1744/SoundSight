# H1 最小数据接口候选

版本：`ss-data-draft-0.3`；日期：2026-09-08；状态：待 A/B 一次共同确认，可先用于包内开发。

这是 document/minimal-data-interface.md 中 0.2 起草版的补全候选，不覆盖活动文档。升级原因：明确 JSON 类型、uint64/PCM 边界、错误与跳号关联、重启及未知坐标处理。0.2 数据不得仅改标签假装 0.3；转换器须校验新增字段。CSV 头与四路顺序不变。

## 1. 文件与范围

每段目录包含 metadata.json 和 samples.csv。UTF-8；写入不带 BOM，读取允许 BOM；CSV 逗号分隔、LF/CRLF 均接受，结尾换行不算空数据行。禁止注释、空数据行及重复表头。CSV 整数为十进制整数字面量，不接受浮点、科学计数法或首尾空白。

每行是一组相同原始采样时刻的四通道值，固定头为：

`sample_id,mic0,mic1,mic2,mic3,stream_error,error_flags`

这只是离线交换格式。int32 是解析后的数值存储类型，不表示 CSV 占四字节；不定义 DMA 字宽、端序、寄存器或引脚。底层 packed 仍为 {mic3,mic2,mic1,mic0}，mic0 在低位，导出器显式转换。

## 2. metadata.json 必填字段

| 字段 | 类型与约定 |
|---|---|
| schema_version | 字符串，必须是 ss-data-draft-0.3；未知版本拒绝 |
| acquisition_id | 非空字符串，唯一标识一次启动采集；重启必须换值 |
| config_version | 非空字符串，绑定本段完整配置，不由读取器猜测参数 |
| channel_order | 本候选固定字符串数组 [mic0,mic1,mic2,mic3]；重复/换列拒绝 |
| coordinates_m | 4×3 有限数值数组，与列序一致；完全未知时可为 null，但须在 provisional_fields 说明，禁止方向求解 |
| geometry_version | 非空字符串；未知坐标也用明确版本标识，不从通道数反推 |
| coordinate_system | 字符串 x-forward_y-left_z-up，右手系 |
| direction_convention | 字符串 array-to-source，指向声源而非传播方向 |
| angle_unit | 字符串 deg；后续方位 atan2(y,x)，俯仰 atan2(z,sqrt(x²+y²))；极点方位无效。本文件不定义算法输出结构 |
| sample_rate_hz | 有限正数；候选 48000，不自动当作硬件实测值 |
| sample_format | 对象，固定见下文；与未知 schema 一样，不支持的格式须拒绝 |
| source_kind | synthetic-code / synthetic-acoustic / hardware-test-pattern / hardware-audio |
| evidence_level | synthetic / diagnostic / accepted；本样例只能 synthetic |
| capture_point | 非空字符串，实际抓取位置；无法确定写 unknown 并在暂定项说明，不伪造链路位置 |
| provisional_fields | 对象，键为暂定/未知字段路径，值为非空原因；没有暂定项时为 {} |
| calibration_status | not-calibrated / partial / calibrated；不能由文件可解析推定标定完成 |

sample_format 必须为：

`{"encoding":"signed-pcm","storage_dtype":"int32","valid_bits":24,"alignment":"right","fractional_bits":0}`

PCM 范围 [-8388608,8388607]，负数写十进制负值；不得把 0xFFFFFF 当正数 16777215。转 int32 时符号扩展，不额外缩放。24 bit 仅是交换码值范围，不是 IM73D122V01/PDM 实际有效精度或最终 RTL 位宽。

候选 geometry_version=square40-provisional-0.1：mic0=(-0.02,-0.02,0)，mic1=(0.02,-0.02,0)，mic2=(0.02,0.02,0)，mic3=(-0.02,0.02,0)，单位 m；全部是软件名义坐标，不是实物测量。变更映射/几何/格式/采样率必须新 config_version，并更新受影响 geometry_version 和暂定项。同一版本出现不同内容须报冲突；新版本参数完整且受支持时可以读取，不要求为每个 config_version 写硬编码白名单。

新增无关描述字段可以保留，不得覆盖标准字段语义。JSON 重复键应拒绝，布尔值不能当数字字段。calibrated 须额外提供 calibration_record 非空可追溯引用；accepted 须额外提供 acceptance_record 并经人工核对，解析器不得自行签署。synthetic-* 对应 synthetic；hardware-* 首批用 diagnostic，除非有正式 accepted 记录。码型永不冒充真实录音。

## 3. 编号、间断与错误

- sample_id 范围 0..18446744073709551615；读取时直接转精确整数/uint64，不经 float64。允许首行非零，表示一次采集中的截取；本文件之外的先前数据不作推断。
- 同一段严格递增，允许跳号，不允许重复、倒退或 uint64 回绕。若 current > previous+1，保留原编号，并在 current 行标 stream_error=1、error_flags 含 drop；缺失区间为 previous+1..current-1。
- stream_error=0 时 error_flags 必须为空；为 1 时必须非空。error_flags 用分号分隔，不带空格、无重复；本版支持 drop、overflow、relock、unknown。
- 未知错误码：保存原输入并报不支持，不能静默当正常。A 无法辨明原因时写 unknown。未观测到精确缺失编号仍可标 overflow/drop，不凭错误标记虚构丢样数量。
- 错误标记表示本行样本或到达本行之前已发现的问题；不能把硬件 sticky 标记当作逐次错误计数。连续干净区间遇到跳号或任何错误行即切断；先保留错误行供诊断，不直接送方向计算。之后恢复连续且 error=0 的区间可另行分析。
- 重启/计数复位使用新的 acquisition_id 和新目录；配置变化也另存目录，同一次采集未重启时可以保持 acquisition_id 和原始 sample_id。任何片段都不自动拼接、补零或重新编号。

## 4. A/B 各交什么

A：按此格式导出元数据与码值，保留真实编号、错误和抓取点；硬件未知项如实标注。B：实现读取器、格式诊断、连续区间识别和测试；坐标未知时只做幅值/格式诊断，暂定坐标下方向必须注明假设，不得宣称已验精度。

B 最小测试预期见 data/fixtures/h1/reader-test-plan.json。固定码型只验证接口，不是四麦声学模拟，亦不证明 TDOA 轴向符号正确；轴向声学 golden 属于 B 后续算法包。六麦数据继续用其独立模型配置，不在本候选里强行当四路读取。

## 5. H1 完成定义

A/B 对本候选的格式、编号/错误语义、暂定值标识共同确认，并记录准确版本/清单哈希，即完成 H1 约定；不要求先做完读取器、板测、H2 或 M0。读取器测试是后续联试证据，不增加过程审批点。未确认仍可依据本候选并行开发；正式覆盖总工程由 B 复核授权后执行。
