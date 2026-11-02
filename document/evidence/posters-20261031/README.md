# 双语海报制作与验证记录

本任务只创建`document/posters`及本证据目录，未修改报告、公共指导和原始材料，未运行Vivado或板端程序，未提交/推送Git。

最终文件为`document/posters/output/SoundSight-poster-{zh,en}-review-v4.{pptx,pdf,png}`。事实与材料缺口见`document/posters/README.md`和独立核验清单。

## 输入与预期

完整读取项目AGENTS、海报总指导、比赛材料规则及材料索引；解包读取老师PPT唯一一页全部文本、尺寸与图件清单，实际渲染并查看该页，同时查看标注JPEG。案例原始尺寸12192000×6858000 EMU，即16∶9。`reference/`保留只读渲染参考，源PPT/JPEG未改动。

项目事实使用当前架构、三维算法说明、声纹资料索引、两轮现场JSON、优化基准串口与结构化数据、实际FPGA物理实现PNG。检索到的旧历史状态未覆盖后续原件事实。没有把方向有效率、过线评分数或命令提交数写成准确率。

预期是两张单页横版、五项功能范围一致、数字和结论一致、文字不越界/重叠、所有正文与解释图/图表保持可编辑，缺少原件时明确登记。

## 验证结果

- `zh-review-v4-validation.json`、`en-review-v4-validation.json`：PPTX结构通过；各1页，零几何发现、零警告；所选字体声明通过。每页一个原生图表、一个原生表格，图表内嵌工作簿与缓存数值/类别对应通过。第一方工具重新导入通过。
- 真实数值复算来自`prepare_facts.py`；`assets/facts.json`保留原始精度与来源散列，图表为可移植性使用三位小数显示值。40.55%由未舍入均值复算。
- LibreOffice Impress分别将最终两份PPTX导出单页PDF，Poppler EXE导出2560×1440 PNG；逐张目视检查最终PNG，英文长标签与中文单元格都已适配。审阅PDF保留矢量文字、框图和表格。
- 几何通过不等于已经实测功能，也不代替视觉检查。未在Microsoft PowerPoint内做打开后编辑/重存验证，未做印刷样张、未知尺寸/出血或色彩打样。

## 有用的失败及修正

1. 参考PPT成功转出PDF/PNG后，控制台遇到`UnicodeEncodeError: 'gbk' codec can't encode character '\ufffd'`。原因是输出PDF元数据的编码，不是转换失败或中文路径错误；修复stdout UTF-8。保留成功参考渲染。
2. 初次finalizer报`Every source-required native-table owner must have exactly one validation policy`，补齐`--require-native-table-slide 1`。
3. 原始双精度数值直接写入内嵌Excel快照时报`Excel cannot preserve the literal chart's numeric precision`。改用海报显示精度三位小数作为图表数据；完整原值仍留facts.json，百分比仍由原值计算。
4. 重导入校验需要`RUNTIME_NODE_MODULES`，补为调用方提供的运行时根目录；不安装替代依赖。
5. 视觉检查发现原生图表数字自动换成两行，英文PL标题/PS正文/双轴标签换行越框，初版中文表格侵入注释。`failures/`保留真实失败PNG。缩短英文标签、明确图表数值不折行、设置表格内边距并增加间隔；最终重新导出检查。
6. finalizer不覆盖已有validation receipt，曾返回`EEXIST`。按版本后缀分开输出和receipt，不覆盖旧验证记录。最终交付目录只留当前版本，历史检查报告在本目录保留。

## 实际执行命令形态

```text
<runtime-python> document/posters/src/prepare_facts.py
<runtime-node> document/posters/src/build_posters.mjs
<runtime-python> document/posters/src/render_pptx.py document/posters/output/SoundSight-poster-zh-review-v4.pptx document/posters/output --dependencies <本机dependencies>
<runtime-python> document/posters/src/render_pptx.py document/posters/output/SoundSight-poster-en-review-v4.pptx document/posters/output --dependencies <本机dependencies>
```

本轮工具：Codex bundled runtime Node 24.19.0 / Python 3.12，Artifact Tool 2.8.99，LibreOffice 26.2.4.2，真实Poppler二进制。缺少`load_workspace_dependencies`工具入口，因此只读核对本机现有运行时的runtime.json后使用该捆绑运行时，没有安装或改写依赖。

## 收尾

必要失败PNG与验证报告归档本目录；代码、共用数据和原件展示副本在`document/posters`；当前成品在其output子目录。旧中间PPTX/PDF/PNG和本任务`codex_out/posters`于确认归档后清理。其他聊天的codex_out子目录及既有未提交修改不触碰。详细删除清单与最后文件核对记录见`delivery-check.json`。
