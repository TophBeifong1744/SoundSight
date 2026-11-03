"""Delete one explicitly confirmed local profile, never models or recordings.

The caller must hold the existing PS owner lock. Preview is read-only; its
content token binds confirmation to the displayed profile, not a list index.
"""
import hashlib
import json
from pathlib import Path

from speaker_targets import SELECTOR, atomic_json, profile_path, target_name


def preview(root, target):
    target_name(target)
    if target.upper() == 'P01':
        raise ValueError('BUILTIN_P01_PROTECTED: shared baseline is not a local user')
    if target.casefold() == 'p02-v1':
        raise ValueError('Use the displayed target P02')
    root = Path(root).resolve()
    path = profile_path(root, target)
    # Reject links/redirects before reading, and never recurse for deletion.
    for item in (root/'speaker-profiles', path.parent, path):
        if item.is_symlink() or item.resolve() != item.absolute():
            raise ValueError('PROFILE_PATH_REDIRECTED')
    if not path.is_file() or path.stat().st_size > 65536:
        raise ValueError('PROFILE_MISSING_OR_TOO_LARGE')
    profile = json.loads(path.read_text(encoding='utf-8'))
    if profile.get('target_id') != target:
        raise ValueError('PROFILE_TARGET_MISMATCH')
    files = sorted(path.parent.iterdir())
    for item in files:
        if (item.name not in ('profile.json', 'evaluation.json') or
                item.is_symlink() or not item.is_file() or item.stat().st_size > 1024*1024):
            raise ValueError('UNEXPECTED_PROFILE_CONTENT: preserve and inspect')
    token = hashlib.sha256()
    for item in files:
        token.update(item.name.encode('ascii') + b'\0' + item.read_bytes())
    return dict(target=target, token=token.hexdigest(), files=files)


def delete(root, target, confirm_target, expected_token):
    if confirm_target != target:
        raise ValueError('CONFIRM_TARGET_MISMATCH')
    root = Path(root).resolve()
    info = preview(root, target)
    if expected_token != info['token']:
        raise ValueError('PROFILE_CHANGED: reopen deletion confirmation')
    selector = root/SELECTOR
    gate = root/'speaker-follow.local.json'
    for item in (selector, gate):
        if item.is_symlink():
            raise ValueError('CONFIG_PATH_REDIRECTED')
    selected = json.loads(selector.read_text('utf-8')) if selector.exists() else {}
    active = selected.get('target_id') == target
    if active:
        from speaker_follow_setup import configure
        # Disable permission first. Keep an explicit empty selector: unlinking
        # it would silently reactivate the built-in P01 fallback.
        configure(root, disable=True)
        atomic_json(selector, dict(schema=1, target_id=None))
    # Only named files immediately within this exact validated user directory.
    # Unlink profile last so any earlier failure remains retryable.
    for item in sorted(info['files'], key=lambda p: p.name == 'profile.json'):
        item.unlink()
    profile_path(root, target).parent.rmdir()
    return dict(deleted=target, active_target_cleared=active,
                recordings_and_logs_preserved=True, hardware_actions=0)
