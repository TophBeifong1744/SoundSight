"""Offline Tcl command model: copy/backup only; not a Vivado validation claim."""
from pathlib import Path
import tkinter
import unittest
import test_dual_axis_tcl as fixture
ROOT = fixture.ROOT


class LatestTclTests(unittest.TestCase):
    def setUp(self):
        fixture.Tests.setUp(self)
        for base, prefix in ((self.repo/'project/rtl','NEW '),(self.copy,'USER ')):
            (base/'ss_snapshot_queue.sv').write_text(prefix+'ss_snapshot_queue.sv')
        self.src.append(self.copy/'ss_snapshot_queue.sv')
        self.t.setvar('srcs',tuple(p.as_posix() for p in self.src))
        self.t.eval('namespace eval ss_latest_result_update {variable library_only 1}')
        self.t.call('source',str(ROOT/'project/bd/update_ps_latest_result.tcl'))
        self.t.setvar('::ss_latest_result_update::root',self.repo.as_posix())
        self.t.eval('''
          dict set ::params DUAL_AXIS_ENABLE 1
          proc update_module_reference {args} {
            if {$args ne {-verbose design_bd_ps_link_0_0}} {error WRONG_MODULE_OBJECT}
            lappend ::calls REFRESH
          }
        ''')

    def test_only_two_sources_changed_and_backup_kept(self):
        original={p:p.read_bytes() for p in [*self.src,self.xdc,self.bd]}
        self.t.call('ss_latest_result_update::run')
        names=('ss_snapshot_queue.sv','ss_ps_control_regs.sv')
        backup=list((self.copy/'handoff').glob('before_latest_result_*'))
        self.assertEqual(len(backup),1)
        for p,data in original.items():
            if p.name in names:
                self.assertEqual(p.read_bytes(),(self.repo/'project/rtl'/p.name).read_bytes())
                self.assertEqual((backup[0]/p.name).read_bytes(),data)
            else: self.assertEqual(p.read_bytes(),data)
        self.assertEqual(self.t.eval('dict get $params DUAL_AXIS_ENABLE'),'1')
        self.assertNotIn('CLOSE',self.t.splitlist(self.t.getvar('calls')))

    def test_busy_and_wrong_configuration_rejected_before_write(self):
        for state in ('Running','Queued','Launching'):
            self.t.setvar('status',state)
            with self.assertRaisesRegex(tkinter.TclError,'active run'):
                self.t.call('ss_latest_result_update::run')
        self.t.setvar('status','Out-of-date')
        self.t.eval('dict set ::params AUDIO_ENABLE 0')
        with self.assertRaisesRegex(tkinter.TclError,'AUDIO_ENABLE'):
            self.t.call('ss_latest_result_update::run')
        self.assertFalse((self.copy/'handoff').exists())

    def test_refresh_parameter_loss_stops_before_success(self):
        self.t.eval('proc update_module_reference {args} {dict set ::params AUDIO_ENABLE 0}')
        with self.assertRaisesRegex(tkinter.TclError,'AUDIO_ENABLE'):
            self.t.call('ss_latest_result_update::run')
        self.assertTrue(list((self.copy/'handoff').glob('before_latest_result_*')))

    def test_external_source_reference_rejected(self):
        outside=self.repo/'project/rtl/ss_snapshot_queue.sv'
        srcs=[p for p in self.src if p.name!='ss_snapshot_queue.sv']+[outside]
        self.t.setvar('srcs',tuple(p.as_posix() for p in srcs))
        with self.assertRaisesRegex(tkinter.TclError,'source not copied'):
            self.t.call('ss_latest_result_update::run')
        self.assertFalse((self.copy/'handoff').exists())


if __name__=='__main__':
    unittest.main()
