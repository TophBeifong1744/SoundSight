# 用户回传：源码复制后模块刷新退出

日期：2026-10-21。保留的用户原文：

```text
PS_VOLUME_COPIED=F:/AMD/work/SoundSight_PS_Volume/SoundSight_PS_Volume.srcs/sources_1/imports/rtl/bd_ps_link.v

    while executing
"update_module_reference {compute ps_link}"
    (procedure "ss_volume_update::run" line 87)
    invoked from within
"ss_volume_update::run"
    (file "E:/Users/Toph Beifong/Documents/GitHub/SoundSight/project/bd/update_ps_volume.tcl" line 135)
```

回传没有更前面的Vivado原始ERROR说明。只读当前BD文件确认`compute`和`ps_link`的xci_name分别是`soundsight_stm32_bd_bd_clean_compute_0_0`与`soundsight_stm32_bd_bd_ps_link_0_0`。因此修正错误的显示名单元寻址，使用真实IP对象，并开启verbose及完整errorinfo。尚不能排除修正寻址后出现其他RTL/刷新问题，不能标记现场故障闭合。

没有修改外部工程或撤销已复制源码。原始源码/BD备份在用户工程`handoff/before_ps_volume_*`，接续入口不覆盖它。此故障是Vivado准备阶段失败，不是综合/实现时序违例。
