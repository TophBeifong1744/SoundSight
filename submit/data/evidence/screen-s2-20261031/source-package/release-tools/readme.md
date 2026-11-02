# SCREEN_PS_I2C_S2

本候选把触摸通路从 PL AXI IIC 改为旧成功屏幕工程使用的 **PS I2C0 → EMIO**。RGB显示、屏幕GPIO、音频、三维/声纹业务和J3舵机引脚保留；没有新增ILA。

旧工程是裸机，本候选通过Linux Cadence I2C驱动和i2c-dev执行组合事务，不把旧C程序直接搬入运行中的Linux。用户已回传I2C0/I2C1均disabled、无适配器、configfs动态设备树可用；仅启用I2C0并设置100kHz，不改I2C1或启动分区。

两个交付文件（仅在构建及独立复核通过后生成）：

- `delivery/soundsight_screen_ps_i2c_s2.zip`：现有PYNQ运行目录的SD更新包，包含匹配bit/HWH、屏幕驱动和预编译DTBO。
- `delivery/soundsight_screen_ps_i2c_s2_source.zip`：可重建硬件源码/约束/脚本、输出、屏幕软件和验证资料。主构建入口`build.bat route`，不包含私有声纹资产或替代A的全部PS业务工程。

原开发工程`F:/NUEC/ss-screen-s1`及S1/S1a/S1b文件保留，新工程在`F:/NUEC/ss-screen-ps-i2c-s2/project/par/SoundSight_PS_3D.xpr`。新软件在`F:/NUEC/ss-screen-ps-i2c-ui-s2`。

板端步骤见[SD-INSTALL.md](sd-install.md)。安装仅修改运行目录文件，先备份、保护已知版本；不会自动下载位流、启用设备树或启动动作。新安装后须重启，再按步骤prepare/apply。板端实际触摸结果仍待回传，不能据此声称已修复或整机验收。
