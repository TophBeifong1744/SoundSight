# S2：用旧屏幕方案的PS I2C0 EMIO替换AXI IIC，不改变外部管脚及其余地址。
set_property -dict [list CONFIG.PCW_I2C0_PERIPHERAL_ENABLE {1} CONFIG.PCW_I2C0_I2C0_IO {EMIO} CONFIG.PCW_I2C_PERIPHERAL_FREQMHZ {111.111115}] [get_bd_cells ps7]
if {[llength [get_bd_cells -quiet screen_iic]]} {
    # 删除AXI IIC及其接口连线；原GPIO从M05移到M04，保持0x41200000。
    foreach endpoint {screen_iic/IIC screen_iic/S_AXI screen_gpio/S_AXI} {
        set nets [get_bd_intf_nets -quiet -of_objects [get_bd_intf_pins $endpoint]]
        if {[llength $nets]} {delete_bd_objs $nets}
    }
    delete_bd_objs [get_bd_cells screen_iic]
    set_property CONFIG.NUM_MI 5 [get_bd_cells control_bus]
    connect_bd_intf_net [get_bd_intf_pins control_bus/M04_AXI] [get_bd_intf_pins screen_gpio/S_AXI]
    connect_bd_intf_net [get_bd_intf_pins ps7/IIC_0] [get_bd_intf_ports screen_iic]
    assign_bd_address -offset 0x41200000 -range 0x00010000 -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs screen_gpio/S_AXI/Reg] -force
}
if {[get_property CONFIG.NUM_MI [get_bd_cells control_bus]] != 5} {error "Unexpected control bus width"}
if {[llength [get_bd_cells -quiet screen_iic]]} {error "Obsolete AXI IIC still present"}
