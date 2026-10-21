"""生成RAM队列增量包；沿用已经上板的bit/HWH、C库及原软件，不操作硬件。"""
import argparse
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'software/ps/ram_queue.py',
    'software/ps/run_buffered.py',
    'software/ps/volume_gate.py',
    'software/ps/recover_ram.py',
    'software/tests/test_buffered.py',
    'document/pynq-ram-queue.md',
)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=ROOT/'release/output/soundsight_ram_queue_update.zip')
    args = p.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'x', zipfile.ZIP_DEFLATED) as package:
        for name in FILES:
            package.write(ROOT/name, 'SoundSight_PYNQ/'+name)
    print('UPDATE_CREATED', args.output, 'files=', len(FILES))


if __name__ == '__main__':
    main()
