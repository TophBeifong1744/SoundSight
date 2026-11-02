"""SD zip installer. Changes files only; preserves profiles and calibration."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
import zipfile

TARGET = Path('/home/xilinx/SoundSight_PYNQ_3D_Speaker')
HARDWARE = ('soundsight.bit', 'soundsight.hwh')
ALLOWED = set(HARDWARE + ('soundsight-screen.sh', 'SCREEN-README.md',
    'software/screen/hardware.py', 'software/screen/backend.py',
    'software/screen/ui.py', 'software/screen/__init__.py',
    'soundsight-screen-i2c.sh', 'software/screen/linux_i2c.py',
    'software/screen/screen_i2c_prepare.py', 'software/screen/ps_i2c0_enable.dts',
    'software/screen/ps_i2c0_enable.dtbo'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def regular_path(root, name, required=False):
    rel = PurePosixPath(name)
    if rel.is_absolute() or '..' in rel.parts or '\\' in name:
        raise RuntimeError('Invalid package path: ' + name)
    path = root
    for part in rel.parts:
        path = path / part
        if path.is_symlink():
            raise RuntimeError('Refusing symlink: ' + str(path))
    if path.exists() and not path.is_file():
        raise RuntimeError('Expected regular file: ' + str(path))
    if required and not path.is_file():
        raise RuntimeError('Missing runtime file: ' + str(path))
    return path


def save(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(str(path), mode)


def install(archive, target, boot_id=None):
    target = Path(target)
    if target.is_symlink() or not target.is_dir():
        raise RuntimeError('Expected existing runtime directory: ' + str(target))
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read('manifest.json'))
        if manifest.get('revision') != 'SCREEN_PS_I2C_S2':
            raise RuntimeError('Wrong screen package revision')
        names = set(manifest['files'])
        if not set(HARDWARE).issubset(names) or not names.issubset(ALLOWED):
            raise RuntimeError('Unexpected package file list')
        payload = {name: z.read(name) for name in sorted(names)}
    for name, data in payload.items():
        if digest(data) != manifest['files'][name]:
            raise RuntimeError('Package checksum mismatch: ' + name)
    regular_path(target, 'soundsight-3d.sh', True)
    source_path = regular_path(target, 'SOURCE.json', True)
    current = {name: digest(regular_path(target, name, True).read_bytes())
               for name in HARDWARE}
    new = {name: manifest['files'][name] for name in HARDWARE}
    if current not in manifest['accepted_hardware'] + [new]:
        raise RuntimeError('Unrecognized hardware baseline; nothing changed')
    for name in names | {'SCREEN-INSTALL.json'}:
        regular_path(target, name)
    # Reject unknown local changes instead of silently replacing another version.
    for name in names - set(HARDWARE):
        path = regular_path(target, name)
        current_hash = digest(path.read_bytes()) if path.exists() else None
        allowed = manifest['accepted_files'].get(name, []) + [manifest['files'][name]]
        if current_hash not in allowed:
            raise RuntimeError('Unrecognized local file; nothing changed: ' + name)
    source = json.loads(source_path.read_text(encoding='utf-8'))
    if boot_id is None:
        boot_id = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    source['screen_previous_hardware'] = source.get('hardware', {})
    source['hardware'] = {name.split('.')[-1]: dict(path=name,
        bytes=len(payload[name]), sha256=manifest['files'][name]) for name in HARDWARE}
    source['hardware_identity'] = dict(revision=manifest['revision'], sha256=new,
        board_test='NOT_RUN', servo_pins=dict(horizontal='M15', vertical='J14'))
    source['servo_pins'] = dict(horizontal='M15', vertical='J14')
    source['servo_connector'] = dict(horizontal='J3 pin 2', vertical='J3 pin 3')
    source['board_joint_test'] = 'SCREEN_PS_I2C_S2_CANDIDATE_NOT_BOARD_TESTED'
    source['screen'] = dict(revision=manifest['revision'], resolution=[800, 480],
        default_axes='off', validation=manifest['validation'])
    payload['SOURCE.json'] = (json.dumps(source, indent=2) + '\n').encode()
    payload['SCREEN-INSTALL.json'] = (json.dumps(dict(
        revision=manifest['revision'], installed_boot_id=boot_id,
        reboot_required=True, hardware=new, software=manifest['files'],
        touch_transport='PS_I2C0_EMIO_LINUX'), indent=2) + '\n').encode()
    originals = {}
    modes = {}
    for name in payload:
        path = regular_path(target, name)
        originals[name] = path.read_bytes() if path.is_file() else None
        modes[name] = (path.stat().st_mode & 0o777) if path.is_file() else 0o644
    backup = Path(tempfile.mkdtemp(prefix='backup_screen_ps_i2c_s2_', dir=str(target)))
    for name, data in originals.items():
        if data is not None:
            save(backup / name, data, modes[name])
    save(backup / 'restore.json', json.dumps(dict(
        present=[n for n, v in originals.items() if v is not None],
        absent=[n for n, v in originals.items() if v is None]), indent=2).encode())
    if hasattr(os, 'sync'):
        os.sync()
    print('BACKUP_DIR=' + str(backup), flush=True)
    stage = Path(tempfile.mkdtemp(prefix='.screen_ps_i2c_s2_stage_', dir=str(target)))
    changed = []
    try:
        for name, data in payload.items():
            save(stage / name, data, modes[name])
        for name in payload:
            dest = target / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.replace(str(stage / name), str(dest))
            changed.append(name)
        if hasattr(os, 'sync'):
            os.sync()
    except BaseException:
        for name in reversed(changed):
            if originals[name] is None:
                (target / name).unlink()
            else:
                shutil.copy2(str(backup / name), str(target / name))
        if hasattr(os, 'sync'):
            os.sync()
        raise
    finally:
        shutil.rmtree(str(stage))
    print('SCREEN_PS_I2C_S2_INSTALLED=1 HARDWARE_ACCESS=0 DEFAULT_AXES=off')
    print('REBOOT_REQUIRED=1 THEN_PREPARE=1 USER_PROFILES_UNCHANGED=1')
    return backup


def main():
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise RuntimeError('Run with sudo python3 on the PYNQ board')
    import fcntl
    locks = []
    for lock_path in ('/tmp/soundsight-screen-owner.lock', '/tmp/soundsight-ps-owner.lock'):
        owner = open(lock_path, 'a')
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        locks.append(owner)
    tokens = (b'board_3d.py', b'run_pcm.py', b'run_buffered.py',
              b'live_speaker.py', b'speaker_process.py', b'pipeline_backend',
              b'software/screen/screen_i2c_prepare.py', b'software/screen/ui.py', b'software.screen.ui', b'soundsight-screen.sh')
    for path in Path('/proc').iterdir():
        if not path.name.isdigit() or int(path.name) == os.getpid():
            continue
        try:
            command = (path / 'cmdline').read_bytes()
        except OSError:
            continue
        if any(token in command for token in tokens):
            raise RuntimeError('Stop screen/capture/control first; PID=' + path.name)
    install(Path(sys.argv[0]), TARGET)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('STOP: ' + str(exc), file=sys.stderr)
        sys.exit(1)
