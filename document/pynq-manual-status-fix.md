# PS状态位兼容修复：C bridge -2

新RTL的STATUS bit18表示无声标定能力，旧PS C桥误把该位当作保留位。只修改PS桥允许此能力位，随后仍只提取原冻结帧字段给S1；其他保留位/锁帧/六对格式检查不变。RTL、bit/HWH、冻结头和S1源码均不改。

用户原帧sequence=1、STATUS=1015601(0xf7f31)、LEVEL=9766>门限7000、fault/drop=0、motion_requested=false。C桥返回-2，消费0帧，STOP后FAULT=0x40；不是低音量或机械问题。

## 不拔SD、不重载FPGA的现场修复

当前程序已报NORMAL_STOPPED并返回提示符。逐条执行，下条只在上一条成功后执行。不要重启、prepare、清故障或开舵机；保留当前锁帧及原日志。

```sh
cd /home/xilinx/SoundSight_PYNQ_Servo
```

下面是一整行，备份原C文件并只改一个状态检查；重复执行不会覆盖第一次备份：

```sh
sudo python3 -c "from pathlib import Path; p=Path('software/ps/ss_solver_bridge.c'); s=p.read_text(encoding='utf-8'); a='if (status & ~SNAP_STATUS_DEFINED_MASK) return -2;'; b='if (status & ~(SNAP_STATUS_DEFINED_MASK | UINT32_C(0x00040000))) return -2; /* PS manual capability */'; assert s.count(a)==1 or s.count(b)==1, 'STOP: unexpected source'; q=p.with_name('ss_solver_bridge.before_manual_status.c'); q.exists() or q.write_bytes(p.read_bytes()); p.write_text(s.replace(a,b),encoding='utf-8'); print('PS_STATUS_FIXED')"
```

看到PS_STATUS_FIXED后重新编译板端C库：

```sh
sudo sh software/ps/build_solver.sh
```

只读重放已保存日志，不访问MMIO、不消费帧：

```sh
python3 -c "import sys,json; sys.path.insert(0,'software/ps'); from ps_client import Solver; d=json.load(open('logs/normal-real-20211118-065946-343704-658.json')); r=Solver('software/ps/libss_solver.so').solve(d['last_processed_record']['frame']); print(r); assert r['bridge_status']==0, 'STOP: bridge still failing'"
```

应为bridge_status=0。这条原始帧参考结果为direction_valid=0、reason=3、valid_pairs=6，仍被原算法拒绝为无有效方向，不强制产生角度。旧桥提前返回时api_status/reason是初始化值，不能拿旧reason=0说算法通过。

离线重放通过后，保存并排空设备保留旧帧，再进行短轮只测角度：

```sh
sudo sh soundsight.sh drain
sudo sh soundsight.sh run normal --frames 100
```

drain报其他错误就停下保留原文，不继续采集。新一轮正常后，再按完整操作说明调参/标定。

## 文件与验证

仓库software/ps/ss_solver_bridge.c已修复，software/tests/test_solver_migration.py新增真实板帧重放、157组能力位有无数值等价、其余4个保留位负例。原S1 4705项、原157组数值对照及6个桥负例通过。旧C桥真实编译重现-2，修复后真实C桥返回0并与直接S1参考一致。精确串口补丁在旧源码副本执行两次，结果/备份核对通过。首次补丁验证遇Windows默认GBK读取中文源码错误，明确UTF-8后通过，未改变修复范围。

完整release/output/soundsight_pynq_servo.zip同步修复C源码、测试和说明；bit/HWH与修复前逐字节不变。在线板建议用上述串口补丁避免重启丢失现场；以后从完整包安装时必须执行build_solver.sh，不复用旧so。

父级纯Python/假MMIO测试未覆盖真实C桥对新STATUS的检查，这是本次接合漏测。新真实C用例保留为回归；PC通过不等于ARM板端已验证。无RTL仿真、Vivado或硬件动作。
