# PYNQ USB 网络维护

操作入口见仓库`document/pynq-usb-network.md`，交付包为`release/output/soundsight_usb_network.zip`。本目录维护Linux运行助手、两阶段设备树及匹配内核的模块构建配方，不修改PL位流或启动镜像。

板端已验证的是`usb-root-phandle-v2`加`10-bootpy.conf`，含手动启用、Windows枚举、SSH、WinSCP目录访问以及用户确认的正常重启后重连。`usb-boot-order-v3`在新安装时直接生成相同Requires/After依赖。已工作的板端保持v2加drop-in即可，不必覆盖/opt安装目录；安装器会拒绝不同版本覆盖。

## 文件职责

- `usb_network.py`：只读check、一次性start、status、开机服务安装/禁用。失败留下状态标记，不能在线移除overlay或反复复位。
- `usb-pins-phy.dts`：先建pinctrl与PHY，PHY位于/amba，避免Linux5.4根路径双斜线缺陷。
- `usb-controller.dts`：GPIO9复位完成后启用USB0 peripheral，USB1保持disabled。
- `10-bootpy.conf`：既有v2服务的增量依赖配置；/boot由本板bootpy.service挂载。
- `vendor/linux-xlnx`及`source-receipt.json`：官方xilinx-v2020.2源码/许可证与来源哈希，按原许可证保留。
- `build_modules.sh`、`build_overlays.sh`、`check_artifacts.py`：主机离线构建与核验，禁止据此宣称板测通过。
- 仓库`tools/collect_usb_gadget_inputs.py`：采集本板内核/启动/设备树输入；`tools/package_usb_network.py`：生成交付ZIP。

## 重建输入和命令

运行脚本兼容板端Python3.8；主机构建使用Linux、Python3.9+、make、gcc、bison、flex、m4、dtc/fdtoverlay和ARM GNU-A9.2.1交叉工具链。原内核GCC9.2.0，构建器允许编译器版本元数据差异但验证目标配置/符号CRC。

`document/evidence/usb-network-preflight-20261102/board-inputs.zip`是本机原始采集，不公开提交；其SHA256为`323c41cc36427e626539c4d8d5174ea144a45b2b3de514c96969c813e45f24b0`。它包含原始启动二进制和板级识别数据。已有交付包可以直接使用；从源码完全重建需要此匹配输入及工具链。更换内核或硬件必须重新采集、核对电气/设备树，不能只改版本号绕过预检。

在仓库根目录运行，下面工具链路径为示意，应替换成本机实际路径：

```bash
bash software/ps/usb_network/build_modules.sh document/evidence/usb-network-preflight-20261102/board-inputs.zip /path/to/arm-toolchain.tar.xz software/build/usb-network
SS_HOST_TOOLS=/path/to/unpacked-host-tools bash software/ps/usb_network/build_overlays.sh document/evidence/usb-network-preflight-20261102/board-inputs.zip software/build/usb-network
python3 -B software/ps/usb_network/check_artifacts.py document/evidence/usb-network-preflight-20261102/board-inputs.zip software/build/usb-network
python3 -B -m unittest discover -s software/tests -p 'test_usb*.py' -v
python3 -B tools/package_usb_network.py
```

设备树构建强制要求SS_HOST_TOOLS，不能仅把DTC装入PATH。该变量必须指向解包根目录，其下应有usr/bin/dtc、usr/bin/fdtoverlay及usr/lib/x86_64-linux-gnu中的libfdt等依赖。可先把适配主机的Debian工具包放入software/build/usb-network，再执行`bash software/ps/usb_network/unpack_host_tools.sh software/build/usb-network`，并将SS_HOST_TOOLS设为生成的host-tools绝对路径。模块构建则可以使用系统PATH中的主机工具或同一个SS_HOST_TOOLS。

SS_HOST_PYTHON是可选Python路径覆盖；不要把安装路径写进公共脚本。模块脚本为诊断保留/var/tmp/soundsight-usb-build.*并记录native-work-paths.txt；确认产物/证据已归档、无运行进程后清理本批目录。设备树构建使用自己的临时目录并自动清理。

本次USB已可用，VS Code Remote-SSH的LinuxARM32错误是独立平台兼容问题。用户已取消旧版VS Code路线，相关下载与准备代码已清理，不属于本包。
