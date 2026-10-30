# 用户指定T15/W15引脚修正

目标：水平360度舵机T15、垂直220度舵机W15；垂直仍固定LOW，不扩大为双轴驱动。
只修改目标XDC/更新配方、文档和交付包装警示。用户外部工程只读核对，未改写、启动或打开到EDA。

已有工程入口：`project/bd/update_ps_servo_pins.tcl`。预检项目/运行/本地约束/冲突，备份两份XDC后只替换引脚。
从Volume副本完整接入仍用`update_ps_horizontal.tcl`，现在同样输出T15/W15。

实际Tcl测试7项通过：备份、精确两处改动、重复执行、忙运行/原工程/器件拒绝、冲突、重复/未知/缺失约束、外部约束拒绝、注释/大括号/CRLF保持。
原完整更新脚本保护测试4项通过。命令为：

```sh
python -B software/tests/test_servo_pin_update.py -v
python -B software/tests/test_horizontal_tcl.py -v
```

证据为本目录两个log与results.json。初测遇到本机沙箱AppData被Tcl归一化后路径变化，测试夹具改在simulation/work并模拟外部导出包；产品脚本未绕过路径检查。临时夹具自动清理。
对实际F盘Servo约束执行纯文本转换预览，见actual-xdc-preview.diff；读前读后字节一致，未修改F盘。

交付：`release/output/soundsight_horizontal_project_update.zip`更新为11份输入加README。
既有SD完整包bit/HWH和软件保持原样，仅修改README/SOURCE并添加PIN_UPDATE_REQUIRED.txt，明确它还是V7/U7候选；尚不能在T15/W15输出。
软件增量包只刷新说明，不改运行源码。本批没有新的实现时序结果，不复用旧WNS宣称新引脚通过。
用户需自行运行更新脚本、重新实现/生成bit、核对时序/DRC、导出新bit/HWH/XSA。之后再更新完整SD包。
