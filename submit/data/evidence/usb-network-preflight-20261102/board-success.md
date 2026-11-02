# USB 单线调试：板端结果与范围

记录日期2026-11-02。证据来自用户串口/PowerShell输出、WinSCP截图与重启确认；板端日期停留在2021年，不能用它推断实际测试日期。

## 实际通过的组合

- Zynq7020领航者板，PYNQ Linux 5.4.0-xilinx-v2020.2，保留当前B修改的应用bit/HWH。
- DC适配器供电；P4为Slave，SN–DN、SP–DP（1–3、2–4）竖接。
- 一根电脑数据线：配置时USB UART，日常USB SLAVE。USB1不启用。
- 安装包为`usb-root-phandle-v2`，在既有systemd服务上增加`10-bootpy.conf`，内容为Requires/After=bootpy.service。
- Windows USB网卡“以太网 2”，192.168.77.1/24；板卡usb0，192.168.77.2/24；网关/DNS留空。

## 真实结果

Windows原先为169.254.87.107，连接错误地走Realtek网卡；设置固定地址后用户输出：

```text
ComputerName     : 192.168.77.2
RemoteAddress    : 192.168.77.2
RemotePort       : 22
InterfaceAlias   : 以太网 2
SourceAddress    : 192.168.77.1
TcpTestSucceeded : True
```

随后SSH进入`xilinx@pynq:~$`，用户截图显示WinSCP连接`xilinx@192.168.77.2`并列出`/home/xilinx/`。未保存账户密码、私钥或用户目录内容。

加启动依赖后，用户串口状态：

```text
Loaded: loaded (/etc/systemd/system/soundsight-usb-network.service; enabled; vendor preset: enabled)
Drop-In: /etc/systemd/system/soundsight-usb-network.service.d
         10-bootpy.conf
Active: active (exited)
ExecStart=/usr/bin/python3 /opt/soundsight-usb-network/usb_network.py start --confirm-slave --board-ip=192.168.77.2/24
code=exited, status=0/SUCCESS
CHECK_OK: matching kernel/boot inputs; USB0 disabled; MIO baseline matches; revision=usb-root-phandle-v2
USB_READY board=192.168.77.2/24 interface=usb0
```

随后按正常重启、不手动start、USB SLAVE接线验证步骤执行，用户回报“已经可以了”。记为用户确认正常重启后连接恢复；没有第二次完整PowerShell日志，不扩大为重复冷启动次数或长期稳定性结果。

## 当前仓库与交付

`usb-boot-order-v3`生成的基础unit已内置同样的Requires/After=bootpy.service；两个KO、两份DTBO沿用已验证字节。v3全新安装包尚未直接上板，不把v2加drop-in的实测身份改写为v3实测。已工作的板卡无需重装。

完整文件上传下载的哈希核验、长时间大文件传输、掉线恢复及当前B版应用并发运行仍未验证。SSH不覆盖上电U-Boot/早期内核串口日志，也不是JTAG。

VS Code 1.144.0的Remote-SSH报UnsupportedPlatform("LinuxARM32")，用户取消独立旧版方案；下载/解压/准备脚本均已清理。日常入口保持SSH终端与WinSCP，平台兼容失败不计为USB链路失败。
