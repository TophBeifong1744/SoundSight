"""Install P1 onto a matching idle S2/S3 runtime; enable next-boot service only."""
import argparse
from contextlib import ExitStack, contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile

REVISION = 'SCREEN_PRODUCT_P1'
SERVICE = 'soundsight-product.service'
PAYLOAD = ('software/screen/backend.py', 'software/screen/ui.py', 'software/screen/hardware.py',
           'software/screen/product.py', 'soundsight-product.sh',
           'document/screen-product.md', 'software/tests/test_screen_product.py',
           'tools/install_product.py')
PAYLOAD += ('software/tetra3d/linux/coherent_frontend.py',
            'software/tetra3d/linux/speaker_capture_3d.py',
            'software/tetra3d/linux/speaker_runtime_3d.py',
            'software/tetra3d/linux/board_3d.py',
            'software/tetra3d/linux/capture_recovery.py',
            'software/tetra3d/tests/test_cf1.py',
            'software/tetra3d/tests/test_capture_recovery.py',
            'document/screen-speaker-capture-fix.md')
PAYLOAD += ('software/tetra3d/linux/filter_3d.py',
            'software/tetra3d/linux/client_3d.py',
            'software/tetra3d/linux/runtime_3d.py',
            'software/tetra3d/linux/direction_diagnostics.py',
            'software/tetra3d/tests/test_pcm_gap_filter.py',
            'document/cf1-pcm-gap-filter.md')
PAYLOAD += ('software/tests/test_screen_rotation.py', 'document/screen-rotation.md')
PAYLOAD += ('soundsight-3d.sh', 'software/ps/speaker_delete.py', 'software/ps/speaker_targets.py',
            'software/tests/test_speaker_delete.py', 'document/screen-user-delete.md')
PAYLOAD += ('software/ps/board_tools.py', 'software/tests/test_screen_quick_boot.py',
            'software/tests/test_board_tools.py', 'document/screen-quick-boot.md')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def regular(root, name):
    p = PurePosixPath(name)
    if not name or p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name or p.as_posix() != name:
        raise ValueError('Invalid relative path: '+name)
    path = Path(root)
    for part in p.parts:
        path /= part
        if path.is_symlink() or (path.exists() and path != Path(root)/name and not path.is_dir()):
            raise ValueError('Unexpected path: '+name)
    if path.exists() and not path.is_file():
        raise ValueError('Not a regular file: '+name)
    return path


def load_package(path):
    with ZipFile(path) as z:
        expected = {'manifest.json', '__main__.py'} | {'payload/'+n for n in PAYLOAD}
        if len(z.namelist()) != len(expected) or set(z.namelist()) != expected:
            raise ValueError('Unexpected ZIP entries')
        if sum(i.file_size for i in z.infolist()) > 8*1024**2 or z.testzip() is not None:
            raise ValueError('Invalid ZIP size/CRC')
        m = json.loads(z.read('manifest.json'))
        if m.get('revision') != REVISION or set(m['files']) != set(PAYLOAD):
            raise ValueError('Wrong product revision/files')
        data = {n:z.read('payload/'+n) for n in PAYLOAD}
        if any(digest(data[n]) != m['files'][n] for n in data):
            raise ValueError('Corrupt payload')
        for n in m['requires']:
            regular(Path('.'), n)
    return m, data


def unit_text(root):
    root = Path(root).as_posix()
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', root) or '..' in PurePosixPath(root).parts:
        raise ValueError('Use an absolute Linux application path without spaces/metacharacters')
    return ('[Unit]\nDescription=SoundSight standalone touch product\n'
            'Requires=bootpy.service\nAfter=local-fs.target systemd-modules-load.service bootpy.service\n'
            'RequiresMountsFor='+root+' /boot\n'
            'ConditionPathExists='+root+'/PRODUCT-INSTALL.json\n'
            '[Service]\nType=simple\nUser=root\nWorkingDirectory='+root+'\n'
            'Environment=PYTHONUNBUFFERED=1\nEnvironment=XILINX_XRT=/usr\n'
            'ExecStart=/bin/sh '+root+'/soundsight-product.sh boot\n'
            'Restart=no\nKillMode=mixed\nSendSIGKILL=no\nTimeoutStopSec=90\n'
            'UMask=0077\nStandardOutput=journal\nStandardError=journal\n'
            '[Install]\nWantedBy=multi-user.target\n')


def systemctl(*args):
    return subprocess.run(['systemctl', *args], capture_output=True, text=True, timeout=20)


@contextmanager
def idle():
    import fcntl
    with ExitStack() as stack:
        for name in ('soundsight-screen-owner', 'soundsight-ps-owner', 'soundsight-ps-i2c0-owner'):
            h = stack.enter_context(open('/tmp/'+name+'.lock', 'a'))
            fcntl.flock(h, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for p in Path('/proc').iterdir():
            if not p.name.isdigit() or int(p.name) == os.getpid():
                continue
            try:
                raw = (p/'cmdline').read_bytes()
            except OSError:
                continue
            if any(n in raw for n in (b'board_3d.py', b'pipeline_backend', b'run_pcm.py',
                                      b'run_buffered.py', b'software/screen/ui.py',
                                      b'software/screen/product.py')):
                raise RuntimeError('Exit runtime/panel before installation; PID='+p.name)
        yield


def install(archive, root, unit_path, ctl=systemctl, unit_root=None):
    """File/service transaction; fake ctl and unit path permit hardware-free tests."""
    m, data = load_package(archive)
    root, unit_path = Path(root).absolute(), Path(unit_path).absolute()
    if any(p.is_symlink() for p in (root, *root.parents, unit_path, *unit_path.parents)):
        raise ValueError('Symlink destination rejected')
    if not root.is_dir():
        raise ValueError('Install on the existing S2/S3 application directory')
    state = ctl('is-active', SERVICE).stdout.strip()
    if state not in ('inactive', 'failed', 'unknown'):
        raise RuntimeError('Product service must be stopped before updating: '+state)
    if ctl('show', 'bootpy.service', '-p', 'LoadState', '--value').stdout.strip() != 'loaded':
        raise RuntimeError('Expected PYNQ bootpy.service; no service installed')
    for name, accepted in m['requires'].items():
        p = regular(root, name)
        permitted = accepted + ([m['files'][name]] if name in m['files'] else [])
        if not p.is_file() or digest(p.read_bytes()) not in permitted:
            raise ValueError('BASELINE_MISMATCH: preserve board version: '+name)
    for name in data:
        p = regular(root, name)
        if p.exists() and digest(p.read_bytes()) not in m['previous'].get(name, [])+[m['files'][name]]:
            raise ValueError('LOCAL_CHANGE_PRESERVED: '+name)
    receipt_path = regular(root, 'SCREEN-INSTALL.json')
    receipt = json.loads(receipt_path.read_text('utf-8'))
    if (receipt.get('revision') != 'SCREEN_PS_I2C_S2' or
            receipt.get('touch_transport') != 'PS_I2C0_EMIO_LINUX' or not receipt.get('installed_boot_id')):
        raise ValueError('Valid installed S2 receipt required')
    for group in ('hardware', 'software'):
        for name, sha in receipt[group].items():
            p = regular(root, name)
            if digest(p.read_bytes()) != sha:
                raise ValueError('Installed S2 receipt differs: '+name)
    unit = unit_text(unit_root or root).encode()
    if unit_path.exists() and unit_path.read_bytes() != unit:
        raise ValueError('Existing different systemd unit preserved')
    enabled = ctl('is-enabled', SERVICE).stdout.strip()
    if enabled not in ('enabled', 'disabled', 'not-found', ''):
        raise ValueError('Unexpected existing service state: '+enabled)
    # Preserve the actual old S2 boot requirement; this update changes no bitstream.
    for name in receipt['software']:
        if name in m['files']:
            receipt['software'][name] = m['files'][name]
    data['SCREEN-INSTALL.json'] = (json.dumps(receipt, indent=2)+'\n').encode()
    data['PRODUCT-INSTALL.json'] = (json.dumps(dict(revision=REVISION, files=m['files'],
        service=SERVICE, auto_motion=False, reboot_validation='PENDING'), indent=2)+'\n').encode()
    for name in data:
        regular(root, name)
    backup = Path(tempfile.mkdtemp(prefix='backup_screen_product_p1_', dir=str(root)))
    paths = {name:root/name for name in data}
    paths['systemd-unit'] = unit_path
    payload = dict(data, **{'systemd-unit':unit})
    old = {n:p.read_bytes() if p.exists() else None for n,p in paths.items()}
    modes = {n:p.stat().st_mode & 0o777 if p.exists() else 0o644 for n,p in paths.items()}
    for n, raw in old.items():
        if raw is not None:
            p = backup/n; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(raw)
            os.chmod(p, modes[n])
    (backup/'restore.json').write_text(json.dumps(dict(present=[n for n in old if old[n] is not None],
        absent=[n for n in old if old[n] is None], service_was_enabled=enabled == 'enabled'), indent=2))
    changed = []
    def replace(path, raw, mode):
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix='.p1-', dir=str(path.parent))
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(raw); f.flush(); os.fsync(f.fileno())
            os.chmod(tmp, mode)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    try:
        for n,p in paths.items():
            replace(p, payload[n], 0o755 if n.endswith('.sh') else modes[n])
            changed.append(n)
        for command in (('daemon-reload',), ('enable', SERVICE)):
            r = ctl(*command)
            if r.returncode:
                raise RuntimeError('Service setup failed: '+r.stderr)
    except BaseException as original:
        errors = []
        if enabled != 'enabled':
            try:
                r = ctl('disable', SERVICE)
                if r.returncode: errors.append('disable: '+r.stderr)
            except Exception as exc:
                errors.append('disable: '+str(exc))
        for n in reversed(changed):
            try:
                if old[n] is None:
                    paths[n].unlink()
                else:
                    replace(paths[n], old[n], modes[n])
            except Exception as exc:
                errors.append(n+': '+str(exc))
        try:
            r = ctl('daemon-reload')
            if r.returncode: errors.append('reload: '+r.stderr)
        except Exception as exc:
            errors.append('reload: '+str(exc))
        if errors:
            (backup/'rollback-errors.json').write_text(json.dumps(errors))
            raise RuntimeError('Rollback needs inspection: '+str(backup)) from original
        raise
    if hasattr(os, 'sync'):
        os.sync()
    return dict(revision=REVISION, screen_rotation_default=180, filter_policy='CF1_PCM_GAPS_V1', capture_revision='CAPTURE_COOPERATIVE_V1', backup=str(backup), autostart_enabled=True,
                service_started=False, hardware_actions=0, reboot_required=True,
                user_profiles_preserved=True, reboot_validation='PENDING')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--destination', type=Path, default=Path('/home/xilinx/SoundSight_PYNQ_3D_Speaker'))
    p.add_argument('--disable', action='store_true', help='Disable future autostart, do not stop a running session')
    a = p.parse_args()
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise RuntimeError('Run with sudo python3 on the PYNQ board')
    if a.disable:
        r = systemctl('disable', SERVICE)
        if r.returncode:
            raise RuntimeError(r.stderr)
        print('PRODUCT_AUTOSTART_DISABLED=1 RUNNING_SESSION_UNCHANGED=1')
        return
    with idle():
        result = install(Path(sys.argv[0]), a.destination, Path('/etc/systemd/system')/SERVICE)
    print('SCREEN_PRODUCT_P1_INSTALLED='+json.dumps(result), flush=True)
    print('NEXT: sudo reboot. Then use the screen; axes start OFF.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('STOP: '+str(exc), file=sys.stderr)
        raise SystemExit(1)
