# SoundSight 比赛提交材料 — 2026-11-02

本目录可整体复制、压缩和上交。七类目录存放实际源码、脚本、产物和证据；无需外层仓库或发送方盘符。

```text
submit/
  README.md
  src/
  sim/
  build/
  board/
  data/
  skill/
  report/
```

## 当前候选与效果

唯一方案为Zynq-7020 PL+PS/PYNQ，四麦40mm正四面体，水平J3-2/M15、垂直J3-3/J14。硬件为S2 RGB/VDMA/GPIO + PS I2C0 EMIO，面板为S3，三维软件为CF1A。原有score_ttl_v2许可保留；普通声音模式与声纹模式分开，默认关轴。

S2既有实现WNS +0.203ns/WHS +0.036ns，仍有CDC和外部I/O时序缺项。用户两轮基础显示/触摸与停止已有证据。S3首板中断、CF1两轮最终输出0/4的失败现象保留。P02本人→到期→另一人本轮串行验证通过，不能写成总体识别率。CF1A历史PC回放4598完整/3833稀疏一致、74回归、前端wall下降45.5%，ARM实时性仍待A板测；真实三维精度、联合长稳未验收。

详见[本次来源与结果](report/release-20261102-submit.md)、[贡献报告](report/design-report.md)、[未完成项](report/pending-materials.md)。A总工程与B侧后续实现、用户现场操作和第三方模型贡献分别记载。

## 独立准备

在本目录执行（输出须为新的空目录）：

```text
python -B build/prepare_workspace.py --output ../soundsight_work
```

只用包内文件恢复源码原路径和大小写；不需要Git、不联网、不启动EDA或硬件。进入生成的soundsight_work后：

```text
python -B tools/prepare_screen_s2.py --output ../s2_work
python -B tools/check_current_software.py --output ../software_check
```

第一条只复制49项S2硬件配方文件并生成可搬移BAT。Vivado2025.2（xc7z020clg400-2）由使用者安装；s2_work完整路径须ASCII且不超过78字节。后续人工运行build.bat只创建工程，显式synth/route才综合/实现；本次资料维护未执行EDA。

第二条需要Python、NumPy和PATH中的gcc，使用源码新编译C库，运行合成输入/逻辑回归，不访问硬件。历史私有录音回放和安装器测试另需未公开基线，不能作为本包独立验收；见[研究依赖](sim/research/coherent-study/readme.md)。

配套S2 bit/HWH/XSA位于board/artifacts/screen_s2。板端操作见[材料说明](report/release-20261102-submit.md)和board/instructions；原CF1A ZIP要求已经安装CF1，不能直接套到10月30日旧工程。个人模型、录音、声纹模板和机械标定不在本包。原S2源ZIP保留历史build.bat默认综合行为，当前可搬移准备入口以本页为准。

file-map记录实际来源和字节校验；源代码、原始JSON/日志/ZIP不作导航改写，Markdown/HTML仅调整链接。历史W16/PR30配方和失败按当时版本保留，不代表当前S2。当前整理没有新增实测，也没有向比赛平台提交。
