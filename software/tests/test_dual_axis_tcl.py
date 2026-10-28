"""Tcl复制/登记/保护的离线模型；不等同真实Vivado Validate或输出生成。"""
from pathlib import Path
import tempfile
import tkinter
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'project/bd/update_ps_dual_axis.tcl'
REPLACE = ('bd_ps_link.v', 'ss_ps_link.sv', 'ss_ps_control_regs.sv',
           'ss_dual_axis_control.sv', 'motor_drive.v', 'i17_turntable_pwm_guard.sv')


class Tests(unittest.TestCase):
    def setUp(self):
        work = ROOT / 'simulation/work'
        work.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='dual axis Tcl ', dir=work)
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.repo = base / 'source repo'
        self.copy = base / 'user external copy'
        self.copy.mkdir()
        (self.repo / 'project/rtl').mkdir(parents=True)
        (self.repo / 'project/sdc/ps').mkdir(parents=True)
        self.timing = self.repo / 'project/sdc/ps/dual_axis_output_timing.xdc'
        self.timing.write_bytes((ROOT / 'project/sdc/ps/dual_axis_output_timing.xdc').read_bytes())
        for name in REPLACE:
            (self.repo / 'project/rtl' / name).write_text('NEW ' + name)
        self.src = [self.copy / n for n in REPLACE if n != 'ss_dual_axis_control.sv']
        self.src += [self.copy / 'user_extra.sv', self.copy / 'user table.mem']
        for p in self.src:
            p.write_text('USER ' + p.name)
        self.bd = self.copy / 'design.bd'
        self.bd.write_text('USER BD')
        (self.copy / 'SoundSight_PS_3D.xpr').write_text('USER XPR')
        self.xdc = self.copy / 'board pins.xdc'
        self.xdc.write_text('set_property PACKAGE_PIN T15 [get_ports {servo_pwm}]\n'
                            'set_property PACKAGE_PIN W15 [get_ports {servo_vertical_pwm}]\n'
                            '# preserved user clock constraint\n')
        self.t = tkinter.Tcl()
        self.t.eval('namespace eval ss_dual_axis_update {variable library_only 1}')
        self.t.call('source', str(SCRIPT))
        self.t.setvar('::ss_dual_axis_update::root', self.repo.as_posix())
        for name, value in [('srcs', tuple(p.as_posix() for p in self.src)),
                            ('xdcs', (self.xdc.as_posix(),)), ('bd', self.bd.as_posix()),
                            ('dir', self.copy.as_posix()), ('name', 'SoundSight_PS_3D'),
                            ('part', 'xc7z020clg400-2'), ('status', 'Out-of-date')]:
            self.t.setvar(name, value)
        self.t.eval('''
            set calls {};set params [dict create AUDIO_ENABLE 1 LEVEL_ENABLE 1 ACTUATOR_BOUND 1 CLK_FREQ_HZ 61440000 SERVO_MAX 360]
            proc get_projects {args} {return project}
            proc get_filesets {name} {return $name}
            proc get_runs {args} {return synth_1}
            proc current_bd_design {args} {return design}
            proc current_bd_instance {args} {}
            proc get_files {args} {
                if {[lsearch -exact $args -of_objects]>=0} {
                    if {[lindex $args end] eq {sources_1}} {return $::srcs}
                    return $::xdcs
                }
                set q [lindex $args end]
                if {[llength $q]==1} {set q [lindex $q 0]}
                if {[string match *.bd $q]} {return [list $::bd]}
                set result {}
                foreach p [concat $::srcs $::xdcs] {if {[string match $q $p]} {lappend result $p}}
                return $result
            }
            proc get_bd_cells {args} {if {[lindex $args end] eq {link}} {return {}};return ps_link}
            proc get_bd_ports {args} {return [lindex $args end]}
            proc get_bd_pins {args} {
                set x [lindex $args end]
                if {[string match net_* $x]} {return ps_link/[string range $x 4 end]}
                return $x
            }
            proc get_bd_nets {args} {return net_[lindex $args end]}
            proc list_property {object} {
                if {$object eq {ps_link}} {
                    set props {VLNV};foreach key [dict keys $::params] {lappend props CONFIG.$key};return $props
                }
                return {IS_GENERATED PARENT_COMPOSITE_FILE FILE_TYPE LIBRARY USED_IN_SYNTHESIS USED_IN_SIMULATION USED_IN_IMPLEMENTATION PROCESSING_ORDER IS_ENABLED}
            }
            proc get_property {prop object} {
                if {$object eq {project}} {
                    switch $prop {NAME {return $::name} DIRECTORY {return $::dir} PART {return $::part}}
                }
                switch $prop {
                    NAME {return $object} STATUS {return $::status} TOP {return design_wrapper}
                    VLNV {return xilinx.com:module_ref:bd_ps_link:1.0}
                    IS_GENERATED {return 0} PARENT_COMPOSITE_FILE {return {}}
                    FILE_TYPE {return SystemVerilog} LIBRARY {return xil_defaultlib}
                    PROCESSING_ORDER {return NORMAL}
                    USED_IN_SYNTHESIS - USED_IN_SIMULATION - USED_IN_IMPLEMENTATION - IS_ENABLED {return 1}
                }
                if {[string match CONFIG.* $prop]} {return [dict get $::params [string range $prop 7 end]]}
                error "unexpected get_property $prop $object"
            }
            proc set_property {args} {
                if {[lindex $args 0] eq {CONFIG.DUAL_AXIS_ENABLE}} {dict set ::params DUAL_AXIS_ENABLE [lindex $args 1]}
            }
            proc remove_files {objects} {
                foreach x $objects {
                    foreach collection {srcs xdcs} {
                        set index [lsearch -exact [set ::$collection] $x]
                        if {$index>=0} {set ::$collection [lreplace [set ::$collection] $index $index]}
                    }
                }
            }
            proc add_files {args} {
                set index [lsearch -exact $args -fileset];set fs [lindex $args [expr {$index+1}]]
                set collection [expr {$fs eq {sources_1} ? "srcs" : "xdcs"}]
                foreach p [lindex $args end] {if {![file isfile $p]} {error "missing add $p"};lappend ::$collection $p}
            }
            proc save_bd_design {} {lappend ::calls SAVE}
            proc close_project {} {lappend ::calls CLOSE}
            proc open_project {p} {if {$p ne [file join $::dir ${::name}.xpr]} {error WRONG_PROJECT};lappend ::calls OPEN}
            proc open_bd_design {p} {if {[lindex $p 0] ne $::bd} {error WRONG_BD}}
            proc update_compile_order {args} {lappend ::calls COMPILE_ORDER}
            proc get_ips {args} {return design_bd_ps_link_0_0}
            proc update_module_reference {args} {
                if {$args ne {-verbose design_bd_ps_link_0_0}} {error WRONG_MODULE_OBJECT}
                dict set ::params DUAL_AXIS_ENABLE 0;lappend ::calls REFRESH
            }
            proc validate_bd_design {} {lappend ::calls VALIDATE}
            proc generate_target {args} {
                if {[lindex [lindex $args 1] 0] ne $::bd} {error NESTED_BD_LIST}
                lappend ::calls PRODUCTS
            }
            proc make_wrapper {args} {
                set p [file join $::dir design_wrapper.v];set h [open $p w];puts $h {GENERATED_WRAPPER};close $h
                return [list $p]
            }
        ''')

    def run_script(self):
        self.t.call('ss_dual_axis_update::run')

    def test_space_paths_copy_preserve_and_native_call_order(self):
        self.run_script()
        for name in REPLACE:
            self.assertEqual((self.copy / 'dual_axis_sources' / name).read_text(), 'NEW ' + name)
        for name in ['user_extra.sv', 'user table.mem']:
            self.assertEqual((self.copy / 'dual_axis_sources' / name).read_text(), 'USER ' + name)
        self.assertEqual((self.copy / 'dual_axis_constraints/01' / self.xdc.name).read_bytes(), self.xdc.read_bytes())
        self.assertEqual((self.copy / 'dual_axis_constraints' / self.timing.name).read_bytes(), self.timing.read_bytes())
        self.assertEqual(self.t.eval('dict get $params DUAL_AXIS_ENABLE'), '1')
        calls = self.t.splitlist(self.t.getvar('calls'))
        self.assertLess(calls.index('REFRESH'), calls.index('VALIDATE'))
        self.assertLess(calls.index('VALIDATE'), calls.index('PRODUCTS'))
        self.assertEqual(len(list((self.copy / 'handoff').glob('before_dual_axis_*'))), 1)
        self.run_script()  # 重复运行仍保存当前内容，源登记不重复。
        sources = tuple(map(str, self.t.splitlist(self.t.getvar('srcs'))))
        self.assertEqual(len(sources), len(set(sources)))
        constraints = tuple(map(str, self.t.splitlist(self.t.getvar('xdcs'))))
        self.assertEqual(len(constraints), len(set(constraints)))
        self.assertEqual(sum(Path(p).name == self.timing.name for p in constraints), 1)

    def test_missing_timing_budget_refused_before_copy(self):
        self.timing.unlink()
        with self.assertRaisesRegex(tkinter.TclError, 'missing dual-axis timing'):
            self.run_script()
        self.assertFalse((self.copy / 'handoff').exists())

    def test_unregistered_user_timing_file_is_preserved(self):
        target = self.copy / 'dual_axis_constraints' / self.timing.name
        target.parent.mkdir()
        target.write_text('USER PRIVATE CONSTRAINT')
        with self.assertRaisesRegex(tkinter.TclError, 'unregistered timing file'):
            self.run_script()
        self.assertEqual(target.read_text(), 'USER PRIVATE CONSTRAINT')
        self.assertFalse((self.copy / 'handoff').exists())

    def test_original_or_wrong_part_refused_before_copy(self):
        for key, value, message in [('name', 'SoundSight_PS_PCM', 'COPY named'),
                                     ('part', 'xc7z020clg400-1', 'expected xc7z020')]:
            old = self.t.getvar(key)
            self.t.setvar(key, value)
            with self.assertRaisesRegex(tkinter.TclError, message):
                self.run_script()
            self.t.setvar(key, old)
        self.assertFalse((self.copy / 'handoff').exists())

    def test_running_project_refused(self):
        for status in ['Running', 'Queued', 'Launching']:
            self.t.setvar('status', status)
            with self.assertRaisesRegex(tkinter.TclError, 'active run'):
                self.run_script()

    def test_pin_conflict_refused_before_copy(self):
        self.xdc.write_text(self.xdc.read_text().replace('W15', 'W14'))
        with self.assertRaisesRegex(tkinter.TclError, 'unexpected servo pin'):
            self.run_script()
        self.assertFalse((self.copy / 'handoff').exists())

    def test_repository_itself_is_never_modified(self):
        self.t.setvar('dir', self.repo.as_posix())
        with self.assertRaisesRegex(tkinter.TclError, 'COPY named'):
            self.run_script()


if __name__ == '__main__':
    unittest.main()
