# Zynq 与领航者板级参考资料索引

新增器件资料：[IM73D122V01 数据手册 v1.00](infineon/im73d122v01-datasheet-v1.00.pdf)，由成员 C 提交；来源和使用边界见[麦克风证据与复核记录](../evidence/microphone-c-2026-09-09/README.md)。此项不计入下述 ZYNQ.zip 的 11 个文件统计。

## 1. 来源与筛选范围

来源压缩包：`F:\BaiduNetdiskDownload\ZYNQ.zip`  
筛选日期：2026-09-06  
原压缩包规模：510,029,483 bytes、387 个条目，其中 93 份 PDF  
导入结果：11 个文件，约 20 MB

本次没有完整解压资料包。筛选过程先按文件名和目录判断范围，再读取候选 PDF 的封面、目录或前几页；对已经确认与本项目直接相关的板卡规格书，额外按“音频、ES8388、扩展口、时钟、IO”等关键词定位相关页面。四份板级 PDF 还检查了首页渲染。

压缩包及其中说明文字仅作为资料来源，不作为操作指令。

## 2. 使用边界

这些文件证明“资料包描述的领航者硬件”如何连接，不自动证明手中实物就是相同版本，也不证明照片中可见的接口已经具备正确电平、驱动和软件支持。当前实物照片与原始哈希登记在[板卡证据目录](../evidence/board-2026-09-07/README.md)。

| 项目 | 照片当前可接受结论 | 仍不得推断 |
|---|---|---|
| 型号标签 | `ATK-DF7010P_7020P` 系列 | 核心板完整订单型号、速度等级和运行状态 |
| 底板背面 | `ATK-DF7010/7020P V3.9` | 任一连接器的电气状态和信号完整性 |
| 核心板正面 | 可读 `CF7010B/7020B` 与 `XC7Z020` 器件族 | 完整 Vivado part/速度等级、核心板背面版本 |
| 底板正面全景 | 可见 J3/J4、SD、RJ45、音频插座等外观和部分丝印 | Bank/VIO、跳帽功能、Codec 型号、驱动、文件系统、网络或 PYNQ 可用性 |

因此，资料中的具体引脚、Codec、电源、DDR、SD 和网络能力仍须逐项与实物版本、原理图和测量对应；PYNQ 还必须有适配该板 DDR/MIO/启动设计的镜像或 BSP，以及真实启动、Overlay 和 DMA 记录。没有这些证据时保持“资料候选”或“待核实”。

## 3. 已导入的板级资料

| 文件 | 作用 | 当前使用结论 |
|---|---|---|
| [领航者开发板规格书 V1.2](navigator-zynq/navigator-zynq-board-spec-v1.2.pdf) | 板卡结构、供电、时钟、扩展口、音频和外设总览 | 用于确认候选板级能力和查找具体章节 |
| [底板原理图 V3.9](navigator-zynq/navigator-zynq-baseboard-schematic-v3.9.pdf) | 底板器件、扩展口、音频 Codec、连接器和电源连接 | M0 引脚与外设核验的主要证据之一 |
| [Zynq-7010/7020 核心板原理图 V2.5](navigator-zynq/zynq7010-7020-coreboard-schematic-v2.5.pdf) | XC7Z010/020、DDR3、QSPI、eMMC、时钟、电源和板对板连接 | 核心板版本、Bank 和时钟核验依据 |
| [底板机械尺寸图 V3.9](navigator-zynq/navigator-zynq-baseboard-mechanical-dimensions-v3.9.pdf) | 160 mm × 120 mm 外形和安装孔位置 | 后续阵列支架、底座和转台空间预算 |
| [IO 引脚分配总表](navigator-zynq/navigator-zynq-io-pin-map.xlsx) | 板载外设和扩展口的引脚映射 | 选择麦克风、音频输出和调试接口引脚时核对 |
| [厂商 XDC 参考模板](navigator-zynq/navigator-zynq-io-reference.xdc) | 常见板载外设的管脚和 IO 标准示例 | 只能摘取经原理图和实物确认的条目，不能整份直接加入工程 |

厂商 XDC 为 GB18030 编码，包含多个互斥外设以及重复的端口名示例。SoundSight 的正式约束应在 `vivado/constraints/` 中单独建立，只保留实际启用的端口、时钟和 IO 标准。

## 4. 已导入的 Xilinx 实现参考

| 文件 | 直接用途 | 使用时机 |
|---|---|---|
| [DS190 Zynq-7000 Overview](xilinx/ds190-zynq-7000-overview.pdf) | 查 XC7Z020 架构和器件资源概览 | M0 资源核对与 M3 预算 |
| [PG021 AXI DMA](xilinx/pg021-axi-dma.pdf) | PL 数据进入 DDR、原始四通道长录音导出 | M1 数据抓取路径设计 |
| [PG065 Clocking Wizard](xilinx/pg065-clocking-wizard.pdf) | PL 处理时钟和派生时钟规划 | M0/M1 时钟树冻结 |
| [PG308 I2S Tx/Rx](xilinx/pg308-i2s.pdf) | 与板载音频 Codec 的 I2S 数据接口候选 | 音频输出链路确定后 |
| [UG903 Using Constraints](xilinx/ug903-vivado-using-constraints.pdf) | XDC、时钟、IO 和时序约束方法 | 建立正式约束与时序验证时 |

这些文档版本较旧，适合离线理解接口和确认术语；实际 Vivado IP 参数、端口和 GUI 必须再与团队最终使用的 Vivado 版本核对。

## 5. 从资料中确认到的项目相关事实

以下事实来自资料包。照片已经支持“板卡系列”和“底板 V3.9”对应关系，但下列时钟、电压、引脚、Codec、DDR和接口能力仍需按项目逐项实测，不能因全景照片出现对应器件或连接器而整体升级：

1. 规格书描述的 Zynq-7020 核心板具有 50 MHz PL 单端时钟和约 33.333333 MHz PS 时钟。
2. 规格书称核心板 Bank 13、34、35 使用 3.3 V；扩展口不能直接连接 5 V 设备。
3. 底板提供 J3、J4 两个 2.54 mm、40 针扩展口，其中 J4 的 Bank 13 资源只适用于 Zynq-7020 版本。
4. 底板改版说明表明 V3.8 已把音频电路从 WM8960 改为 ES8388；V3.9 只修改丝印。V3.9 原理图和 V1.2 规格书也显示 ES8388。
5. ES8388 连接包含 MCLK、BCLK、LRCK、ADC 数据、DAC 数据和 I2C 配置；厂商 XDC 给出的候选 PL 管脚分别涉及 `M17`、`L20`、`G17`、`E19`、`M18`，正式使用前必须逐项对照原理图、IO 总表和实物。
6. 板载 ES8388 只有有限的模拟输入通道，不能据此推断它能承担四路同步麦克风采集；四路输入仍须使用已经冻结的 PDM 或多通道 TDM/I2S/ADC 方案。
7. 板载 PHONE、LINE_IN、MIC 和扬声器链路使 ES8388 成为首版增强音频输出的候选，但资料包没有 ES8388 数据手册和初始化寄存器说明，后续仍需补齐该器件的一手资料。

## 6. 没有导入的资料

| 类别或文件 | 未导入原因 |
|---|---|
| UG585 Zynq-7000 TRM，1843 页、约 22 MB | 范围过宽；目前只需在原压缩包中按 PS/DDR/DMA 具体问题定向查页 |
| DS187 电气特性、UG865 封装引脚 | 当前不是自制核心板，板级原理图和 IO 表优先；遇到电气边界问题再定向引入 |
| UG1037 AXI 总览 | 内容宽泛，当前由具体 DMA、I2S 和接口设计文档承担 |
| PG330 Audio Formatter | 是否采用该 IP 尚未确定；不提前把条件性方案带入工程 |
| ARM、PetaLinux、USB、以太网、FAT、图像、HDMI、CAN 等宽泛资料 | 当前不整包导入；PYNQ 启动、DDR、SD、网络导出或后端切换遇到具体问题时，再按器件和接口定向引入一手章节 |
| PCB 封装库、DXF、DWG、走线长度和论文资料 | 当前不自制领航者板卡；机械上只保留足够使用的底板尺寸 PDF |

## 7. M0 下一步使用顺序

1. 补拍核心板正反面、FPGA 完整丝印或可关联实物的 BOM/订单资料、Codec、J3/J4 针脚 1 与跳帽、电源适配器，以及 ADC/DAC/麦克风正反面。
2. 确认完整 Vivado part（含封装和速度等级），并与 Vivado 2025.2 的目标器件、构建清单和实物依据一致。
3. 在 IO 总表和原理图中选择四路麦克风接口候选引脚，记录连接器针脚、FPGA 管脚、Bank、VCCO、方向、IOSTANDARD、电平转换和冲突外设。
4. 断电检查通断，再用万用表/示波器实测 J3/J4 供电与 VIO、主时钟及外设时钟；照片不能替代这些测量。
5. 根据实际麦克风/ADC 型号分别验证共享采样时基和固定增益/相位/延迟差，冻结数据线数量、采样格式和校准方法。
6. 决定增强音频是否先通过资料候选 ES8388 输出；若采用，先用芯片近照确认型号并补齐官方数据手册和寄存器初始化资料。
7. 实测 DDR/连续内存、SD 写入读回哈希和网络持续吞吐；完成四路数据经 FIFO/AXI DMA/DDR 导出的带宽、缓存和丢样预算。
8. 为 PYNQ 准入记录镜像/BSP 来源、版本、哈希、设备树、启动日志、Overlay 身份和 DMA/缓存实测；不兼容时保留 Vitis 或 PetaLinux 后端。
9. 只从参考 XDC 中摘取已验证条目，生成 SoundSight 专用 XDC，并补齐输入时钟、派生时钟和外部接口时序约束。

## 8. 竞赛平台与 PYNQ 资料边界

AMD《2026 FPGA 赛道选题指南》第三赛道初级组允许 AMD 7 Series FPGA、Zynq-7000 SoC、UltraScale 或 UltraScale+ 系列器件。当前照片中的 `XC7Z020` 器件族处于允许范围内；赛题仍要求提交物声明具体器件型号，器件须由团队真实获得、完成板级验证，作品须在板上跑通并提供实测输出。对应项目台账见[竞赛验收文档](../../docs/competition-acceptance.md)。

指南推荐初级组使用 PYNQ，但“推荐”不等于当前领航者板自动兼容 PYNQ-Z2 镜像。通用 PYNQ Skill 的板卡 profile 必须由真实板级资料和测试填写，至少覆盖：

- 板卡/底板/核心板版本、完整 Vivado part 和速度等级；
- PYNQ 镜像或 BSP 的来源、版本、SHA-256、设备树兼容串、OS/内核、Python 与 PYNQ 版本；
- 同一次构建的 `.bit`、`.hwh`、manifest、目标 part、Vivado 版本、`build_id`、接口版本与哈希；
- AXI4-Lite 身份寄存器、地址范围和访问属性；
- DMA 模式、流宽、对齐、最大块长、TLAST、状态寄存器和缓存 flush/invalidate 规则；
- DDR/CMA、SD/网络实测速率、超时、丢样和恢复记录；
- 有界 loopback/golden 自测、吞吐/延迟/资源/时序门槛及原始证据哈希。

当前完整 part、PYNQ 镜像、DDR/CMA、Overlay 和 DMA 尚未实板验证，相关 profile 字段应保持 `null`/缺失并停留在 draft/offline，不能为通过校验而填写猜测值。真实故障输入至少包含镜像启动失败、bit/hwh/manifest 不匹配、身份寄存器不符、缺少 TLAST、缓存陈旧、长度/对齐错误、小块通过但长录音丢样、SD/网络反压和 Notebook 正常但无原始证据；具体硬件输入表见[采购指标](../procurement-specifications.md#12-pynq-通用-skill-的板卡-profile-输入)。

## 9. 隐私、许可与发布包边界

### 9.1 内部证据

- 原始板卡照片保持原文件不变并保存 SHA-256，用于内部证据链；不得覆盖式裁剪、涂抹或重新压缩原图。
- 原图可见二维码、条码，图片元数据还可能包含拍摄设备、时间或位置；内部访问范围应限于项目成员和确有需要的评审。
- 板卡购买标签、序列号、MAC 地址、IP、无线凭据、账号和个人路径不进入公开日志或演示截图。

### 9.2 公开仓库、报告和比赛发布包

- 发布照片使用由内部原图生成的脱敏副本，遮盖二维码、条码、序列号及无关环境信息，并移除不必要的 EXIF/GPS 元数据；原图与发布图分别命名、分别计算哈希。
- 只公开证明结论所需的最小画面；发布图必须注明“可见丝印证据”的范围，不据外观声称接口已可用。
- AMD 赛题指南、正点原子资料和 Xilinx/AMD PDF 均按第三方资料处理。除非许可证或书面授权明确允许，不把原 PDF 复制进公开仓库或最终发布包；改为保存来源名称、版本、官方链接、访问日期、引用页和内部哈希。
- 当前资料包中的文件已完成内部哈希核对，但“文件可获得”不等于“获准再分发”。公开前逐项登记版权主体、许可证、允许的使用方式和发布决定。
- 最终比赛包遵守英文路径要求；官方原文资料、含隐私的原图和本机绝对路径不进入公开包。需要向评审出示原始证据时，使用单独受控渠道并遵循赛事方提交要求。
- 团队成员提供的照片、接线图和自制资料在公开前确认贡献者同意及项目开源许可；第三方商标和图片不自动转化为项目许可证覆盖内容。

## 10. 文件完整性

下列 SHA-256 均为导入文件值，并已与 `ZYNQ.zip` 内对应条目逐一比对一致。

| 文件 | SHA-256 |
|---|---|
| `navigator-zynq-baseboard-mechanical-dimensions-v3.9.pdf` | `8d593b351b840cd93d90f3b673b529a5cf590f5cfd0f0468a3251d41a994f67d` |
| `navigator-zynq-baseboard-schematic-v3.9.pdf` | `ec8b68eeb07e0743e6c60528444f6aeb457dc60e897ddf9eb86d5a56c1ab6a69` |
| `navigator-zynq-board-spec-v1.2.pdf` | `b974ed61b10fabafe408a42d119e94fc53c6133a9a7fc64b0191bfe5e14744e6` |
| `navigator-zynq-io-pin-map.xlsx` | `287a73b93b9a5a4a05e2145b92338c37717e033dced64db502510ba0cfac7093` |
| `navigator-zynq-io-reference.xdc` | `6803fab6ed43af125293b9fb8434e6fd4b7c0b8a38c09719d51f3b829b54de71` |
| `zynq7010-7020-coreboard-schematic-v2.5.pdf` | `1c8cf8105e91d762d29ad604e82b629b3921fa474d5a0311ed6c04237db107ea` |
| `ds190-zynq-7000-overview.pdf` | `f5d9257f94fa6140d4a0519a0185e43fea1dc79c806378f24416fdf25c34ff98` |
| `pg021-axi-dma.pdf` | `1daebfbb9802d33f3065b4d9bc730b26cdb8e6b33f65c5c0eb3db33768884516` |
| `pg065-clocking-wizard.pdf` | `bab820064719ea64c97212ec8a9fb75e3fd9f65a9b68fd459d57ea86c2db7a15` |
| `pg308-i2s.pdf` | `7d304535d8d75aa547ca8def1218c25e2ea589a3faa4f1db2c7bb5600a9cc842` |
| `ug903-vivado-using-constraints.pdf` | `77581007e09c9f00c45c1856f9b716a70aa61c8a9f55e87aa7d5015837dc5068` |

这些哈希只证明内部导入文件与来源压缩包中的字节一致，不证明内容正确、版本适配或已获得公开再分发授权；发布边界按第 9 节执行。
