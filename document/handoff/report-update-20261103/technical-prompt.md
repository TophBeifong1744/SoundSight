你负责继续完善SoundSight技术报告，更新原有可编辑Word及PDF，不改设计报告或海报。

先读取 document/handoff/report-update-20261103/README.md、document/handoff/report-update-20261103/facts.md、document/requirements/report-poster-master-guide.md、document/requirements/final-report-scope.md，以及当前任务原始模板/案例。本次真实资料在 document/evidence/final-board-20261103/；大模型协作以 original/llm-collaboration.txt 为主，它是用户提供的经历叙述，不是逐字对话。最新程序和测试记录见 document/runtime-update-log.md、document/release-20261103.md；接口/RTL/BD使用当前源码与S2配方，不能用旧W16工程替代。

最终仅包括RGB触屏、四麦三维定位、声纹验证、双轴指向。DAS/定向拾音已取消，彻底移除正文、框图、公式、表格、图注、复现步骤和展望中的相关内容，不专设“取消”章节。无证据支撑的结论直接删去，不新增缺项清单或占位；不要编数据，不把尚存的摘要列表扩充为完整时间序列。统一采用facts.md的指标定义：最新联合运行975.374秒、432次动作提交；定位快照淘汰不是PCM丢包，任务数不是识别通过次数，软件命令不是机械到位。原始日志失败和版本边界保持真实。

保护其他聊天在途修改，仅编辑你负责的生成源和产物。默认继续已有稿件，不重新开启工程或硬件测试。引用相对路径，不把本机路径放进成品。先核内容再生成最终文件，实际完成后报告修改文件、真实引用和检查结果。

严格沿用 document/requirements/technical-report-template.docx 的章节和格式，不套设计报告评分权重。重点写实现：系统架构、PL/PS职责、四麦通道/数值格式、时钟复位与CDC、模块接口、AXI寄存器/PCM/DMA、CF1A与三维求解、声纹评分和TTL许可、双轴保护、屏幕模式与用户管理、部署复现。把协作式采集、窗口修复、显示触摸旋转、确认删除和快速启动补入相应实现说明；明确SOUND/SPEAKER/手动模式条件。

数据使用facts.md和原始JSON/实现报告；整机照片用新增whole-system.jpg，照片上的SOUND设置与SPEAKER日志分开说明。工程图使用现有导出，分析图从真实数据生成。报告图黑白为基调、分类可用少量颜色，禁止文字越界。同步修正摘要、目录、交叉引用、图表编号和结论。完成后按Windows文档渲染规则导出并逐页检查，交付Word、PDF及更新说明。

补测表两处误填已由用户确认更正：数据为实际测试记录，阵列为40 mm正四面体。先读document/evidence/final-board-20261103/provenance.md，再用measurement-analysis.json与五份CSV；120分钟人工记录与975.374秒原生JSON分别说明，不合并或混用门限。原始TXT是大模型协作叙述主依据。原件中的历史清单不重新生成当前待补任务，当前成品只写证据支持的内容。
