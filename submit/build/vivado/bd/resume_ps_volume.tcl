# 已复制10份RTL后，从模块刷新断点继续；不再复制，不覆盖首次备份。
namespace eval ss_volume_update {variable resume_once 1}
try {
    source [file join [file dirname [info script]] update_ps_volume.tcl]
} finally {
    unset -nocomplain ::ss_volume_update::resume_once
}
