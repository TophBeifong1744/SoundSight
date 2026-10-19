# PR8：两板基础联调材料核对

2026-10-18；结论：材料足够进入Vitis 2025.2/JTAG首轮无动作P4，现场启动及SPI通信仍待执行。不是PYNQ/SD卡启动镜像交付，也不是板测通过。

受查PR：https://github.com/TophBeifong1744/SoundSight/pull/8 ，已合入。准确head bf6c9b5a9d1201a16ec6a750ec3718d381420376，merge 582d9621ec37fd0ae88e93012463217e903e12b5。

## 实际读取结果

- 已读README、package-check.json及unpack_local.py源码；没有执行交付脚本。
- 独立读取XSA（728431字节），ZIP CRC无错误，12个条目，含pl_stm32.bit、HWH、ps7_init.tcl/C等。
- 独立读取工作区ZIP（8148948字节），Git blob身份与PR文件一致，ZIP CRC无错误，共1557条目。
- 工作区两份XSA均与单独上传XSA一致；其中位流与工作区三份pl_stm32.bit一致，每份bit为4045703字节。
- first/build/first.elf为160576字节；FSBL构建/导出ELF均为356288字节；检查文件头均为ELF32、小端、ARM。此检查不证明运行功能。
- 实际main.c打印PS application running.后循环sleep；不做SPI或运动提交。
- 实际first/_ide/launch.json为baremetal-zynq，启用resetSystem/programDevice，bit指向first/_ide/bitstream/pl_stm32.bit，ELF指向first/build/first.elf、ps7_cortexa9_0；isFsbl=false，usingPs7Init中runPs7Init=true及runPs7PostInit=true，引用first/_ide/psinit/ps7_init.tcl。
- XSA中ps7_init.tcl有ps7_init/ps7_post_config；时钟初始化写F8000170，post_config写F8000240=0以释放PL复位。脚本存在及配置启用不等于现场已执行成功。
- 调试连接为Local，私有.peers.ini未交接；按README须在接收机重新选择JTAG连接。该项是现场配置，不是要求A提供私有连接文件。

## 现在如何推进

1. 获取PR8的software/vitis/stm32目录全部五个文件，按其README用unpack_local.py解到尚不存在的新工作区，指定本机Vitis2025.2位置。不将快照ZIP当官方Import导出包。
2. Vitis Set Workspace打开该目录，确认pl_stm32_platform与first，重新选择本机JTAG连接。保持已有位流/ELF及PS7 Init、Post Init设置，首次不要求重新构建。由现场人员启动配置，系统复位/下载是实际硬件操作。
3. 确认PS串口出现PS application running.并保留调试启动结果；这只证明PS应用已运行，仍需SPI读身份检查PL。
4. 断电完成原五信号与GND接线、两板独立供电及Bank13 3.3V核对。上电并完成FPGA/PS启动后，在已验证的二维STM32固件上逐条发送status、fpga、status（CRLF），返回完整STM32日志。
5. 预期身份0x5A5A2026/0x00010000；成功模型预期32 PASS/0 FAIL/4 SKIP。动作保持关闭，不先运行stream。

启动方式选择Vitis/JTAG，不需要额外BOOT.BIN或PYNQ镜像才能完成这一轮。若现场选择改用SD/PYNQ启动，则需另准备匹配启动材料，不能直接把本包称作此类镜像。

## 保留条件

实际接线、JTAG/PS启动、PL运行时钟/复位及双板SPI/IRQ均未在本轮实测；现场加载bit应来自此包。原PR6/7实现报告与当前位流的完整构建身份关系没有在本轮重建证明，不把旧时序报告提升成新的全系统验收。

读取过程中GitHub raw二进制接口报transform: short source buffer，大blob接口随后stream CANCEL；已改准确提交的公开raw路径经代理读取，最终完整ZIP通过。未保留下载副本，全部在内存检查；没有构建、解包到工程、下载板卡、复位或授权配置变更。用户Keil uvprojx在途修改保留；三维超限构建继续暂停。

## 2026-10-19 当前main组件包增量核对

用户再次指定main目录，当前main为b486b567db3cb20f1c56f98c89a7f081e265dc9b。交付现为六文件：README.md、package-check.json、path-bases.json、pl_stm32.xsa、unpack_local.py、vitis_components.zip；旧vitis_workspace.zip操作名称不再适用。

本轮实际读取新版README/检查说明/解包脚本，并在内存打开准确提交的组件ZIP：8128884字节、1554条目、CRC无错误，根目录只有first与pl_stm32_platform。包内硬件XSA与此前单独交付对象一致；三份bit均与XSA内bit一致；first ELF、FSBL ELF及first/_ide/psinit/ps7_init.tcl存在，调试用ps7_init.tcl与XSA内文件逐字节一致。launch配置仍启用PS7 Init/Post Init、下载匹配bit和first ELF；main仅打印后sleep。

结论保持：足够进入Vitis2025.2/JTAG首轮无动作P4。下载当前六文件同放一个目录，使用同版unpack_local.py和外置path-bases.json配置新工作区，不能混用旧解包器。现场需重新选JTAG连接、完成PS/PL启动和原接线确认，再在既有二维STM32固件运行status→fpga→status。包检查不代表实际板测或自动导入成功；未运行IDE、构建、下载、复位或改授权。三维构建继续暂停。
