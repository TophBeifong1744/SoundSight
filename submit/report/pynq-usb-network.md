# 领航者 PYNQ 单 USB 数据线：SSH、WinSCP 与开机启动

Windows电脑接领航者USB SLAVE，通过一根数据线使用SSH终端和WinSCP；另保留DC供电。板端v2加bootpy依赖补丁已通过Windows枚举、SSH登录、WinSCP目录访问，并获用户确认正常重启后恢复连接。仓库v3内置相同启动依赖，尚未单独执行全新安装板测。范围与原始关键输出见[板端结果](../data/evidence/usb-network-preflight-20261102/board-success.md)。此包只匹配本次采集系统，不是所有PYNQ镜像通用安装器。

## 已配置板卡的日常使用

保持P4为Slave、DC供电和USB SLAVE数据线，开机等待系统启动。在Windows PowerShell执行`ssh xilinx@192.168.77.2`，用板端当前密码登录；看到`xilinx@pynq:~$`后即可执行原串口里的Linux命令。WinSCP使用SFTP、同一地址、端口22和同一账户，工作目录通常是`/home/xilinx/`。不需要每次执行start或enable-service。

现有板卡继续使用v2加drop-in，不必重新解压v3或覆盖`/opt/soundsight-usb-network`。USB活动时运行check会因基线已改变而拒绝，这是预检设计；查看现状使用`sudo systemctl status soundsight-usb-network.service --no-pager -l`或助手status。

USB网络用于Linux启动后的交互；上电日志或系统未启动时仍需把同一根线换回USB UART。VS Code新版Remote-SSH出现LinuxARM32平台不支持，用户已取消旧版路线；该问题与已工作的USB网络无关。本任务不安装旧编辑器、不把VS Code视为使用前提。

## 当前开机修复：usb-boot-order-v3

实板自动启动在预检读取`/boot/BOOT.BIN`时失败，尚未加载模块、写GPIO或应用overlay。此镜像fstab只有swap，/boot不是fstab挂载；`bootpy.service`为Type=oneshot，执行`/usr/local/bin/bootpy.sh`挂载/dev/mmcblk0p1，再运行/boot/boot.py。USB服务原先只等local-fs.target，不能保证此挂载完成。新安装生成的USB unit添加Requires=bootpy.service及After=bootpy.service；保留启动文件哈希预检，不改原厂挂载脚本。

已经安装v2的板卡无需替换包：通过UART添加独立drop-in，原包校验保持有效。以下每框单行；仅针对当前已确认预检退出、UDC为空的失败现场执行一次start。已启用USB或部分加载overlay时，不重复start。

```bash
sudo mkdir -p /etc/systemd/system/soundsight-usb-network.service.d
```

```bash
printf '[Unit]\nRequires=bootpy.service\nAfter=bootpy.service\n' | sudo tee /etc/systemd/system/soundsight-usb-network.service.d/10-bootpy.conf
```

```bash
sudo systemctl daemon-reload
```

```bash
sudo systemctl start soundsight-usb-network.service
```

```bash
sudo systemctl status soundsight-usb-network.service --no-pager -l
```

预期active (exited)及USB_READY，再换线到SLAVE并验证SSH。启动输出现在在journal而非直接终端；失败时贴回status及`sudo journalctl -b -u soundsight-usb-network.service --no-pager -n 80`。本板已获用户确认正常重启后能重连；首次迁移到其他镜像或改动启动脚本后仍需重测。修复可通过移除本任务专用10-bootpy.conf并daemon-reload回退，但会恢复原开机缺陷；不自动重启或在线卸载overlay。

bootpy成功后显示inactive/dead是其oneshot且没有RemainAfterExit的正常状态；本轮首次手动启动USB会再次拉起它。已采集的boot.py全部为注释，不加载应用；若后续用户修改boot.py，它的完成/失败也会影响USB启动，需重新评估依赖。不要用重复start/restart排查未知的部分硬件状态。

2026-11-02 用户明确：当前应用 `.bit/.hwh` 已由 B 修改，不能视为原始版本。本次保留板端当前 B 版，不替换或回退应用 `.bit/.hwh`；采集包没有包含它们，未核验其内部配置。候选也不改 `BOOT.BIN`、`IMAGE.UB`、`BOOT.SCR` 或现有应用入口。后续必须在实际 B 版程序下验证连接共存。

## 历史修复：usb-root-phandle-v2

首次板测已通过预检、模块加载、第一阶段NOP PHY绑定与GPIO9相关检查，但第二阶段失败：旧内核把根节点目标的符号导出为`//soundsight-usb-phy`，解析返回`-2`，USB0仍disabled。原候选的离线libfdt组合没有覆盖这一内核行为，不能沿用为板测成功。

修正版把PHY放在`/amba`下，按实际of_node定位绑定的设备；严格核对导出路径原始字节和phandle，并在写入Overlay后读回DTBO及USB0实际属性。两个驱动模块完全复用，复位时序、电压和应用/启动文件不变。该版预检输出包含`revision=usb-root-phandle-v2`；当前新包为`usb-boot-order-v3`。

已经解压过旧包的用户：正常关机断电后，把SD卡根目录的同名ZIP替换为修正版，插回启动，继续使用UART。先保留旧目录（若备份目录已存在，该命令拒绝覆盖）：

```bash
test ! -e /home/xilinx/SoundSight_USB.failed-phandle && mv -T /home/xilinx/SoundSight_USB /home/xilinx/SoundSight_USB.failed-phandle
```

然后执行下方第2步解压、预检及第3步临时启用。不要在失败的同一次启动里反复start，不删除运行中的overlay。旧目录先保留，成功后再处理。

## 使用候选包

文件：`release/output/soundsight_usb_network.zip`，根目录 `SoundSight_USB`。包含两个 ARM 模块、两阶段 DTBO、源代码/许可证、Python 配置助手、校验清单和本文。不包含应用位流、声纹模型或替换内核。两模块针对 `5.4.0-xilinx-v2020.2` 的实际配置和符号表构建；使用 GCC 9.2.1，原内核 GCC 9.2.0，已检查编译配置语义与符号 CRC，两模块已在v2手动启动中加载成功。

### 1. 拷包与接线（第一次保留串口）

1. 退出正在运行的应用，串口执行 `sudo poweroff`。系统停机后断电，取出 SD 卡。
2. Windows 将 ZIP 复制到 SD 卡可见分区根目录。不要覆盖启动文件或 B 版应用文件。
3. DC 和 USB 全部断开时，核对实板 P4 的针脚标记，跳帽设为 Slave：**1–3、2–4**，不是 1–2、3–4。仓库资料为领航者板规格书 V1.2 §3.19；实板标记不一致时停止改接。
4. 插回 SD 卡，接匹配的 DC 适配器，现有数据线仍连接 **USB UART**。用户只有一根数据线：先完成下面的串口配置，看到`USB_READY`后保持DC供电、不重启，把同一根线的板端插头从UART移到 **USB SLAVE**，电脑端保持不动。不要接四个 USB HOST 口；配置成功并启用开机服务后，日常直接接SLAVE。

### 2. 解压和只读预检

以下每个代码框都是单行，在原 `xilinx@pynq` 串口发送；不在 Windows PowerShell 中执行。若目标目录已存在，首条命令不会覆盖，先核对旧目录来源。

```bash
test ! -e /home/xilinx/SoundSight_USB && python3 -m zipfile -e /boot/soundsight_usb_network.zip /home/xilinx
```

```bash
sudo python3 /home/xilinx/SoundSight_USB/usb_network.py check
```

预期 `CHECK_OK` 且包含 `revision=usb-boot-order-v3`；原v2加服务drop-in的板卡仍显示v2，这是正常的。该步骤只读匹配内核配置、符号表、包内容、原启动文件、USB 状态及 MIO；检查 SSH 单元存在，并拒绝与现有路由重叠的子网。若不通过，保留报错，不强制绕过校验。

### 3. 本次启动临时启用

仅在按第1步完成 Slave 跳帽及 DC 供电后执行。此命令会配置 USB MIO、脉冲复位 USB PHY、加载 USB 模块和设置 USB 网络；不操作 FPGA 位流或执行器。

```bash
sudo python3 /home/xilinx/SoundSight_USB/usb_network.py start --confirm-slave
```

预期 `USB_READY board=192.168.77.2/24 interface=usb0`（网卡名称以实际输出为准）。没有此输出就停止，不重复 start；从 UART 保存下面输出，再正常重启恢复运行时 USB 配置：

```bash
sudo dmesg | tail -n 100
```

```bash
sudo python3 /home/xilinx/SoundSight_USB/usb_network.py status
```

默认不写开机服务；手动启用失败后可以用 `sudo reboot` 正常重启回原状态。不在线移除 overlay、不反复复位正在工作的控制器。如果已按第6步启用服务，必须先禁用服务再重启。

### 4. Windows 设置虚拟网卡

打开设备管理器，预期出现 USB Ethernet/RNDIS 或 Remote NDIS 网络适配器。包提供 Microsoft OS 描述符用于驱动匹配；用户已确认 Windows 出现 Remote NDIS Compatible Device。

如果新出现的 RNDIS 设备有黄色感叹号，可在该设备上选择“更新驱动程序→浏览我的电脑→让我从可用驱动程序列表中选取”，若列表提供 Microsoft 的 Remote NDIS Compatible Device，则使用它。不能把原 CH340 串口强行换成网络驱动。如果系统不提供兼容项，记录新设备硬件 ID 和 Windows 版本，不下载来源不明的 INF、不关闭驱动签名检查。

`Win+R` 输入 `ncpa.cpl`，找到这张新 USB 网卡，在属性的 IPv4 中设置：

| 字段 | 值 |
|---|---|
| IP | `192.168.77.1` |
| 子网掩码 | `255.255.255.0` |
| 默认网关 | 留空 |
| DNS | 留空 |

仅改 USB 网卡，保留 Wi-Fi/普通网卡。显示“无 Internet”是正常的，此连接只用于本机与开发板通信。无需关闭防火墙或开网络共享。

### 5. SSH 与 WinSCP

Windows PowerShell 执行：

```powershell
Test-NetConnection 192.168.77.2 -Port 22
```

应看到 `TcpTestSucceeded : True`。然后：

```powershell
ssh xilinx@192.168.77.2
```

使用板上当前账户密码。首次主机指纹可与 UART 执行 `sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` 的结果核对；不要忽略身份变更提示。Windows 若没有 ssh 命令，可用现有 PuTTY/MobaXterm 的 SSH 会话。

WinSCP 新建站点：协议 **SFTP**、主机 `192.168.77.2`、端口 `22`、用户 `xilinx`、密码为当前板端密码。上传到 `/home/xilinx/` 下的自有目录，不覆盖启动文件或 B 的当前应用。可以同时开 SSH 终端和 WinSCP。

先传一个无关的测试文件，用 Windows `Get-FileHash -Algorithm SHA256` 与板端 `sha256sum` 比较。随后按当前 B 版既有方式做关轴运行，确认 USB 连接保持；USB传包成功不能代替 B 版应用联合验证。

### 6. 确认 SSH、SFTP 均通过后，才启用开机服务

在板端 SSH 或 UART 发送：

```bash
sudo python3 /home/xilinx/SoundSight_USB/usb_network.py enable-service
```

助手要求本轮 start 成功且电脑已经配置 USB 设备，复制已校验包到 `/opt/soundsight-usb-network`，注册专用服务；不改原应用服务，不自动重启。中断后同包可重试，不覆盖不同版本或他人服务。

正常重启验证：

```bash
sudo reboot
```

确认开机后再次能 SSH 和 WinSCP。日常使用保留 **DC适配器＋USB SLAVE这一根电脑数据线**；需要串口排错时，把同一根线插回UART。P4保持Slave；改回Host前先禁用服务。

回退（从 UART 执行）：

```bash
sudo systemctl disable soundsight-usb-network.service
```

```bash
sudo reboot
```

没有在线移除 DT overlay 的 stop 命令。禁用服务再重启即可恢复原运行时USB/MIO状态；正常关机、断电后才改跳帽。包和服务文件保留便于排错，不自动删除用户资料。

## 2026-11-02 用户串口结果

- Linux `5.4.0-xilinx-v2020.2`，用户 `xilinx`。
- `/sys/class/udc` 为空；两个控制器 `/amba/usb@e0002000`、`/amba/usb@e0003000` 均为 `status=disabled`，没有 `dr_mode`，`phy_type=ulpi`。
- `CONFIG_USB_CHIPIDEA=y`、`CONFIG_USB_CHIPIDEA_UDC=y`、`CONFIG_USB_GADGET=y`。
- `CONFIG_USB_LIBCOMPOSITE=m`、`CONFIG_USB_CONFIGFS=m`，ConfigFS mass-storage 已启用。
- `CONFIG_USB_ETH`、`CONFIG_USB_CONFIGFS_RNDIS`、ECM、ACM 均未启用。`g_ether` 不存在；已找到 `libcomposite.ko`。
- build 目录有 680298 字节的 `Module.symvers`；`ether.c`、`f_rndis.c`、`u_ether.c` 不存在。不能把已安装头文件当成完整厂商内核源码，也不能仅凭相同 uname 字符串认定外来模块 ABI 匹配。
- `/boot` 是 `/dev/mmcblk0p1`，vfat。含 `BOOT.BIN`、`BOOT.SCR`、`IMAGE.UB`、`REVISION`、`boot.py`；不能仅因文件名判断 FIT 内设备树或 boot script 的实际加载方式。
- 用户启动参数：`root=/dev/mmcblk0p2 rw earlyprintk rootfstype=ext4 rootwait devtmpfs.mount=1 uio_pdrv_genirq.of_id="generic-uio" clk_ignore_unused`。
- 实际 SLCR：MIO9=`0x1601`；MIO28～39全为`0x1201`，说明仍为GPIO复用，Bank500/501分别是LVCMOS33/LVCMOS18。

结论：需要补齐网络 Gadget 功能，并配置实际接线对应的 USB 控制器、PHY 与复位。优先评估匹配现有内核的模块增补，不直接重刷系统，不同时盲目启用两个控制器，不先修改启动文件。

## 已完成的输入采集

正式助手：`tools/collect_usb_gadget_inputs.py`，Python 3.8 标准库。仅读取指定启动文件、运行设备树、内核配置、已安装 build 目录及系统版本/挂载信息；唯一写入为新 ZIP，已有输出拒绝覆盖。不执行构建、加载模块、网络设置、复位、FPGA 下载或执行器动作。不会采集用户主目录、SSH 密钥或声纹数据。

把脚本通过现有网络，或正常关机后经 Windows 读卡器，复制到 SD 卡 Windows 可见启动分区根目录。重新启动后，在原串口发送单行命令：

```bash
sudo python3 /boot/collect_usb_gadget_inputs.py
```

默认生成 `/boot/soundsight_usb_inputs.zip`。正常关机并等系统停机后断电取卡，把 ZIP 复制回电脑；有现成网络也可直接取回。采集含部分失败时返回 2，ZIP 内 `manifest.json` 登记失败；仍需交回分析，不能称输入完整。磁盘满等中断可能留下不完整 ZIP，不自动覆盖。输出目录需至少 128 MiB 可用空间；输入有单文件 64 MiB、总计 512 MiB 上限，不保证压缩输出固定大小。

本板启动分区约130MB，最初因剩余空间小于128MiB的保守检查而拒绝输出，后改到`/home/xilinx/soundsight_usb_inputs.zip`成功生成22MB包，再复制回启动分区。收件后已核对启动包、实际PHY/复位、MIO读回、内核配置/符号并生成上文候选。采集脚本本身仍不是USB网卡安装器。

## 最终接线与网络目标

仓库板卡规格书 V1.2 第34～35页：USB3320 经 P4 选择连接 USB SLAVE 或 USB HUB；Slave 为 1–3、2–4 短接。断电后核对实板版次及标记再操作。USB SLAVE 与 CH340 USB UART 是不同接口；选择 Slave 后同一路控制器不再服务四口 HUB。

目标采用 Windows 可用的 USB 网络，SSH 和 WinSCP 使用同一板端 IP 与已有账户。USB 网络不能替代 Linux 启动前的 UART 日志，亦不等于 JTAG。已存在 USB 供电重启记录，继续使用匹配 DC 适配器。

采集包已收件，12202项文件完整校验；13个提示全是跳过DTC include-prefixes符号链接。首包在第二阶段引用解析失败；v2手动启动已验证枚举、SSH和WinSCP目录访问，尚未收到文件上传校验结果。v2加启动补丁已获用户确认正常重启后连接成功；v3新安装仍未直接板测。离线结果和剩余验证见 `evidence/usb-network-preflight-20261102/README.md`。
