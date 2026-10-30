# main集成验证记录

范围：在远端839ed62上接入LAT1、score_ttl_v2、评分显示、累计统计、导出脚本及用户证据。AI未执行EDA或硬件动作。

- Linux软件与真实增量安装输出保存在相邻的speaker-statistics-20261030目录（本次集成树重新运行）。统计按成功计算计，开启/关闭、过线、无效值、原子保存和短命令均覆盖。
- 本目录portable-tests.json与三个日志是本次Tcl离线模型及配方验证；Tcl模型通过不等于实际Vivado Validate。
- 包生成器校验50份Vivado依赖无机器路径、ZIP CRC正确；软件增量22份源/文档，与集成树逐字节对齐并保留原设置、bit/HWH。
- submit检查结果保存在submit-check.json：独立ZIP解压、恢复工作目录、路径及对应回归；这是交付可搬移验证，不是综合实现。
- 板端真实两轮原件见../speaker-dual-axis-20261030；不是本机仿真。

## 非作者复核

speaker_release_review独立只读审查未发现BLOCKER/HIGH；复跑声纹跟随、显示、最新结果和统计相关测试通过。低优先级覆盖缺口：IPC测试未专门组合follow=True+collect_statistics=True；直接引擎测试及本次ARM原始日志提供另外证据，不能写成该组合已由独立IPC单测覆盖。

lat1_release_review独立只读结论PASS WITH CONDITIONS。两RTL与原XSim测试、用户工程源相符，FREE优先、READY淘汰、LOCKED保护及同拍事务未发现阻断；真实latestqueue427、latestps76、旧queue10047、ps852、dualaxis319254检查通过。完整物理签核仍有HIGH范围问题：servo_vertical_pwm未约束输出延迟，须后续同候选有效约束/报告；无新CDC报告。旧软件证据不能替代本次TTL回归。旧hardware-review的板测未运行是当时状态，新日志独立归档，不改写原件。

本次只做限定源码集成，不宣称声纹身份准确率、双轴长期可靠性和全部物理签核完成。

源码整理只将上述RTL/TB的CRLF统一为仓库LF，逐字节去换行差异核对一致，见rtl-source-equivalence.json；原测试摘要保持原文，未假装归档后的文件原始摘要不变。
