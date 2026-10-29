"""报告Tcl护栏与文件副作用的离线模型；不能证明Vivado命令/STA结果正确。"""
import hashlib
from pathlib import Path
import tempfile
import tkinter
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'project/bd/report_ps_dual_axis.tcl'


class Tests(unittest.TestCase):
    def setUp(self):
        work = ROOT / 'simulation/work'
        work.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='dual axis reports ', dir=work)
        self.addCleanup(self.tmp.cleanup)
        self.copy = Path(self.tmp.name) / 'user external project'
        self.copy.mkdir()
        self.run_dir = self.copy / 'SoundSight_PS_3D.runs/impl_1'
        self.run_dir.mkdir(parents=True)
        self.protected = [self.copy / 'SoundSight_PS_3D.xpr',
                          self.run_dir / 'soundsight_stm32_bd_wrapper_routed.dcp',
                          self.run_dir / 'soundsight_stm32_bd_wrapper.bit',
                          self.run_dir / 'original_timing.rpt']
        for file in self.protected:
            file.write_bytes(b'USER ORIGINAL ' + file.name.encode())
        self.before = {file: hashlib.sha256(file.read_bytes()).hexdigest() for file in self.protected}
        self.out = self.copy / 'handoff/dual_axis_reports'
        self.t = tkinter.Tcl()
        self.t.tk.wantobjects(False)
        self.t.eval('namespace eval ss_dual_axis_report {variable library_only 1}')
        self.t.call('source', str(SCRIPT))
        # 模型用户副本位于隔离测试树；替换仓库边界不影响真实XDC来源。
        self.t.setvar('dir', self.copy.as_posix())
        self.t.setvar('run_dir', self.run_dir.as_posix())
        self.t.eval(r'''
            set name SoundSight_PS_3D
            set part xc7z020clg400-2
            set design_part xc7z020clg400-2
            set tool_version 2025.2
            set status {write_bitstream Complete!}
            set refresh 0
            set runs {impl_1}
            set design_open 1
            set full_route 1
            set route_errors 0
            set source_top soundsight_stm32_bd_wrapper
            set report_top soundsight_stm32_bd_wrapper
            set empty_path {}
            set negative_path {}
            set infinite_path {}
            set wrong_requirement {}
            set wrong_pin {}
            set missing_port {}
            set legacy_worst 1
            set calls {}
            proc version {args} {return $::tool_version}
            proc get_projects {args} {return project}
            proc get_runs {args} {
                if {[lindex $args end] eq {impl_1}} {
                    if {[lsearch -exact $::runs impl_1]<0} {return {}}
                    return impl_1
                }
                return $::runs
            }
            proc get_designs {args} {if {$::design_open} {return design_1};return {}}
            proc current_design {args} {if {$::design_open} {return design_1};return {}}
            proc get_filesets {args} {return sources_1}
            proc get_property {key object} {
                switch $key {
                    NAME {if {$object eq {project}} {return $::name};return $object}
                    DIRECTORY {if {$object eq {project}} {return $::dir};return $::run_dir}
                    PART {if {$object eq {design_1}} {return $::design_part};return $::part}
                    STATUS {return $::status}
                    NEEDS_REFRESH {return $::refresh}
                    TOP {return $::source_top}
                    CONSTRSET {return constrs_1}
                    DIRECTION {return OUT}
                    IOSTANDARD {return LVCMOS33}
                    PACKAGE_PIN {
                        if {$object eq $::wrong_pin} {return W14}
                        if {$object eq {servo_pwm}} {return T15};return W16
                    }
                    PERIOD {return 16.276}
                    SLACK {
                        if {$object eq $::negative_path} {return -0.125}
                        if {$object eq $::infinite_path} {return inf}
                        if {[string match servo*_min $object]} {return inf}
                        return 0.311
                    }
                    REQUIREMENT {
                        if {$object eq $::wrong_requirement} {return 30.0}
                        if {[string match *_max $object]} {return 20.0};return 0.0
                    }
                    DATAPATH_DELAY {return 7.392}
                    STARTPOINT_PIN {
                        if {$object eq {servo_pwm_max} && $::legacy_worst} {return top/regs/manual/guard/pwm_o_reg/C}
                        set axis [expr {[string match servo_vertical_pwm_* $object] ? "v" : "h"}]
                        return top/with_dual_axis.dual_axis/${axis}_guard/pwm_o_reg/C
                    }
                    ENDPOINT_PIN {
                        if {[string match servo_vertical_pwm_* $object]} {return servo_vertical_pwm}
                        return servo_pwm
                    }
                }
                error "UNMODELED get_property $key $object"
            }
            proc all_registers {args} {return {h_clock_pin v_clock_pin}}
            proc get_ports {args} {
                set port [lindex $args end]
                if {$port eq $::missing_port} {return {}}
                return $port
            }
            proc get_pins {args} {
                set pattern [lindex $args end]
                set axis [expr {[string match */h_guard/* $pattern] ? "h" : "v"}]
                return top/with_dual_axis.dual_axis/${axis}_guard/pwm_o_reg/C
            }
            proc get_clocks {args} {return clk_6144}
            proc set_max_delay {args} {lappend ::calls [list set_max_delay {*}$args]}
            proc set_min_delay {args} {lappend ::calls [list set_min_delay {*}$args]}
            proc get_timing_paths {args} {
                set kind [lindex $args [expr {[lsearch -exact $args -delay_type]+1}]]
                set index [lsearch -exact $args -to]
                set port [expr {$index<0 ? "global" : [lindex $args [expr {$index+1}]]}]
                set path ${port}_${kind}
                set from [lindex $args [expr {[lsearch -exact $args -from]+1}]]
                if {[string match */pwm_o_reg/C $from]} {set path ${port}_guard_${kind}}
                if {$path eq $::empty_path} {return {}}
                return $path
            }
            proc emit {command args} {
                lappend ::calls [list $command {*}$args]
                set file [lindex $args [expr {[lsearch -exact $args -file]+1}]]
                set h [open $file w]
                puts $h "| Design       : $::report_top"
                puts $h "MOCK_REPORT $command"
                close $h
            }
            proc report_route_status {args} {
                if {[lsearch -exact $args -boolean_check]>=0} {
                    if {[lindex $args end] eq {ROUTED_FULLY}} {return $::full_route}
                    return $::route_errors
                }
                emit report_route_status {*}$args
            }
            foreach command {check_timing report_timing report_timing_summary report_bus_skew report_cdc
                             report_clock_interaction report_exceptions report_drc report_io report_utilization} {
                proc $command {args} [format {emit %s {*}$args} $command]
            }
            proc open_run {run} {lappend ::calls [list open_run $run];set ::design_open 1}
            proc close_design {} {lappend ::calls close_design;set ::design_open 0}
        ''')

    def audit(self):
        return self.t.call('ss_dual_axis_report::audit', self.out.as_posix())

    def calls(self):
        return [tuple(map(str, self.t.splitlist(row)))
                for row in self.t.splitlist(self.t.getvar('calls'))]

    def assert_protected(self):
        self.assertEqual(self.before, {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in self.protected})

    def prepare_user_entry(self):
        self.t.setvar('design_open', 0)
        # 正式run拒绝仓库内工程；测试副本所在临时目录用独立根模拟边界。
        repo = Path(self.tmp.name) / 'source repo'
        xdc = repo / 'project/sdc/ps/dual_axis_output_timing.xdc'
        xdc.parent.mkdir(parents=True)
        xdc.write_bytes((ROOT / 'project/sdc/ps/dual_axis_output_timing.xdc').read_bytes())
        self.t.setvar('::ss_dual_axis_report::root', repo.as_posix())

    def test_complete_reports_preserve_input_files_and_repeat(self):
        self.audit()
        self.audit()
        self.assertTrue((self.out / 'audit_status.txt').read_text().startswith('REPORTS_COMPLETE'))
        self.assertEqual(len(list(self.out.glob('*.rpt'))), 18)
        self.assertIn('HOLD_N_A', (self.out / 'audit_status.txt').read_text())
        self.assertIn('manual/guard', (self.out / 'audit_status.txt').read_text())
        self.assert_protected()
        cdc = next(row for row in self.calls() if row[0] == 'report_cdc')
        self.assertIn('-no_waiver', cdc)
        self.assertIn('-all_checks_per_endpoint', cdc)
        self.assertNotIn('-severity', cdc)
        maximum = next(row for row in self.calls() if row[0] == 'set_max_delay')
        self.assertEqual(maximum[-1], 'servo_vertical_pwm')
        self.assertIn('20.000', maximum)
        self.assertFalse(any(row[0] == 'set_min_delay' for row in self.calls()))

    def test_empty_negative_infinite_or_wrong_budget_keeps_full_reports(self):
        for variable, value, error in [
            ('empty_path', 'servo_vertical_pwm_max', 'empty timing path'),
            ('empty_path', 'servo_pwm_guard_max', 'empty timing path'),
            ('negative_path', 'servo_pwm_max', 'negative slack'),
            ('negative_path', 'global_max', 'negative slack'),
            ('infinite_path', 'servo_vertical_pwm_max', 'non-finite slack'),
            ('wrong_requirement', 'servo_pwm_max', 'expected requirement'),
        ]:
            with self.subTest(variable=variable, value=value):
                self.t.setvar(variable, value)
                with self.assertRaisesRegex(tkinter.TclError, error):
                    self.audit()
                self.assertTrue((self.out / 'audit_status.txt').read_text().startswith('ERROR'))
                self.assertTrue((self.out / 'cdc.rpt').is_file())
                self.assertTrue((self.out / 'utilization.rpt').is_file())
                self.assert_protected()
                self.t.setvar(variable, '')

    def test_wrong_design_route_clock_pin_or_port_stops_before_constraints(self):
        for variable, value, error in [
            ('design_part', 'xc7z020clg400-1', 'expected xc7z020'),
            ('full_route', '0', 'not fully routed'),
            ('route_errors', '1', 'not fully routed'),
            ('wrong_pin', 'servo_vertical_pwm', 'unexpected direction/pin'),
            ('missing_port', 'servo_vertical_pwm', 'expected one servo_vertical_pwm'),
        ]:
            old = self.t.getvar(variable)
            self.t.setvar(variable, value)
            self.t.setvar('calls', ())
            with self.subTest(variable=variable):
                with self.assertRaisesRegex(tkinter.TclError, error):
                    self.audit()
                self.assertFalse(any(row[0] == 'set_max_delay' for row in self.calls()))
                self.assert_protected()
            self.t.setvar(variable, old)

    def test_design_header_must_match_source_top(self):
        self.t.setvar('report_top', 'another_wrapper')
        with self.assertRaisesRegex(tkinter.TclError, 'source/design top mismatch'):
            self.audit()
        self.assert_protected()

    def test_user_entry_reopens_only_completed_run_and_closes_its_view(self):
        self.prepare_user_entry()
        self.t.call('ss_dual_axis_report::run')
        self.assertEqual(self.calls()[0], ('open_run', 'impl_1'))
        self.assertEqual(self.calls()[-1], ('close_design',))
        self.assert_protected()

    def test_user_entry_refuses_missing_active_stale_or_unrouted_run(self):
        self.prepare_user_entry()
        for variable, value, error in [
            ('runs', (), 'expected one impl_1'),
            ('status', 'Running', 'active run'),
            ('status', 'Queued', 'active run'),
            ('status', 'Launching', 'active run'),
            ('status', 'place_design Complete!', 'has not completed routing'),
            ('refresh', '1', 'out-of-date'),
            ('design_open', '1', 'close the current design'),
            ('name', 'SoundSight_PS_Reliaze', 'external 3D/DualAxis'),
        ]:
            old = self.t.getvar(variable)
            self.t.setvar(variable, value)
            with self.subTest(variable=variable, value=value):
                with self.assertRaisesRegex(tkinter.TclError, error):
                    self.t.call('ss_dual_axis_report::run')
                self.assertFalse(any(row[0] == 'open_run' for row in self.calls()))
                self.assert_protected()
            self.t.setvar(variable, old)

    def test_no_construction_hardware_or_project_mutation_commands(self):
        # 未在模型中声明任何写工程/构建/硬件命令；静态检查再防止藏在未走到的分支。
        text = SCRIPT.read_text(encoding='utf-8')
        for command in ('launch_runs', 'synth_design', 'place_design', 'write_bitstream',
                        'write_checkpoint', 'save_project', 'save_constraints', 'add_files',
                        'remove_files', 'open_hw_manager', 'program_hw_devices', 'set_false_path'):
            self.assertNotRegex(text, rf'(?m)^\s*{command}\b')
        self.assertNotIn('file delete', text)


if __name__ == '__main__':
    unittest.main()
