'Copy retained RAM records to a new SD file after capture stops. Originals are retained.'
import argparse
import json
from pathlib import Path

from run_capture import durable_sink


def recover(directory, output):
    paths = sorted(Path(directory).glob('*.jsonl'))
    if not paths:
        raise ValueError('No complete RAM records; .partial files are not accepted records')
    count = 0
    with Path(output).open('x', encoding='utf-8') as handle:
        save = durable_sink(handle)
        for path in paths:
            # 若还有writer在删文件则会明确失败，不把缺件当成功。
            record = json.loads(path.read_text(encoding='utf-8'))
            save(record)
            count += 1
    return count


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    print('RECOVERED_RECORDS=', recover(args.directory, args.output))
    print('Original RAM records retained; verify the new file before manual cleanup.')


if __name__ == '__main__':
    main()
