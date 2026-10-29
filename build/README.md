# 构建与复现入口

最新配方来自已合并的[PR #30](https://github.com/TophBeifong1744/SoundSight/pull/30)，合入基线`4adfc48086e889951806102a782d5f804e390d97`。唯一主方案为Zynq-7020 PL+PS/PYNQ；旧`prepare ps/stm32`不是最新三维配方。

## 从完整仓库开始

1. 下载并完整解压仓库，或克隆仓库；进入有根README的目录。单独下载本README不包含依赖。
2. 安装Python 3及Vivado 2025.2，把工具加入PATH；也可复制根目录`tools.local.env.example`为`tools.local.env`，按本机位置填写。不要传递个人工具配置。
3. 先检查源包：`python -B -m unittest discover -s software/tests -p test_vivado_portable.py`。需要独立Vivado源码ZIP时执行`python -B tools/package_vivado_ps_3d.py`，输出为本地`release/output/soundsight_vivado_ps_3d.zip`；此生成物不预设已上传远端。
4. 在Windows终端执行以下命令，选择新的空输出目录。输出完整路径须ASCII且不超过78字节，这是此配方的保守限制。

```bat
project\script\rebuild_ps_3d.bat --output "..\soundsight_work"
```

5. 成功后打开输出中的`SoundSight_PS_3D.xpr`。该入口复制31个RTL及Hann数据，重建BD、PS、两个FFT和5份XDC，生成IP HDL与wrapper。综合、实现、STA检查、生成bit、下载与板测由使用者后续执行；本次整理没有执行这些操作。
6. PS软件、匹配的bit/HWH、环境与私人模型需按[三维SD说明](../document/pynq-three-d-sd.md)、[W16更新](../document/pynq-w16-update.md)、[声纹说明](../document/pynq-speaker-3d.md)配套准备。源仓库ZIP不是可直接更新SD卡的完整运行镜像。

完整参数与限制见[工程复现说明](../document/vivado-ps-3d-rebuild.md)。脚本仍在[project/script](../project/script)、[tools](../tools)，没有复制另一套工程。

## 已有构建结果的边界

- [PR #30验证记录](../document/evidence/portable-vivado-20261029/README.md)：实际Vivado工程创建、BD Validate、IP HDL及wrapper生成通过；未运行综合、实现。
- [W16实现与现场记录](../project/reports/ps_3d/w16)：来自用户已实现候选的报告，不代替新重建工程的STA；双轴手动可转与长稳重启分开记录。
- [软件源码同步](../document/evidence/sd-program-source-sync-20261029/README.md)：91项Linux主机离线测试，不是新增ARM板测。

生成工程/数据库仍存既定`project/par`或使用者选择的新空目录；本目录仅组织复现入口和报告链接。
