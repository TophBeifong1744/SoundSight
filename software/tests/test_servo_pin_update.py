"""Execute the delivered Tcl against real temporary XDC files and a fake project.

This verifies file edits/guards, not Vivado placement or board pin voltages.
"""
from pathlib import Path
import tempfile
import tkinter
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PinTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT/'simulation/work'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='ss pin test ', dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.h = self.root/'board_pins.xdc'
        self.v = self.root/'horizontal_reserved.xdc'
        self.extra = self.root/'other.xdc'
        self.h.write_text('set_property PACKAGE_PIN V7 [get_ports servo_pwm]\n'
                          'set_property PACKAGE_PIN V15 [get_ports {pdm_data[3]}]\n'
                          'set_property IOSTANDARD LVCMOS33 [get_ports servo_pwm]\n')
        self.v.write_text('set_property PACKAGE_PIN U7 [get_ports servo_vertical_pwm]\n'
                          'set_property IOSTANDARD LVCMOS33 [get_ports servo_vertical_pwm]\n')
        self.extra.write_text('# Preserve all timing constraints\nset_false_path -from foo -to bar\n')
        self.t = tkinter.Tcl()
        self.t.eval('namespace eval ss_servo_pins {variable library_only 1}')
        self.t.call('source', str(ROOT/'project/bd/update_ps_servo_pins.tcl'))
        # Model an extracted kit and an external project. Avoid this machine's
        # sandbox AppData junction, which Tcl normalizes differently from Python.
        self.t.setvar('ss_servo_pins::root', (self.root/'kit').as_posix())
        for key, value in dict(projectdir=self.root.as_posix(), projectname='My_Servo',
                               part='xc7z020clg400-2', status='Complete',
                               files=tuple(p.as_posix() for p in (self.h,self.v,self.extra))).items():
            self.t.setvar(key, value)
        self.t.eval('''
            proc get_projects {args} {return project}
            proc get_runs {args} {return impl_1}
            proc get_filesets {args} {return constrs_1}
            proc get_files {args} {return $::files}
            proc list_property {args} {return IS_GENERATED}
            proc get_property {p object} {
                switch $p {
                    NAME {if {$object eq "project"} {return $::projectname}; return $object}
                    DIRECTORY {return $::projectdir}
                    PART {return $::part}
                    STATUS {return $::status}
                    IS_GENERATED {return 0}
                    default {error "unexpected property $p"}
                }
            }
        ''')

    def test_rewrites_only_two_pins_with_backup_and_is_repeatable(self):
        old_h,old_v,other = self.h.read_bytes(),self.v.read_bytes(),self.extra.read_bytes()
        self.t.call('ss_servo_pins::run')
        self.assertEqual(self.h.read_bytes(),old_h.replace(b'PACKAGE_PIN V7',b'PACKAGE_PIN T15'))
        self.assertEqual(self.v.read_bytes(),old_v.replace(b'PACKAGE_PIN U7',b'PACKAGE_PIN W15'))
        self.assertEqual(self.extra.read_bytes(),other)
        backup = next((self.root/'handoff').iterdir())
        self.assertEqual((backup/self.h.name).read_bytes(),old_h)
        self.assertEqual((backup/self.v.name).read_bytes(),old_v)
        once = (self.h.read_bytes(),self.v.read_bytes())
        self.t.call('ss_servo_pins::run')
        self.assertEqual((self.h.read_bytes(),self.v.read_bytes()),once)

    def refused(self, pattern):
        before = (self.h.read_bytes(),self.v.read_bytes())
        with self.assertRaisesRegex(tkinter.TclError,pattern): self.t.call('ss_servo_pins::run')
        self.assertEqual((self.h.read_bytes(),self.v.read_bytes()),before)
        self.assertFalse((self.root/'handoff').exists())

    def test_busy_original_wrong_part_refused(self):
        for key,bad,good,reason in (('status','Running','Complete','active run'),
                                   ('projectname','Original_Volume','My_Servo','COPY'),
                                   ('part','xc7z020clg400-1','xc7z020clg400-2','wrong part')):
            self.t.setvar(key,bad); self.refused(reason); self.t.setvar(key,good)

    def test_pin_conflicts_refused_before_either_write(self):
        for pin in ('T15','W15'):
            self.extra.write_text('set_property PACKAGE_PIN '+pin+' [get_ports other]\n')
            self.refused('collision')

    def test_duplicate_or_unknown_assignment_refused(self):
        self.h.write_text('set_property PACKAGE_PIN T15 [get_ports servo_pwm]\n'*2)
        self.refused('one known')
        self.h.write_text('set_property PACKAGE_PIN A1 [get_ports servo_pwm]\n')
        self.refused('one known')

    def test_missing_vertical_refused(self):
        self.t.setvar('files',(self.h.as_posix(),))
        self.refused('expected one board_pins')

    def test_external_constraint_refused(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'simulation/work') as temp:
            p=Path(temp)/self.v.name; p.write_bytes(self.v.read_bytes())
            self.t.setvar('files',(self.h.as_posix(),p.as_posix()))
            self.refused('outside your project')

    def test_comments_braces_and_crlf_preserved(self):
        text='# set_property PACKAGE_PIN V7 [get_ports servo_pwm]\r\nset_property PACKAGE_PIN V7 [get_ports {servo_pwm}]\r\n'
        actual=self.t.call('ss_servo_pins::rewrite',text,'horizontal')
        self.assertEqual(actual,text.replace('V7 [get_ports {servo_pwm}]','T15 [get_ports servo_pwm]'))


if __name__=='__main__': unittest.main()
