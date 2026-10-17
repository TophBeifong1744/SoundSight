# 六麦声学软件评审材料包 v1

2026-09-07。可单独复制本文件夹用于后续报告取材与复现；这是合成浮点预评审材料，不是完整竞赛提交包，也不是实板验收。

## 阅读顺序

1. [完整评审报告](REPORT.md)：假设、方法、结果、失败条件和后续工作。
2. [方向统计](results/direction-summary.csv)、[三张结果图](results/SUMMARY.md)、[音频指标](results/audio-demo.json)。
3. [源代码](src/six_mic_acoustic_review.py)、[配置](results/config.json)、[21 项自检](results/self-tests.json)、[逐帧数据](results/direction-trials.csv)。
4. [来源与版本](provenance.json)、[文件校验清单](package-manifest.json)。

只包含六麦：水平 40 mm 方形四麦，加中心上、下各一麦（z=±28.284 mm）。保留既定 IM73D122V01/PDM 选型，但软件使用理想一致全向麦模型，没有验证真实模块/PDM 接口。输出三维方向而非距离或高度坐标。

## 可引用与不可引用的结论

- 2700 个独立合成帧、21 项自检；单目标名义全频白噪声 20 dB 条件下球面误差 P50/P95 为 0.22°/0.47°，有效率 100%。该行实际处理频带内约 28 dB。
- 真正带内 0 dB 噪声下有效率只有 47%；等强竞争声源下只有 26%，有效帧 P95 误差 75.31°。不能宣布可靠定位全面通过。
- 一个有利的带限干扰场景中，手动和自动静态波束相对单麦 SIR 改善 5.65/5.29 dB；自动方向有效帧仅 43.55%。不是语音清晰度、连续跟踪或真实房间 SNR 验收。
- 3D-G0 未整体通过；没有 FPGA 定点、资源、时序、PDM、实录或板测证据。V1 四麦计划与截止时间不变；本包没有新增四麦模拟。

## 独立复现

已验证环境：Windows、Python 3.12.14、NumPy 2.3.5、Pillow 12.3.0。依赖版本见 [requirements.txt](requirements.txt)，请在自选隔离环境准备依赖；本包不自动安装软件。

在本文件夹打开终端：

```text
python verify_package.py
python src/six_mic_acoustic_review.py --out reproduced-results --repeats 5
python verify_package.py --reproduced reproduced-results
```

`reproduced-results` 必须是新目录，不要用 `results` 覆盖保留证据。首条校验文件完整性，末条比较原始 15 个结果产物；相同环境已做逐字节复现。不同 Python/数值库/字体环境可能造成配置、浮点或 PNG 哈希差异，此时须解释差异，不能仅凭哈希不一致判定科学结论错误。

`results/SUMMARY.md` 保留原始生成器写出的仓库命令（并受原始哈希保护）；单独使用本包时以本页复现命令为准。A/B/C 和六通道 WAV 是噪声探针，不是自然语音；建议低音量试听。

## 后续报告与提交

报告引用时同时带上条件、有效输出率和失败案例。重要图表为 `results/six-mic-geometry.png`、`six-mic-beam-cuts.png`、`six-mic-direction-summary.png`；CSV 是数值来源，WAV 与 `audio-demo.json` 配套。

正式提交前仍需自然语音/房间实录、人工科学复核、目标锁定与异常处理、定点/PL/板测证据，以及赛题格式、英文材料、隐私和第三方许可检查。本包不含官方资料 PDF、个人会议备份、板卡照片或第三方库源码；原仓库 [MIT LICENSE](LICENSE) 随包保留，第三方依赖仍遵循各自许可。
