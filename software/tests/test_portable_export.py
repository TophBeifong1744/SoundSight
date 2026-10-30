"""Export path/collection tests in a Tcl model, without launching Vivado."""
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import tkinter
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ExportTests(unittest.TestCase):
    def setUp(self):
        work = ROOT/'simulation/work'
        work.mkdir(parents=True, exist_ok=True)
        self.temp = TemporaryDirectory(prefix='export 中文 ', dir=work)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base/'source project'
        self.project.mkdir()
        self.paths = [self.project/name for name in ('rtl/top.v', 'constraints/pins.xdc',
                       'memory/window.mem', 'ip/fft.xci', 'bd/design.bd')]
        for p in self.paths:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('{}\n' if p.suffix in ('.bd', '.xci') else '// source\n', encoding='utf-8')
        old = self.project/'handoff/latest/old.txt'
        old.parent.mkdir(parents=True)
        old.write_text('preserve old export')
        self.t = tkinter.Tcl()
        self.t.setvar('root', self.project.as_posix())
        self.t.setvar('sources', tuple(p.as_posix() for p in self.paths))
        self.t.setvar('top', self.paths[0].as_posix())
        self.t.setvar('bd', self.paths[-1].as_posix())
        self.t.eval('''
set status {Complete};set repo {};set current design;set generate_bad 0
proc get_projects {args} {return project}
proc get_runs {args} {return run}
proc get_filesets {args} {return {sources_1 constrs_1 utils_1}}
proc get_property {key obj} {
    switch $key {
        DIRECTORY {return $::root}
        STATUS {return $::status}
        IP_REPO_PATHS {return $::repo}
        FILESET_TYPE {if {$obj eq {utils_1}} {return Utils};return DesignSrcs}
        NAME {return $obj}
        PARENT_COMPOSITE_FILE {return {}}
        INCLUDE_DIRS {return {}}
        default {error "UNEXPECTED_PROPERTY $key"}
    }
}
proc get_files {args} {if {[lindex $args end] eq {sources_1}} {return $::sources};return {}}
proc current_bd_design {args} {if {$args eq {-quiet}} {return $::current};set ::current [lindex $args 0]}
proc open_bd_design {args} {set ::current design}
proc save_bd_design {} {}
proc write_bd_tcl {args} {
    set h [open [lindex $args end] w];fconfigure $h -encoding utf-8
    puts $h "# Original $::root"
    puts $h "import_files -quiet -fileset sources_1 $::top"
    close $h
}
proc write_project_tcl {args} {
    if {[lsearch -exact $args -ignore_utils]>=0} {error {Unknown option -ignore_utils}}
    foreach flag {-internal -no_copy_sources -use_bd_files} {
        if {[lsearch -exact $args $flag]<0} {error "MISSING_FLAG $flag"}
    }
    set h [open [lindex $args end] w];fconfigure $h -encoding utf-8
    puts $h "# Original $::root"
    puts $h {set origin_dir .}
    puts $h {if {[info exists ::origin_dir_loc]} {set origin_dir $::origin_dir_loc}}
    puts $h {set ::located [file normalize [file join $origin_dir rtl/top.v]]}
    puts $h {if {![file isfile $::located]} {error MISSING_INPUT}}
    if {$::generate_bad} {puts $h {set tool C:/unresolved/tool}}
    close $h
}
namespace eval ss_portable_export {variable library_only 1}
''')
        self.t.call('source', str(ROOT/'project/script/export_portable_handoff.tcl'))

    def test_bundle_moves_and_recreates_from_an_unrelated_working_directory(self):
        self.t.call('ss_portable_export::run')
        latest = self.project/'handoff/latest'
        inventory = (latest/'source_files.txt').read_text()
        self.assertNotIn(self.project.as_posix(), inventory)
        for line in inventory.splitlines():
            self.assertTrue((latest/line).is_file())
        self.assertTrue(list((self.project/'handoff').glob('previous_*/old.txt')))
        for p in self.paths:
            self.assertEqual(p.read_bytes(), (latest/'payload'/p.relative_to(self.project)).read_bytes())
        moved = self.base/'different computer'/ 'moved package'
        shutil.copytree(latest, moved)
        shutil.rmtree(self.project)  # Only this test's isolated source fixture.
        self.t.eval('proc get_projects {args} {return {}}')
        before = self.t.call('pwd')
        self.t.call('source', str(moved/'project.tcl'))
        self.assertEqual(Path(str(self.t.getvar('located'))), moved/'payload/rtl/top.v')
        self.assertEqual(self.t.call('pwd'), before)
        self.assertFalse(self.t.eval('info exists ::origin_dir_loc') == '1')

    def test_unknown_absolute_path_cannot_publish_and_previous_latest_survives(self):
        self.t.setvar('generate_bad', 1)
        with self.assertRaisesRegex(tkinter.TclError, 'unresolved machine path'):
            self.t.call('ss_portable_export::run')
        self.assertEqual((self.project/'handoff/latest/old.txt').read_text(), 'preserve old export')

    def test_busy_and_custom_repo_stop_before_export(self):
        self.t.setvar('status', 'Running')
        with self.assertRaisesRegex(tkinter.TclError, 'active run'):
            self.t.call('ss_portable_export::run')
        self.t.setvar('status', 'Complete')
        self.t.setvar('repo', 'custom_ip')
        with self.assertRaisesRegex(tkinter.TclError, 'custom IP repository'):
            self.t.call('ss_portable_export::run')
        self.assertFalse(list((self.project/'handoff').glob('.pending_*')))

    def test_external_reference_is_not_silently_dropped(self):
        p = self.base/'external.v';p.write_text('// external')
        self.t.setvar('sources', (p.as_posix(),))
        with self.assertRaisesRegex(tkinter.TclError, 'outside project'):
            self.t.call('ss_portable_export::run')

    def test_source_absolute_path_and_missing_source_fail(self):
        self.paths[0].write_text('initial $readmemh("C:/private/data.mem", mem);')
        with self.assertRaisesRegex(tkinter.TclError, 'unresolved machine path'):
            self.t.call('ss_portable_export::run')
        self.paths[0].unlink()
        with self.assertRaisesRegex(tkinter.TclError, 'missing dependency'):
            self.t.call('ss_portable_export::run')

    def test_bd_import_quotes_spaces_and_rejects_unknown_file(self):
        files = (str(self.paths[0].relative_to(self.project)).replace('\\','/'), self.paths[0].as_posix())
        text = self.t.call('ss_portable_export::portable_bd',
                           'import_files -quiet -fileset sources_1 '+self.paths[0].as_posix(),
                           self.project.as_posix(), files)
        self.assertNotIn(self.project.as_posix(), text)
        self.assertIn('[list [file join $::ss_handoff_source rtl/top.v]]', text)
        with self.assertRaisesRegex(tkinter.TclError, 'uncollected'):
            self.t.call('ss_portable_export::portable_bd',
                        'import_files -quiet -fileset sources_1 '+(self.project/'missing.v').as_posix(),
                        self.project.as_posix(), files)

    def test_include_collection_and_escape_rejection(self):
        header = self.paths[0].parent/'nested/value.vh'
        header.parent.mkdir();header.write_text('// https://example.org/license\n')
        self.paths[0].write_text('`include "nested/value.vh"\n')
        self.t.call('ss_portable_export::run')
        self.assertEqual((self.project/'handoff/latest/payload/rtl/nested/value.vh').read_bytes(), header.read_bytes())
        outside = self.base/'external.vh';outside.write_text('// external')
        self.paths[0].write_text('`include "../../external.vh"\n')
        with self.assertRaisesRegex(tkinter.TclError, 'outside project'):
            self.t.call('ss_portable_export::run')

    def test_recipe_extra_input_is_collected_and_missing_one_stops(self):
        extra = self.project/'generated/wrapper.v'
        extra.parent.mkdir();extra.write_text('// wrapper')
        self.t.setvar('collected', ())
        self.t.call('ss_portable_export::collect_recipe_inputs',
                    '"${origin_dir}/generated/wrapper.v"', self.project.as_posix(), 'collected')
        self.assertEqual(int(self.t.eval('dict size $collected')), 1)
        with self.assertRaisesRegex(tkinter.TclError, 'missing dependency'):
            self.t.call('ss_portable_export::collect_recipe_inputs',
                        '"$origin_dir/generated/missing.v"', self.project.as_posix(), 'collected')


class CacheRemovalTests(unittest.TestCase):
    def setUp(self):
        self.t=tkinter.Tcl()
        self.t.eval('namespace eval ss_portable_export {variable library_only 1}')
        self.t.call('source',str(ROOT/'project/script/export_portable_handoff.tcl'))

    def test_actual_archived_vivado_utils_removed_without_changing_other_sections(self):
        from zipfile import ZipFile
        with ZipFile(ROOT/'project/reports/ps_3d/w16/original-export.zip') as z:
            text=z.read('project.tcl').decode('utf-8-sig')
        clean=self.t.call('ss_portable_export::strip_path_comments',text).replace('\r\n','\n')
        result=self.t.call('ss_portable_export::without_utils_cache',clean)
        self.assertNotIn('get_filesets utils_1',result)
        self.assertNotIn('soundsight_stm32_bd_wrapper.dcp',result)
        self.assertIn('create_project',result)
        self.assertIn('CONFIG.PCW',result)
        self.assertIn('get_filesets constrs_1',result)
        self.assertEqual(int(self.t.call('info','complete',result)),1)
        begin=clean.index("# Set 'utils_1' fileset object")
        end=clean.index('# Adding sources referenced in BDs')
        original_rest=clean[:begin]+clean[end:]
        for line in original_rest.splitlines():
            if line.strip() and '/utils_1/' not in line and not line.startswith('#'):
                self.assertIn(line,result)

    def test_json_relative_separators_are_not_unc_paths(self):
        cases = [
            (r'"xci_path": "ip\\block\\block.xci"', False),
            (r'ip\block\block.xci', False),
            (r'"path": "..\\rtl\\top.v"', False),
            ('https://example.org/home/manual', False),
            (r'"path": "C:\\private\\top.v"', True),
            ('source {F:/private/top.v}', True),
            (r'"path": "\\\\server\\share\\top.v"', True),
            (r'\\server\share\top.v', True),
            ('"path": "/home/person/top.v"', True),
            ('payload/home/rtl/top.v', False),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(bool(int(self.t.call('ss_portable_export::machine_path',value))),expected)

    def test_unknown_utils_layout_stops_instead_of_dropping_later_design(self):
        with self.assertRaisesRegex(tkinter.TclError,'unrecognized utils'):
            self.t.call('ss_portable_export::without_utils_cache',
                        "# Set 'utils_1' fileset object\nset obj [get_filesets utils_1]\ncreate_run synth_1\n")


if __name__ == '__main__':
    unittest.main()
