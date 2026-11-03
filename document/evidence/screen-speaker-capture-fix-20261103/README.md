# CAPTURE_COOPERATIVE_V1 离线验证与故障依据

## 来源和结论

- `B-diagnostic-original.md` 是用户提供的原件，SHA256 为 `b6188a036194c9a0fe2a073a10d3b1806718d6ea3c9c3da597674d4b02b4f32f`。其中的本机路径属于历史记录，不是本修复的运行依赖。未收到它引用的完整失败 JSON，不能声称已复算该实板会话。
- 程序基线是本地 main `d78efe2` 的 CF1A + 原始 P1 ZIP，四个被改动的 CF1A/入口文件与现有完整运行 ZIP 内容逐一比较（忽略 CRLF/LF）一致。P1 产品代码来自原包，不将整段 P1 引入冒充为本次新设计。
- 新增收包检查点解决可复现的同步历史补算期间无人收包的问题；没有证明这就是所有板上停机的唯一原因。新日志用于进一步区分计算、提交、显示与调度间隔。
- UI 恢复使用已有寄存器，不修改位流或放宽声音、身份和机械限制。原失败保持 FAIL；恢复不等于采集测试通过。

## 自测

Windows 11、Python 3.14.6、NumPy 2.4.6；C 求解器用本机 MinGW GCC、C99、O2、Wall/Wextra/Wconversion/Wshadow/Werror/pedantic 编译为本机共享库。此库仅供 PC 测试，不进入 SD 包。

|测试|数量|结果|
|---|---:|---|
|CF1A 数值、固定输入窗口、服务检查点、收包所有权|16|通过|
|声纹 TTL、联合运行故障及停止保护|27|通过|
|显式采集恢复、保存失败、复位失败、屏幕确认|8|通过|
|P1 生命周期、界面、安装与回滚|43|通过|
|三维滤波、限位、命令与停止规则|21|通过|
|纯声源模式与声纹模式分离|7|通过|
|合计|122|通过|

完整输出是同目录 `test_*.log`；环境及返回码见 `checks.json`。

Windows 缺少 `resource`，前两项测试仅为导入未使用的 Linux RSS 统计模块提供空占位，不提供任何 resource 函数；若测试调用它会失败。未模拟或宣称验证 Linux 内核调度。现有 WSL Debian 没有 Python，未修改其系统环境。板端仍须运行原始测试和真实联测。

复现 PC 数值库构建（在仓库根目录，GCC 在 PATH）：

```text
gcc -std=c99 -O2 -Wall -Wextra -Wconversion -Wshadow -Werror -pedantic -shared -Isoftware/common -Isoftware/common/s1 -Isoftware/tetra3d/core software/tetra3d/linux/ss_solver_3d_bridge.c software/common/s1/doa_solver.c software/tetra3d/core/doa_solver_3d.c software/tetra3d/core/doa_geometry.c software/tetra3d/core/doa_target_3d.c -lm -o software/tetra3d/linux/libss_solver_3d.so
```

Windows 前两组测试入口（将路径分别替换为表中对应测试）：

```sh
python -B -c "import sys,types,runpy; sys.modules['resource']=types.ModuleType('resource'); runpy.run_path('software/tetra3d/tests/test_cf1.py',run_name='__main__')"
```

其余直接 `python -B 测试路径`。Linux 使用原始测试入口，不注入占位模块，按 `build_solver_3d.sh` 构建 Linux 库。

额外检查：使用真实原始运行 ZIP + P1 ZIP 建立临时安装树，再安装本更新包两次；验证配置未变、S2/P1 回执与安装内容相符、没有 start/restart/reboot 调用，结果通过。临时安装树已自动清理。ZIP CRC、载荷 SHA256、未知基线拒绝与无本机路径依赖检查通过。

## 板测尚未完成

需回传屏幕关闭的 SPEAKER axes-off、屏幕开启的 axes-off/both，以及两轮 START/STOP/恢复日志。操作见 `../../screen-speaker-capture-fix.md`。不可把调度模型的 3 ms 步长当成 ARM 实测耗时，不可将本次 122 项 PC 测试写成板上验收。

本次工作在独立 `codex/screen-speaker-capture-fix` 工作副本中完成，以免覆盖主聊天在途代码。工作副本保留至本板复测及集成完成；临时测试共享库已删除，交付 ZIP 位于 release/output。未推送远端或切换主目录分支。
