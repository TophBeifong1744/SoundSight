# VS Code ARM32 兼容尝试：用户取消

用户已确认USB服务修复后正常重启可连接。VS Code 1.144.0连接PYNQ armv7l时出现UnsupportedPlatform("LinuxARM32")，与USB链路无关。官方当前源码不再提供ARM32 Server。

2026-11-02曾核实微软api/latest/server-linux-armhf/stable返回1.122.1；对应Windows ZIP与ARM32服务包已下载并通过官方SHA256，Remote-SSH 0.120.0声明编辑器要求^1.96.0。独立准备入口仅写release/output/pynq-vscode，没有替换现有VS Code、安装扩展、启动旧版编辑器或操作板卡。

准备未完成：Windows ZIP采用commit前缀目录8761a5560c/resources/app，而准备脚本假定resources/app，校验读取product.json报FileNotFoundError退出。尚未安装或连接验证，不将资产可下载标为兼容实测通过。

用户随后明确取消，不接受下载旧版VS Code。停止此路线；已结束的进程不再重试。清理本次独占release/output/pynq-vscode（下载资产和解压副本）及tools/prepare_pynq_vscode.py，保留本简记作为失败和取消记录。不改原VS Code、USB服务、SSH和WinSCP。后续仅在用户重新明确要求时恢复该路线。
