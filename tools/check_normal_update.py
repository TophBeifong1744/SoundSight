"""解压交付ZIP，在隔离副本运行离线自测并保存真实输出；不访问硬件。"""
import ast
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
GROUPS = ('test_filter_controls.py', 'test_launcher.py', 'test_board_tools.py', 'test_serial_english.py', 'test_smp.py', 'test_normal.py', 'test_normal_update.py', 'test_sd_batch.py',
          'test_buffered.py', 'test_online_angle_filter.py', 'test_volume_gate.py', 'test_horizontal_motion.py', 'test_manual_servo.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'document/evidence/pynq-filter-controls-20261022')
    parser.add_argument('--archive', type=Path, default=ROOT/'release/output/soundsight_normal_update.zip')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    archive = args.archive.resolve()
    results = []
    with tempfile.TemporaryDirectory(prefix='soundsight-normal-check-') as temp:
        with ZipFile(archive) as z:
            assert z.testzip() is None
            assert all(not n.startswith('/') and '..' not in Path(n).parts for n in z.namelist())
            z.extractall(temp)
        source = Path(temp)/'soundsight_normal_update'
        payload = source/'payload'
        files = json.loads((source/'FILES.json').read_text())
        for name in files:
            assert (payload/name).read_bytes() == (ROOT/name).read_bytes(), name
        python_files = list(source.rglob('*.py'))
        for p in python_files:
            ast.parse(p.read_text(encoding='utf-8'), feature_version=(3, 8))
        # 在临时假安装目录执行实际安装器核心，再测试安装后的文件。
        sys.path.insert(0, str(source))
        import install
        target = Path(temp)/'SoundSight_PYNQ_Volume'
        for name in ('soundsight.bit', 'soundsight.hwh', 'software/ps/libss_solver.so', 'history.jsonl'):
            p = target/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b'UNCHANGED')
        install.install(source, target)
        for name in files: assert (target/name).read_bytes() == (ROOT/name).read_bytes(), name
        for name in ('soundsight.bit', 'soundsight.hwh', 'software/ps/libss_solver.so', 'history.jsonl'):
            assert (target/name).read_bytes() == b'UNCHANGED'
        for group in GROUPS:
            command = [sys.executable, '-B', '-X', 'utf8', str(target/'software/tests'/group), '-v']
            run = subprocess.run(command, cwd=target, capture_output=True, text=True, encoding='utf-8')
            (output/(group+'.log')).write_text(run.stdout+'\n'+run.stderr, encoding='utf-8')
            results.append(dict(test=group, exit_code=run.returncode))
            print(group, 'PASS' if run.returncode == 0 else 'FAIL')
    report = dict(zip_crc=True, package_source_match=True, install_copy_match=True,
                  hardware_library_logs_preserved=True, python38_syntax_files=len(python_files),
                  groups=results, arm_board='NOT_RUN', vivado='NOT_RUN', motion=False)
    (output/'checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return int(any(r['exit_code'] for r in results))


if __name__ == '__main__': raise SystemExit(main())
