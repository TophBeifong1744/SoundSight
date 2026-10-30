# 定位队列保新策略：2026-10-30

用户授权：FPGA持续产生定位结果，PS未及时取走时清除旧结果。实现为满槽淘汰最旧READY，不覆盖LOCKED；主动淘汰增加DROPS而不产生满槽FAULT。STOP和真实故障保持原处理。

## 保留的原始失败事实

用户串口回传，旧位流运行 `speaker --axes off --seconds 15`：

- 输出文件名 `speaker-3d-20211118-220423-746944.json`，RuntimeError: Device fault while reading frame; retain locked snapshot。
- consumed=444，last_sequence=445，fault_or=8，drops由0到1。first_fault读到FAULT=72(0x48)，status=1015607；该快照可能已包含STOP收尾，不能把0x40定为原始故障。
- PCM published=448，errors=0，rejected=0；447包送入声纹，447包被前端取走，IPC highwater=2。max_service_gap_seconds=0.01063086。单凭这些摘要不能确定Linux停顿的具体根因。
- 声纹score=0.3451737614，compute_seconds=2.585097985；capture_failed，不可作许可；motion_commits=0。
- 后续drain文件 `drain-20211118-220702-079343.jsonl` 成功保存445、446两帧，均fault=72、drops=1。用户贴回摘要作为证据；未宣称取得板端原JSON文件。

该失败仍有效。新策略接受丢弃旧定位结果，不代表旧实验无损通过，也不保证PCM/DMA或声纹端不会发生其他拥塞。

## 本次检查

| 检查 | 实际结果 |
|---|---|
| latestqueue XSim | 427项通过；LOCKED跨97次淘汰数据稳定、所有权同拍、元数据、计数饱和等 |
| latestps XSim | 76项通过；真实寄存器层接合、STOP/源错/取消/非法事务/BIST禁止替换，FREE接收取消尾 |
| queue XSim | 1500随机步，10047项通过，默认旧策略 |
| ps XSim | 852项通过，包括旧BIST及总线复位保留两槽 |
| dualaxis XSim | 319254项通过，包括AXI、双轴、无声手动、排尾、租约、防重放、STOP优先 |
| Linux新鲜度 | 5项通过：750ms边界、ARM/COMMIT写间停顿、旧目标撤销、低音量撤许可与旧评分屏障 |
| Linux三维/声纹回归 | 21+23项通过 |
| Tcl离线模型 | 4项通过：只复制两源、备份、忙碌/外部引用拒绝、刷新丢参停止 |
| 解压安装 | 3文件安装；备份字节核对，4个人文件和bit/HWH不变；包内5+21+23项再次通过 |

XSim日志和阶段结果在本目录。源文件摘要仅用于记录本次测试对象，不是板端运行门槛。日志内厂商/工作目录历史路径不是重建依赖。Linux和安装结果来自本次真实工具输出，上表为摘录，不伪造板端日志。

## 复现命令（仓库根目录）

```sh
python tools/run_sim.py latestqueue
python tools/run_sim.py latestps
python tools/run_sim.py queue
python tools/run_sim.py ps
python tools/run_sim.py dualaxis
python software/tests/test_latest_result_tcl.py -v
```

下面在Linux Python环境执行（本机用了已有WSL环境）：

```sh
python3 software/tests/test_latest_result.py -v
python3 software/tetra3d/tests/test_online_3d.py
python3 software/tests/test_speaker_follow.py
python3 tools/package_latest_result_update.py
python3 tools/check_latest_result_update.py
```

## 复核修正与边界

独立复核初次发现LR-001（非法寄存器事务到达拍先淘汰、错误后一拍才出现）与LR-002（过期帧提前返回绕过低音量撤许可）。本批已分别改为当前事务组合检查、先撤许可后判断过期，并加入针对性回归。最终独立增量只读复核确认两项闭合，核对latestps 76项与dualaxis 319254项真实日志，并独立运行Tcl模型4项通过；独立内存行为检查确认过期低音量后的晚到旧高分不能恢复许可。本次源码与离线验证范围无剩余阻断。复核者在Windows运行Linux专项测试遇到既有resource模块依赖，不将该次启动失败算作通过；目标Linux测试由本批实际WSL运行提供。

没有运行用户工程综合、实现、下载、复位或舵机操作。Tcl模型不等于实际BD通过，XSim不等于STA通过。新bit/HWH尚不存在；完整三维SD包与已验证便携Vivado快照仍为上一硬件候选。本次单独交付更新Tcl和软件增量，待用户导出新硬件后统一打包。

本任务未创建codex_out；解压安装临时目录由测试退出时自动删除。必要仿真证据归档于此，仿真缓存留在既定simulation/work，不迁移为另一套源码。
