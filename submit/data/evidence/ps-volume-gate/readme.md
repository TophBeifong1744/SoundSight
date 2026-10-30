# PL+PS 音量门限：候选与自测记录

日期：2026-10-21。本页最初记录定向仿真与主机软件自测；随后用户已完成综合、实现和bit生成（WNS +0.265ns、WHS +0.021ns），接收记录见[sd-package](sd-package/readme.md)。新音量候选尚未上板。这些自测和用户实现结果不等于独立复核或整机验收。

## 本次改动与用户决定

只启用PL+PS扩展，STM32默认参数和冻结SPI合同不变。FPGA计算四路、每路1024点的去直流PCM平均绝对幅度，跟六对结果原子保存和跨时钟传递。PS根据显式命令参数筛选方向，低音量记录仍保存，应用方向为无效而不是0°。不改变C求解器，不驱动舵机。

用户确认先使用假设起点，再实测调整。**1000个PCM采样计数仅为试调起点**，没有声学标定依据，不是“合理音量”的结论。使用`--min-level 1000`，以后改参数即可；没有隐藏的默认门限。原1000帧板测的energy固定0且无效，不能用来选门限。本次新接口ABI为`0x00010001`；旧位流不能运行新的音量功能。

## 真实自测

命令均在仓库根运行；本批没有打开、综合或实现用户外部工程。

|命令|真实输入与主要预期|结果|
|---|---|---|
|`python -B -X utf8 tools/run_sim.py level`|纯直流、四路不同幅值、S24满量程、部分帧重新开始；包含输出背压|4组平均幅度分别0、640、8388607、4；32次单元检查通过。与关闭扩展的预处理逐周期比较：数据和握手一致|
|`python -B -X utf8 tools/run_sim.py levelstore`|上一帧保持100，新帧900在满时被丢；取消后恢复|旧帧幅度100不被覆盖；取消无有效幅度；恢复400通过|
|`python -B -X utf8 tools/run_sim.py pslevel`|真实AXI事务、两槽640/4、主机复位、无效幅度和BIST|新ABI/能力位正确；主机复位保槽；BIST合成100000保留|
|`python -B -X utf8 tools/run_sim.py duallevel`|CIC出口注入确定PCM，官方FFT/IFFT、XPM异步FIFO，100MHz/约61.44MHz，正常→STOP取消→恢复|3帧、12个麦克风对检查通过；两正常帧幅度263172、251126，取消幅度无效；沿用655360计算周期上界断言通过|
|`python -B -X utf8 tools/run_sim.py preprocess`|原预处理黄金数据，扩展默认关闭|8192点逐点检查通过|
|`python -B -X utf8 tools/run_sim.py ps`|原PS寄存器/BIST/双槽复位用例，扩展默认关闭|852项检查通过，原ABI保持|
|`python -B -X utf8 software/tests/test_volume_gate.py -v`|门限上下/等于边界、低音量、缺能力、旧ABI、故障/取消、BIST、先存再消费、保存失败|15项通过|
|`python -B -X utf8 software/tests/test_buffered.py -v`|RAM先存再消费、高水位、失败恢复、启动等待等既有用例|19项通过|

新软件及测试文件按Python3.8语法解析通过。实际运行主机Python为3.14；尚未运行此次候选的ARM软件测试。

六个XSim用例的`RESULT.json`及`simulate.log`按用例归档在本目录；`duallevel/duallevel_six_pairs.txt`保留两正常帧的六对原始输出。软件日志为`test_volume_gate.log`、`test_buffered.log`。报告中的绝对路径是执行原件，不是交接依赖；仿真工作目录仍在`simulation/work`，不搬入大型数据库。

## 时序与资源边界

幅度累计只复用既有MULTIPLY拍，不新增状态或等待拍；RTL增加37位累加器、32位结果及有效位，异步整帧通道从992扩为1025位，深度仍为1；两槽复用原energy字段。没有增加FFT、除法器或外部IP。实际LUT/FF/BRAM、布线、STA及CDC报告必须由新候选构建取得，旧bit的通过报告不覆盖本次。

双时钟用例从PCM出口注入，**没有验证自然PDM输入、电气、实际声压、室内反射、安静/发声可分性或机械动作**。后续为修复用户回传的BD刷新失败，已在用户工程的干净隔离副本中实际通过Vivado模块刷新、Validate及输出生成，未写入用户实际工程；详见[TCL-UPDATE.md](tcl-update.md)及[native-bd](native-bd/readme.md)。门限也没有带来语音识别能力；任何超过门限的噪声仍可能通过。

替换文件、BD两条新增内部连线、软件字段与后续手工步骤见[音量扩展说明](../../../report/ps-volume-gate.md)。测试期间未修改`software/common`或两版XDC；没有删除旧bit、原始板测或有效失败记录。本任务未创建`codex_out`临时副本。
