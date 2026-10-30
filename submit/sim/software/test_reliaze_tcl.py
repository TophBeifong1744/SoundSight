"""Tcl syntax and pre-mutation target guards; no Vivado or external writes."""
from pathlib import Path
import tkinter
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ReliazeTclTests(unittest.TestCase):
    def setUp(self):
        self.t = tkinter.Tcl()
        self.t.setvar('ss_reliaze_library_only', 1)
        self.t.call('source', str(ROOT/'project/bd/update_ps_reliaze.tcl'))
        self.t.eval('''
            set mock_name SoundSight_PS_Reliaze
            set mock_dir F:/unit-test/SoundSight_PS_Reliaze
            set mock_part xc7z020clg400-2
            set mock_status {Not started}
            proc get_projects {args} {return p}
            proc get_runs {args} {return r}
            proc get_property {key obj} {
                switch $key {
                    NAME {return $::mock_name}
                    DIRECTORY {return $::mock_dir}
                    PART {return $::mock_part}
                    STATUS {return $::mock_status}
                    default {error "Unexpected property $key"}
                }
            }
        ''')

    def reject(self, expected):
        with self.assertRaisesRegex(tkinter.TclError, expected):
            self.t.call('ss_reliaze_update::run')

    def test_loaded_complete_script(self):
        self.assertEqual(int(self.t.call('info', 'complete',
                         (ROOT/'project/bd/update_ps_reliaze.tcl').read_text('utf-8'))), 1)

    def test_original_servo_rejected(self):
        self.t.setvar('mock_name', 'SoundSight_PS_Servo')
        self.reject('open the external SoundSight_PS_Reliaze copy')

    def test_repository_project_rejected(self):
        self.t.setvar('mock_dir', str(ROOT/'project/par'))
        self.reject('open the external SoundSight_PS_Reliaze copy')

    def test_wrong_part_rejected(self):
        self.t.setvar('mock_part', 'xc7z020clg400-1')
        self.reject('wrong part')

    def test_active_run_rejected(self):
        self.t.setvar('mock_status', 'Running synth_design')
        self.reject('active run')

    def test_bd_open_cannot_clobber_validated_paths(self):
        self.t.eval('''
            proc open_bd_design {args} {uplevel 1 {set dir tool_internal_path}}
            proc probe_scope {} {
                set dir validated_project_path
                ss_reliaze_update::open_design fixture.bd
                return $dir
            }
        ''')
        self.assertEqual(self.t.call('probe_scope'), 'validated_project_path')

    def control_fixture(self, mode):
        self.t.eval('''
            set pins [dict create ps_link/run_enable run_old compute/draining drain_old \
                compute/audio_run run_new compute/audio_draining drain_new]
            proc get_bd_pins {args} {
                set p [lindex $args end]
                if {[dict exists $::pins $p]} {return $p}
                return {}
            }
            proc get_bd_nets {args} {return [dict get $::pins [lindex $args end]]}
        ''')
        if mode in ('old', 'mixed'):
            self.t.eval('dict set pins audio_capture/run_enable_async run_old; dict set pins audio_capture/compute_draining_async drain_old')
        if mode in ('new', 'mixed'):
            self.t.eval('dict set pins audio_capture/run_enable run_new; dict set pins audio_capture/compute_draining drain_new')

    def test_old_audio_control_migration_is_read_only(self):
        self.control_fixture('old')
        result = self.t.call('ss_reliaze_update::control_migration')
        self.assertEqual(int(self.t.call('llength', result)), 2)
        self.assertEqual(self.t.call('lindex', result, 0, 0), 'audio_capture/run_enable_async')
        self.assertEqual(self.t.call('lindex', result, 1, 0), 'audio_capture/compute_draining_async')

    def test_repeat_control_update_needs_no_disconnect(self):
        self.control_fixture('new')
        self.assertFalse(self.t.call('ss_reliaze_update::control_migration'))

    def test_mixed_or_missing_ports_rejected(self):
        for mode in ('mixed', 'missing'):
            self.control_fixture(mode)
            with self.assertRaisesRegex(tkinter.TclError, 'partially migrated'):
                self.t.call('ss_reliaze_update::control_migration')

    def test_wrong_control_source_rejected(self):
        self.control_fixture('old')
        self.t.eval('dict set pins audio_capture/run_enable_async unrelated_net')
        with self.assertRaisesRegex(tkinter.TclError, 'unexpected audio control connection'):
            self.t.call('ss_reliaze_update::control_migration')


if __name__ == '__main__':
    unittest.main()
