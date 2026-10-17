# DS187 来源与用途

- 文件：`ds187-zynq-7000-dc-ac.pdf`。
- 标题：Zynq-7000 SoC (Z-7007S, Z-7012S, Z-7014S, Z-7010, Z-7015, and Z-7020): DC and AC Switching Characteristics。
- 版本：DS187 v1.21，2020-12-01；本次获取日期 2026-09-10。不将获取日期当作版本日期。
- [AMD 官方文档页](https://docs.amd.com/v/u/en-US/ds187-XC7Z010-XC7Z020-Data-Sheet)；[官方 PDF 下载](https://docs.amd.com/api/khub/documents/uaBd8Qxmf_K1~~tiVnOxrw/content)。旧 xilinx.com 文件地址返回 HTML，已改用官方 PDF 端点并验证 PDF 可解析，共 73 页。
- SHA-256：`61e245380c01d2b9cc1350d529265d185e04c1c0379b0fdb3adcba76585c8dac`。
- 本次只针对需要的 PL IO 电平核验：第 11 页 Table 10 与脚注，未声称审查整份手册。适用 xc7z020；不可把第 10 页的 PS MIO 表套到 PL Bank13。
- 实际核对与限制见 `task-packages/PKG-A-ACQ/evidence/existing-electrical-timing-audit-2026-09-10/`；资料入库不代表电平或采集已验收。
