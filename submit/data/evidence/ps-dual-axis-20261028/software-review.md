# 三维在线与双轴PS接合验证

2026-10-28；产品源码在`software/tetra3d/linux`，入口`soundsight-3d.sh`，实际板端未安装。原二维`run_normal.py`仅增加可选状态/显示/最终输出钩子，以及独立尝试两个STOP清理入口，二维默认调用方式保持。

## 真实执行结果

- `software-tests.json`：在线21、原normal17、filter13、manual8、volume15、原shell12、新shell13，共99项主机测试通过。新在线模型覆盖默认无动作、音量/无效组/序号跳变撤目标、空间绕回/极点/离群筛选、单轴及双轴同帧提交、无声手动、租约不自动恢复、故障不消费、正常收尾寄存器失败仍尝试STOP、统计和debug上界。
- `three-d-numeric.json`：154组C/独立解析期望与参考接口数值对照、155组PS能力位兼容、28个桥接负例、15个几何检查通过。该文件含实际合成输入、预期/输出及原C测试结果；AMD64耗时不等于ARM服务预算。
- `launcher-tests.json`及两个txt：真实Git Bash/Python执行短入口，含旧PYNQ_PYTHON失效回退、带空格路径、无可用PYNQ必须停止；check/配置不需要PYNQ，manual需要。只替换板端不存在的路径和PYNQ替身，不访问硬件。
- `package-check.json`、`package-step-0..3.txt`：实际解压最终ZIP、检查每项源码与仓库一致、Python3.8语法，安装到带空格接收目录，再执行21项在线测试和154组C数值对照；重复安装成功、旧源码存在备份、6类个人数据/原bit/HWH未改、缺依赖接收目录在写入前拒绝。测试临时树已清除。

正常模式没有每帧写盘；debug显式限定最多1000帧，加最多2个STOP尾帧，停止后才通过父进程保存。内存和输出上界不等于实际ARM长稳验证。筛选用单位向量上的平方弦距中心和角距阈值，单组O(N)，避免在每次收满时做N²次acos；20/12、10°、2/3、3°为初始策略，实际声学效果仍需测。

## 修正与失败事实

- 独立复核发现DA-SW-001：扩展撤许可MMIO失败可能跳过旧STOP/SYS路径。已修为两个清理动作独立尝试，并汇总错误；对STATE读失败、A4写失败补测试。手动收尾也对扩展访问失败提供旧STOP/SYS尝试。不能把“尝试停止”写成故障条件下必然机械停到位。
- 首轮旧shell测试12项失败是未提供Windows POSIX shell路径，见`test_launcher_environment_failure.txt`及`software-tests-initial.json`。只在测试进程提供`SOUNDSIGHT_TEST_SH`后旧12、新13通过，没有为这个环境问题修改产品逻辑。
- FPGA两项复核修正和原仿真失败见本目录README，PS测试没有替代RTL/PWM检查。

## 非作者复核

独立只读上下文`/root/dual_axis_review`从需求、接口及原始代码/日志核对，未参与产品或测试写入，独立运行21项在线测试通过。确认DA-001、DA-002、DA-SW-001闭合；源码/主机离线范围无开放BLOCKER/HIGH/MEDIUM。实际ZIP CRC、32项内容及源码一致性由该上下文核查，未含bit/HWH、私人录音/模型或local配置。其初次终报时隔离安装和归档21项日志尚待更新，补齐后同一上下文确认源码、主机离线及增量交付范围通过，99项归档结果和安装测试已核。最后仅把debug汇总的retention标签写成bounded_debug_ram_before_consume，数据路径与边界未改。

## 复现命令

```text
python -B software/tetra3d/tests/test_online_3d.py
python -B software/tests/test_normal.py
python -B software/tetra3d/tests/test_solver_3d_migration.py --cc <本机gcc> --output <结果JSON>
python -B software/tests/test_three_d_launcher.py
python -B tools/package_three_d_update.py
python -B tools/check_three_d_update.py --cc <本机gcc>
```

Windows shell测试需在当前测试进程设置`SOUNDSIGHT_TEST_SH`为Git Bash，不写公共脚本默认路径。详尽命令/日志见相邻JSON和txt。

没有启动Vivado实际工程、综合实现、下载、复位、声源或舵机动作。未证明ARM连续三维、通道排列、机械映射、W15真实输出、同时声纹/三维负载或实板长期稳定。软件包没有新bit/HWH；用户生成同候选产物后才补完整SD包。
