"""把停止运行后留下的RAM记录复制到新的SD文件；不删除原件，不访问硬件。

只在采集进程已经退出后运行。原SD日志可能已含某条记录，合并时用
ram_record.session和ram_record.ticket识别重复；不能按行数当作新采集帧数。
"""
import argparse
import json
from pathlib import Path

from run_capture import durable_sink


def recover(directory, output):
    paths = sorted(Path(directory).glob('*.jsonl'))
    if not paths:
        raise ValueError('没有完整RAM记录；.partial不能作为已接收记录')
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
    print('RAM原件保留；先核对新文件，再自行清理。')


if __name__ == '__main__':
    main()
