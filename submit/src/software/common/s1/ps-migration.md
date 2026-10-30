# B → C：二维求解器 ARM Linux 接合

2026-10-20。按 `document/team/pl-ps-migration/README.md` 的新分工推进。
本次 B 第二步（PC 离线自测）完成；ARM 编译、实际调用和耗时尚待目标环境。
器件采用用户确认的 xc7z020clg400-2。旧 CPU0 Linux + CPU1 standalone
环回报告只作历史参考，本轮目标为同一个 Linux/PYNQ 调用 C 共享库。

## 直接使用的文件

- 唯一算法：本目录 `doa_solver.c`、`doa_solver.h`。
- 唯一公共字段：`software/common/fpga_stm32_abi_frozen.h`。
- 现有生产桥：`software/ps/ss_solver_bridge.c`。
- C 负责的 Python 调用：`software/ps/ps_client.py` 中 `Solver`。
- 现有目标构建入口：`software/ps/build_solver.sh`。
- B 本次提供的可重跑测试：`software/tests/test_solver_migration.py`、
  `solver_migration_reference.c`。后者仅用于测试，不加入生产共享库。
- 固定 PC 输入/输出基准：
  `document/evidence/ps-solver-migration-20261020/PC-RESULT.json`。
  每个 `cases[]` 包含 frame、config、expected 和 actual；其中输入是合成数值
  或标准 BIST，不是实录四麦数据。

S1 与 STM32 V3 的算法源码相同。本次没有复制求解器或改变整数舍入、
CORDIC、lag 符号、二维几何和对外接口；没有修改 C 的 Python/生产桥代码。

## 已验证的调用方式

```python
from ps_client import Solver
solver = Solver("software/ps/libss_solver.so")
result = solver.solve(frame, config=None)
```

从仓库根运行时，应把 `software/ps` 加入模块搜索路径；现有 run_capture.py
已在同目录，不需要新建 Python 接口。frame 为 sequence/status/words[30]。
参数定义及 out[12] 含义以团队接口表为准。底层唯一函数为：

```c
int ss_solve_words(uint32_t sequence, uint32_t status,
                   const uint32_t words[30], const int32_t config[7],
                   int32_t out[12]);
```

先检查 bridge_status。负数时不得使用其他结果字段；正数为 S1 API 错误；
0 时还要检查 direction_valid。BIST 可产生有效方向，但 servo_cmd_valid
始终为0。测试中的90°偏置、0～180°范围是示例，不是现场标定值。
合成真实模式用例中的 servo_cmd_valid=1 仅表示软件候选，测试不访问硬件，
不授予动作许可，也不提交角度。

## C 接收后先做什么

提供/记录目标环境的实际输出：

```sh
uname -m
getconf LONG_BIT
python3 --version
gcc --version
cat /sys/devices/system/cpu/online
cat /proc/cmdline
```

已有报告为 PYNQ 2.7.0 / Python 3.8.2 / Linux 5.4.0，仍需确认本次使用的
实际解释器和编译器。旧报告中的 maxcpus=1、DDR预留和CPU1裸机属于旧实验；
C 与 A 对齐最终运行环境，不在本次脚本中修改启动参数、停止CPU或加载ELF。
只跑离线C算法不要求PL已加载，也不要求先启用两个Linux核。

在目标板仓库根执行（不要把PC DLL拷成.so）：

```sh
sh software/ps/build_solver.sh
python3 software/tests/test_solver_migration.py \
  --library software/ps/libss_solver.so \
  --golden document/evidence/ps-solver-migration-20261020/PC-RESULT.json \
  --output software/build/solver-migration/ARM-RESULT.json
```

如实际 PYNQ Python 位于独立虚拟环境，用那个解释器替代 python3。
该测试兼容 Python 3.8，使用标准库，不导入 PYNQ、不访问 MMIO。
它会在目标机编译原S1测试及测试用直接调用适配器，并检查生产.so。
生产库的实际位数/ABI必须与加载它的Python进程一致。

期望终端输出：

```text
MIGRATION_PASS original_s1=4705 equivalence=157 bridge_negative=6
```

将完整输出和 ARM-RESULT.json 返回 B。若失败，保留第一个差异，不改符号、
阈值、舍入或扩大超时来凑通过。ARM共享库本次尚未生成或交付；这一步在C的
目标环境执行并核对结果后，才能标为ARM数值迁移通过。

## 接下来仍需完成

1. B/C：目标ARM构建与同输入对照；B测求解耗时，不能拿PC耗时代替。
2. A直接交C配套bit/HWH；C接真实快照，先双BIST，再真实数据，保存后消费。
3. C测取数、求解和保存的总耗时；512/48000=10.667ms是采样步进，
   不是已经测得的软件耗时。
4. A/C负责现场接合与动作；B分析输入和方向。真实几何、通道及机械标定
   齐备后再接闭环。BIST和本次离线测试均不启用动作。

本次测试输出在软件build内生成，临时可执行文件/DLL自动释放并清理。
仓库只提交测试源码、必要结果及本说明，不提交Windows二进制或伪称ARM产物。
