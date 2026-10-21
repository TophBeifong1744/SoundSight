# PYNQ 上传包：先做不运动验证

本包采用同一个 Linux/PYNQ 管理两个 ARM 核。CPU1 的进程独占硬件寄存器并调用 C，CPU0 的进程控制会话、显示和保存。当前硬件为二维方位、水平轴接口，`ACTUATOR_BOUND=0`，本轮不驱动舵机。

2026-10-21补充：当前板已完成双BIST和20帧真实无动作采集；100帧尝试暴露逐帧SD同步导致的溢出。已增加显式RAM接收策略，SD搬运、旧镜像的XRT/FCLK加载修正及新版操作见 [pynq-ram-queue.md](pynq-ram-queue.md)。以下保留首次安装步骤；已经安装的板只需要增量，不能覆盖实验日志。新版RAM路径仍待板上复验。

## 第一步：上传、解压、检查环境

在 Jupyter 新建一个空文件夹，把 `soundsight_pynq.zip` 上传进去。在同一文件夹新建 Python 3 Notebook，执行：

```python
from pathlib import Path
from zipfile import ZipFile

target = Path("SoundSight_PYNQ")
if target.exists():
    raise RuntimeError("该目录已经存在，请进入原目录继续；不要覆盖已保存的实验记录。")
with ZipFile("soundsight_pynq.zip") as archive:
    archive.extractall(".")
```

接着在另一个单元执行：

```python
%cd SoundSight_PYNQ
%run tools/pynq_preflight.py
```

这一步只读取环境和 HWH；不加载位流、不访问硬件寄存器、不复位、不采集。

预期 `result` 为 `READY_FOR_ARM_OFFLINE_TEST`，`allowed_cpus` 包含 0 和 1，`ps_link` 地址为本次 HWH 的实际地址，`actuator_bound` 为 `"0"`。把完整输出返回后再继续；如果只有 CPU0，不要把 CPU1 的旧裸机程序加载进去，也不要直接照抄修改启动参数。

## 第二步：板上编译与数值对照

确认第一步环境正常后，在相同 Notebook 工作目录执行：

```python
!sh software/ps/build_solver.sh
```

编译成功后执行；使用当前 Notebook 的解释器，避免系统 Python 与 PYNQ 环境不一致：

```python
import subprocess
import sys

subprocess.run([
    sys.executable, "software/tests/test_solver_migration.py",
    "--library", "software/ps/libss_solver.so",
    "--golden", "document/evidence/ps-solver-migration-20261020/PC-RESULT.json",
    "--output", "software/build/solver-migration/ARM-RESULT.json",
], check=True)
```

正确标记是：

```text
MIGRATION_PASS original_s1=4705 equivalence=157 bridge_negative=6
```

返回完整终端输出及 `ARM-RESULT.json`。这一步仍然不需要加载 PL，不访问 MMIO，也不授权运动。PC 已通过不代表这一步自动通过；包内没有 Windows DLL 或预先冒充 ARM 的共享库。

## 后续：硬件加载、双 BIST、真实取数

前两步完成后，再指导加载同名 `soundsight.bit` 和 `soundsight.hwh`，确认 100/61.44 MHz 时钟、冷复位释放和寄存器 ID/ABI。当前两路复位有不同用途，不能为了能读寄存器就把两路合并或盲写复位寄存器。

硬件核对完成后的正式入口为 `software/ps/run_smp.py`，单进程 `run_capture.py` 留作诊断；不要同时启动两个取数程序。先拒绝 BIST、通过 BIST，再真实音频取数和保存。BIST 一次仅一帧，不请求运动。运行命令和恢复方法见 `software/ps/运行说明.txt`。

只读查看硬件描述可在前两步期间执行：

```python
from pynq import Overlay
description = Overlay("soundsight.bit", download=False)
print(description.ip_dict.get("ps_link"))
```

`download=False` 不下载位流。不要将描述解析成功当成 MMIO 已接通。

## 文件与边界

- `soundsight.bit`、`soundsight.hwh`：A 本次 PS 工程产物；打包时核对二者与 A 的 XSA 内文件逐字节一致。
- `software/common`：冻结 ABI、唯一 S1 算法及其测试。
- `software/ps`：C 的双进程运行程序、C 桥、板上构建入口。
- `software/tests`、PC 基准：B 的同输入数值对照及必要软件测试。
- `tools/pynq_preflight.py`：只读环境检查。
- `SOURCE.json`：软件版本和硬件来源说明，仅供交接追溯，不作为运行门槛。

XSA、Vivado 工程缓存、Windows 编译产物及本机工具配置不需要上传到 PYNQ。包里的 PC/实现报告用于说明已有证据，不等于 ARM、实采或机械闭环通过。硬件时序 WNS=+0.278 ns、WHS=+0.036 ns；DRC 仍有流水线/异步控制等警告，不能称作零警告或完整 CDC/RDC 通过。

如异常，应保留输出与已有记录。恢复未消费帧时不重新下载位流、不冷复位；动作记录不等于机械到位。双轴接口仍待后续交付，不影响这次无动作取数验证。

## 在开发电脑重打包

从仓库根目录执行，参数使用实际工作工程和XSA位置：

```text
python tools/package_pynq.py --hardware-project <外部PS工程目录> --xsa <同次导出的XSA路径>
```

输出为 `release/output/soundsight_pynq.zip`，根目录为 `SoundSight_PYNQ`。脚本只读外部工程，核对XSA内的bit/HWH与待打包文件一致；不运行Vivado。已有同名包时拒绝覆盖，可用 `--output` 指定本次诊断输出；核实旧包用途结束后再替换正式入口，不按日期永久堆放多套交付。
