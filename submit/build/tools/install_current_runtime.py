"""Install the complete S2/S3/CF1A runtime; files only, no hardware actions.

Run the ZIP with system Python. Existing hardware and private base assets must
match; local settings/profiles/logs are never part of the replacement manifest.
"""
import argparse
from contextlib import ExitStack, contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
from zipfile import ZipFile

REVISION = 'S2_S3_CF1A_NO_DAS_20261102'
PREFIX = 'SoundSight_PYNQ_3D_Speaker/'
HARDWARE = ('soundsight.bit', 'soundsight.hwh')
SCREEN = ('software/screen/hardware.py', 'software/screen/ui.py',
          'software/screen/linux_i2c.py', 'software/screen/screen_i2c_prepare.py',
          'software/screen/ps_i2c0_enable.dtbo')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def regular(root, name):
    rel = PurePosixPath(name)
    if not name or rel.is_absolute() or '..' in rel.parts or '\\' in name or ':' in name or rel.as_posix() != name:
        raise ValueError('Invalid relative path: '+name)
    p = root
    for part in rel.parts:
        p = p/part
        if p.is_symlink():
            raise ValueError('Symlink rejected: '+name)
    if p.exists() and not p.is_file():
        raise ValueError('Not a regular file: '+name)
    return p


def load_package(archive):
    with ZipFile(archive) as z:
        if len(z.namelist()) != len(set(z.namelist())):
            raise ValueError('Duplicate ZIP entries')
        manifest = json.loads(z.read('manifest.json'))
        if manifest.get('revision') != REVISION:
            raise ValueError('Wrong runtime revision')
        expected = {'manifest.json', '__main__.py'} | {PREFIX+n for n in manifest['files']}
        if set(z.namelist()) != expected or sum(i.file_size for i in z.infolist()) > 512*1024**2:
            raise ValueError('Unexpected package files/size')
        data = {}
        for name, sha in manifest['files'].items():
            regular(Path('.'), name)
            if ('.local.' in name or name.startswith(('logs/', 'speaker-profiles/')) or
                    '/das/' in name or name in ('SCREEN-INSTALL.json', 'RUNTIME-INSTALL.json', 'RUNTIME-INCOMPLETE.json')):
                raise ValueError('Protected/unsupported payload: '+name)
            raw = z.read(PREFIX+name)
            if digest(raw) != sha:
                raise ValueError('Corrupt payload: '+name)
            data[name] = raw
    for name in HARDWARE+SCREEN+('soundsight-3d.sh', 'soundsight-panel.sh', 'SOURCE.json'):
        if name not in data:
            raise ValueError('Incomplete runtime: '+name)
    return manifest, data


@contextmanager
def idle():
    """Hold all existing application owner locks; never stop another process."""
    if sys.platform != 'linux':
        raise RuntimeError('Installation CLI is for Linux/PYNQ; use offline tests on PC')
    import fcntl
    with ExitStack() as stack:
        for name in ('soundsight-screen-owner', 'soundsight-ps-owner', 'soundsight-ps-i2c0-owner'):
            h = stack.enter_context(open('/tmp/'+name+'.lock', 'a'))
            fcntl.flock(h, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Covers a worker starting before it acquires the application lock.
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit() or int(proc.name) == os.getpid():
                continue
            try:
                cmd = (proc/'cmdline').read_bytes()
            except OSError:
                continue
            if any(t in cmd for t in (b'board_3d.py', b'pipeline_backend', b'run_pcm.py',
                    b'run_buffered.py', b'software/screen/ui.py', b'software.screen.ui',
                    b'screen_i2c_prepare.py')):
                raise RuntimeError('Stop runtime/panel before installing; PID='+proc.name)
        yield


def install(archive, target, boot_id):
    """Offline-testable transaction. Caller holds locks and supplies actual boot ID."""
    manifest, data = load_package(archive)
    target = Path(target).absolute()
    if any(p.is_symlink() for p in (target, *target.parents)):
        raise ValueError('Destination symlink rejected')
    if not isinstance(boot_id, str) or not boot_id.strip():
        raise ValueError('Real boot ID required')
    existing = target.exists() and any(target.iterdir())
    pending = regular(target, 'RUNTIME-INCOMPLETE.json')
    if existing and pending.is_file() and json.loads(pending.read_text('utf-8')) == {'revision': REVISION, 'fresh': True}:
        # A failed fresh transaction leaves only our backup and empty directories.
        # Never treat real program files or an unknown bitstream as a blank install.
        others = [p for p in target.rglob('*') if p.is_file() and p != pending and
                  not (p.relative_to(target).parts[0].startswith('backup_runtime_') and
                       (target/p.relative_to(target).parts[0]/'restore.json').is_file())]
        if not others:
            existing = False
    if existing:
        # A software refresh must not silently replace an unknown/newer bitstream.
        for name in HARDWARE:
            p = regular(target, name)
            if not p.is_file() or digest(p.read_bytes()) != manifest['files'][name]:
                raise ValueError('HARDWARE_MISMATCH: preserve board files; '+name)
        for name in manifest['private_assets']:
            p = regular(target, name)
            if p.exists() and p.read_bytes() != data[name]:
                raise ValueError('PRIVATE_ASSET_DIFFERS: preserve enrollment binding; '+name)
    for name in list(data)+['SCREEN-INSTALL.json', 'RUNTIME-INSTALL.json']:
        regular(target, name)
    screen = dict(revision='SCREEN_PS_I2C_S2', touch_transport='PS_I2C0_EMIO_LINUX',
                  installed_boot_id=boot_id, reboot_required=True,
                  hardware={n: digest(data[n]) for n in HARDWARE},
                  software={n: digest(data[n]) for n in SCREEN})
    old = target/'SCREEN-INSTALL.json'
    if old.is_file():
        receipt = json.loads(old.read_text('utf-8'))
        if (receipt.get('revision') == screen['revision'] and
                receipt.get('touch_transport') == screen['touch_transport'] and
                receipt.get('hardware') == screen['hardware'] and
                all(receipt.get('software', {}).get(n) == screen['software'][n] for n in SCREEN) and
                isinstance(receipt.get('installed_boot_id'), str) and receipt['installed_boot_id'].strip()):
            screen = receipt  # Preserve the genuine previous-install boot requirement.
    data['SCREEN-INSTALL.json'] = (json.dumps(screen, indent=2)+'\n').encode()
    data['RUNTIME-INSTALL.json'] = (json.dumps(dict(revision=REVISION,
        source_commit=manifest['source_commit'], hardware_actions=0,
        das_enabled=False, local_settings_preserved=True), indent=2)+'\n').encode()
    target.mkdir(parents=True, exist_ok=True)
    if not existing:
        pending.write_text(json.dumps({'revision': REVISION, 'fresh': True}), encoding='utf-8')
    changes = {n: raw for n, raw in data.items() if not (target/n).is_file() or (target/n).read_bytes() != raw}
    backup = Path(tempfile.mkdtemp(prefix='backup_runtime_', dir=str(target)))
    stage = Path(tempfile.mkdtemp(prefix='.runtime-stage-', dir=str(target)))
    present = []
    for name in changes:
        p = target/name
        if p.exists():
            q = backup/name; q.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, q); present.append(name)
    (backup/'restore.json').write_text(json.dumps(dict(present=present,
        absent=[n for n in changes if n not in present]), indent=2)+'\n', encoding='utf-8')
    changed = []
    try:
        for name, raw in changes.items():
            p = stage/name; p.parent.mkdir(parents=True, exist_ok=True)
            with p.open('wb') as f:
                f.write(raw); f.flush(); os.fsync(f.fileno())
            os.chmod(p, 0o755 if name.endswith('.sh') or name.endswith('/pipeline_backend') else 0o644)
        for name in changes:
            dest = target/name; dest.parent.mkdir(parents=True, exist_ok=True)
            os.replace(stage/name, dest); changed.append(name)
    except BaseException:
        for name in reversed(changed):
            if name in present:
                shutil.copy2(backup/name, target/name)
            else:
                (target/name).unlink()
        raise
    finally:
        shutil.rmtree(stage)
    if hasattr(os, 'sync'):
        os.sync()
    if pending.exists():
        pending.unlink()
    return dict(revision=REVISION, changed_files=len(changes), backup=str(backup),
                reboot_required=screen['installed_boot_id'].strip() == boot_id.strip(),
                hardware_actions=0, das_enabled=False, settings_preserved=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--destination', type=Path, default=Path('/home/xilinx/SoundSight_PYNQ_3D_Speaker'))
    args = ap.parse_args()
    with idle():
        if os.geteuid() != 0:
            raise RuntimeError('Use sudo python3 PACKAGE.zip')
        result = install(Path(sys.argv[0]), args.destination,
                         Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    print('RUNTIME_INSTALLED='+json.dumps(result), flush=True)
    print('NEXT: reboot if required; then sh soundsight-3d.sh prepare. No automatic motion.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('STOP: '+str(exc), file=sys.stderr)
        raise SystemExit(1)
