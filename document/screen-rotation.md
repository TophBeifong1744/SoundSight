# 屏幕和触摸同步旋转180度

2026-11-03。用户屏幕安装方向需要以中心为轴旋转180°。本包默认把画面及触摸坐标同时旋转；不是镜像，也不交换宽高。布局、RGB颜色和按钮逻辑不变。软件仍用800×480逻辑坐标；显示像素及触摸采用(x,y)↔(799-x,479-y)。现有触摸swap/invert校准在旋转转换之前执行。

本包继承CF1_PCM_GAPS_V1和CAPTURE_COOPERATIVE_V1，定位、声纹、舵机参数不变。无需Vivado、位流、HWH或PS引脚修改。安装与启动屏幕由用户执行，初始不开轴。

## 安装

WinSCP上传soundsight_screen_rotation_compat_update.zip到/home/xilinx。先停止当前业务，在屏幕STOP确认后执行：

```sh
sudo systemctl stop soundsight-product.service
sudo python3 /home/xilinx/soundsight_screen_rotation_compat_update.zip --destination /home/xilinx/SoundSight_PYNQ_3D_Speaker
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
python3 -B software/tests/test_screen_rotation.py
sudo systemctl start soundsight-product.service
```

安装更新文件与产品回执、备份旧版本，不启动硬件，不覆盖本地参数/用户档案/日志。已有匹配方向筛选包可直接升级。未知文件修改会拒绝，保留错误，不手工强覆盖。启动服务会沿用现有prepare流程重新准备FPGA和显示，等待屏幕READY；不会自动启动转台。本次不需要整板重启。

屏幕出现后保持轴off，依次点HOME、USERS、SETTINGS、DIAGNOSTICS确认点击位置一致，不用START来试触摸。串口/服务日志显示SCREEN_ROTATION=180 TOUCH_ROTATION=180。离线验证不代替真实触摸复测。此前60秒实麦测试尚未执行，待显示方向确认后继续。

## 持久配置及恢复旧方向

默认180，无须额外参数，P1自动启动和手动panel均生效。如以后恢复原0°方向，在停止服务后执行：

```sh
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
sudo python3 -c "import json; from pathlib import Path; p=Path('screen-orientation.local.json'); p.write_text(json.dumps({'rotation':0})+'\n',encoding='utf-8')"
```

再启动服务。需要180时把0改为180。本文件独立于screen.local.json，切换模式不会覆盖方向；可用CLI --rotation 0/180临时覆盖，不能把它与--invert-x/--invert-y混用来再次翻转触摸。局部方向配置仅影响屏幕，不旋转声源坐标或修改舵机映射。

## 旧版 Pillow 兼容修正

板端原6项测试中导航绘制因 ImageDraw 没有 textbbox 失败；不是坐标测试失败。本次实际UI优先使用textbbox，旧版本使用textsize保持文字裁切，不要求升级Pillow。新增旧API四页面渲染和旋转导航测试，共7项；PC模拟旧API不等于板端实测通过，安装后仍运行上述测试。兼容此前旋转包和方向筛选包安装，保留位流、个人配置与声纹档案。
