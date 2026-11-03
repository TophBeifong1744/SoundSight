# 2026-10-21 / 正四面体三维算法迁移

问题：把原C三维求解移入Zynq ARM Linux接口且不干扰二维。

旧方案与修改原因：把原C三维求解移入Zynq ARM Linux接口且不干扰二维。

候选：三维独立目录、几何校验、六对特征桥接、ctypes/JSONL；原C规则保持。

输入：标称40mm、48k/343m/s；PC合成特征及实际C/Python对照。

预期：数值和原二维调用兼容，非法几何与极点明确拒绝/标记。

方法：test_solver_3d_migration.py；Windows AMD64 GCC8.1，非ARM。

结果：154数值/17非法/15几何/4CLI通过，原2110/2378/92270断言；PC调用中位11微秒。

结论：B负责早期核心迁移；不据PC数值声称实物角度精度或A当前上板版本完全等同。

报告引用：B-TETRA-MIGRATE-MEDIAN；S11；06贡献索引

下一步：保留当前进度；产品接入/板测按相应负责人继续，本批仅报告整理。

证据：[E17](../records/E17/README.md)。候选哈希/提交及原路径见[source-map](../source-map.json)和[源码摘录](../03-code-highlights.md)。
