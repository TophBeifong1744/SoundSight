# SoundSight 双语海报

2026-11-02：英文已按已确认的中文`zh-content-v3`完成专业翻译和版面适配。两版使用相同官方版式、系统范围、试验条件、数据与结论；中文PPTX/PDF/PNG未改。内容依据仍为[中文内容定稿与证据交接快照](assets/reference/zh-content-handoff.md)。当前均为内部预写稿，不是正式提交或印刷放行版。

**发布时发现的范围差异：** 远端`main`在PR #38中已按用户决定取消DAS，并接回S2/S3屏幕及新声纹/CF1A进展；本套海报仍是此前确认的中文内容快照，保留DAS设计与触摸待接合表述。此次按内部预写稿归档，不将其标为当前整机最终方案。下一次内容更新需同时修订两版和报告，优先移除已取消的DAS内容、据原件更新屏幕与测试状态。

| 版本 | 可编辑海报 | 审阅PDF | PNG预览 |
|---|---|---|---|
| 中文 | [PPTX](output/SoundSight-poster-zh-content-v3.pptx) | [PDF](output/SoundSight-poster-zh-content-v3.pdf) | [PNG](output/SoundSight-poster-zh-content-v3.png) |
| 英文 | [PPTX](output/SoundSight-poster-en-content-v3.pptx) | [PDF](output/SoundSight-poster-en-content-v3.pdf) | [PNG](output/SoundSight-poster-en-content-v3.png) |

两版保留官方PPT白底、深灰标题条、黑色分隔线、红色小标题、圆角文字框、AMD标识及分区位置，依次放置项目简介与应用流程、系统结构与两项创新、联合运行结果与后续验证。框图沿用淡红/淡绿配色。案例的人员、学校、图片与成果未混入；黄色格式说明未当作项目内容。

页面统一为16∶9、13⅓×7½英寸，最终印刷尺寸与出血待确认。学校/团队/成员/指导老师与校徽口径待确认，未套用报告匿名要求。2560×1440 PNG只供审阅，不作为大幅印刷分辨率证明。两版文字、框图、线条与7×3结果表均可编辑。中文正文微软雅黑、英文Calibri，主字号11 pt；标题宋体/Times New Roman，表格10 pt。英文自行适配行数、表格列宽与局部文本框，不靠缩小正文迁就中文行数。

## 数据与图件

- E2（当前两版）：10月30日归档的两轮现场测试，时长32.159/27.254 s，读取定位帧3012/2552，停止前声纹计算6/6，目标提交117/94，运行故障值0/0，旧结果淘汰0/1。条件为48 kHz、方向筛选窗3帧/至少1帧合格、PCM统计门限12000、同一目标模板、试验门限0.45、许可10 s、两轴启用。
- 两轮时长不同，不是优化前后对照。第2轮序号间隙1；帧数含无效方向帧，计算数不等于识别正确数，提交数不等于机械到位。6/6按有限数值评分且`completed_at <= at`统计；含STOP后收尾的8/7不用于海报。来源散列见[joint-run-facts.json](assets/joint-run-facts.json)。
- 两版右上保留实物照片缺口，不生成或借用设备图。AMD标识来自官方模板。历史工程截图E3与离线前端对比E1已不在当前两版展示；原`facts.json`与历史输出仍保留。
- 中部是可编辑功能说明图，不冒充Vivado原始BD。PL采集分别送相关运算及PCM/DMA；PS求解、声纹与跟随分开；PWM归PL。DAS同时接收四路PCM和方向；声纹使用单路输入，未接DAS输出。虚线表示该内容快照中待整机接合的部分，不确认电气接口。定位只估方位/俯仰，不估距离。
- 英文用speaker verification表达目标模板比对，用pan–tilt tracking表达双轴跟随。限时许可不保证多人身份与当前方向绑定。55处中英对照见[translation-map.json](../evidence/posters-en-20261102/translation-map.json)；出处与结论边界写入PPT备注。

## 待补与跨聊天同步

详见[独立核验清单](verification-checklist.md)。需补整机正面/斜45°照片、RGB触摸实际操作、三维真值及机械指向误差、本人/他人对照、实麦定向拾音对照。未取得的测量数字没有填入海报。

本次只同步已确认中文内容。11月2日CF1A、USB/SSH和屏幕新进展未单独并入英文；接收原件后应共同更新两版、备注、事实文件及清单，并同步两份报告。新试验不能覆盖原始两轮记录。本任务未修改报告或公共指导，未主动向其他聊天发送消息。

## 编辑与再生成

中文入口[src/build_official_zh.mjs](src/build_official_zh.mjs)，英文入口[src/build_official_en.mjs](src/build_official_en.mjs)，译文及局部适配在[copy-en.json](assets/copy-en.json)。两者共用编排与事实，由[src/merge_official_template.py](src/merge_official_template.py)保留官方对象。事实复算[src/prepare_joint_run_facts.py](src/prepare_joint_run_facts.py)只读原始归档。[输入快照与原始路径映射](assets/reference/README.md)补齐干净检出的依赖，不改报告和公共指导。旧`build_posters.mjs`、`facts.json`及已交付历史输出保留历史用途。

设置本机`CODEX_RUNTIME_DEPENDENCIES`、`CODEX_PRESENTATIONS_SKILL`、`CODEX_SOFFICE_EXE`和新`POSTER_REVISION`；已有最终文件不自动覆盖。从仓库根运行：

```text
<runtime-python> document/posters/src/prepare_joint_run_facts.py
<runtime-node> document/posters/src/build_official_en.mjs
<runtime-python> document/posters/src/render_pptx.py <新PPTX> document/posters/output --dependencies <dependencies目录>
<runtime-python> document/posters/src/check_official_en.py <新输出后缀>
```

中文再生成用`build_official_zh.mjs`与`check_official_zh.py`。渲染器隔离LibreOffice用户环境，使用标准file URI、稳定PDF等待及真实Poppler EXE。脚本不访问板卡、不启动Vivado、不控制执行器。

## 验证与收尾

英文通过PPTX结构、字体、页面边界、原生表格和重新导入检查；55处文案与中文源对象对应，12个结果数值同时与中文及事实一致。76处正文/单元格在PDF中完整找到，字形在容器内、对象间无重叠。官方9个保留对象几何一致，两处AMD图片字节一致。检查整页及局部后修正异步说明越框、展望靠近页脚问题；中文三个文件与原交付SHA256一致。

未执行Microsoft PowerPoint打开后编辑/重存、实际印刷或非作者审查。证据见[英文同步记录](../evidence/posters-en-20261102/README.md)；此前[中文内容证据](../evidence/posters-content-20261101/README.md)、[官方模板证据](../evidence/posters-official-20261101/README.md)、[初版证据](../evidence/posters-20261031/README.md)保留。生成阶段只清理本次英文中间输出和`codex_out/poster-content-en`，未清理其他聊天文件，也未提交或推送Git；之后用户明确授权推送合并，按隔离分支和PR发布，详见[发布核验](../evidence/posters-en-20261102/publication.md)。
