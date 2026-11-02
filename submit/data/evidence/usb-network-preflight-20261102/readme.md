# USB 网络候选离线验证与输入采集

## 最新：USB手动链路与开机依赖补丁已获板端确认

v2已获Windows枚举、SSH登录、WinSCP目录访问实板结果。正常重启后USB服务在`/boot/BOOT.BIN`预检失败；实际挂载者为Type=oneshot的bootpy.service。v3及v2独立drop-in添加Requires/After=bootpy.service，设计经独立复核。用户随后确认v2加drop-in单次服务启动成功，正常重启后可重连；具体身份及范围见[板端结果](board-success.md)。v3全新安装仍未直接板测。原始关键输出、依赖、范围与验证见[本轮记录](boot-order-failure/readme.md)。下方内容是历史阶段，不覆盖本条状态。v2最终包后来也已获独立29项清单/哈希复核通过；早先模型容量失败记录保留。

## 首次板测失败与usb-root-phandle-v2修正

原候选SHA256 `c2074f43fa14189a0f0ec537586b8843aa6b2e62bbea08a1c5aba8b0f9cef42e`已真实板测失败；原ZIP归档`phandle-failure/original-candidate.zip`，用户关键输出归档`phandle-failure/board-output.txt`。下文原“离线通过”保留为当时事实，不代表实板成功。

原包实际走过模块加载、NOP PHY绑定、MIO9检查及GPIO复位命令，第二阶段resolver返回`-ENOENT/-2`，UDC未出现。用户只读确认导出符号是`//soundsight-usb-phy`，实际节点是`/soundsight-usb-phy`，USB0仍disabled。没有物理复位波形证据，不把GPIO读回扩展为电气验收。

根因：该版官方`drivers/of/overlay.c`的`dup_and_fixup_symbol_prop()`直接拼接target_path与path_tail，根目标`/`产生双斜线；`base.c`节点查询不归一化，因此`resolver.c`找不到节点。先前DTC/libfdt离线组合会得到规范路径，遗漏了这版内核差异。独立复核与用户原始bytes一致。

另一个故障定位问题：configfs二进制属性在close时提交，底层错误未反映到用户态close；失败后的ov_id仍可能使status显示applied。官方create失败会清空保存的dtbo，所以修正版写后重开读回完整DTBO，再查live属性，不只信status。

最小修改：PHY目标改`/amba`；通过platform device的of_node寻找驱动绑定；严格验证raw symbol路径与四字节有效phandle；核对USB0实时status/dr_mode/usb-phy/pinctrl-0。保持原两模块的字节、两个阶段的硬件顺序、GPIO复位延迟和原bit/HWH/BOOT/IMAGE不变。

新增3项定向验证：用原失败ZIP复现旧内核拼接规则并拒绝双斜线；raw路径校验拒绝坏值/接受正确值；模拟configfs已applied但DTBO被清空时拒绝成功。当前运行配置器9项通过，重编DTBO、实际树组合和内核5.4符号路径检查通过。没有重编模块，没有重跑无关仿真。新版仍须由用户在正常重启后复测同一start入口；不能称故障已在板上闭合。

本轮DT编译使用独立临时目录并自动清理，没有新增codex_out；保留原失败包和原始输出供复现。最新包身份见本目录package.json及package-manifest.json，原候选身份保留在下文历史记录。

修正版最终ZIP为85942字节、29项，SHA256 `cc54cb589f89ff678c77611672f4c89180b289e3c7d60942a5ecd163e780fecf`。主执行者逐项验证CRC、manifest SHA256和包内新检查报告；报告含`kernel54_symbol_exports`，PHY路径为`/amba/soundsight-usb-phy`，已同步本证据目录。独立审核者对当前源码和新DTBO复核通过，无新增P1/P2，确认两个KO与原包逐字节相同；其后最终ZIP补充审核因模型容量不可用未执行，不将包自检称为独立包审核。修正版仍为待板测候选。

## 后续收件与候选构建

收到用户 `G:/soundsight_usb_inputs.zip`，原样保存在本地本目录 `board-inputs.zip`（含原始启动文件/识别信息，不公开提交；构建需要自行提供匹配采集输入），SHA256 `323c41cc36427e626539c4d8d5174ea144a45b2b3de514c96969c813e45f24b0`。ZIP CRC、12202项文件长度及SHA256全部通过。13项提示全部是DTC include-prefixes目录符号链接跳过，没有启动文件或Module.symvers读取失败。

用户只读SLCR回报：MIO9=`0x1601`，MIO28～39=`0x1201`。硬件独立复核原理图确认：USB0使用MIO28～39、Bank501为1.8V，PHY RESETB由3.3V Bank500的MIO9经二极管吸低，PHY侧1.5k/10uF上拉RC。详细实现采用官方pinctrl，NOP PHY不自行复位，用户态GPIO低20ms再释放等待100ms后才应用USB0控制器overlay；不在线移除overlay。

`BOOT.SCR` 指定 SD0 FAT `IMAGE.UB#conf@1`，FIT使用 `kernel@0`、`fdt@0`；两者内部哈希通过。本任务不改这些启动文件。用户明确当前B已修改应用bit/HWH，未采集其内容；本候选不携带或替换应用位流。

官方来源：`Xilinx/linux-xlnx` 的 `xilinx-v2020.2`，11份原样源/许可证记录在 `software/ps/usb_network/source-receipt.json`。使用实际采集头文件、运行.config及Module.symvers，Linux主机ARM GNU-A 9.2.1交叉编译；原内核GCC9.2.0，不能声称编译器完全相同。构建配置语义对照仅豁免编译器版本文本和版本号；不改目标功能配置。正式入口 `build_modules.sh`、`build_overlays.sh`、`check_artifacts.py`，本机路径只在构建日志/环境参数中出现。

离线验证：

- 两个ELF32 ARM模块 `u_ether.ko`、`usb_f_rndis.ko`；vermagic与实际内核匹配，54/64项导入符号CRC分别通过；独立复核所有强未定义符号均覆盖版本检查、新旧导出无重名。
- DTC编译两份DTBO，`fdtoverlay`依次与采集树组合通过，验证跨overlay符号/PHY/pinctrl引用。既有属性只改USB0的status，USB1保持disabled；新增属性由报告登记。独立复核基础DT与采集的473项非name属性一致。
- `python -B -m unittest discover -s software/tests -p 'test_usb*.py' -v`：9项通过（3项采集器＋6项运行配置器边界测试）。没有模拟USB硬件，也不把主机单元测试算作板测。
- 最终构建日志、检查报告及包清单与本文同目录归档；发布ZIP在 `release/output/soundsight_usb_network.zip`。

独立审核发现并修复：

1. RNDIS function的class/subclass/protocol使用内核 `%02hhx` 解析，`0xe0/0x01/0x03`会截断，已改成`e0/01/03`并在绑定前读回。此为离线发现，没有把错误候选交给板端执行。
2. 服务安装失败不可重试：已改为暂存完整校验后提交，同包同unit允许恢复，enable失败禁用，复制失败和外来unit保护均有定向测试。启用开机服务后回退必须先disable-service再正常重启。

构建失败事实（均为主机环境/准备流程，没有板端失败）：初次缺Python，复用既有离线Python；缺flex/bison/m4与DTC运行库，改在任务目录解包，不做全局安装；原头文件导出未含ARM生成包装/系统调用头及modpost，改用原Kbuild的archprepare与scripts/mod规则生成；无需用于USB模块的证书提取器因缺OpenSSL头文件失败，构建主机辅助工具时跳过该目标，不改变运行内核配置。曾用make --eval补modpost目标导致规则传播递归，已中止并改独立补充Makefile、显式__build目标。完整新目录复现用于确认最终流程不依赖这些排错残留。

尚未验证：实际模块加载、运行时overlay及PHY/UDC、Windows枚举/驱动匹配、SSH/SFTP传输、自动启动/禁用回退，以及当前B版应用运行时的USB稳定性。不得标为整机或USB链路通过。

最终交付记录：全新隔离目录构建成功，两模块与排错完成后的产物SHA256逐字节相同。最终ZIP 84310字节、29文件，SHA256 `c2074f43fa14189a0f0ec537586b8843aa6b2e62bbea08a1c5aba8b0f9cef42e`。独立只读审核者核对manifest覆盖其余28项、源与模块一致、无bit/HWH/BOOT/IMAGE载荷、无发送方绝对路径运行依赖，结论为“PASS（离线候选审核）”，无未关闭的重要发现。不可据此宣称实板通过。

收尾：本任务5个WSL隔离构建目录均在核对无运行进程后删除，详情见`cleanup.json`。未创建codex_out；源码在`software/ps/usb_network`，包在`release/output`，输入/报告在本证据目录。必要的模块/DTBO构建输出和小型主机依赖保留在`software/build/usb-network`供复现，原有其他任务工具链缓存未动。

## 最初的采集助手检查

最初阶段仅准备采集工具；后续模块构建见上文。用户串口回报及使用步骤见 `../../pynq-usb-network.md`。

正式文件：

- `tools/collect_usb_gadget_inputs.py`：只读输入，独占创建输出 ZIP。
- `software/tests/test_usb_input_collector.py`：离线模拟启动文件、二进制设备树属性、内核配置和 build 资料。

执行命令（仓库根目录）：

```text
python -B -m unittest discover -s software/tests -p test_usb_input_collector.py -v
```

Windows 本机 Python 3.14 执行，3 项通过：

1. 用 Python 3.8 语法规则解析采集脚本。
2. 完整模拟输入打包：ZIP CRC 正常、每项 SHA256/字节数一致、含 NUL 的设备树属性及空属性保真、运行配置解压正确、源文件不变、重复运行拒绝覆盖且原输出不变。
3. 缺少 IMAGE.UB：返回 2，manifest 明确记录缺件，仍可取回其余输入，不误报完整。

模拟资料均由测试生成，不能当成真实板端输入。未在 ARM/PYNQ Python 3.8 上运行采集器，未验证真实 sysfs 读取、所有文件权限、启动包可恢复性或 USB 枚举/网络/SSH/SFTP。未作模块 ABI 匹配判断或独立发布签核。

测试使用独占临时目录并自动清理；未创建 codex_out 文件或修改其他任务的临时资料。没有软件编译二进制需要归档。真实采集包待用户回传。
