# D1 三维应用接合记录

2026-10-18；父提交4821794d34e6b24c65713f03e985c8a4ed3480b5；分支codex/stm32-3d-diagnostics-d1。**PC接合通过；三维AC5源编译通过但链接受限，D1完整固件条件未满足。** 二维默认目标完整构建通过。没有三维HEX，没有新板测。

## 实现

新增ss_spatial，复用S2的acquire_at/finish_at，保持一个deadline、一次成功消费、错误隔离和不重试不确定CONSUME。P1/P3编译选择SS_DOA_PROFILE，三维结果独立，planar结果在三维模式为零。真实三维stream暂不开放，须D5与A对齐实际几何/通道/时差符号/窗口/频带；三维应用禁止arm，编译打开motion写会报错。保留原二维S1/BIST/ABI、FPGA RTL、128MHz和物理动作门禁。

同一Keil工程增加Tetra3D_Diagnostic目标和独立build/keil-3d输出。默认Template保持二维。三维本地检查使用离线推导的三组Q12时差，明确标记合成且几何未实测；旧双BIST仍按二维数值/传输检查，不充当三维算法通过证据。

## 输入/预期/实测（PC寄存器模型）

|输入方位/俯仰|预期|实际Q8输出|其他|
|---|---|---|---|
|45°/+30°|有效，双角有效|11520 / 7680|42事务；只消费一次|
|-45°/-30°|有效，双角有效|-11520 / -7680|42事务；只消费一次|
|正上方|俯仰90°，方位无效|0 / 23040|azimuth_valid=0|
|正下方|俯仰-90°，方位无效|0 / -23040|azimuth_valid=0|
|120°/+15°|有效，双角有效|30720 / 3840|42事务；只消费一次|
|mask不足/取消/旧BIST|对应原因拒绝，仍诊断消费一次|均符合|无动作输出|
|40次事务逐位IO/超时，生效前后|错误传播、清输出、不盲目重试消费|160组合通过|恢复不消费|
|40ms总预算+每事务1ms|第40次可能已消费但报告超时|符合，输出清零|未另起消费deadline|
|设备时钟回绕|正确处理总时限|通过|40事务完整读解消费|
|非法采样率配置|solver错误、隔离、不消费|通过|不当作方向拒绝成功|
|同HAL毫秒内DROP_COUNT读取失败|消费后不发布结果，显式恢复回IDLE|修复后通过|二维同负例也通过|

- D1：8072项断言、0失败（app.log）。这些是合成六对特征，不是PCM前端端到端或实录精度。
- 三维主机board/live/no_peer/commands四场景通过：16/0/11、35/0/4、16/1/10以及stream门禁零总线访问。no_peer的FAIL是预期拒绝，不记为设备通过。
- 三维board合成三向量的主机计时显示0；它不是F407耗时测量。
- 三维motion编译开关=1被预定#error拒绝，runner核对了错误文字，不把任意编译失败当成功。
- 二维回归：S1 4705、S2 15980、P1 27104项；P3默认3070/测试开启3283项；五自检场景和实际串口分发模型均通过。新共用状态机修复增加了P3负例，原测试不降低断言。
- P1/P3 AC5对象回归通过；新三维模块在Keil编译阶段0警告，完整链接未通过。

## Keil真实构建结果与工具条件

|配置|结果|
|---|---|
|Template二维|0错误0警告；Code29326、RO1994、RW48、ZI10080字节；AXF/HEX已生成|
|三维原优化配置|L6050U：代码38258字节超许可限额|
|三维O2尺寸优化（最终配置）|L6047U：映像33936字节超许可限额；没有AXF/HEX|
|三维O3尺寸试验|仍L6047U，33976字节；最终恢复较小O2并重建留证|

用户表示不确定授权状态，随后只读执行armcc/armlink --vsn，二者均报告 **MDK-ARM Lite 5.36 / AC5 5.06 update7 build960**，见tool-edition.txt。未读出/发布密钥，未改许可证或环境；不能据本机Lite模式推断用户没有其他有效授权。

3D失败链接报告已经列出doa3d_solve/doa_dispatch_solve/ss_spatial_poll，但它们不是成功映像证据。栈8KiB为配置值；二维静态深度1192、三维O2失败链接分析1624字节均含Unknown间接调用/循环，不是实际栈高水位。

下一步需要支持该程序大小的合法AC5环境，或单独决定工具链适配；不以删除故障检查或改数值算法来掩盖限额。正常板卡Flash容量不是本次报错原因。

## 失败记录

1. app-first-failure.log：新增同毫秒统计读取失败测试暴露P3已有问题——poll_due提前返回，runtime未进入FAULT，recover后仍RUNNING。修正为恢复隔离优先于节流，保留原错误；二维/三维都补负例。
2. board-commands-first-failure.log：测试编译单元遗漏doa_dispatch.h，SS_DOA_TETRAHEDRAL未定义导致选错测试分支；补头后四场景通过，未更改产品预期。
3. keil-3d-size-first-failure.log / o2-failure / o3-failure及最终keil-3d-build.log保留真实链接限额。没有三维构建成功声明。

## 命令与交接

仓库根目录执行（GCC按tools.local.env/PATH，ARMCC由参数指定）：

```text
python software/stm32/tests/run_spatial_app_tests.py
python software/stm32/tests/run_app_tests.py --armcc <armcc.exe>
python software/stm32/tests/run_runtime_tests.py --armcc <armcc.exe>
python software/stm32/tests/run_host_tests.py
UV4.exe -r software/stm32/keil/soundsight_f407/Projects/MDK-ARM/atk_f407.uvprojx -t Template -o <二维日志>
UV4.exe -r software/stm32/keil/soundsight_f407/Projects/MDK-ARM/atk_f407.uvprojx -t Tetra3D_Diagnostic -o <三维日志>
```

D1～D6已录入同一模块进度表。D1保持“PC接合完成／三维固件链接阻断”，不标整项完成。D2几何配置、D3回放、D4软件双轴映射可先离线准备；D5接口和D6实物验收保留外部依赖。本轮按单项方式暂停。

有效代码在software，说明/必要日志在document。本批未创建codex_out副本或压缩包；没有需要清理的本任务临时副本。可再生成产物仅在既定build目录，二进制不提交。
