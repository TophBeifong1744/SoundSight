# P3 本板确认准备与 AC5 授权核查

2026-10-18。来源软件：49814defbaa9f81c2f8498e6dfb8b645857e933f（本批只补文档/构建记录，产品源码未改）。

## 实际结果

|检查|实际结果|
|---|---|
|二维 Template 完整 Rebuild|Keil退出0；0 Error、0 Warning；已生成 AXF/HEX|
|Program Size|Code=29326，RO-data=1994，RW-data=48，ZI-data=10080|
|armcc / armlink --vsn|均报告 MDK-ARM Lite 5.36；ARM Compiler 5.06 update 7 build 960|
|P3 新固件板端结果|尚未下载/未取得新串口日志；不能填写实板通过|
|三维完整链接|本次未重跑。原D1候选33936字节触发L6047U；当前工具仍为Lite，后续候选大小未知|

日志：[二维构建](keil-template-rebuild.log)、[工具模式](tool-edition.txt)。本次无许可证修改/密钥采集，也不能据当前Lite模式断言用户没有其他合法授权。

## 用户现在操作

1. 打开仓库内 `software/stm32/keil/soundsight_f407/Projects/MDK-ARM/atk_f407.uvprojx`，明确选择 **Template**（二维），AC5。不要选择三维目标。
2. 当前已生成 `software/stm32/build/keil/atk_f407.axf` 与 `atk_f407.hex`。Keil使用原CMSIS-DAP/SWD下载配置；Flash算法STM32F4xx 1 MB。若在另一机器打开，则先重建。
3. 本步只需STM32、DAP及串口，无需FPGA或舵机。打开串口115200、8N1、无流控，下载后复位，完整保存启动日志；启动默认BOARD_ONLY。
4. 发送 `board` 加CRLF可再运行一次；随后发送 `status` 加CRLF检查应用状态。不要发送fpga/stream等跨板命令。
5. 返回完整启动、自检和status日志。若失败，保留原始输出，勿只发送汇总PASS。

预期（不是本次实测）：

```text
APP_PROFILE,0,legacy_BIST=PLANAR_TRANSPORT,motion=DISABLED
CHECK,P3_APP_INIT,PASS
CHECK,P2_BUILD_GATE_CLOSED,PASS
SUMMARY,scope=BOARD_ONLY,pass=13,fail=0,skip=11,result=PASS_WITH_SKIPS,NOT_SYSTEM_ACCEPTANCE
```

时钟应为128/128/32/64MHz。双BIST关键数值：拒绝ux=46831、uy=-171729、residual=590912626、valid=0、reason=3；通过ux=749295、uy=0、residual=0、valid=1、reason=0。耗时按本次板端实测，不要求与旧685/729us完全相同。动作门禁保持关闭；未连接FPGA的各项SKIP不计PASS。

## 授权下一步

在Keil uVision的 Help → License Management 查看当前产品/许可证状态，若菜单名称有差异，以该版本License管理入口为准。只需提供产品类型、有效/过期状态及是否覆盖当前AC5；不要提供序列号、CID/PSN、许可证密钥。若有有效授权，按官方流程配置后再复核当前armcc/armlink及三维链接。若没有，后续由用户决定取得合法授权或安排其他工具链适配；本批不切换工具链。二维P3可立即进行。

## 复现命令

```text
armcc.exe --vsn
armlink.exe --vsn
UV4.exe -r software/stm32/keil/soundsight_f407/Projects/MDK-ARM/atk_f407.uvprojx -t Template -o <二维构建日志绝对路径>
```

构建产物保留在既定本地build目录（不上传AXF/HEX）；必要日志已归本文目录。未创建codex_out或临时工程副本，没有删除其他文件。下一等待用户本板日志与许可证界面信息；P4及真实三维仍未开始。
