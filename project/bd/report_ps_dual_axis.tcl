# 用户在外部3D/DualAxis工程的Project Manager中source本文件；不启动任何构建或硬件动作。
# 为避免丢弃用户内存修改，先由用户关闭已打开的设计视图；工程本身保持打开。
# library_only=1时只定义过程：已打开原routed DCP的独立会话可调用audit <报告目录>。
# 补查只在内存中增加垂直20ns最大预算，不证明原bit已经按该约束实现。
# 异步PWM没有外部采样时钟，datapath_only自动忽略hold；min只报告数据路径。
namespace eval ss_dual_axis_report {
    variable root [file normalize [file join [file dirname [info script]] ../..]]
    variable expected_top soundsight_stm32_bd_wrapper
    proc one {objects label} {
        if {[llength $objects]!=1} {error "STOP: expected one $label, got [llength $objects]"}
        return [lindex $objects 0]
    }
    proc inside {path base} {
        set path [string tolower [file normalize $path]]
        set base [string trimright [string tolower [file normalize $base]] /]
        return [string equal -length [string length "$base/"] "$base/" $path]
    }
    proc write_text {path value} {
        set h [open $path w];fconfigure $h -encoding utf-8 -translation lf
        puts $h $value;close $h
    }
    proc read_text {path} {set h [open $path r];set value [read $h];close $h;return $value}
    proc finite {value} {
        return [expr {[string is double -strict $value] && ![regexp -nocase {nan|inf} $value]}]
    }
    proc audit {out} {
        variable root
        variable expected_top
        set out [file normalize $out]
        file mkdir $out
        set status [file join $out audit_status.txt]
        # 固定报告入口可复跑；状态文件列出本轮生成的文件，失败时不能沿用旧PASS。
        write_text $status "RUNNING\nReport-only: existing routing plus in-memory vertical PWM budget."
        set produced {};set failures {};set rows {}
        set code [catch {
            if {[version -short] ne {2025.2}} {error {STOP: expected Vivado 2025.2}}
            set design [one [get_designs -quiet [current_design]] current-design]
            if {[get_property PART $design] ne {xc7z020clg400-2}} {error {STOP: expected xc7z020clg400-2 design}}
            report_route_status -file [file join $out route_status.rpt]
            lappend produced route_status.rpt
            if {![report_route_status -boolean_check ROUTED_FULLY] || [report_route_status -boolean_check ERRORS_IN_ROUTES]} {
                error {STOP: current design is not fully routed without routing errors}
            }
            set launch [all_registers -clock_pins]
            if {![llength $launch]} {error {STOP: no register clock pins}}
            set ports {};set previous_clock {}
            foreach {port package axis} {servo_pwm T15 h servo_vertical_pwm W16 v} {
                set object [one [get_ports -quiet $port] $port]
                if {[get_property DIRECTION $object] ne {OUT} || [get_property PACKAGE_PIN $object] ne $package ||
                    [get_property IOSTANDARD $object] ne {LVCMOS33}} {error "STOP: unexpected direction/pin/IOSTANDARD for $port"}
                set pattern [format {.+/with_dual_axis[.]dual_axis/%s_guard/pwm_o_reg/C} $axis]
                set pin [one [get_pins -quiet -hier -regexp $pattern] ${axis}-PWM-register-clock-pin]
                set clk [one [get_clocks -quiet -of_objects $pin] ${axis}-PWM-clock]
                set period [get_property PERIOD $clk]
                if {![finite $period] || abs($period-1000.0/61.44)>0.002} {error "STOP: unexpected PWM clock period $period"}
                if {$previous_clock ne {} && $previous_clock ne $clk} {error {STOP: PWM axes do not share the same clock}}
                set previous_clock $clk
                lappend ports [list $port $object $pin]
                lappend rows "$port: pin=$package clock=$clk period_ns=$period launch=$pin"
            }
            # 先保留原覆盖检查，再加载与未来重建相同的单份垂直预算。
            check_timing -verbose -file [file join $out check_timing_before.rpt]
            lappend produced check_timing_before.rpt
            set xdc [file join $root project sdc ps dual_axis_output_timing.xdc]
            if {![file isfile $xdc]} {error "STOP: missing $xdc"}
            source $xdc
            check_timing -verbose -file [file join $out check_timing.rpt]
            lappend produced check_timing.rpt
            foreach row $ports {
                lassign $row port object pin
                foreach kind {max min} {
                    set file ${port}_${kind}.rpt
                    set ignored [expr {$kind eq {min} ? {-user_ignored} : {}}]
                    report_timing -from $launch -to $object -delay_type $kind -max_paths 4 -nworst 4 \
                        {*}$ignored -path_type full_clock_expanded -input_pins -warn_on_violation -file [file join $out $file]
                    lappend produced $file
                    set paths [get_timing_paths -from $launch -to $object -delay_type $kind -max_paths 1 -nworst 1 {*}$ignored]
                    if {![llength $paths]} {lappend failures "$port $kind: empty timing path";continue}
                    set path [one $paths "$port $kind path"]
                    set source [get_property STARTPOINT_PIN $path]
                    set endpoint [get_property ENDPOINT_PIN $path]
                    set delay [get_property DATAPATH_DELAY $path]
                    if {$endpoint ne $port} {lappend failures "$port $kind: unexpected timing endpoint"}
                    if {![finite $delay]} {lappend failures "$port $kind: non-finite data path delay"}
                    if {$kind eq {min}} {
                        lappend rows "$port min: HOLD_N_A (datapath_only), data_path_ns=$delay start=$source end=$endpoint"
                    } else {
                        set slack [get_property SLACK $path]
                        set actual [get_property REQUIREMENT $path]
                        lappend rows "$port max: requirement_ns=$actual slack_ns=$slack data_path_ns=$delay start=$source end=$endpoint"
                        if {![finite $actual] || abs($actual-20.0)>0.001} {lappend failures "$port max: expected requirement 20.0, got $actual"}
                        if {![finite $slack]} {lappend failures "$port max: non-finite slack $slack"} elseif {$slack<0} {lappend failures "$port max: negative slack $slack"}
                    }
                }
                # 水平端口保留旧手动/声音PWM并联路径；全口最差路径不必来自双轴guard。
                # 单独检查新增guard到端口的max路径，证明它确实连接且受20ns预算覆盖。
                set file ${port}_dual_guard_max.rpt
                report_timing -from $pin -to $object -delay_type max -max_paths 1 -path_type full_clock_expanded \
                    -warn_on_violation -file [file join $out $file]
                lappend produced $file
                set paths [get_timing_paths -from $pin -to $object -delay_type max -max_paths 1]
                if {![llength $paths]} {lappend failures "$port dual guard: empty timing path";continue}
                set path [one $paths "$port dual guard path"]
                set slack [get_property SLACK $path]
                set actual [get_property REQUIREMENT $path]
                if {[get_property STARTPOINT_PIN $path] ne $pin || [get_property ENDPOINT_PIN $path] ne $port} {
                    lappend failures "$port dual guard: unexpected timing endpoints"
                }
                if {![finite $actual] || abs($actual-20.0)>0.001} {lappend failures "$port dual guard: expected requirement 20.0, got $actual"}
                if {![finite $slack]} {lappend failures "$port dual guard: non-finite slack $slack"} elseif {$slack<0} {lappend failures "$port dual guard: negative slack $slack"}
                lappend rows "$port dual guard max: requirement_ns=$actual slack_ns=$slack"
            }
            # 保留全局、总线偏斜和所有CDC等级；不得过滤Warning/Critical或忽略原有waiver。
            report_timing_summary -delay_type min_max -check_timing_verbose -report_unconstrained \
                -max_paths 10 -warn_on_violation -file [file join $out timing_summary.rpt]
            lappend produced timing_summary.rpt
            set summary [read_text [file join $out timing_summary.rpt]]
            if {![regexp -line {^\| Design\s+:\s+(\S+)} $summary -> top] || $top ne $expected_top} {
                lappend failures "source/design top mismatch: expected $expected_top"
            }
            report_bus_skew -delay_type min_max -warn_on_violation -file [file join $out bus_skew.rpt]
            lappend produced bus_skew.rpt
            report_cdc -details -all_checks_per_endpoint -no_waiver -file [file join $out cdc.rpt]
            lappend produced cdc.rpt
            report_clock_interaction -delay_type min_max -file [file join $out clock_interaction.rpt]
            lappend produced clock_interaction.rpt
            report_exceptions -coverage -file [file join $out exceptions_coverage.rpt]
            lappend produced exceptions_coverage.rpt
            report_exceptions -ignored -file [file join $out exceptions_ignored.rpt]
            lappend produced exceptions_ignored.rpt
            report_drc -no_waivers -verbose -file [file join $out drc.rpt]
            lappend produced drc.rpt
            report_io -file [file join $out io.rpt]
            lappend produced io.rpt
            report_utilization -file [file join $out utilization.rpt]
            lappend produced utilization.rpt
            foreach kind {max min} {
                set paths [get_timing_paths -delay_type $kind -max_paths 1 -nworst 1]
                if {![llength $paths]} {lappend failures "global $kind: empty timing path";continue}
                set slack [get_property SLACK [one $paths "global $kind path"]]
                if {![finite $slack]} {lappend failures "global $kind: non-finite slack $slack"} elseif {$slack<0} {lappend failures "global $kind: negative slack $slack"}
                lappend rows "global $kind: worst_slack_ns=$slack"
            }
            foreach file $produced {
                if {![file isfile [file join $out $file]] || [file size [file join $out $file]]==0} {
                    lappend failures "missing/empty report: $file"
                }
            }
            if {[llength $failures]} {error "STOP: [join $failures {; }]"}
        } message options]
        set result [expr {$code ? "ERROR" : "REPORTS_COMPLETE"}]
        write_text $status "$result\nVivado=[version -short]\nExpected_top=$expected_top\nExisting routing; vertical max=20ns added only in memory. PWM min paths are report-only; HOLD_N_A (datapath_only).\nNo bit/checkpoint/project saved. CDC/DRC/coverage still require review.\n[join $rows \n]\nGenerated_this_attempt=[join $produced {, }]\n$message"
        puts "DUAL_AXIS_REPORTS=$out STATUS=$result"
        if {$code} {return -options $options $message}
        return $out
    }
    proc run {} {
        variable root
        variable expected_top
        set project [one [get_projects -quiet] project]
        set name [get_property NAME $project]
        set dir [file normalize [get_property DIRECTORY $project]]
        if {![regexp -nocase {3d|dualaxis} $name] || [inside $dir $root] || [string equal -nocase $dir $root]} {
            error {STOP: open the external 3D/DualAxis project copy}
        }
        if {[get_property PART $project] ne {xc7z020clg400-2}} {error {STOP: expected xc7z020clg400-2 project}}
        if {![file isfile [file join $dir ${name}.xpr]]} {error {STOP: project launcher missing}}
        foreach item [get_runs -quiet] {
            if {[regexp -nocase {running|queued|launching} [get_property STATUS $item]]} {error "STOP: active run $item"}
        }
        set run [one [get_runs -quiet impl_1] impl_1]
        set state [get_property STATUS $run]
        if {![regexp {^(route_design|post_route_phys_opt_design|write_bitstream) Complete!?$} $state]} {
            error "STOP: impl_1 has not completed routing: $state"
        }
        if {[get_property NEEDS_REFRESH $run]} {error {STOP: impl_1 is out-of-date; do not force it up-to-date for this report}}
        if {[get_property PART $run] ne [get_property PART $project]} {error {STOP: project/run part mismatch}}
        set run_dir [file normalize [get_property DIRECTORY $run]]
        if {![inside $run_dir $dir]} {error {STOP: impl_1 points outside the project copy}}
        set top [get_property TOP [one [get_filesets -quiet sources_1] sources_1]]
        if {$top ne $expected_top || ![file isfile [file join $run_dir ${top}_routed.dcp]]} {
            error {STOP: unexpected source top or missing routed checkpoint}
        }
        if {[llength [get_designs -quiet]]} {error {STOP: close the current design view first; this script will not discard or save your in-memory edits}}
        # 只打开本工程的既有impl_1，结束后丢弃本脚本添加的内存约束，不改文件集。
        open_run impl_1
        set code [catch {
            if {[get_property CONSTRSET [current_design]] ne [get_property CONSTRSET $run]} {error {STOP: design/run constraint-set mismatch}}
            audit [file join $dir handoff dual_axis_reports]
        } message options]
        close_design
        if {$code} {return -options $options $message}
        return $message
    }
}
if {![info exists ::ss_dual_axis_report::library_only] || !$::ss_dual_axis_report::library_only} {ss_dual_axis_report::run}
