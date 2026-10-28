# 固定阵列与转轴位置配置

用户确认麦克风固定，要求相对位置可在PYNQ配置。本批仅修改PS软件、短入口、测试和说明，无RTL/BD/位流变更。

模型：阵列中心原点，X=DOA 0度，Y=DOA +90度；用户给出转轴XY和可选声源水平距离，单位cm。
无距离不进行视差补偿；有距离先算源点再减转轴坐标，映射成舵机角度。指向轴穿过转轴，安装朝向通过front_deg标定；不是自动测距或机械反馈模型。
原始数值/筛选/3度死区/停止握手不变。未定义方向或越界撤输出，手动角度不叠加补偿。

复验入口（Windows shell测试需将SOUNDSIGHT_TEST_SH设为本机Git bash路径）：

```sh
python -B tools/check_normal_update.py --archive release/output/soundsight_horizontal_update.zip --output document/evidence/ps-horizontal-20261022/geometry
```

实际检查先在`.next.zip`上执行，通过后提升为上述正式文件。12组174项全部通过，日志与checks.json在本目录。
新增7项测试覆盖：所有92160个Q8角在未知距离时与旧映射一致；正负45度/135度已知三角形；零偏移、范围边界、方向奇点；非法数字；真实Client路径撤输出/释放；手动角度；命令保存、两组配置互不覆盖及不访问硬件。
实际shell测试覆盖servo-geometry参数转发和无PYNQ时配置可用。初次新增测试错误地期望非法输入返回2，既有helper实际返回1；修正测试预期后通过，产品失败处理未改。

完整包与增量包29个安装文件逐字节一致；完整包bit/HWH与先前交付完全相同，所有Python文件通过3.8语法检查，见package-check.json。
before-geometry.zip只保存上一次完整包中被本批替换的10项软件/说明/元数据，用于对应之前96项验收记录，不保留整套重复位流包。
检查使用的临时安装目录已自动清理。新几何功能未运行ARM、下载、复位或舵机；参数和实际指向精度仍由实测确定。
