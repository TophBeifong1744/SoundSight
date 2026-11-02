# SoundSight 屏幕 PS I2C S2

本增量把触摸总线交给 Zynq PS I2C0/EMIO 与 Linux Cadence 驱动，代替原 AXI IIC。显示、触摸寄存器协议、GPIO复位、VDMA双缓冲、声纹、轴控制与个人资料不改。候选尚未板测，不声称已解决此前故障。安装仅替换匹配的候选文件，不自动编程、复位或开轴。

## 人类板端步骤

1. 安装协调者提供的 S2 包，保留全部用户配置和校准。重启后使用原命令 `sudo sh soundsight-3d.sh prepare` 准备新位流；不要在旧 UI 或 VDMA 活动时安装/重编程。
2. `sudo sh soundsight-screen-i2c.sh check`。它核对安装哈希、重启、已加载硬件身份、原 PS 空闲状态、运行设备树、内核驱动、专用总线占用、字符设备和原生 I2C ABI，不执行触摸读写或GPIO复位。
3. 已确认本板 `/amba/i2c@e0004000` 原为 disabled/400kHz，I2C1也禁用、configfs overlays入口存在。因此首次 check 可能提示尚未启用；执行 `sudo sh soundsight-screen-i2c.sh apply`，只对这个已经存在且再次验证的PS0节点应用 `status=okay` 和 `clock-frequency=100000`。包内已有本机官方dtc编译的DTBO，板上不需要安装dtc。I2C1、时钟源、IRQ、reg、MIO和其他设备树属性均不改。
4. apply 成功后再 check，然后 `sudo sh soundsight-screen.sh --seconds 60`，默认关轴自检。观察 `PS_I2C_READY` 中实际动态分配的设备路径、`TOUCH`、首屏/颜色/四角和 `VDMA_STOPPED`；有任何失败保留完整日志，不反复重置或强行解除设备占用。

check/apply 把完整结果输出为 `SCREEN_I2C_SETUP=`，同时保存到运行目录 `logs/screen-i2c-*.json`，包括前后运行DT原始属性、平台驱动和adapter信息。保存失败也明确报错。不会联网安装、mount configfs、modprobe、unbind、强制接管已有内核设备或覆盖boot配置。

`/dev/i2c-*` 为空可能仅因原adapter禁用，不表示设备冲突。若apply后诊断显示驱动或i2c-dev未就绪，先只读查询本机已有模块：`modinfo i2c-cadence`、`modinfo i2c-dev`。已内建/加载的组件可由报告中的platform driver、i2c-dev class及module字段识别，无需重复加载。确认为本机现成模块时，人类可执行 `sudo modprobe i2c-cadence`、`sudo modprobe i2c-dev`，然后重新 `check`；不下载或安装内核模块。若modinfo提示模块不存在且对应内建组件也未就绪，STOP并回传报告，不用其他控制器或裸寄存器代替。已插入的overlay保持，加载驱动后无需再次覆盖该路径。

若DT节点、clock phandle、IRQ、Cadence驱动、i2c-dev或configfs前提缺失，程序会明确STOP。若节点已经启用但频率不是100kHz，也停止：动态改属性不等于已绑定驱动会重新读取属性。若apply已经插入但3秒内未形成可用适配器，保留overlay和诊断，不自动卸载/回滚。后续由人类结合实际信息处理，不能乱跑 `ps7_init` 或写SLCR。

## Linux 总线与所有权

- 从运行DT及 `/sys/class/i2c-adapter` 解析所属 `e0004000` 平台设备，校验 `cdns,i2c-r1p10`、enabled、100kHz、clock provider及IRQ，再验证 `cdns-i2c`/`i2c-cadence` 驱动。绝不假定 `/dev/i2c-0`。
- 原生 `I2C_FUNCS` 必须支持 `I2C_FUNC_I2C`。在触摸GPIO初始化/复位/探测前打开并验证对应字符设备（major89及bus minor）。专用适配器任何已注册I2C client都会被拒绝，包括0x14、0x38、0x5D，既有pinctrl/DT子设备也不被覆盖。`I2C_RDWR` 本身不能替代这项占用检查。
- 每次事务前再次检查客户端、适配器路径、驱动、节点状态和频率。合作进程通过 `/tmp/soundsight-ps-i2c0-owner.lock` 保持单一所有者；UI仍使用屏幕锁，原业务仍使用原PS所有者锁。外部root动态绑定或直接另开总线不受这些合作锁强制约束，运行期间不得进行此类并发操作。
- 读寄存器：一次 `I2C_RDWR` 包含写指针和读数据两个message，只使用 `I2C_M_RD`，末尾一个STOP；写寄存器：一次单message。要求返回恰好2/1个message。NACK、短事务和错误直接上抛，不软件重试、不拆成两次系统调用，不用 `I2C_SLAVE_FORCE`、IGNORE_NAK、SMBus替代或裸MMIO。
- `ctypes.Structure` 使用本机自然对齐，`i2c_msg`为u16/u16/u16/指针、指针偏移8；ARM32大小12，64位大小16；`i2c_rdwr_ioctl_data`为指针/u32，分别8/16字节。缓冲和message数组在同步ioctl返回前保持存活。错误保留errno、地址、payload和count；finally关闭fd。

**本版选择直接使用 Cadence 内核超时，没有worker线程/进程。** 不修改会影响整个adapter的 `I2C_TIMEOUT`/`I2C_RETRIES`。因此原AXI版本的100ms事务截止不再适用，实际超时和内核可能的重试行为取决于本板Linux5.4驱动，尚未实测。ioctl阻塞期间触摸/UI循环及退出信号处理可能延后；`--seconds 60`是UI循环目标时长，不是涵盖内核阻塞的严格墙钟上限。首次必须关轴验证，不能把未测内核超时当作即时STOP保证。

## 硬件身份与原业务边界

`SCREEN-INSTALL.json` 要求 revision=`SCREEN_PS_I2C_S2`、transport=`PS_I2C0_EMIO_LINUX`，安装boot ID与当前不同；匹配bit/HWH及关键软件/DTBO哈希。`Overlay(download=False)` 不下载硬件。检查PYNQ已加载路径/非空时间戳及live IP字典：VDMA `0x43000000`、GPIO `0x41200000` 保留，明确拒绝任何旧AXI IIC类型或 `0x41600000`。

官方PYNQ2.7的HWH解析器具有 `root` 和 `ps_name`，并通常把PS参数放入 `ip_dict`；`Device.ip_dict` 是PL server的已加载快照。`Overlay.parser` 是磁盘HWH解析器，不是独立的硬件读回。程序优先核对已加载PS参数；若该字典缺PS项，仍依靠上述已加载PL拓扑/路径/时间戳加安装哈希，联合验证parser中的唯一PS7、I2C0 enable/EMIO和 `IIC_0` 到 `screen_iic` 的实际同名BUSNAME连接。缺少这些证据即拒绝，不只比较文件名。

旧成功工程使用PS I2C0 `0xe0004000`、100kHz和组合寄存器事务；裸机中的PS GPIO编号54/55只用于旧工程说明。本候选RST/INT/BL仍通过原AXI GPIO，不改原Touch坐标/复位/探测协议。S2硬件导出的ps7_init与S1逐字一致、I2C时钟门原已开启是本机静态事实，不代表板端实时SLCR读回；Linux驱动通过时钟框架接管，本代码不执行ps7_init或SLCR写。

SOUND对应原follow-sound，SPEAKER保留score_ttl_v2。默认selftest无运行时命令，`--control`才允许显式START，`--enable-motion`另行允许选轴；选轴后仍须START。模式切换、用户选择及STOP规则沿用S1；未增加录入、键盘或模型功能。原PS运行脚本、后台业务源码和屏幕启动脚本均原样保留。

## 来源和当前验证边界

读取的官方PYNQ tag `v2.7.0` 文件：`pynq/pl_server/hwh_parser.py`、`device.py`、`embedded_device.py`、`server.py`、`pynq/devicetree.py`。动态DT使用已有 `DeviceTreeSegment.insert()`，该API检查configfs回读和applied状态；不存在该能力时不尝试替代PS访问。

Linux UAPI来源：本机AMD2025.2 ARM sysroot `usr/include/linux/i2c.h` 与 `i2c-dev.h`；DTS节点参考本机zynq-7000.dtsi，并由本板只读回传确认target-path/status/compatible/reg。DTBO由官方DTC1.7.0编译，反编译确认只含目标节点的两项修改。

本批允许Python3.8语法、shell语法、UAPI本机布局与静态比较检查。独立门禁/ABI/资源生命周期验证由下一批完成，没有新功能仿真或硬件操作。实际内核绑定、组合事务、触摸与显示/音频共存仍须匹配S2硬件后由人类验证。
