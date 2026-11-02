# 六麦方向模型研究资料

这是历史浮点合成研究，未进入当前四麦产品；保留方向数据和失败场景。

读[原方向分析](report.md)、[方向统计](../../../data/research/six-mic/results/direction-summary.csv)、[21项自检](../../../data/research/six-mic/results/self-tests.json)和[来源](provenance.json)。

2026-11-02将生成器裁剪为方向分析；历史方向CSV和自检原件不变。原config中的源码哈希对应历史完整生成器，不冒称现在源码逐字节未变。

```text
python verify_package.py
python src/six_mic_acoustic_review.py --out reproduced-results --repeats 5
python verify_package.py --reproduced reproduced-results
```

输出到新目录。最后一条只比对方向CSV和自检；跨数值库版本差异需单独解释。配置/渲染差异不算新声学证据。已知带内低信噪比和竞争声源失败仍保留。
