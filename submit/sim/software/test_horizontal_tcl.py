"""Guard/helper-only Tcl tests; native BD evidence is separate."""
from pathlib import Path
import tkinter
import unittest

ROOT = Path(__file__).resolve().parents[2]


class GuardTests(unittest.TestCase):
    def interpreter(self, name='My_Servo', part='xc7z020clg400-2', status='Not started'):
        t = tkinter.Tcl()
        t.setvar('mockname', name); t.setvar('mockpart', part); t.setvar('mockstatus', status)
        t.eval('''
          proc get_projects {args} {return project}
          proc get_property {p object} {
            switch $p {
              NAME {return $::mockname}
              DIRECTORY {return {C:/some external copy}}
              PART {return $::mockpart}
              STATUS {return $::mockstatus}
              default {error "unexpected read $p"}
            }
          }
          proc get_runs {args} {return synth_1}
          proc current_bd_design {args} {error {REACHED_BD_STAGE}}
        ''')
        return t

    def test_original_volume_refused_before_touching_files(self):
        t = self.interpreter(name='SoundSight_PS_Volume')
        with self.assertRaisesRegex(tkinter.TclError, 'COPY named'):
            t.call('source', str(ROOT/'project/bd/update_ps_horizontal.tcl'))

    def test_active_run_refused(self):
        for status in ('Running', 'Queued', 'Launching'):
            t = self.interpreter(status=status)
            with self.assertRaisesRegex(tkinter.TclError, 'active run'):
                t.call('source', str(ROOT/'project/bd/update_ps_horizontal.tcl'))

    def test_wrong_part_refused(self):
        t = self.interpreter(part='xc7z020clg400-1')
        with self.assertRaisesRegex(tkinter.TclError, 'wrong part'):
            t.call('source', str(ROOT/'project/bd/update_ps_horizontal.tcl'))

    def test_idle_copy_reaches_bd_without_creating_project(self):
        t = self.interpreter(status='Out-of-date')
        with self.assertRaisesRegex(tkinter.TclError, 'REACHED_BD_STAGE'):
            t.call('source', str(ROOT/'project/bd/update_ps_horizontal.tcl'))
        self.assertEqual(t.getvar('::ss_volume_update::library_only'), 0)


if __name__ == '__main__': unittest.main()
