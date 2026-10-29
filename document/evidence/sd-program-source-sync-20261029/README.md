# 最新 SD 包程序补齐远端

2026-10-29，基于远端 main `4aaa94cef9381963fc983285e9cf8663d2940e5e`，对照当前私下交付的 `soundsight_pynq_3d_speaker.zip`。没有覆盖本地正在进行的修改，没有操作开发板。

## 同步内容

- 包中 73 份 Python/C/H/Shell 程序：57 份已在 main 且一致，补入剩余 16 份。逐项位置见 [inventory.json](inventory.json)；比较允许 Git 的 CRLF/LF 转换。
- 补入声纹实时计算、调度、目标/模型配置、CPU 诊断、原生前端与配套测试。`speaker_core/source/` 的 C/H 在仓库统一归入 `software/ps/speaker_core/`，不维护第二份。
- 额外补齐 `pipeline_backend.c` 包含的 `core_bench.c` 和可选 CPU 诊断导入的 `cpu_profile_bench.py`，以及原有构建依赖锁、构建准备工具、许可证。打包脚本后续也会包含这两份源文件。
- 更新维护边界和双轴手动成功、长稳重启未闭合的事实；收录 [B 报告补充原件](../b-report-supplement-20261029/README.md)。

**当前已发的 SD ZIP 内容保持不变**，便于用户继续同候选重启对照。这次补齐 Git 源码和下一次打包的依赖，不要求重新安装。私人模板、录音、模型权重及完整私有 SD 包不上传公开 Git。

## 实际验证

[tests.json](tests.json)：Linux 主机 91 项离线测试通过，0 失败、0 错误、0 跳过。测试涵盖声纹许可撤销/保留、IPC 背压与子进程退出、真实 Linux 进程调度、收包、CPU 计数、三维模式和双轴停止。数据与硬件访问使用已有模拟对象；没有执行 ARM 模型推理、Vivado 或板测。

Linux 中从仓库根目录复现：

```sh
export PYTHONPATH="$PWD/software/ps:$PWD/software/ps/speaker_core:$PWD/software/tests:$PWD/software/tetra3d/linux:$PWD/software/tetra3d/tests"
export SS_LIVE_PACKAGE="$PWD"
python3 -B -m unittest -v test_speaker_follow test_speaker_process test_speaker_live test_speaker_rx test_live_cpu_profile.Tests test_stream_scheduler test_online_3d test_follow_sound
```

本机 Debian 没有系统 `python3`，本次使用已有缓存 Linux Python 3.13 解释器执行上述测试集合；不能将该主机验证称为新增 ARM/Python 3.8 板测。Python 产品文件另做 3.8 语法检查。

当前 SD ZIP 与维护源码的逐项比较、B 原件检查和测试数量均可复核；这不代表尚未完成的整机验收通过。

[source-check.json](source-check.json)：73份源码对齐、39份Python文件通过3.8语法检查；使用已有固定ORT头文件，流式C后端执行 `gcc -fsyntax-only` 通过。没有链接或替换ARM二进制。
