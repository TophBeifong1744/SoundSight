# D3：三维离线回放实际记录 — 2026-10-18

父提交ef8db5be9aa4af8984f0146f19cb43a01d2ed409；任务分支codex/stm32-replay-d3。只新增主机工具/测试和文档；原S1/S2、三维求解器、几何校验、Keil、板级代码和FPGA均未改。

## 做了什么

`replay_3d.py`解析JSONL，调用`replay_3d_bridge.c`编译出的现有C求解器，生成逐帧/逐对CSV与统计JSON；复用D2同一几何校验。支持参考缺失、极点、模帧号回绕、序列拒绝、错误分类、来源声明和配置对照。`generate_replay_demo.py`使用解析几何的前向到达时差合成输入，不调用逆解来制造预期。

操作、完整输入格式和结果表见[REPLAY-D3.md](../../../software/stm32/REPLAY-D3.md)。

## 实测结果（仅PC）

- `python software/stm32/tests/test_replay_3d.py`：D3_RESULT,PASS,checks=776,failures=0；20个负例全部按期拒绝，成功/无参考/全部拒绝/CSV来源转义/回绕场景通过。
- [实际68条输入](example/input.jsonl)、[逐帧CSV](example/frames.csv)、[逐对CSV](example/pairs.csv)、[汇总](example/summary.json)：57有效、6算法拒绝、3输入拒绝、2序列拒绝，408条逐对记录。观察ID间隔总数2，不声称物理丢帧2。
- 42条理想方向最大三维夹角误差0.000902188636°；12条±0.05样点人为扰动最大0.506212269408°。误差以原拟合向量计算，CSV同时保留浮点角及Q8码。
- 56个有效参考样本：平均夹角误差0.068269594416°，RMS0.158640271798°。方位误差54样本，两极点不计方位；有效无参考帧不计误差。不能将此数据当真实录音精度。
- [原数值回归](solver-regression.log)：profile0 2110项 / profile1 2378项，0失败。
- 正常编译和执行原始记录在[example/build-run.log](example/build-run.log)。每个异常CLI调用单独日志保留；异常EXIT_CODE=2表示预期拒绝。

首次测试断言把“含参考的记录”写成67；无参考帧的重复副本同样无参考，正确应为66。原失败信息在test-first-failure.txt；只修测试计数。后续精化三维误差为原向量计算，避免以Q8量化后的角计算时理想角差被舍为0，最终CSV与数字均为此口径。

本批不做三维固件链接（D1已知MDK Lite限额未解决），也不重跑未变二维板端工程。没有真实特征/PCM、独立现场角度或板端时间证据；RECORDED_FEATURES分支只用合成夹具测试声明处理，并非新增实录。

有效文件均在software/document正式目录，无codex_out或ZIP。临时C工作程序和失败夹具自动清理；必要最终示例及日志归档本目录，build保留可再生成结果。下一D4纯软件双轴映射；本批完成暂停。
