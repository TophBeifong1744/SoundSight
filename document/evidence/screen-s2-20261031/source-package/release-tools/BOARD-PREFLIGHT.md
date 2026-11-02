# 用户回传的板端只读信息 — 2026-10-31

原始命令只读 `/proc/device-tree`、`/sys/class/i2c-adapter`、平台设备目录与 `/dev`，未探测总线或修改硬件。

```text
{"node": "/proc/device-tree/amba/i2c@e0004000", "status": "disabled ", "compatible": "cdns,i2c-r1p10 ", "clock-frequency": "00061a80", "reg": "e000400000001000"}
{"node": "/proc/device-tree/amba/i2c@e0005000", "status": "disabled ", "compatible": "cdns,i2c-r1p10 ", "clock-frequency": "00061a80", "reg": "e000500000001000"}
PATH= /sys/class/i2c-adapter EXISTS= True
PATH= /sys/bus/platform/devices EXISTS= True
PATH= /sys/kernel/config/device-tree/overlays EXISTS= True
DEV_I2C= []
KERNEL= Linux version 5.4.0-xilinx-v2020.2 (oe-user@oe-host) (gcc version 9.2.0 (GCC)) #1 SMP PREEMPT Wed Aug 27 07:20:50 UTC 2025
```

没有适配器或匹配平台设备条目输出。两个PS I2C节点均禁用，当前DT标称400kHz。动态overlay配置接口存在，但尚未证明模块、时钟和启用后的驱动绑定可用。

S2准备入口仅对已有真实路径`/amba/i2c@e0004000`应用`status=okay`及`clock-frequency=100000`，保留clocks/interrupts/reg等原配置，不修改I2C1。必须在匹配S2位流加载后操作；不修改启动分区或执行整套ps7_init。
