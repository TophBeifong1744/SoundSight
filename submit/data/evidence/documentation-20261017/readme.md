# 建工程资料校对（2026-10-17）

本次只修正文档和模块目录，不改RTL、BD/IP配方、XDC或冻结ABI。

- TXT、Word及两版模块目录统一使用SoundSight当前路径；修正工程准备、IP输出、报告和仿真入口。
- STM32逐线表：13个单元、30条普通网、2条接口网；PS逐线表：19个单元、32条普通网、5条接口网。静态展开当前Tcl配方，与已准备原生BD的单元和连接一致。本次没有启动Vivado。
- 明确draining→compute_draining、run_enable→enable、数据位宽、跨域边界、低有效复位、冷复位与总线复位的用途，以及旧单域模块不加入新BD。
- 33份模块声明对照当前RTL一致；Word内33条源码路径全部存在。正文未发现旧仓库路径或旧准备脚本名。
- 运行 `python -B -X utf8 tools/check_project.py`：PASS，26/26/33条源清单、8份Python语法检查；只证明项目静态结构。
- Word通过指定Windows渲染器生成41页，逐页视觉检查完成；修正了一处多余空白页。预览属于可再生成临时文件，未长期保存。

## 工具失败与处理

Windows渲染器首次读取Poppler本地化信息时发生UTF-8解码错误（0xd6），继而对None执行正则失败。任务内适配为先按字节收取输出、UTF-8失败时按GB18030解码，仍调用原Windows渲染器、真实Poppler EXE及隔离的LibreOffice，最终渲染成功；未修改全局工具。静态Tcl核对遇到打包Python缺少/不匹配Tcl库，改用本机Python3.14自带Tcl完成，不涉及EDA。

## 范围

未重新执行RTL仿真、综合、实现、STA或板测；文档一致不等于物理验证通过。DDR/MIO/PYNQ仍由用户按实物配置。历史证据原路径保留，不作为当前操作指令。

本次临时目录codex_out/build-docs-update中的编辑助手、渲染PDF/PNG及中间检查文件在记录归档后清理。正式Word仍在document/manuals，连线与时钟说明在document/design。
