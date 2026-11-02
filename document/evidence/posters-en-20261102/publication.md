# 双语海报发布核验

2026-11-02，用户在完成审阅稿后明确授权“也一并推送合并”。生成阶段“不提交/推送”的记录描述此前事实，此次按新授权进行版本集成。

- 从远端`main`的`89c18c18c3a7bab89dc5474a5027efd4d575ac7c`建立`codex/bilingual-posters`隔离工作副本；该远端基线没有`document/posters`及本次海报证据目录。
- 发布范围仅含`document/posters`、`document/evidence/posters-20261031`、`posters-official-20261101`、`posters-content-20261101`、`posters-en-20261102`。包含当前双语PPTX/PDF/PNG、已交付历史对照、可编辑生成源和必要核验材料。没有夹带共享工作目录的RTL、软件、报告或公共指导改动；没有改变比赛正式提交包的状态。
- 远端缺少官方模板与文案交接，在`document/posters/assets/reference`保留逐字节快照，原始路径及SHA256见该目录README。当前构建、事实准备和核验读快照；文案快照禁用Git换行转换。没有将其他聊天的报告或公共指导目录顺带发布。
- 在隔离工作副本重新运行`prepare_joint_run_facts.py`，得到停止前6/6次，与已归档原件一致；再运行`check_official_zh.py content-v3`及`check_official_en.py content-v3`均PASS。每版76处文字/单元格边界通过；英文55处文本对应中文源，12个结果数值一致；既有六个当前成品文件SHA256未变。
- 原有结构、字体、原生表格、模板、视觉检查范围见本目录README；没有增加硬件、EDA、印刷或Microsoft PowerPoint编辑/重存验证。
- 发布时阅读远端最新说明发现：用户已在另一任务取消DAS，且S2/S3屏幕与新声纹/CF1A状态已推进。本套海报仍为此前中文定稿的双语内部快照；README和核验清单显著登记了DAS删除、屏幕/声纹依据更新的后续同步项，已向用户提醒，不将这次归档说成最新整机终版。

合并状态和提交身份以GitHub PR及Git提交记录为准。合并核实后移除本次`codex_out/poster-publish`临时工作副本；其他聊天工作副本与共享脏目录原样保留。
