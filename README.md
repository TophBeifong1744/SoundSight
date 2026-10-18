# SoundSight

四麦二维声音定位与转台控制。新项目独立管理，旧仓库不再是编译或运行依赖。

当前包含两种目标，共用一份 PL RTL 和 S1 算法：

- **STM32主方案**：PL采集、FFT/PHAT/IFFT、六对特征、双槽、SPI和PWM保护；STM32负责S1方向求解和动作提交。PS提供时钟、加载与必要平台初始化。
- **PL+PS实验版**：PS接替STM32，通过AXI寄存器读取同一类特征并调用S1，不使用跨板SPI。

两版分别生成自己的独立Vivado工程。当前器件 `xc7z020clg400-2`，Vivado `2025.2`；采集/公共控制61.44MHz，计算及PS侧AXI100MHz。

## 先读这些

1. [目录怎么用](document/directory-guide.md)
2. [迁移了什么、还缺什么](document/migration-report.md)
3. [实际操作入口](document/run-guide.md)
4. [当前状态和下一步](document/current-status.md)
5. [全部33个RTL文件的模块与端口](document/modules/RTL-INTERFACES.html)
6. [这次RTL和BD改动总结](document/rtl-bd-changes.md)
7. [Git与日常协作](document/git-workflow.md)
8. [删除旧项目之前](document/delete-old-project.md)
9. [实际STM32工程配方与完整交接清单](document/stm32-handoff.md)
10. [Vitis裸机平台与application交接](software/vitis/stm32/README.md)

用户外部STM32手工工程已有布线后时序/资源报告（WNS +0.248 ns，WHS +0.036 ns），实际BD/PS/IP配方已接回，详见[交接说明](document/stm32-handoff.md)。本次仅完成静态配置比对，没有重新构建验证仓库配方；真实启动、声学精度、机械闭环及独立PS目标仍未完成。STM32 S2仍按收到的B侧材料标为未实施。

## 三个常用入口

```powershell
# 在自己克隆的 SoundSight 根目录打开终端；工具配置见 document/run-guide.md。
.\project\script\run.bat prepare stm32
.\project\script\run.bat prepare ps
.\simulation\script\run.bat batch samplecdc
```

已存在工程时使用 `open stm32` 或 `open ps`。默认准备动作不会覆盖已有工程。PS板级DDR/MIO与PYNQ由A配置；综合和实现由A点击。详细说明见操作入口。

源代码、模型、约束、IP/BD配方、测试与小型必要结果进入Git。生成工程、仿真数据库、模型权重和旧技术原件本地档案按用途保留，默认不随 `git add .` 推送。

原仓库许可证保留在 [LICENSE](LICENSE)；厂商和外部资料的原许可证/声明继续有效，见 [第三方资料说明](THIRD_PARTY.md)。
