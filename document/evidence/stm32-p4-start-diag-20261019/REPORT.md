# P4 启动首错诊断固件

2026-10-19。用户授权补充诊断，起点39ad462。已完成源码、PC定向验证和二维Template构建；尚未下载，本批不是首错修复。

## 修改与边界

三个产品文件：include/fpga_link.h增加RAM诊断结构；src/fpga_link.c记录本次ss_start最后事务；User/soundsight_selftest.c打印首错及有效性。冻结跨板ABI、算法输入输出、FPGA RTL、SPI模式、判定条件/失败隔离、动作门禁未改。ss_link_t内部诊断结构扩展，使用该头的对象须统一重编；本次已完整Rebuild。

记录step、R/W、address、expected、mask、actual、actual_valid、bus_status和result。ss_start返回后才打印，既有总线事务数量和顺序不变，无新增读回、重试或清故障。fail()执行REVOKE前关闭记录，保护操作不能覆盖原首错。后续显式恢复也保留记录，下次ss_start开始新记录。

actual_valid=1只表示成功读取；总线失败和写事务均为0，actual不能当作硬件值。step=0代表在进入总线前被参数/上下文检查拒绝。bus_status为传输返回码，result为启动最终判定；bus_status=0/result=10表示传输返回成功但设备检查不符。

安全检查增加各寄存器返回码；有任何无效读回时输出INVALID_READBACK，不再打印伪零值。原FAIL不被改成PASS。status另输出LINK_DIAG，以区别自检link错误与应用状态。固件标记为FIRMWARE_DIAG,P4_START_V1。

BIST模式的step表：1读SYS_CTRL；2写禁用；3验证禁用；4读SNAP_STATUS；5读FAULT_STATUS；6 REVOKE；7关WATCHDOG；8写BIST_SELECT；9验证选择；10写模式0x0A；11验证模式；12写启用0x0B；13验证启用。实际模式跳过BIST_SELECT两次事务，所以后续步号减2。

## 实测（PC/构建，不是板测）

|验证|结果|
|---|---|
|新增诊断测试|1459项断言0失败；8种读回异常、52种传输故障（13步×前/后×IO/超时）|
|UART故障注入|模拟SYS_CTRL模式读回8而期望10，准确定位step11；安全读回三个返回码均12，输出INVALID_READBACK；仍14通过/3失败/5跳过|
|S1/S2原回归|4705/15980项通过|
|原自检模型/命令|5场景和命令通过；成功live仍32/0/4，302次模型事务，与原来一致|
|P3应用模型|3070/3283项通过，动作默认关闭|
|AC5二维完整构建|退出0，0 Error/0 Warning，生成AXF/HEX；Code29810、RO2286、RW48、ZI10104|
|用户uvprojx|构建前后内容一致；保留现有本地改动，未提交|

复现：
```text
python software/stm32/tests/run_start_trace_tests.py
python software/stm32/tests/run_app_tests.py
UV4.exe -r software/stm32/keil/soundsight_f407/Projects/MDK-ARM/atk_f407.uvprojx -t Template -o <日志绝对路径>
```

主机模拟样例（不是用户硬件读回）：
```text
DATA,START_TRACE,step=11,op=R,addr=0x04,expected=0x0000000A,mask=0xFFFFFFFF,actual_valid=1,actual=0x00000008,bus_status=0,result=10,recovery=1
DATA,SAFETY_READ_STATUS,act=12,watchdog=12,fault=12,last_error=10,recovery=1
DATA,SAFETY,INVALID_READBACK,values_not_reported
```

## 用户下一步

打开原Keil工程，选择Template，用原DAP/SWD下载本次已生成的software/stm32/build/keil/atk_f407.axf（HEX也已生成）。下载/运行由用户执行，不切到三维目标。

启动应看到FIRMWARE_DIAG,P4_START_V1和本板预期13/0/11。FPGA保持当前匹配映像/启动状态及接线，首轮不要求重新生成或反复复位PL。随后逐条发送status、fpga、status，加CRLF，保存完整日志，尤其START_TRACE和SAFETY_READ_STATUS。若在DIAGNOSTIC_PREPARE即失败，同样返回原输出，不擅自清其他故障。不发送stream或动作命令。

这次增加诊断不保证原BIST失败消失。依据新实板寄存器值再决定哪一端修复。三维超限目标未构建、许可未修改；Template工程含共用三维源文件的正常编译不等于三维目标完整构建。

必要结果在本目录，构建产物在既定本地build目录，不上传二进制；未建立codex_out或工程副本，无删除用户文件。
