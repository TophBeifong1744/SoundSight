"""Normalize a user's Vivado PS export into the existing portable recipe.

Reads the supplied export and work project; never invokes Vivado or hardware.
The original export is retained as evidence, not an executable dependency.
"""
import argparse
from pathlib import Path
import re
import shutil
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--export-dir', type=Path, required=True)
    p.add_argument('--hardware-project', type=Path, required=True)
    args = p.parse_args()
    export, hw = args.export_dir.resolve(), args.hardware_project.resolve()
    evidence = ROOT/'document/evidence/ps-volume-handoff'
    evidence.mkdir(parents=True, exist_ok=True)
    archive = evidence/'original-export.zip'
    if archive.exists():
        raise FileExistsError('Preserve the previous original export before receiving another one.')
    with ZipFile(archive, 'x', ZIP_DEFLATED) as z:
        for f in sorted(export.iterdir()):
            if f.is_file(): z.write(f, f.name)
    bd = (export/'soundsight_stm32_bd.tcl').read_text('utf-8-sig')
    body = bd[bd.index('proc create_root_design {'):bd.index('# End of create_root_design()')]
    body = body.replace('proc create_root_design { parentCell }', 'proc ss_create_ps_bd { parentCell recipe_root }', 1)
    config = re.search(r'  set_property -dict \[list \\\n(.*?)\] \$ps7', body, re.S)
    if not config:
        raise ValueError('Expected exported PS7 configuration')
    (ROOT/'project/ip/ps7_ps.tcl').write_text(
        '# User-exported PS board configuration; supplied ps7 object, no hardware action.\n'+config.group(0).lstrip()+'\n', encoding='utf-8')
    body = body[:config.start()]+'  source [file join $recipe_root project ip ps7_ps.tcl]'+body[config.end():]
    (ROOT/'project/bd/ps.tcl').write_text(
        '# Actual PL+PS Volume BD, normalized from the user export.\n'
        '# Keep the canonical ps target; no external workspace dependency.\n'
        'create_bd_design soundsight_ps_bd\n'+body+
        '\nss_create_ps_bd "" $ss_root\nrename ss_create_ps_bd {}\n',encoding='utf-8')
    project = (export/'project.tcl').read_text('utf-8-sig')
    previous = (ROOT/'project/script/stm32_settings.tcl').read_text('utf-8-sig')
    header = previous[:previous.index('set obj [get_runs synth_1]')].replace('soundsight_stm32_bd','soundsight_ps_bd')
    header = '# Actual PS Volume Global/IP and run settings; configure only.\n'+'\n'.join(header.splitlines()[1:])+'\n'
    lines = [header]
    for run, stop in [('synth_1', "# Create 'impl_1' run"), ('impl_1', '# set the current impl run')]:
        start = project.rindex('set obj [get_runs '+run+']')
        block = project[start:project.index(stop,start)]
        oldstart = previous.index('set obj [get_runs '+run+']')
        oldblock = previous[oldstart:]
        if run=='synth_1': oldblock = oldblock[:oldblock.index('set obj [get_runs impl_1]')]
        lines.append('set obj [get_runs '+run+']')
        for prop in re.findall(r'^set_property -name "([^"]+)"', oldblock, re.M):
            matches = [s for s in block.splitlines() if s.startswith('set_property -name "'+prop+'"')]
            if len(matches)!=1: raise ValueError((run,prop,matches))
            if re.search(r'[A-Za-z]:[/\\]|\$proj_dir', matches[0]):
                raise ValueError('Nonportable run option: '+matches[0])
            lines.extend(matches)
    (ROOT/'project/script/ps_settings.tcl').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    # Resolve the registered paths from the export rather than guessing which copy was built.
    sources = [Path(s) for s in (export/'source_files.txt').read_text('utf-8-sig').splitlines()]
    for name in ('board_pins.xdc','interface_timing.xdc'):
        matches = [f for f in sources if f.name==name]
        if len(matches)!=1: raise ValueError((name,matches))
        shutil.copy2(matches[0],ROOT/'project/sdc/ps'/name)
    reports = ROOT/'project/reports/ps'
    reports.mkdir(parents=True,exist_ok=True)
    run = next(hw.glob('*.runs/impl_1'))
    for suffix in ('timing_summary_routed','utilization_placed','drc_routed'):
        f=next(run.glob('*_'+suffix+'.rpt'))
        shutil.copy2(f,reports/(suffix+'.rpt'))
    print('PS_EXPORT_RECEIVED',evidence,'no EDA or hardware actions')


if __name__=='__main__': main()
