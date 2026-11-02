# 中文海报官方模板调整证据

2026-11-01，按拓芙“排版、配色和内容要完全采用官方示例的样子，先只修改中文海报”执行。内容组织遵循示例，项目文字、图件与结果全部采用SoundSight依据；模板内教学提示不当作项目要求或成果。

## 来源与结果

- 指定文件：桌面`AMD_poster_template(3).pptx`。与仓库`document/requirements/poster-reference.pptx`逐字节散列一致：`b99946c7443efd2a169035159185ed45b0021272e03d180786c2718ec40259df`。生成脚本使用仓库副本，不依赖桌面绝对路径。
- 当前输出：`document/posters/output/SoundSight-poster-zh-official-v4.pptx`及同名PDF、PNG。可编辑文字、图形、连接线、原生柱状图及内嵌数据工作簿；保留模板两处AMD标识原件。
- 模板9个保留对象的坐标/尺寸保持一致，包括标题条、竖条、三条分隔线、大AMD图和两个圆角框。白底、深灰、黑线与红色小标题保持模板样式。中文标题使用宋体、品牌用Times New Roman，正文以11 pt微软雅黑适配中文。字体提示及示例项目图片、人员、校徽、技术参数均未移入SoundSight内容。
- `template-inspection.json`为artifact-tool导入原始模板后的对象检查；`authored-elements.json`记录新正文对象；`official-v4-validation.json`为结构、布局、字体和原生图表验证；`delivery-check.json`为本任务的来源、数值、渲染字形边界及英文文件不变核验。
- 数据沿用`document/posters/assets/facts.json`和已有E1/E2原件，未产生新测试数据或新结论。中文版与英文版事实一致，内容表达和版式按本轮要求分别维护。

## 实际验证

以LibreOffice Impress导出PDF、真实Poppler导出2560×1440 PNG；查看整页及左右栏、中部框图与顶部身份区放大图。PDF全部新正文文本框内容完整，字形边界在文本框内（容许字体指标2 CSS px误差）。数字7.333、4.360、40.55%、32.159、27.254、3012、2552、117、94、0.45、10.912均在PDF中核对。图表缓存与工作簿数值通过原生图表校验。

英文PPTX/PDF/PNG的SHA256与上一轮`posters-20261031/delivery-check.json`一致。两处AMD图片字节未变，示例项目4幅图片已从中文输出包移除。未在Microsoft PowerPoint中执行编辑后重存测试；最终实物照片、正式署名/校徽、印刷尺寸仍待补齐，未作印刷或整机验收放行。

## 修复与保留范围

首轮导入曾遇到`Presentation.load`需要Node安装接口，改用文档支持的`PresentationFile.importPptx(FileBlob.load(...))`。合并时规范化包内绝对关系路径；从输出副本移除与海报无关的Templafy/SharePoint自定义表单元数据，保留原始PPT不变。

首轮渲染暴露空标题占位缺少显式矩形，以及圆角框依赖继承样式的问题；给输出对象补齐与模板一致的矩形、白填充和黑边。系统框图长句与底部PL说明经精简后恢复边界，未缩小正文。保留`rejected-v1.png`作为失败预览；其余本轮中间PPTX/PDF/PNG和`codex_out/poster-official-zh`已在核验后清理。上一轮中文输出保留作历史对照，英文未改。

重现命令（本机依赖路径由环境提供）：

```text
<runtime-node> document/posters/src/build_official_zh.mjs
<runtime-python> document/posters/src/render_pptx.py <输出PPTX> document/posters/output --dependencies <dependencies目录>
<runtime-python> document/posters/src/check_official_zh.py official-v4
```

已有输出不自动覆盖，再运行先设置新的`POSTER_REVISION`。未运行Vivado、板端程序或执行器，未改报告、公共指导和工程源码，未提交或推送Git。
