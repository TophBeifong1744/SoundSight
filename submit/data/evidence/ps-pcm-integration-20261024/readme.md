# Reliaze PCM接入候选验证

日期：2026-10-23至24。范围：作者定向自测、隔离Vivado工程准备、文件核对。不是独立签核、综合/实现、板测或声纹闭环验收。

## 结果

- `audio`：四通道交错、S24极值符号扩展、包头/长度/TLAST、周期背压稳定、512步进定位窗、停止半包、满FIFO显式停止、会话复用拒绝、DMA复位与重新采集通过。
- `audiotime`：人为设置源计数器起值，覆盖低32位进位；暂停读时钟填满跨域FIFO，确认源采样计数仍前进、故障跨域及停用恢复。不是运行了2^32个真实采样。
- `audiometa`：通过实际AXI-Lite事务读取PS扩展区，确认时间元数据随双槽锁定/消费，下一帧不能改旧锁帧，总线复位保留快照，BIST没有真实音频关联。
- `audiostore`：原特征输出槽的元数据背压保持、满时丢新、取消失效及恢复通过。
- `manual`：原无声手动标定回归通过，含限位、看门狗、STOP排尾和模式互斥。
- `duallevel`、`dualaudio`：官方FFT/IFFT完整链路各完成正常、在途STOP取消、恢复共3帧；开启音频时间扩展后，正常帧音量和六对结果保持原判据，增加源窗口编号/采样范围/取消有效性检查。
- Tcl静态加载与保护测试5项通过：脚本完整性、拒绝原Servo、拒绝仓库内工程、拒绝错误器件、拒绝活动运行。
- Vivado 2025.2在隔离副本执行统一脚本，首次接入、重复执行均完成Validate与输出生成。最终RTL更新后再次通过。没有打开用户原始工程，也没有执行综合、实现、bit生成或硬件操作。
- `bd-audit.json`核对保存后的BD、原外部端口/旧接口/时钟复位组件、原显式PS参数、IRQ变更、地址、DMA位宽及17份候选文件。它记录文件对应关系，不代表物理结果。

仿真结果和原生日志在 `simulation/<case>`；原始仿真运行目录及命令见 `tests.json`。同候选相关源码与仿真输入副本已经逐字节核对。实际麦克风输入、PYNQ续接速度、DMA写DDR行为和声纹推理尚未板测。

## 复现入口

```powershell
python tools/run_sim.py audio
python tools/run_sim.py audiotime
python tools/run_sim.py audiometa
python tools/run_sim.py audiostore
python tools/run_sim.py manual
python tools/run_sim.py duallevel
python tools/run_sim.py dualaudio
python -m unittest discover -s software/tests -p test_reliaze_tcl.py -v
```

实际工程接入使用 `project/bd/update_ps_reliaze.tcl`，运行前提见 `document/ps-pcm-integration.md`。保存前后BD后，可用 `tools/check_reliaze_bd.py --before ... --after ... --sources ... --output ...`只读核对。工具位置由现有本机配置提供。

## 原件与失败事实

`bd/before.bd`、`bd/after.bd`、`bd/first-repeat.log`和`bd/final-candidate.log`为隔离工程原件。`bd/fixture-only.hwh`仅供这次结构核对，不配套位流，不能替换板端HWH。日志、BD和路径清单中的临时绝对路径是历史来源，不是交付包运行依赖。

准备隔离夹具时曾遇到：沙箱Tcl Store初始化包不可见、失败初始化留下工程、带空格路径未包装成Vivado文件列表、BD放置目录不合Vivado规则。分别改为进程内加入安装目录的包索引、打开已创建夹具、使用Tcl列表、按`.srcs/sources_1/bd`放置。没有重置用户Tcl Store或修改全局工具配置。相关原始输出在 `failures/fixture-*`。恢复过程中重复登记FFT产生的同名IP警告保留；最终更新日志不包含该夹具登记步骤。

音频TB初次编译因混合声明带初始化的wire失败，已修正TB声明。时间进位TB初次在XPM仍处于复位忙期间注入数据，触发设计预期的丢样故障；诊断原件显示 `ready=0,busy=1`，改为先等FIFO准备好再开始进位用例，另行保留真正的填满故障刺激。未修改产品代码去屏蔽该故障。

原生工具还报告本机Tcl Store/无关开发板目录警告、首次模块端口增加提示，以及DMA传播试图把内存宽度改成32但被明确的64位设置拒绝。最终保存的DMA配置、HP0配置和生成接口按64位核对；保留警告，不把工具返回0当作没有警告。

## 未完成范围与整理

资源增量、布线拥堵、STA/CDC/RDC物理报告、用户Reliaze实际运行统一脚本、PYNQ环境、DMA板端持续接收及真实录音均未完成。后续需要用户构建同候选并提供报告；此包不自动执行这些动作。

有效RTL和入口位于 `project/rtl`、`project/bd`，测试位于 `simulation/tb`与`software/tests`，交付包位于 `release/output/soundsight_reliaze_update.zip`。隔离工程用途完成后清理本任务的 `codex_out/pcm-integration`；上述必要原件已归档。仿真运行目录仍按项目`simulation/work`约定保留，本任务不清理其他工作。
