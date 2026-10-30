# 给A：垂直手动命令被接受，但110/115度均无可见运动

日期：2026-10-29。用户要求定位问题后交回A修复；本交接只陈述已确认现象和排查边界，未确认唯一根因。

## 已确认的板端现象

使用你交付的soundsight_pynq_3d_speaker.zip，B新增AF1仅开放follow-sound命令入口；本次测试走原manual路径，未用声纹、未开启声音采集。用户确认舵机供电已开；此前试转/接线细节由A掌握，用户不清楚，不再要求用户补充A的历史记录。

1. 新目录P02导入、CP1/VF1校验成功。
2. AF1安装成功，备份backup_follow_sound_af1_7j_sh9wo；板端21项原三维+7项新入口测试通过。
3. prepare成功，LOADED=True，FCLK0=99.999999MHz，FPGA_RST_CTRL=0，末态fault=0/drops=0/dual_axis=0。
4. 水平旧三个目录配置一致，迁入horizontal={front_deg:180,direction:1,min_deg:0,max_deg:360}。这不是本轮重新标定。
5. 垂直原配置null；B只为小范围试探保存vertical={front_deg:110,direction:1,min_deg:105,max_deg:115}。该配置是假设，不是实测零位/限位；不要作为验收标定值。
6. manual --vertical 110 --seconds 3：commits=30、axes=2、audio_started=false、mechanical_arrival=UNVERIFIED、stop_confirmed=true。用户观察没有移动，朝正前方。
7. manual --vertical 115 --seconds 3：相同成功返回、目标115；用户仍观察没有移动。
8. 随后status：status=983040(0xF0000)、fault=0、drops=0、sys=8、actuator=0、dual_axis=512(0x200)。

目前停止继续扩大角度或进入自动跟随。110度未被确认是机械零位，direction=1未被确认是抬头方向。

## 寄存器证据与局限

交付包software/tetra3d/linux/motion_3d.py的DualAxis.commit在每次COMMIT后读取FAULT、LAST_TARGET(0xC0)、STATE(0xA8)的have_command位；任一不符会报错，manual成功计数只在commit返回后增加。因此30次成功返回支持“每次目标被寄存器控制器确认接受”，不只是Python写操作次数。

最终0x200只表示垂直配置轴bit9保留；active/follow/have_command/draining位均0，符合正常REVOKE收尾。actuator=0是旧动作通路状态，不足以判断双轴运行期间是否有PWM。stop_confirmed只确认逻辑撤销/排尾，不是机械位置反馈。

开头python3.8缺pynq随后自动回退到/usr/local/share/pynq-venv/bin/python3，PYNQ_IMPORT_OK=1，最终命令完成；不能把该前置探测报错当作本轮不动的根因。

## 静态代码核查

核对远端main提交e6d28f47eec1bc8b821e5002663fe90ca50c7990及实际交付ZIP：

- board_3d.manual传递targets={'vertical':...}，mask=2，模式为无声手动。
- motion_3d.py以h|(v<<16)写0xAC，以3写0xA4提交。未发现垂直误放低半字或错误选成水平轴。
- ss_dual_axis_control.sv垂直motor_drive使用angle_shadow[24:16]、MAX_ANGLE_DEG=220，接受条件使用axes[1]，经独立v_guard输出pwm_v。
- motor_drive.v标称周期20ms，角度映射500+round(angle*2000/220)微秒。应观察110度约1500us，115度约1545us，两者差约45us；这是代码预测，不是本次实测。
- 包内bit/HWH实际哈希与SOURCE.json一致；AF1不替换bit/HWH。该检查只保证包内身份，不能替代板上波形/端点接线验证。

## 请A接手定位与修复

1. 用你此前实际试转记录确认：测试的是哪只舵机、何种控制器、实际供电/共地和W15对应连接器针脚。仓库最终信号为水平T15、垂直W15，不用旧V7/U7候选接线。
2. 在manual有效的3秒内，用示波器/逻辑分析仪从板上W15对应输出一路测到垂直舵机信号端；停止后信号低是预期，不能只在结束后测。
3. 对照110/115两条命令的周期、脉宽、幅度和共地：无输出则追查加载位流/约束/BD输出复用/控制门；板端有、舵机端无则查接线；到舵机端波形正确仍不动则查供电带载、连接器/舵机/机械及其真实命令响应。不要未测就指定是哪一项。
4. 若需内部定位，同步看accepted target、raw_v、v_guard permit/open/pwm_v及顶层输出；不得用寄存器成功代替管脚有波形。
5. 修复后回传相同110/115命令的波形与可见位移，再确定真实水平零位、增角方向和允许范围；随后先单轴再双轴follow-sound。声纹优化不在本问题内。

本轮没有重新综合、修改RTL/机械参数算法、自动清错或远程操作板卡；当前未发现可直接归因的PS角度打包错误，但也没有证明PL/物理链路无故障。

## 可选的停止态只读补充

若用户继续回传，下列命令仅读状态/已接受目标/限位，不驱动：

```sh
sudo env XILINX_XRT=/usr /usr/local/share/pynq-venv/bin/python3 -c "from pynq import MMIO; m=MMIO(0x40000000,4096); print('CAP=',hex(m.read(0xa0)),'STATE=',hex(m.read(0xa8)),'LAST_TARGET=',hex(m.read(0xc0)),'V_LIMITS=',hex(m.read(0xd0)),'FAULT=',hex(m.read(0x64)))"
```

在115度命令后没有重置/重配的前提下，预期CAP=0x44554101、STATE=0x200、LAST_TARGET=0x730000、V_LIMITS=0x730069、FAULT=0。此额外回读尚未执行，不当作实测证据。

## 文件身份

- 原私有包SHA256：40ebebc59010143da9fa6a80b623ac09cb976f7b9566c990452fb0d7cff59c46。
- bit SHA256：40d19dfcb77ee87e7f92f479c11300c45d789d6699beb7a6945c13ea8273725f。
- HWH SHA256：de42bdb325d202a27161f9be7e4197701f1d0c644d8bb8d80d4d547efdf2ab3f。
- AF1 SHA256：1a2b38166899b1e03942d86e9efa94d4f5a0f4c61935bde23043823bfd00404b。
- 新板端目录：/home/xilinx/SoundSight_PYNQ_3D_Speaker。
- AF1备份：/home/xilinx/SoundSight_PYNQ_3D_Speaker/backup_follow_sound_af1_7j_sh9wo。

附件保留本轮prepare/status原始粘贴文件、手动结果与用户观察的转录，以及AF1更新包/差异/说明。不包含私人声音、模型或P02模板；不自动发消息或公开推送。
