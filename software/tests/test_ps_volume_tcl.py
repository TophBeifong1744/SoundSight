"""Real Tcl/file copies with mocked Vivado commands; no Vivado or hardware.

These tests check path/backup/control flow, not BD validation or EDA results.
"""
from pathlib import Path
import shutil
import tempfile
import tkinter
import unittest

ROOT = Path(__file__).resolve().parents[2]
MOCK = r'''
set files {}; set notes {}; set runstate {Out-of-date}; set fail_validate 0; set fail_refresh 0
set nets [dict create]; set parameters [dict create]
proc get_projects {args} {return project}
proc get_runs {args} {return synth_1}
proc get_filesets {args} {return [lindex $args end]}
proc close_project {} {lappend ::notes close_project}
proc open_project {path} {
    if {$::fail_refresh} {error {injected reopen failure}}
    if {![file isfile $path]} {error {missing project}}
    lappend ::notes reopen
}
proc open_bd_design {path} {lappend ::notes open_bd}
proc current_bd_design {args} {return test_bd}
proc current_bd_instance {args} {}
proc get_bd_cells {args} {
    set name [lindex $args end]
    if {$name in {compute ps_link}} {return $name}
    return {}
}
proc get_property {name object} {
    switch $name {
        DIRECTORY {return $::projectdir}
        PART {return xc7z020clg400-2}
        STATUS {return $::runstate}
        TOP {return test_bd_wrapper}
        NAME {if {$object eq "project"} {return Demo}; return $object}
        VLNV {if {$object eq "compute"} {return xilinx.com:module_ref:bd_clean_compute:1.0}; return xilinx.com:module_ref:bd_ps_link:1.0}
        FILE_TYPE {return SystemVerilog}
        LIBRARY {return xil_defaultlib}
        USED_IN_SYNTHESIS - USED_IN_IMPLEMENTATION - USED_IN_SIMULATION {return 1}
        default {error "unmodelled property $name"}
    }
}
proc get_files {args} {
    if {[lsearch -exact $args -of_objects]>=0} {
        if {[lindex $args end] eq "constrs_1"} {return $::constraints}
        return $::files
    }
    set target [lindex [lindex $args end] 0]
    if {[file extension $target] eq ".xdc"} {return $target}
    return [list $::bdpath]
}
proc remove_files {objects} {
    foreach f $objects {
        if {$f in $::constraints} {
            set ::constraints [lreplace $::constraints [lsearch -exact $::constraints $f] [lsearch -exact $::constraints $f]]
        } else {set ::files [lreplace $::files [lsearch -exact $::files $f] [lsearch -exact $::files $f]]}
    }
}
proc add_files {args} {
    foreach f [lindex $args end] {
        if {"constrs_1" in $args} {lappend ::constraints $f} else {lappend ::files $f}
    }
}
proc set_property {args} {lappend ::notes [linsert $args 0 set_property]}
proc update_compile_order {args} {lappend ::notes compile_order}
proc get_ips {args} {
    if {[lindex $args end] ne "test_bd_*"} {error {wrong BD scope}}
    set filter [lindex $args [expr {[lsearch -exact $args -filter]+1}]]
    if {[string match *:bd_clean_compute:* $filter]} {return test_bd_bd_clean_compute_0_0}
    if {[string match *:bd_ps_link:* $filter]} {return test_bd_bd_ps_link_0_0}
    error {unexpected IP filter}
}
proc update_module_reference {args} {
    if {$::fail_refresh} {error {injected module refresh failure}}
    if {[llength $args]!=2 || [lindex $args 0] ne "-verbose" ||
        [lindex $args 1] ni {test_bd_bd_clean_compute_0_0 test_bd_bd_ps_link_0_0}} {
        error {expected generated IP object, not a BD cell name}
    }
    lappend ::notes refresh
}
proc list_property {args} {return CONFIG.LEVEL_ENABLE}
proc get_bd_pins {args} {
    if {[lsearch -exact $args -of_objects]>=0} {
        set n [lindex $args [expr {[lsearch -exact $args -of_objects]+1}]]
        return [lindex [dict get $::nets $n] 0]
    }
    return [lindex $args end]
}
proc get_bd_nets {args} {
    set pin [lindex $args end]
    dict for {n pins} $::nets {if {$pin in $pins} {return $n}}
    return {}
}
proc connect_bd_net {args} {
    if {[lindex $args 0] eq "-net"} {
        dict lappend ::nets [lindex $args 1] [lindex $args 2]
    } else {dict set ::nets net_[dict size $::nets] $args}
    lappend ::notes wire
}
proc save_bd_design {} {lappend ::notes save}
proc validate_bd_design {} {
    if {$::fail_validate} {error {injected Validate failure}}
    lappend ::notes validate
}
proc generate_target {target objects} {
    if {$target ne "all" || [llength $objects]!=1} {error {bad generation call}}
    lappend ::notes outputs
}
rename puts native_puts
proc puts {args} {
    if {[llength $args]==1} {lappend ::notes [lindex $args 0]} else {native_puts {*}$args}
}
'''


class TclUpdateTests(unittest.TestCase):
    def setUp(self):
        base = ROOT/'simulation/work'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='volume tcl ', dir=base)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base/'repository with spaces'
        self.proj = self.base/'external project'
        self.proj.mkdir()
        (self.proj/'Demo.xpr').write_text('original xpr', encoding='utf-8')
        self.bd = self.proj/'test_bd.bd'
        self.bd.write_text('original bd', encoding='utf-8')
        scripts = self.repo/'project/bd'
        scripts.mkdir(parents=True)
        for name in ('update_ps_volume.tcl','enable_ps_level.tcl','resume_ps_volume.tcl'):
            shutil.copy2(ROOT/'project/bd'/name,scripts/name)
        self.entry = scripts/'update_ps_volume.tcl'
        self.t = tkinter.Tcl()
        self.t.eval(MOCK)
        # Load definitions, suppress only the final automatic call.
        self.t.eval(self.entry.read_text(encoding='utf-8').split('\nif {[info exists ::ss_volume_update::resume_once]')[0])
        self.t.setvar('ss_volume_update::root',self.repo.as_posix())
        self.names = self.t.splitlist(self.t.getvar('ss_volume_update::names'))
        self.paths = []
        for name in self.names:
            src = self.repo/'project/rtl'/name
            src.parent.mkdir(exist_ok=True)
            shutil.copy2(ROOT/'project/rtl'/name,src)
            old = self.proj/'imported RTL'/name
            old.parent.mkdir(exist_ok=True)
            old.write_text('old '+name, encoding='utf-8')
            self.paths.append(old.as_posix())
        self.t.setvar('files',tuple(self.paths))
        self.t.setvar('projectdir',self.proj.as_posix())
        self.t.setvar('bdpath',self.bd.as_posix())
        constraints=[]
        for name in ('board_pins.xdc','interface_timing.xdc'):
            f=self.base/name
            f.write_text('original actual constraint '+name,encoding='utf-8')
            constraints.append(f.as_posix())
        self.t.setvar('constraints',tuple(constraints))

    def run_script(self):
        self.t.call('source', self.entry.as_posix())

    def test_copy_backup_refresh_outputs_and_repeat(self):
        self.run_script()
        notes = str(self.t.getvar('notes'))
        self.assertIn('PS_VOLUME_READY_FOR_GENERATE_BITSTREAM',notes)
        self.assertLess(notes.index('reopen'),notes.index('validate'))
        self.assertLess(notes.index('validate'),notes.index('outputs'))
        backup = next((self.proj/'handoff').iterdir())
        for name in self.names:
            self.assertEqual((backup/name).read_text(), 'old '+name)
            self.assertEqual((self.proj/'imported RTL'/name).read_bytes(),(self.repo/'project/rtl'/name).read_bytes())
        self.run_script()
        self.assertEqual(len(self.t.splitlist(self.t.getvar('files'))),10)
        self.assertEqual(int(self.t.eval('dict size $nets')),2)
        for name in ('board_pins.xdc','interface_timing.xdc'):
            self.assertEqual((self.proj/'ps_constraints'/name).read_bytes(),(self.base/name).read_bytes())

    def test_external_source_is_copied_without_overwriting_original(self):
        external = self.base/'external source.sv'
        name = self.names[0]
        external = external.parent/name
        external.write_text('preserve external',encoding='utf-8')
        self.paths[0]=external.as_posix()
        self.t.setvar('files',tuple(self.paths))
        self.run_script()
        self.assertEqual(external.read_text(),'preserve external')
        self.assertEqual((self.proj/'ps_volume_sources'/name).read_bytes(),(self.repo/'project/rtl'/name).read_bytes())

    def test_active_run_makes_no_copies(self):
        self.t.setvar('runstate','synth_design Running')
        with self.assertRaisesRegex(tkinter.TclError,'active run'): self.run_script()
        self.assertFalse((self.proj/'handoff').exists())

    def test_duplicate_registration_stops_before_backup(self):
        self.t.setvar('files',tuple(self.paths+[self.paths[0]]))
        with self.assertRaisesRegex(tkinter.TclError,'expected one'): self.run_script()
        self.assertFalse((self.proj/'handoff').exists())

    def test_validate_failure_has_backup_but_no_outputs_or_success(self):
        self.t.setvar('fail_validate',1)
        with self.assertRaisesRegex(tkinter.TclError,'Validate failure'): self.run_script()
        notes=str(self.t.getvar('notes'))
        self.assertNotIn('READY_FOR_GENERATE_BITSTREAM',notes)
        self.assertNotIn('outputs',notes)
        self.assertTrue((self.proj/'handoff').exists())

    def test_resume_refresh_failure_without_recopies_or_new_backup(self):
        self.t.setvar('fail_refresh',1)
        with self.assertRaisesRegex(tkinter.TclError,'reopen failure'): self.run_script()
        original_backups=list((self.proj/'handoff').iterdir())
        mtimes={p:Path(p).stat().st_mtime_ns for p in self.paths}
        self.t.setvar('fail_refresh',0)
        self.t.call('source',(self.entry.parent/'resume_ps_volume.tcl').as_posix())
        self.assertEqual(original_backups,list((self.proj/'handoff').iterdir()))
        self.assertEqual(mtimes,{p:Path(p).stat().st_mtime_ns for p in self.paths})
        self.assertIn('PS_VOLUME_READY_FOR_GENERATE_BITSTREAM',str(self.t.getvar('notes')))

    def test_resume_rejects_sources_not_copied(self):
        with self.assertRaisesRegex(tkinter.TclError,'source not copied/current'):
            self.t.call('source',(self.entry.parent/'resume_ps_volume.tcl').as_posix())
        self.assertFalse((self.proj/'handoff').exists())


if __name__=='__main__': unittest.main()
