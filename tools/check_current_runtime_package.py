"""Validate the actual private runtime ZIP offline; never import PYNQ or touch hardware."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import types
from unittest.mock import patch
from zipfile import ZipFile


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--cc', default=os.environ.get('CC', 'gcc'))
    args = p.parse_args()
    out, archive = args.output.resolve(), args.package.resolve()
    if out.exists():
        raise ValueError('Use a new output directory; preserve earlier failures')
    out.mkdir(parents=True)
    with ZipFile(archive) as z:
        assert z.testzip() is None
        manifest = json.loads(z.read('manifest.json'))
        installer = types.ModuleType('actual_zip_installer')
        exec(compile(z.read('__main__.py'), 'zip/__main__.py', 'exec'), installer.__dict__)
        assert not any('/das/' in n or '.local.' in n or '/speaker-profiles/' in n for n in z.namelist())
    app = out/'unpacked'/'SoundSight_PYNQ_3D_Speaker'
    result = installer.install(archive, app, 'offline-install-boot')
    assert result['hardware_actions'] == 0 and result['reboot_required']
    sys.path.insert(0, str(app/'software/ps'))
    from speaker_settings import verify_assets
    from speaker_models import verify_candidates
    verify_assets(app/'software/ps/speaker_core', use_selected=False)
    verify_candidates(app/'software/ps/speaker_core')
    spec = importlib.util.spec_from_file_location('offline_screen_hardware', app/'software/screen/hardware.py')
    hardware = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hardware)
    spec = importlib.util.spec_from_file_location('offline_product', app/'software/screen/product.py')
    product = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(product)
    product.verify_product(app)
    # A second installation must preserve private user state while replacing a
    # stale P1 receipt with hashes of the actual complete-package payload.
    sentinels = {'settings.local.json': b'{"min_level": 9000}\n',
                 'speaker-profiles/offline-user/profile.json': b'{"private":true}\n',
                 'logs/retained.txt': b'offline preservation sentinel\n'}
    for name, raw in sentinels.items():
        path = app/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    (app/'PRODUCT-INSTALL.json').write_text('{"revision":"OLD"}', encoding='utf-8')
    installer.install(archive, app, 'offline-install-boot')
    product.verify_product(app)
    for name, raw in sentinels.items():
        assert (app/name).read_bytes() == raw
    read_text = Path.read_text
    # Only the boot-ID file is mocked. Hashes are checked on installed real files.
    for boot in ('offline-install-boot', 'offline-next-boot'):
        def read(path, *a, **kw):
            return boot if path.as_posix() == '/proc/sys/kernel/random/boot_id' else read_text(path, *a, **kw)
        with patch.object(Path, 'read_text', read):
            if boot == 'offline-install-boot':
                try:
                    hardware.verify_install(app)
                except ValueError as exc:
                    assert 'Reboot' in str(exc)
                else:
                    raise AssertionError('Same-boot screen receipt was accepted')
            else:
                hardware.verify_install(app)
    regression = out/'regression'
    subprocess.run([sys.executable, '-B', str(app/'tools/check_current_software.py'),
                    '--cc', args.cc, '--output', str(regression)], cwd=app, check=True)
    results = json.loads((regression/'result.json').read_text('utf-8'))['tests']
    env = os.environ.copy()
    env.update(PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    tests = ('test_current_runtime test_speaker_statistics '
             'test_latest_result test_normal test_volume_gate test_serial_english '
             'test_board_tools test_filter_controls test_manual_servo test_pcm_capture').split()
    for name in tests:
        test = 'software/tests/'+name+'.py'
        r = subprocess.run([sys.executable, '-B', str(regression/'run_host.py'), str(app/test)],
                           cwd=app, env=env, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=120)
        log = r.stdout+r.stderr
        (regression/(name+'.log')).write_text(log, encoding='utf-8')
        results.append(dict(test=test, exit=r.returncode, output=log))
        print(name+' EXIT='+str(r.returncode), flush=True)
    counts = [re.search(r'Ran (\d+) tests?', r['output']) for r in results]
    summary = dict(package_revision=manifest['revision'], files=len(manifest['files']),
        crc='PASS', actual_zip_install='PASS', screen_receipt_after_mock_reboot='PASS',
        product_receipt_and_upgrade='PASS', private_state_preservation='PASS',
        private_asset_bindings='PASS', das=False, hardware_actions=0,
        scope='PC_SYNTHETIC_AND_PACKAGE_VALIDATION',
        test_invocations=sum(int(m.group(1)) for m in counts if m),
        tests=[dict(test=r['test'], exit=r['exit']) for r in results],
        result='PASS' if all(r['exit'] == 0 for r in results) else 'FAIL')
    (out/'validation.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(summary), flush=True)
    return 0 if summary['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
