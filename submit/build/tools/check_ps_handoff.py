"""Compare the PS recipe to the original export without starting Vivado."""
import argparse
import json
from pathlib import Path
import re
import tkinter
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def interpreter():
    t = tkinter.Tcl()
    events = []
    def record(cmd, *args):
        events.append((cmd, args))
        return args[-1] if args else ''
    for cmd in ('create_bd_cell','create_bd_port','create_bd_intf_port','connect_bd_net',
                'connect_bd_intf_net','set_property','assign_bd_address','create_ip'):
        t.createcommand(cmd,lambda *args,cmd=cmd:record(cmd,*args))
    for cmd in ('get_bd_cells','get_bd_pins','get_bd_ports','get_bd_intf_ports',
                'get_bd_intf_pins','get_bd_addr_spaces','get_bd_addr_segs','get_ips','get_files','get_runs'):
        t.createcommand(cmd,lambda *args:args[-1])
    t.createcommand('get_property',lambda *args:'hier')
    for cmd in ('current_bd_instance','create_bd_design','validate_bd_design','save_bd_design'):
        t.createcommand(cmd,lambda *args:'/')
    t.createcommand('source',lambda path:t.eval(Path(path).read_text('utf-8-sig')))
    return t,events


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--hardware-project',type=Path)
    args=ap.parse_args()
    archive=ROOT/'document/evidence/ps-volume-handoff/original-export.zip'
    with ZipFile(archive) as z:
        raw=z.read('soundsight_stm32_bd.tcl').decode('utf-8-sig').replace('\r\n','\n')
        expected=raw[raw.index('proc create_root_design {'):raw.index('# End of create_root_design()')]
        t,e=interpreter(); t.eval(expected); t.eval('create_root_design ""')
        u,a=interpreter(); u.setvar('ss_root',ROOT.as_posix())
        u.eval((ROOT/'project/bd/ps.tcl').read_text('utf-8-sig'))
        assert e==a,'BD electrical/configuration events differ from actual export'
        t,ip_events=interpreter(); t.setvar('destination',ROOT.as_posix())
        # The recipe's only filesystem action is creating its IP output folder.
        t.eval('rename file real_file; proc file {sub args} {if {$sub eq "mkdir"} {return}; return [real_file $sub {*}$args]}')
        t.eval((ROOT/'project/ip/create_fft_ip.tcl').read_text('utf-8-sig'))
        fft_count=0
        for cmd,values in ip_events:
            if cmd!='set_property':continue
            pairs=t.splitlist(values[1]); configured=dict(zip(pairs[::2],pairs[1::2]))
            actual=json.loads(z.read(values[-1]+'.xci'))['ip_inst']['parameters']['component_parameters']
            for key,value in configured.items():
                assert actual[key.removeprefix('CONFIG.')][0]['value']==value,(values[-1],key)
                fft_count+=1
        # Compare every retained run option with the original exported value.
        project=z.read('project.tcl').decode('utf-8-sig')
        t,settings=interpreter(); t.eval((ROOT/'project/script/ps_settings.tcl').read_text('utf-8-sig'))
        run_count=0
        for cmd,values in settings:
            if values[0]!='-name':continue
            _,prop,_,value,_,run=values
            start=project.rindex('set obj [get_runs '+run+']')
            end="# Create 'impl_1' run" if run=='synth_1' else '# set the current impl run'
            block=project[start:project.index(end,start)]
            line=next(s for s in block.splitlines() if s.startswith('set_property -name "'+prop+'"'))
            v,observed=interpreter(); v.setvar('obj',run); v.eval(line)
            assert observed==[(cmd,values)],(run,prop)
            run_count+=1
        lines=[s for s in (ROOT/'document/build/ps-src-list.txt').read_text().splitlines() if s and not s.startswith('#')]
        source_count=0
        if args.hardware_project:
            paths=[Path(s) for s in z.read('source_files.txt').decode('utf-8-sig').splitlines()]
            for rel in lines+['project/sdc/ps/board_pins.xdc','project/sdc/ps/interface_timing.xdc']:
                matches=[p for p in paths if p.name==Path(rel).name]
                assert len(matches)==1,(rel,matches)
                assert matches[0].resolve().is_relative_to(args.hardware_project.resolve()),matches[0]
                normalize=lambda b:[s.rstrip() for s in b.decode('utf-8-sig').splitlines()]
                assert normalize(matches[0].read_bytes())==normalize((ROOT/rel).read_bytes()),rel
                source_count+=1
    manifest=[s for s in (ROOT/'document/build/ps-handoff-files.txt').read_text().splitlines() if s and not s.startswith('#')]
    assert len(manifest)==len(set(manifest))
    for rel in manifest:
        p=(ROOT/rel).resolve(); assert p.is_relative_to(ROOT) and p.is_file(),rel
        if p.suffix in ('.tcl','.py','.bat','.v','.sv','.xdc'):
            text=p.read_text('utf-8-sig').replace('C:/Windows/System32/cmd.exe','OS_COMMAND_SHELL')
            assert not re.search(r'[A-Za-z]:[/\\]',text),'Machine path: '+rel
        if p.suffix=='.tcl':assert t.call('info','complete',p.read_text('utf-8-sig')),rel
    print(json.dumps(dict(result='PASS_STATIC_ONLY',bd_events=len(e),fft_parameters=fft_count,
                         run_settings=run_count,live_source_and_constraint_matches=source_count,
                         portable_dependencies=len(manifest),native_rebuild='NOT_RUN',board='NOT_RUN'),indent=2))


if __name__=='__main__':main()
