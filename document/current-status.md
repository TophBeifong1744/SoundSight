# 当前状态 — 2026-10-21

目标：四麦二维定位、连续测量、转台闭环。FPGA+STM32为主方案，PL+PS为独立实验目标。

## PYNQ现场进展与RAM队列修复

用户已在旧PYNQ 2.7镜像上确认双核Linux、ARM编译及数值对照通过（ARM结果原文件尚待回传）；完成overlay加载、FCLK0分频修正、ID/ABI读取、双BIST及真实采集。原双进程的20帧实采完成，19帧方向有效，音乐来自长条音响，用户观察方向相符；这不是声学精度标定。

100帧连续测试未通过：逐帧fsync阻塞槽位释放，出现0x48（溢出+STOP）且DROPS从1增至2；锁定37帧及排队38帧已由用户恢复。相关串口原文与分析补归档于[evidence/pynq-board-20261021](evidence/pynq-board-20261021/README.md)，完整板端JSONL及ARM-RESULT仍需从SD复制。此前这些最新串口证据主要留在聊天，没有全部进入仓库。

用户已同意断电可能丢失未落盘RAM记录。新无动作入口`software/ps/run_buffered.py`采用有界RAM队列、独立SD写入、高水位STOP及双槽排尾；旧动作/耐久确认入口不变。新版自测证据见[evidence/pynq-ram-queue-20261021](evidence/pynq-ram-queue-20261021/README.md)，更新及操作见[pynq-ram-queue.md](pynq-ram-queue.md)。新入口的ARM与实采复验尚未执行，旧100帧失败事实保留，不记为已修复验收通过。

## PS双核软件接合与首次上传包

已接合检查并合并B的PR #15（61e7303）与C的PR #16（0d38858）；main合入点为6482d52。组合实跑通过原S1 4705项、桥接/客户端9项、157组数值对照、6组非法桥输入、双进程17项与应用8项。检查者未参与这两个PR的实现，本次没有改写生产算法或双进程程序。范围仅为离线软件接合，非ARM、板上或双轴批准。

A的外部PS工程已生成bit；读取其布线后报告WNS +0.278 ns、WHS +0.036 ns、setup/hold失败端点为0，DRC仍有警告。本次bit/HWH与A导出的XSA内容一致。10月20日打包时板测未执行，10月21日现场增量见上节，不能用打包状态覆盖现场结果。ACTUATOR_BOUND=0，双轴接口仍未交付。

上传包入口为release/output/soundsight_pynq.zip（本地产物，不提交缓存或Windows DLL）；重打包工具tools/package_pynq.py，步骤见[pynq-first-run.md](pynq-first-run.md)，证据见[evidence/pynq-integration-20261020](evidence/pynq-integration-20261020/README.md)。第一步只检查环境和HWH，不访问MMIO、不加载位流、不复位。

用户2026-10-18更正：两版器件约定和新建工程默认值统一为`xc7z020clg400-2`。本次仅更正配置和说明，未重建已有工程、重新Validate、生成IP输出或运行综合/实现。迁移阶段报告及固定官方仿真参考中的旧器件记录保留原文，不能据此宣称当前目标已验证。

## 最新STM32手工工程接回

2026-10-19读取外部`handoff/latest`，将用户已实施的`ss_spi_mode0.sv`末沿修正（CS释放时要求`!fall`）接回`project/rtl`。公共RTL继续只有一份；其余源码、Hann数据和两份STM32 XDC无实质变化。最新BD的63项功能配置/连线事件、两份FFT XCI及77项运行属性与现有配方一致，保留原工程入口及GUI布局，不创建第二套工程源码。

外部工程最新布线后报告：WNS +0.379 ns、WHS +0.036 ns；布局后资源LUT 13895、FF 14458、BRAM 25、DSP 41。导出仍登记一份禁用的ILA XDC，正式仓库配方不引用它。28份实际输入在忽略换行与行尾空格后匹配，40项重建依赖存在。本批未运行Vivado、未重复板上修正的仿真，也未执行新板测；不是仓库配方重建或整机验收通过。PS目标不继承这些物理结果。完整记录见[本次证据](evidence/stm32-handoff-20261019/README.md)。

先前带ILA的板测已捕获首次SPI_FORMAT：同步CS在第39位后高一个采样周期，事务分裂为39位和1位；BIST_REJECT通过，第二次启动检查失败。该CS异常的电气/软件根因仍未确定，`!fall`修正和禁用ILA不构成此故障已解决的证据。原始ILA及UART保存在本次证据中，与最新无ILA实现报告分开标识。

## Vitis小型裸机交接

用户已完成Vitis 2025.2的pl_stm32_platform和first，目标ps7_cortexa9_0/standalone；现有构建记录显示平台和应用成功。XSA（含bit）、组件包及本机路径准备工具归入[software/vitis/stm32](../software/vitis/stm32/README.md)。main只打印启动信息并休眠，源码仅随application包保留，不与PYNQ业务代码混淆。

组件包现为vitis_components.zip，根目录仅first和pl_stm32_platform；XSA、路径清单与解压工具在包外单独保留。交付ZIP内九份元数据的61项路径改为相对引用；仅在接收方工作副本中填写厂商必需的本机路径。XSA/bit/ELF与应用代码未改写，解压和路径核验通过；本次未打开Vitis、重新编译或上板，既有构建记录不等于实机启动验证。

10月19日FPGA接回没有更新此Vitis包中的XSA、bit或BOOT镜像；它们不能作为最新FPGA候选的配套启动产物。

## 已有成果

- 简化后的采集/分窗/预处理/官方FFT/六对PHAT与IFFT/整帧封存。
- 双槽快照、SPI寄存器、自检、停止排尾、PWM保护。
- 61.44/100MHz双域、官方XPM跨域、官方时钟/复位设计。
- 独立PS AXI入口、S1桥和应用的PC验证。
- B提供的冻结ABI、S1 C代码、4705项PC测试及v2接线/分工原文。
- 两套BD原有准备结果、定向仿真原文；模块、算法、端口和连接说明。

新目录的迁移复现结果另见migration-report.md，不能用旧目录的成功标记代替本次执行。

## 尚未完成

| 项目 | 当前边界/责任 |
|---|---|
| 实际PS7 DDR/MIO与启动 | STM32版已接回A的真实配置；独立PS版已用旧PYNQ启动并执行双核程序，启动镜像与HWH时钟差异需按现场修正处理 |
| 当前100MHz组合综合/实现/STA/CDC/RDC | 外部STM32工程已有正裕量报告；整理后的配方未重建，CDC/RDC及约束语义专项复核未在本批执行 |
| STM32 S2及外设工程 | 按收到的B侧v2仍未实施；不能由目录迁移宣称完成 |
| 实际SPI/IRQ/接线电平 | 已有ID/ABI及部分BIST/IRQ板测；首次CS异常已捕获，根因及稳定性复验未完成 |
| PS版ARM/PYNQ执行与调度预算 | 已有双BIST及20帧实采；100帧旧版失败，新RAM入口尚待板测；不宣称持续零丢帧 |
| 声学精度与通道/几何标定 | 合成PDM链路不能代替真实声源试验 |
| 舵机机械标定与闭环 | ACTUATOR_BOUND默认0，不默认启用输出 |
| PS↔STM32遥测/展示 | 未冻结；主方案PS不抢STM32快照所有权 |

六麦三维、声纹放在research，保留成果但不进入当前关键路径。两个比赛Skills已适配新仓库：PCM示例自包含、当前路径/说明统一，仓库内离线回归与六次真实XSim验证通过；独立导出包及其配套验证见[Skills交付说明](competition-skills-delivery.md)。PYNQ真实驱动和板测仍NOT_RUN，不占用本次上板安排。
