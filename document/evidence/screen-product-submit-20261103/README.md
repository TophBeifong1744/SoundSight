# P1 submit 与报告同步 — 2026-11-03

按用户要求，将最新 P1 安装包、源码、说明和已有软件证据更新到 submit，使用用户原样脚本重新导出 S2 硬件报告。
没有修改产品算法、位流或用户配置，没有操作板卡；板子离线，P1 新增流程仍待实板验收。

## 验证

- [独立提交检查](validation.json)：1032 个文件，1019 个源映射；272 个相对链接无断链，文件命名与原件一致性通过。
- 独立 ZIP 解包、源码恢复、缺件/目录覆盖/路径越界拒绝通过；49 项 S2 配方一致。
- 从提交内源码构建 C 求解器并完成 141 项软件测试（P1 43 项），无板级执行。
- 从独立恢复目录重建 P1 ZIP，10 个条目，逐字节等于提交内的可安装 ZIP。
- 对 1019 项源映射另外核对 Git 暂存对象内容，均与导出时读取的源码一致；原始报告和日志保留换行，不让 Git 变换原件。
- 本轮 Vivado 实际导出在 [S2 报告](../../../report/screen_s2_20261103/README.md)，五份原生输出、原日志和项目前后内容核对齐全。

`validation.json` 的 `eda=NOT_RUN` 指独立 submit 检查器没有启动 EDA；报告导出另有真实 Vivado 日志，不混淆两者。
先前 P1 软件证据中的1003源码/247链接是上一轮快照，本轮增加安装ZIP、报告脚本及证据后变为1019/272，原证据不改写。

## 当前入口

- `submit/board/artifacts/soundsight_screen_product_p1.zip`：已有 S2/S3/CF1A 板端的 P1 增量安装包。
- `submit/report/screen-product.md`：安装、屏幕操作和两轮冷启动测试步骤。
- `submit/report/design-report.md`：当前功能、已有实测、离线结果和待测项。
- `submit/build/reports/current/screen_s2_20261103/`：本轮原生报告。
- `submit/build/handoff/tools/`：用户报告导出脚本及原说明。

完整公开提交 ZIP 位于 `release/output/soundsight_submit.zip`，另提供到下载目录；不含私人模型、录音或声纹模板。
软件功能仍通过 PR #43 候选分支交付，主线与板端不由本次同步自动改变。
