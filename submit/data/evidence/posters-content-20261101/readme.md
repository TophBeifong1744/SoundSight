# 中文海报内容定稿落实

2026-11-01。用户将技术报告聊天返回的`document/reports/technical-report/中文海报内容定稿与证据交接.md`放回项目后，授权更新海报。仅编辑中文海报及其配套素材、脚本和核验说明；报告、交接原件、公共指导、产品源码与英文输出未改。

## 当前交付

- `document/posters/output/SoundSight-poster-zh-content-v3.pptx`及同名PDF、PNG。
- 白底、深灰标题条、黑色分隔线、红色创新标题、圆角框与两处AMD原图沿用已确认的官方模板。9个原模板对象的坐标及尺寸完全相同。
- 主题更新为会议发言者指向，机器人听觉为后续拓展；上、下圆角框分别说明正四面体四麦三维测角和异步声纹授权。
- 用7行×3列原生表格替换局部离线前端优化图；表格为两轮联合运行记录，不是优化对比。所有正文、框图、连线和表格均可编辑。

## 定稿适配记录

应用背景、系统概述、三维测角说明、第二段结果、后续方向采用交接文案，仅调整空格与断行。四个流程节点保持“选择模式→发声测向→判断跟随→指向与拾音”；节点下说明压缩为两行，第四步明确“并行合成拾音”。技术要点的少量同义压缩保留非共面、方位/俯仰、不测距、异步许可、默认不开轴、停止/超时、同步音频和方向输入等要点。

为避免短尾行，“尚不保证多人场景下的身份与方向绑定”收为“尚不保证多人身份与方向绑定”；“表中提交次数仅表示控制命令，不代表机械到位次数”收为“提交次数仅表示控制命令，不代表机械到位”。平台行按原占位宽度分两行显示，未删除PL+PS及Linux/PYNQ。未为保留相同行数缩小正文，正文仍为11 pt；表格10 pt、框图标签按空间采用8—10 pt。

框图明确采集音频分送相关运算和PCM/DMA，相关特征送PS求解；方向与声纹限时许可分别进入跟随决策；角度命令返回PL PWM后驱动双轴。DAS同时接收音频和方向，声纹单路取样与DAS输出无连接。虚线触摸连接表示应用层操作/状态关系，不确认电气接口。图下保留待接合、PC参考实现及声纹未用DAS输出的边界。

## 来源与验证

`document/posters/src/prepare_joint_run_facts.py`直接读取`document/evidence/speaker-dual-axis-20261030/board-tests.zip`两份会话，核对与`analysis.json`一致。停止前计算数按有限数值评分且`completed_at <= at`复算，均为6；不采用包含STOP后收尾的8/7。采样率、窗口、音量、门限、许可时长、目标及轴配置从原件`settings`读取。结果和来源散列保存在`document/posters/assets/joint-run-facts.json`，旧版`facts.json`未覆盖。

- `content-v3-validation.json`：单页PPTX结构、原生表格、字体、页面边界及重新导入通过。
- `authored-elements.json`：本轮正文对象与坐标。
- `delivery-check.json`：表格逐项与原件数据一致；76个正文文本框/表格单元格全部文字在PDF中找到，字形边界位于对应容器内（字体指标允许2 CSS px）；9个模板对象几何不变、两处AMD图字节不变；英文PPTX/PDF/PNG与原交付SHA256一致。
- LibreOffice Impress导出PDF，真实Poppler导出2560×1440 PNG，检查整页和框图、表格、创新框、左栏放大图。首轮PCM标签贴近斜分隔线、触摸标签贴框，修正连线路由与标签位置后复查；保留`rejected-v1.png`。未在Microsoft PowerPoint内执行打开、编辑及重存测试；印刷尺寸、实物照片和身份信息仍待确认。

内容源要求英文同步，但用户当前授权仍是先改中文，因此只记录待同步事项，未修改英文或向其他聊天发送消息。下一轮英文需同步会议优先、两项创新、框图分工及联合运行结果，不能把目前两版当作已完全同步的最终套装。

## 复现与收尾

设置本机`CODEX_RUNTIME_DEPENDENCIES`、`CODEX_PRESENTATIONS_SKILL`和`CODEX_SOFFICE_EXE`后运行：

```text
<runtime-python> document/posters/src/prepare_joint_run_facts.py
<runtime-node> document/posters/src/build_official_zh.mjs
<runtime-python> document/posters/src/render_pptx.py <输出PPTX> document/posters/output --dependencies <dependencies目录>
<runtime-python> document/posters/src/check_official_zh.py content-v3
```

再生成需设置新的`POSTER_REVISION`，已有输出不自动覆盖。本轮`content-v1/v2`中间PPTX/PDF/PNG及`codex_out/poster-content-zh`在归档必要失败预览后清理，无本轮剩余临时文件；此前已经交付的中文版本保留作历史对照。未运行Vivado、板端程序或执行器；未提交或推送Git。
