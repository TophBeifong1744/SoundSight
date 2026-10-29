"""Validate the horizontal updater in a disposable copy of supplied inputs.

Only project preparation/output generation. Never opens the original project
in Vivado and never launches synthesis, implementation or hardware actions.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from tool_config import vivado_root

ROOT = Path(__file__).resolve().parents[1]


def tcl_path(p):
    s = Path(p).resolve().as_posix()
    if any(c in s for c in '{}\r\n'): raise ValueError('Unsupported path')
    return '{'+s+'}'


def audit(output, work):
    """Compare actual saved BD and copied files, not merely the PASS marker."""
    before = json.loads((output/'before.bd').read_text('utf-8'))['design']
    after = json.loads((output/'after.bd').read_text('utf-8'))['design']
    for key in ('interface_ports','interface_nets','addressing'):
        assert before[key] == after[key], key
    for key, item in before['components'].items():
        if key != 'ps_link': assert after['components'][key] == item, key
    assert set(before['components']) == set(after['components'])
    for key, item in before['nets'].items(): assert after['nets'][key] == item, key
    for key, item in before['ports'].items(): assert after['ports'][key] == item, key
    assert set(after['ports']) - set(before['ports']) == {'servo_vertical_pwm'}
    params = after['components']['ps_link']['parameters']
    for key, expected in dict(ACTUATOR_BOUND=1, LEVEL_ENABLE=1, CLK_FREQ_HZ=61440000,
                              SERVO_MAX=360, MECHANICAL_MIN=0, MECHANICAL_MAX=360).items():
        assert int(params[key]['value']) == expected, key
    names = ('bd_ps_link.v','ss_ps_link.sv','ss_ps_control_regs.sv','ss_actuator_control.sv',
             'motor_drive.v','i17_turntable_pwm_guard.sv','ss_manual_servo.sv')
    for name in names:
        assert (work/'horizontal_sources'/name).read_bytes() == (ROOT/'project/rtl'/name).read_bytes(), name
    xdc = list((work/'horizontal_constraints').rglob('board_pins.xdc'))
    assert len(xdc) == 1
    assert 'PACKAGE_PIN T15 [get_ports servo_pwm]' in xdc[0].read_text('utf-8')
    assert 'PACKAGE_PIN V7' not in xdc[0].read_text('utf-8')
    assert (work/'horizontal_constraints/horizontal_reserved.xdc').read_bytes() == (ROOT/'project/sdc/ps/horizontal_reserved.xdc').read_bytes()
    import sys
    sys.path.insert(0, str(ROOT/'software/ps'))
    from horizontal_motion import check_hwh
    hwh = list(work.rglob('soundsight_stm32_bd.hwh'))
    assert hwh
    check_hwh(hwh[0])
    summary = dict(existing_nets_preserved=len(before['nets']),
                   unchanged_components=len(before['components'])-1,
                   axi_address_interfaces_unchanged=True, existing_ports_unchanged=True,
                   horizontal_rtl_byte_match=len(names), new_vertical_port=True,
                   copied_xdc_pins='T15/W16', generated_hwh_parameters_match=True,
                   synthesis=False, implementation=False, hardware_actions=False)
    (output/'audit.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    project = args.project.resolve()
    tree = ET.parse(project)
    scratch = ROOT/'simulation/work'
    scratch.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='h', dir=str(scratch)))
    # Exercise the delivered scripts byte-for-byte as a relocatable kit.
    # The test project is external to this kit, as the human work copy will be.
    kit = temp/'kit'
    for rel in ('project/bd/update_ps_horizontal.tcl', 'project/bd/update_ps_volume.tcl',
                'project/bd/update_ps_manual.tcl',
                'project/sdc/ps/horizontal_reserved.xdc', *('project/rtl/'+n for n in
                ('bd_ps_link.v','ss_ps_link.sv','ss_ps_control_regs.sv','ss_actuator_control.sv',
                 'motor_drive.v','i17_turntable_pwm_guard.sv','ss_manual_servo.sv'))):
        dst = kit/rel; dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT/rel, dst)
    work = temp/'S_Servo'; work.mkdir()
    tool = vivado_root()
    # Sandbox cannot use the user's Tcl Store. Resolve installed app packages
    # for this disposable process only, without resetting the user's catalog.
    package_dirs = sorted({p.parent for p in (tool/'data/XilinxTclStore').rglob('pkgIndex.tcl')})
    text = ['lappend auto_path '+' '.join(tcl_path(p) for p in package_dirs),
            'create_project S_Servo '+tcl_path(work)+' -part xc7z020clg400-2 -force',
            'set_property target_language Verilog [current_project]',
            'set_property XPM_LIBRARIES {XPM_CDC XPM_FIFO XPM_MEMORY} [current_project]']
    inputs = []
    bd = None
    for fs in tree.iter('FileSet'):
        if fs.get('Name') not in ('sources_1', 'constrs_1'): continue
        for node in fs.findall('File'):
            raw = node.get('Path')
            src = Path(raw.replace('$PSRCDIR', str(project.with_suffix('.srcs')))
                       .replace('$PGENDIR', str(project.with_suffix('.gen')))
                       .replace('$PPRDIR', str(project.parent)))
            if src.name.endswith('_wrapper.v'): continue
            if src.suffix == '.bd':
                dest = work/'S_Servo.srcs/sources_1/bd'/src.stem/src.name
            elif src.suffix == '.xci':
                dest = work/'S_Servo.srcs/sources_1/ip'/src.stem/src.name
            else:
                dest = work/'S_Servo.srcs'/fs.get('Name')/'imports'/src.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            if src.suffix in ('.bd', '.xci'):
                for dep in src.parent.rglob('*.xci'):
                    target = dest.parent/dep.relative_to(src.parent)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dep, target)
            inputs.append(dict(source=str(src), copied=str(dest)))
            if src.suffix == '.bd': bd = dest
            text.append('add_files -norecurse -fileset '+fs.get('Name')+' [list '+tcl_path(dest)+']')
            for attr in node.findall('./FileInfo/Attr'):
                if attr.get('Name') == 'IsEnabled' and attr.get('Val') == '0':
                    text.append('set_property IS_ENABLED false [get_files [list '+tcl_path(dest)+']]')
    assert bd is not None
    # create_project initializes .srcs; stage fixture bytes outside that tree
    # and copy them AFTER project creation, so it cannot remove the fixtures.
    stage = temp/'fixture'
    shutil.move(str(work/'S_Servo.srcs'), str(stage))
    copies = []
    for src in stage.rglob('*'):
        if src.is_file():
            dest = work/'S_Servo.srcs'/src.relative_to(stage)
            copies += ['file mkdir '+tcl_path(dest.parent),
                       'file copy -force '+tcl_path(src)+' '+tcl_path(dest)]
    text[4:4] = copies
    text += ['open_bd_design '+tcl_path(bd), 'current_bd_instance /',
             'update_compile_order -fileset sources_1',
             'set ws [make_wrapper -files [get_files *.bd] -top]',
             'add_files -norecurse $ws',
             'set_property TOP '+bd.stem+'_wrapper [get_filesets sources_1]',
             'save_bd_design',
             'file copy -force '+tcl_path(bd)+' '+tcl_path(output/'before.bd'),
             'source '+tcl_path(kit/'project/bd/update_ps_horizontal.tcl'),
             'source '+tcl_path(kit/'project/bd/update_ps_manual.tcl'),
             'file copy -force '+tcl_path(bd)+' '+tcl_path(output/'after.bd'),
             'set h [open '+tcl_path(output/'registered.txt')+' w]',
             'foreach f [get_files -of_objects [get_filesets sources_1]] {puts $h [get_property NAME $f]}',
             'close $h',
             # Check constraints in a files-only context without elaboration.
             'set h [open '+tcl_path(output/'constraints.txt')+' w]',
             'foreach f [get_files -of_objects [get_filesets constrs_1]] {puts $h [get_property NAME $f]}',
             'close $h', 'puts {HORIZONTAL_BD_CHECK_PASS}', 'close_project', 'exit 0']
    (temp/'check.tcl').write_text('\n'.join(text)+'\n', encoding='utf-8')
    tool = vivado_root()
    argv = ['-mode','batch','-notrace','-source',str(temp/'check.tcl'),'-log',str(output/'vivado.log'),'-nojournal']
    for s in [str(tool), *argv]:
        if any(c in s for c in '\r\n"%&|<>^'): raise ValueError('Unsupported command path')
    (temp/'launch.bat').write_text('@echo off\ncall "'+str(tool/'bin/vivado.bat')+'" '+
                                  ' '.join('"'+s+'"' for s in argv)+'\nexit /b %errorlevel%\n', encoding='utf-8')
    env = os.environ.copy()
    for k in ('PYTHONHOME','PYTHONPATH','PYTHONUSERBASE'): env.pop(k, None)
    with (output/'stdout.log').open('wb') as log:
        run = subprocess.run([os.environ.get('COMSPEC','cmd.exe'),'/d','/c',str(temp/'launch.bat')],
                             cwd=temp, env=env, stdout=log, stderr=subprocess.STDOUT,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    log = (output/'stdout.log').read_text('utf-8', errors='replace')
    okay = run.returncode == 0 and 'HORIZONTAL_BD_CHECK_PASS' in log and '\nERROR:' not in log
    if okay: audit(output, work)
    report = dict(pass_check=okay, exit_code=run.returncode, input_project=str(project),
                  input_files=inputs, scratch=str(temp), synthesis=False, implementation=False,
                  hardware_actions=False)
    (output/'result.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print('HORIZONTAL_BD_CHECK=', okay, 'EVIDENCE=', output, 'SCRATCH=', temp)
    print(log[-3500:])
    # Keep failure work for diagnosis; caller archives useful results before
    # cleaning successful disposable work, with explicit path verification.
    return 0 if okay else 1


if __name__ == '__main__': raise SystemExit(main())
