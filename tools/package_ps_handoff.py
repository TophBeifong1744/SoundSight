"""Create the portable PS recipe/source bundle from its explicit dependency list."""
import argparse
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=ROOT/'release/output/soundsight_ps_volume_handoff.zip')
    args=ap.parse_args()
    manifest=ROOT/'document/build/ps-handoff-files.txt'
    files=[line for line in manifest.read_text().splitlines() if line and not line.startswith('#')]
    files+=['document/build/ps-handoff-files.txt','document/ps-handoff.md','document/pynq-volume-sd.md',
            'document/run-guide.md','project/reports/ps/README.md','project/reports/ps/timing_summary_routed.rpt',
            'project/reports/ps/utilization_placed.rpt','project/reports/ps/drc_routed.rpt','LICENSE']
    assert len(files)==len(set(files))
    for name in files:
        path=(ROOT/name).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():raise ValueError(name)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(args.output,'x',ZIP_DEFLATED) as z:
        for name in files:z.write(ROOT/name,'SoundSight/'+name)
        readme=(ROOT/'document/ps-handoff.md').read_text('utf-8')
        z.writestr('SoundSight/README.md',readme.replace('(pynq-volume-sd.md)','(document/pynq-volume-sd.md)'))
    with ZipFile(args.output) as z:
        assert z.testzip() is None
        for name in files:assert z.read('SoundSight/'+name)==(ROOT/name).read_bytes()
    print('PS_HANDOFF_PACKAGE',args.output,'files=',len(files)+1,'native_rebuild=NOT_RUN')


if __name__=='__main__':main()
