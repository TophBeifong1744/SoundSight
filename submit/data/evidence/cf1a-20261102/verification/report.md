# CF1A 完成记录 — 2026-11-02

范围：已授权的CF1首板问题软件修复与SD增量交付。没有操作板卡、Vivado、ILA或公开仓库。原CF1及用户资料保留。

## 原板证据

原件与两份解析JSON在 `../../ss-three-d-coherent-cf1/verification/board-summary-console.txt`、`board-run-1.json`、`board-run-2.json`。

| 30秒运行 | epoch41 | epoch42 |
|---|---:|---:|
| 完整PCM包 | 2811 | 2811 |
| 定位快照消耗 | 2358 | 2369 |
| 快照序号缺口 | 452 | 441 |
| CF1历史重置 | 453 | 442 |
| CF1有效原始方向 | 20 | 48 |
| 最终滤波输出/动作提交 | 0/0 | 4/4 |
| 最大解算ms | 13.4055 | 13.1916 |
| 最大整帧服务ms | 15.3691 | 16.0539 |

两次PASS、无first_fault/cleanup_errors、DMA已停止，音频errors/rejected均0。第二轮drops起始452，活动结束893、尾部894；不能把累计值解释成当轮PCM丢包。实际配置level12500/window3/min_valid1。本轮原生报告缺完整PCM，以下回放使用此前五段录音，并非这两轮的音频重演。

## 实现与独立预期

只改变频谱前端计算和CF1A版本标记；原集成收包/STOP/动作判断保留。79频点滚动累加、每256谱窗重求和；PCM完整时补齐跳过快照的历史，最大16窗，64PCM包缓存。真实PCM缺口仍停止；缺失/削顶历史中断积累，陈旧当前窗口拒绝。seen_start水位不随历史清除，避免连续重复窗口重新被接受。

`validate_replay.py`直接导入冻结旧CF1真实交付代码，用同一nativeC库、同录音和几何作独立版本预期。检查reason、direction_valid、valid_pairs、azimuth/elevation_valid及有效ux/uy/uz。完整4598窗和每6窗跳1快照的3833窗比较全部相同，有效向量最大差0。五录音都超过256窗，覆盖周期重求和。模拟稀疏输入保留全部PCM，不对应实际任意缺口分布。

| 数据集 | 全窗比较 | 稀疏比较 | 全窗有效滤波组 | 稀疏有效滤波组 |
|---|---:|---:|---:|---:|
| A静止 | 1022 | 852 | 152 | 78 |
| B静止 | 1022 | 852 | 249 | 124 |
| B动态 | 1022 | 852 | 108 | 51 |
| 本人讲话 | 1022 | 852 | 42 | 26 |
| C讲话 | 510 | 425 | 10 | 6 |

这里使用与板相同的12500/3/1滤波设置；下游仍在快照序号缺口处重置，因此稀疏输出组少于完整输入。方向组不是运动提交：实际硬件原始门禁仍可能拒绝动作。这些数据不证明实物角度精度。

回放内部clock固定，仅用于离线freshness，JSON内部耗时0不是测量。`timing.json`独立外部perf_counter/process_time记录实际PC纯前端时间，四轮顺序交替，同1022窗。总wall中位数0.2718743→0.14817765秒，下降45.50%。Windows11/AMD64、Python3.13、NumPy2.2，不能外推ARM/Python3.8/NumPy1.20；不含DMA、声纹、屏幕及补算突发负载。

## 检查与交付

`run_regressions.py`执行实际组合runtime：online21、follow_sound7、speaker_follow27、speaker_display7、CF1A12，共74通过。Windows仅对resource导入作空shim，不伪造计时/硬件；nativeC来自保留的solver.dll。新增测试含重复/倒序、PCM连续快照断帧、大缺口最多16窗、缺失/削顶历史、陈旧来源、STOP及中断。

`test_installer.py`4项通过，基线模拟实际已安装CF1；检查11个替换位置故障自动恢复、重复安装、私有哨兵、旧CF1安装记录、未知改动拒绝及显式回退。新安装记录THREE-D-CF1A-INSTALL.json；备份backup_three_d_cf1a_*；保留旧CF1记录并作为依赖；回退恢复原SCREEN-INSTALL字节及CF1文件。

`check_release.py`检查ZIP CRC、9载荷/31依赖、包内与源及已测Python一致、旧CF1 before校验和、Python3.8语法。最终包34513字节，SHA256 `5649788d4962df613f25e8060c31a4a8ea9f6543e01355ce667fcf70db2f6698`。README含逐条单行命令和边界。

CF1A实板计算期限、快照缺口改善、有效输出和转动尚未验证。下一只做README中的30秒运行与结束status，交回原生SUMMARY；无需新增整套声学对比。软件交付不等于整机验收。
