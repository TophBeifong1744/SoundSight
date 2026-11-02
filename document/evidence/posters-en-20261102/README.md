# 英文海报同步与验证

2026-11-02。按用户要求，将已确认的`zh-content-v3`翻译为`en-content-v3`，保持官方版式、数据和结论一致。中文PPTX/PDF/PNG原字节不变。报告、公共指导、交接原件、产品源码及原始资料未修改。未核查远端推送状态，也未提交/推送Git。

## 交付与适配

输出为`document/posters/output/SoundSight-poster-en-content-v3.pptx`及同名PDF/PNG。沿用白底、深灰条、黑线、红色创新标题、圆角框和AMD标识。文字、框图、连接线、结果表均可编辑；身份/实物图/印刷规格待确认，保留内部预写标识。

声纹验证用speaker verification，双轴用pan–tilt；定位只估方位/俯仰，不测距。两项创新仍为四面体测角和异步声纹许可，不声称许可绑定多人身份。短时联合运行计数与中文相同，不推断识别正确、机械到位或长期稳定。

英文正文11 pt、表格10 pt。按英文宽度适配标题、流程节点、竖排栏目、表格列宽与局部框。异步说明压缩但保留无需逐次等待推理和多人绑定边界；展望缩窄避开页脚AMD，三行完整显示。55处逐项文案在`translation-map.json`，最终坐标在`authored-elements.json`和`table-layout.json`。

## 来源与验证

- 中文基线：`document/evidence/posters-content-20261101/delivery-check.json`登记的三个输出SHA256，均核对未变。
- 依据：`document/reports/technical-report/中文海报内容定稿与证据交接.md`与`document/posters/assets/joint-run-facts.json`；后者登记的原件散列均未变。本次未重新板测。
- 官方模板：`document/requirements/poster-reference.pptx`，SHA256 `b99946c7443efd2a169035159185ed45b0021272e03d180786c2718ec40259df`，同用户提供的AMD模板。
- `content-v3-validation.json`：PPTX单页结构、字体、页面几何、原生表格和artifact-tool重新导入通过。结构检查不等于渲染文字检查。
- `delivery-check.json`：55处译文与当前中文对象逐项对应；12个结果数值与中文及事实一致；76处正文/单元格在PDF中完整找到，字形位于容器内（字体指标容差2 CSS px），对象间字形包围框不相交；展望避开AMD页脚；9个模板对象几何、两处AMD原图字节不变。
- LibreOffice Impress导出PDF，真实Poppler导出2560×1440 PNG，检查整页及框图、创新框、结果栏放大图。初版异步说明越框、展望碰页脚，保留`rejected-v1.png`。第二版展望高度不足，修正后通过。结构校验未发现这些渲染问题，另用PDF字形检查捕获。

没有Microsoft PowerPoint原生编辑/重存、印刷样张或非作者审查。11月2日CF1A/USB/屏幕进展未单独混入英文；后续据原件同步修改两版。本次没有Vivado、板端程序或执行器动作。

## 复现与收尾

设置本机`CODEX_RUNTIME_DEPENDENCIES`、`CODEX_PRESENTATIONS_SKILL`、`CODEX_SOFFICE_EXE`和新`POSTER_REVISION`，从仓库根运行：

```text
<runtime-node> document/posters/src/build_official_en.mjs
<runtime-python> document/posters/src/render_pptx.py <新PPTX> document/posters/output --dependencies <dependencies目录>
<runtime-python> document/posters/src/check_official_en.py <新输出后缀>
```

译文在`document/posters/assets/copy-en.json`，英文入口复用中文编排和共用事实。修改源内容后需重新生成、渲染及检查。

本次英文`content-v1/v2`中间PPTX/PDF/PNG与`codex_out/poster-content-en`在归档必要失败预览后清理。最终`content-v3`与证据保留；之前已交付文件及其他聊天临时内容未清理。本轮无剩余临时文件。
