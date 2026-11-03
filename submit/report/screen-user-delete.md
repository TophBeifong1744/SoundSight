# 触屏删除指定声纹档案

本更新继承180度屏幕/触摸和旧版Pillow兼容修复、CF1方向筛选修复。仅PS软件变化，无需Vivado或新位流。

## 安装

先在屏幕STOP并等到STOP verified。WinSCP上传soundsight_screen_user_delete_update.zip至/home/xilinx，逐条执行：

```sh
sudo systemctl stop soundsight-product.service
sudo python3 /home/xilinx/soundsight_screen_user_delete_update.zip --destination /home/xilinx/SoundSight_PYNQ_3D_Speaker
cd /home/xilinx/SoundSight_PYNQ_3D_Speaker
python3 -B software/tests/test_speaker_delete.py
python3 -B software/tests/test_screen_rotation.py
sudo systemctl start soundsight-product.service
```

两项测试OK后再启动服务。测试只用临时虚拟档案，不删除真实用户或操作硬件。安装器保留用户档案、参数、日志和位流，并备份旧程序。

## 删除操作

1. STOP / AXES OFF，等待IDLE和STOP verified。
2. USERS → Next user，核对Candidate。**删除对象是Candidate，不一定是Current当前识别目标**，不用先SELECT。
3. DELETE candidate → 确认框完整显示USER姓名。CANCEL或底部STOP都取消；确认删除需要松手后另按CONFIRM DELETE，长按或滑动不会连续触发。
4. 等待完成，显示Deleted姓名，列表刷新。若档案在确认期间改变，必须重新打开确认框，不删除变化后的档案。
5. 删除当前目标会清空目标和声纹门限，保留明确的“未选择”状态，不回退到P01。重新录入/SELECT用户、无轴测试评分并配置门限后，才能重新开启声纹跟随。删非当前用户不改现有目标与门限。

## 范围

- 删除该用户speaker-profiles下的profile.json及同目录evaluation.json（若有），随后移除空目录；不递归删除未知文件。
- 内置P01与模型基线共用验证资产，禁止删除。P02及自行录入的用户可删。
- 历史录音、测试日志、外部备份保留。此功能是移除识别档案，**不是个人数据彻底擦除**；不会沿录音路径删除文件，也不影响他人的数据。
- 不自动启动转台。运行/录音中、STOP未确认、另一进程占用设备时拒绝删除。
- 异常路径、链接、用户ID不一致、未知目录内容会拒绝，保留错误供排查。
- 存储错误可能已清空许可而未删完；保留报错，不自动恢复旧许可或宣称删除成功。

## 注册自己的声纹

USERS → NEW voice → 建议5秒 → RECORD new voice → 等待SPEAK NOW后持续自然说话 → 等到Saved → USERS选择新用户SELECT。录入时关闭双轴，成功后不自动选择或启用跟随。

板端删除与触摸验收仍由用户完成，PC回归通过不等于板端验收完成。建议先录入一个临时测试用户，先CANCEL验证保留，再确认删除验证其他用户和当前配置不变。
