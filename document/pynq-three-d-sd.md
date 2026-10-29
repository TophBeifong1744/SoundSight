# 三维双轴版：SD卡安装与首次运行

> 2026-10-29 W16新位流已收件并更新联合SD包。水平T15、垂直W16；安装及复测见 [W16更新说明](pynq-w16-update.md)。旧10月28日报告仅属旧候选。

> 2026-10-28 维护说明：当前 `run --axes` 已进入声纹许可路径，需要 B 的配套运行程序和资产；纯测角与无声手动标定独立可用。公开仓库与私有联合包的边界见 `document/rtl-3d-maintenance.md`。以下早期构建/测试记录按当时范围保留。

完整包为 `release/output/soundsight_pynq_3d.zip`，解压后是独立目录 `SoundSight_PYNQ_3D`。包含用户从 Reliaze 副本生成的同批 bit/HWH、三维C/Python程序、短命令、依赖、自测与报告。不包含B的声纹模板/录音，不覆盖原声纹程序，不重装PYNQ镜像。硬件保留PCM/DMA；三维与声纹仍不能由两个程序同时占用采集设备。

## 首次安装

1. 将 `soundsight_pynq_3d.zip` 复制到Windows可见的SD分区根目录。保留BOOT.BIN、BOOT.SCR、IMAGE.UB、boot.py、REVISION。
2. 停止并保存原程序，正常关机。将SD插回板子并开机进入Linux串口。
3. 下列为第一次安装。若已有同名3D目录，先退出程序并备份该目录，不直接覆盖个人设置或日志。

```sh
ls -lh /boot/soundsight_pynq_3d.zip
python3 -m zipfile -e /boot/soundsight_pynq_3d.zip /home/xilinx
cd /home/xilinx/SoundSight_PYNQ_3D
sudo sh soundsight-3d.sh prepare
```

`prepare` 自动寻找可导入PYNQ的Python，编译两份本机ARM求解库、运行离线自测，然后加载本包位流、准备100MHz FCLK0并核对ID/ABI与双轴能力。默认不采集、不驱动舵机。旧Python环境变量失效时自动回退。首次运行需要板上的gcc；现有PYNQ镜像已经确认有gcc。

单独只编译和自测而不加载FPGA：`sudo sh soundsight-3d.sh check`。程序遇到尚未保存的旧槽或异常会停止并保留状态，不通过重载掩盖；按原原因处理后可用 `sudo sh soundsight-3d.sh drain` 保存旧槽。

## 先测角，不动舵机

先确认四麦实际声孔组成边长40mm的正四面体，CH0～CH3对应关系与 `software/tetra3d/core/tetra40-nominal.json` 一致：CH0前下、CH1左后下、CH2右后下、CH3顶；坐标+X前、+Y左、+Z上。未核实通道时可以检查数据通路，但方位/俯仰不能算已标定正确。

```sh
sudo sh soundsight-3d.sh level 7000
sudo sh soundsight-3d.sh filter 20 12
sudo sh soundsight-3d.sh run --frames 100 --debug
```

7000只是初始调试值。20表示每组总帧数，12表示最低合格一致帧数；已有10°筛选、2/3共识和3°空间死区不变。串口每0.5秒输出英文方位/俯仰或无输出原因。短调试最多1000帧，暂存在RAM，停止后保存到logs；突然断电可能丢失未保存内容。

角度确认后持续只测角：

```sh
sudo sh soundsight-3d.sh run
```

Ctrl+C正常停止、排尾并保存有界统计。默认AXES=off，未选轴不会启动PWM。

## 以后每次开机

```sh
cd /home/xilinx/SoundSight_PYNQ_3D
sudo sh soundsight-3d.sh prepare
sudo sh soundsight-3d.sh run
```

level与filter设置保存在本目录。3D窗口/统计不会自动同步B的声纹配置。

## 手动与跟随

水平输出T15、垂直W16，均Bank34/LVCMOS33。先完成小范围机械标定；无声手动、限位配置、单轴/双轴跟随及阵列相对转轴设置，统一见 [完整操作说明](pynq-three-d-dual-axis.md)。例如：

```sh
# 只保存初次小范围示例，须按实际机械安装确认
sudo sh soundsight-3d.sh servo-config horizontal 180 1 170 190
sudo sh soundsight-3d.sh servo-config vertical 110 1 100 120
# 显式手动，不需要声音，三秒后撤输出
sudo sh soundsight-3d.sh manual --horizontal 185 --seconds 3
sudo sh soundsight-3d.sh manual --vertical 115 --seconds 3
# 两轴均已标定、声学方向确认后，才显式开启跟随
sudo sh soundsight-3d.sh run --axes both
```

再次运行不带 `--axes` 的run就回到只测角。程序不会保存“下次自动开转台”。水平360°位置舵机不等于无限旋转，跨±180°时可能发生端到端转动；先保持合适机械限位。

## 当前证据范围

本包对应2026-10-28用户完成的SoundSight_PS_3D。实现资源/内部时序和原布线补查见包内reports；仓库中完整原报告与补查放在 `project/reports/ps_3d`。补查只为已完成布线增加内存中的垂直PWM 20ns最大延迟预算，没有重新综合/实现或生成位流；原bit逐字节保留。PWM无外部同步采样时钟，外部保持时间不适用，不能把这一点当作舵机电气/机械实测。

尚需板端ARM三维运行、实际通道和角度核对、两轴机械标定与跟随测试。旧声纹/二维板测不能替代这些验证。XSA与Vitis工作区不是本次PYNQ运行依赖。
