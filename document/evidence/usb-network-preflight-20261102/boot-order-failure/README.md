# USB 自动启动挂载顺序失败

用户在v2手动启动后已取得USB_READY、Windows Remote NDIS网卡、192.168.77.1到192.168.77.2:22 TCP成功、SSH登录以及WinSCP列出/home/xilinx/的证据。尚未收到上传文件哈希对比。enable-service返回ENABLED_FOR_NEXT_BOOT，执行sudo reboot后Windows USB网卡消失。

用户串口原始关键输出（板端时钟2021，不作实际日历依据）：

```text
Loaded: loaded (/etc/systemd/system/soundsight-usb-network.service; enabled; vendor preset: enabled)
Active: failed (Result: exit-code)
ExecStart=/usr/bin/python3 /opt/soundsight-usb-network/usb_network.py start --confirm-slave --board-ip=192.168.77.2/24
ERROR: [Errno 2] No such file or directory: '/boot/BOOT.BIN'
ls -l /sys/class/udc: total 0
ip -br addr: only lo, dummy0, sit0
```

稍后findmnt显示`/boot /dev/mmcblk0p1 vfat`，BOOT.BIN存在、866140字节。fstab仅`/var/swap none swap sw 0 0`；boot.mount无文件；rc.local不存在。journal另提示一个旧journal文件truncated，当前服务错误记录可读，不把此提示视为启动失败根因。

用户提供的挂载脚本/usr/local/bin/bootpy.sh：

```bash
#!/bin/bash
. /etc/environment
for f in /etc/profile.d/*.sh; do source $f; done
BOOT_MNT=/boot
BOOT_DEV=/dev/mmcblk0p1
BOOT_PY=$BOOT_MNT/boot.py
if !(mount | grep -q "$BOOT_MNT") ; then
   mount $BOOT_DEV $BOOT_MNT
fi
if test -f "$BOOT_PY"; then
   python3 $BOOT_PY
fi
```

用户提供的/lib/systemd/system/bootpy.service：

```ini
[Unit]
Description=Executing boot.py from the boot partition
Requires=pl_server.service jupyter.service
After=pl_server.service jupyter.service boot.mount
[Service]
Type=oneshot
ExecStart=/usr/local/bin/bootpy.sh
[Install]
WantedBy=basic.target
```

show输出：Type=oneshot，Result=success，ActiveState=inactive，SubState=dead。basic.target.wants存在bootpy链接。采集的boot.py全部为注释示例；未重新采集当前boot.py。

根因是USB单元只等待local-fs.target，未等待自定义挂载者bootpy；BOOT.BIN预检在STATE创建、模块加载、GPIO、overlay之前退出。最小修复给USB增加Requires=bootpy.service和After=bootpy.service。已安装v2用独立10-bootpy.conf drop-in，不修改受manifest校验的代码；新包v3同步生成依赖。具体单行命令见../../../pynq-usb-network.md。

独立只读审核认为依赖设计通过：oneshot完成后自然inactive不等同Requires显式停止，不用BindsTo；已知依赖链无新增回边，但未审计pl_server/jupyter完整依赖图。首次手动start会再拉起inactive bootpy；不要手动restart原有服务，不重复硬件start。本次无模块/DTBO重编，无RTL/位流修改，无仿真；既有运行配置器9项测试通过（python -B -m unittest discover -s software/tests -p test_usb_network.py -v），不把它当作systemd排序或实板通过。

v2原包保存于本目录v2-candidate.zip，SHA256 cc54cb589f89ff678c77611672f4c89180b289e3c7d60942a5ecd163e780fecf。当前包与manifest见上级package.json。未新增临时目录；保留失败包供复现。待用户执行单次服务start并正常重启验证Windows枚举、SSH及SFTP；截至本记录尚未实板验证v3修复。

## 后续复测

用户已返回服务active (exited)、0/SUCCESS及USB_READY，并在正常重启后确认“已经可以了”。实测身份为v2加10-bootpy.conf，完整边界见[板端结果](../board-success.md)；上文失败现场与当时待测状态保留。
