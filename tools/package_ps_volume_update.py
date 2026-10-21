"""Package an exact PS-volume source/software delta; no EDA or board actions.

This is not a complete project or a bitstream. Preserve the existing working
project, replace listed source files, then build manually as documented.
"""
import argparse
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
RTL = ('ss_preprocess.sv', 'ss_fft_frontend.sv', 'f1a_frame_store.sv',
       'ss_pair_engine.sv', 'ss_clean_compute.sv', 'ss_dual_compute.sv',
       'bd_clean_compute.v', 'ss_ps_control_regs.sv', 'ss_ps_link.sv', 'bd_ps_link.v')
FILES = tuple('project/rtl/' + x for x in RTL) + (
    'project/bd/update_ps_volume.tcl', 'project/bd/resume_ps_volume.tcl',
    'project/bd/enable_ps_level.tcl', 'project/bd/ps.tcl',
    'software/ps/volume_gate.py', 'software/ps/run_buffered.py',
    'software/ps/ram_queue.py', 'software/ps/recover_ram.py',
    'software/tests/test_volume_gate.py', 'software/tests/test_buffered.py',
    'software/tests/test_ps_volume_tcl.py',
    'tools/run_sim.py', 'tools/package_ps_volume_update.py',
    'simulation/tb/stm32/tb_level.sv', 'simulation/tb/stm32/tb_levelstore.sv',
    'simulation/tb/stm32/tb_duallevel.sv', 'simulation/tb/ps/tb_pslevel.sv',
    'simulation/tb/stm32/tb_preprocess.sv', 'simulation/tb/stm32/tb_clean.sv',
    'simulation/tb/stm32/tb_dual.sv', 'simulation/tb/stm32/tb_frontstop.sv',
    'simulation/tb/stm32/tb_pair.sv', 'simulation/tb/ps/tb_ps.sv',
    'simulation/tb/ps/tb_pscdc.sv',
    'document/ps-volume-gate.md', 'document/pynq-ram-queue.md',
)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=ROOT/'release/output/soundsight_ps_volume_update.zip')
    args = p.parse_args()
    evidence = ROOT/'document/evidence/ps-volume-gate'
    if not (evidence/'README.md').is_file():
        raise FileNotFoundError('Missing validation record')
    evidence_files = tuple(p.relative_to(ROOT).as_posix() for p in sorted(evidence.rglob('*')) if p.is_file())
    paths = [(name, ROOT/name) for name in FILES + evidence_files]
    if any(not path.is_file() for _, path in paths):
        raise FileNotFoundError('An expected delivery file is missing')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Refuse accidental replacement of an already delivered candidate.
    with ZipFile(args.output, 'x', ZIP_DEFLATED) as z:
        for name, path in paths:
            z.write(path, name)
    with ZipFile(args.output) as z:
        if z.testzip() or any(z.read(name) != path.read_bytes() for name, path in paths):
            raise RuntimeError('Archive verification failed')
    print('PS_VOLUME_DELTA',args.output,'files=',len(paths),'RTL=',len(RTL),'bit=NOT_BUILT')


if __name__ == '__main__': main()
