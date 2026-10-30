# SoundSight 比赛 Skills 交付包

本包包含两个本队开发的 Skills：FPGA 模块开发/仿真验证，以及 PYNQ Overlay/DMA 离线验证。无需旧 SoundSight 仓库、旧工程或历史 Git 对象。源码采用 MIT；AMD/PYNQ 工具本身不随包分发。

## 包里有什么

- skills/fpga-module-verification：Skill、RTL/TB 示例、合同、XSim runner 与 Python 测试。
- skills/pynq-overlay-dma-validation：Skill、配置/golden 检查、DMA 模拟器、合同与 Python 测试。
- check_competition_skills.py：统一复跑入口，不合成、不实现、不下载、不连接板卡。
- evidence：本次迁移前缺源失败，以及修复后的离线/XSim 原始命令、输入、日志和结果；不含仿真数据库。
- ai-corrections.md：用户可见的要求、发现、纠正及结果，不含隐藏推理。
- source-map.json：导出文件与仓库原件的对应关系；仅用于交付管理，不插入 RTL、不作为板上身份协议。

文件名按小写英文导出。支持 Skills 的工具若要求 SKILL.md，把各目录中的 skill.md 改为 SKILL.md 后安装；其余脚本不依赖该文件大小写。不要安装历史说明作为额外 Skill。

## 在另一目录复跑

Python 3.10+，离线部分只需标准库。实测版本见 evidence/source-run 中的原报告。从解压根目录运行：

```text
python -B check_competition_skills.py --skills-root skills --output <新的结果目录>
python -B check_competition_skills.py --skills-root skills --output <另一个新的结果目录> --vivado-bin "<本机Vivado2025.2安装目录>/bin"
```

第二条包含第一条的离线验证，不需要先跑第一条。工具目录由接收方指定；不需要打开 Vivado 工程。输出目录必须尚不存在。XSim 可能需要数分钟；不要把运行中的输出目录删除或覆盖。

预期：模块工具 7 项测试、PYNQ 55 项测试/57 子测试通过；正常接收 96 字节，双超时负例返回 FAIL/retained/session_blocked；板端入口拒绝运行。XSim 为 PCM792、elastic13800、三种故障均检出、恢复后13800。三个负例出现 Fatal 是预期检出，报告 matched=true 才算演示成功。

证据中的实际命令可能保留发送方运行路径；这是历史执行记录，使用上述可搬移命令复跑。references/history 中旧记录保留当时路径和日期，不是当前操作入口。

## 范围与待办

本包交付的是模块仿真与离线软件能力，不证明当前 SoundSight 整机通过。PYNQ 实板适配、Overlay 下载、物理 DMA、TLAST、缓存/中断、恢复和性能验证全部 NOT_RUN；不安排上板，不移除保护入口。当前 FPGA＋STM32 主方案、Vitis 初始化和实现报告不能替代这些验证。

历史 B 的限定批准仅针对当时版本；本次迁移、打包和复跑不自动继承批准。比赛最终提交平台、材料清单及规则修订由参赛者核对，本包不宣称已向赛事提交或获得加分。
