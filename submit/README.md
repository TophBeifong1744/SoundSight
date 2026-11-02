# SoundSight 最终提交材料 — 2026-11-03

最终范围：RGB触屏、四麦三维定位、声纹验证、双轴指向。已包含PR #40、#41后的源码。
当前组合为S2硬件＋S3面板＋CF1A前端＋CP1/VF1声纹与score_ttl_v2许可。
水平J3-2/M15、垂直J3-3/J14；默认不开轴。

P1新增开机自启、触屏录入及确认关机，见[产品化操作与验收](report/screen-product.md)。
用户已回报C的此前功能测试通过；P1冷启动等新增流程尚待本板测试，不将离线检查记为板测。

七类目录均含实际文件，可整体复制上交。旧平台工程、旧安装包、非最终研究和过时海报副本已移出。
保留的历史数据用于解释已采用优化的基线和失败，不作为可安装的另一套工程。
详情见[清理范围](report/submit-final-scope.md)、[系统与结果](report/design-report.md)、[待补材料](report/pending-materials.md)。

## 独立恢复和检查

在本目录执行，输出目录须为空且位于submit之外：

```text
python -B build/prepare_workspace.py --output ../soundsight_work
```

进入soundsight_work后：

```text
python -B tools/prepare_screen_s2.py --output ../s2_work
python -B tools/check_current_software.py --output ../software_check
python -B -m unittest discover -s software/tests -p test_current_runtime.py
```

恢复不依赖Git或外层仓库。S2准备复制49项配方，不执行EDA；使用Vivado2025.2、xc7z020clg400-2，
输出路径须ASCII且最多78字节。生成目录中的build.bat默认只创建工程，显式synth/route才综合/实现。
软件检查需要Python、NumPy和PATH中的gcc，从包内C源码新编译，运行公开合成输入/逻辑测试。

匹配bit/HWH/XSA见board/artifacts/screen_s2；实际GUI导出和报告见build/handoff及build/reports。
板端步骤见[当前完整运行包说明](report/pynq-final-runtime.md)和[屏幕操作](board/instructions/screen-control.md)。
公共提交不含私人模型、声纹模板、原始录音或机械标定；它不是可直接覆盖SD卡的完整私人运行ZIP。
完整私人包的安装器源码仍收录，旧增量包与旧打包入口不再作为当前操作路径。

没有新增板测、综合或实现。真实精度、身份与声源绑定及联合长稳的缺项仍按证据记录。
原件与失败不改写；file-map记录恢复路径。被移出的历史材料仍可从源仓库及Git历史追溯。
