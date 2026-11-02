# 最终提交裁剪验证

基线为合并 PR #40、#41 后的 d78efe2073acce7a4ce747a3b7921ca0172efa64。
当前 `submit` 从 2502 项变为 1009 项；移除 1498 项、增加 5 项、更新 32 项。
逐文件变化见 [changes.json](changes.json)。完整范围见 [说明](../../submit-final-scope.md)。

实际验证见 [validation.json](validation.json)：

- 996 项源文件由独立 ZIP 解包恢复，无外层仓库依赖。
- 246 个相对文档链接，失效 0；校验和、文件名和目录结构通过。
- S2 的 49 项配方载荷一致，拒绝覆盖已有目录。
- 从提交包内源码用 gcc 新编译三维 C 库。
- 安装器 9、音量门限 15、三维在线 21、纯声音跟随 7、声纹许可 27、声纹显示 7、CF1A 12，共 98 项测试通过。
- ZIP 损坏检查、缺输入拒绝、路径穿越拒绝和独立恢复检查通过。
- 当前 Python 源码本地导入依赖扫描未发现被裁掉的模块依赖。
- [压缩文件检查](archive-scan.json)：2 份原始板测 ZIP、赛事 Word/PPT 模板及引脚表 CRC 通过；模板 XML 未发现定向拾音功能内容。历史失败安装候选已移除，日志与诊断仍保留。

复现命令（在仓库根，工作父目录用本机短路径）：

```text
python -B tools/check_submit.py --submit submit --work-parent ../check --result ../check-result.json
```

此记录不再次回流到自己的提交快照，避免打包验证清单自引用。
未运行 Vivado、下载、声纹模型推理或实物动作；没有新增精度、识别率或长稳结论。
