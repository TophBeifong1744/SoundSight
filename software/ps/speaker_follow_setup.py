"""Local settings/profile import only; no hardware access and no re-enrollment."""
import json
import os
from pathlib import Path

from speaker_permission import CONFIG_NAME, settings, load_settings
from speaker_targets import atomic_json, PROFILE, SELECTOR, selected_config, profile_path
from speaker_settings import verify_assets
from speaker_models import verify_candidates


def configure(root, threshold=None, ttl=None, disable=False):
    config = load_settings(root)
    if disable or threshold is not None or ttl is not None:
        config = settings(None if disable else (threshold if threshold is not None else config['threshold']),
                          config['permit_seconds'] if ttl is None else ttl)
        atomic_json(Path(root)/CONFIG_NAME, config)
    return config


def import_profile(root, source):
    """Copy selected real P02/P01 metadata, never overwrite a different local file."""
    root, source = Path(root).resolve(), Path(source).resolve()
    if root == source:
        raise ValueError('Select the previous speaker application as source')
    source_core = source/'software/ps/speaker_core'
    destination_core = root/'software/ps/speaker_core'
    original = verify_assets(destination_core, use_selected=False)
    selected = verify_assets(source_core)
    if not (source/SELECTOR).is_file():
        raise ValueError('Source needs an explicit speaker-target.local.json selector; no silent P01 fallback')
    manifest = json.loads((destination_core/'live-assets.json').read_text())['sha256']
    source_manifest = json.loads((source_core/'live-assets.json').read_text())['sha256']
    if manifest != source_manifest:
        raise ValueError('Enrollment baseline differs; do not overwrite or silently rebind the profile')
    names = [SELECTOR]
    if selected['target_id'] != 'P01':
        names.append(str(profile_path(source, selected['target_id']).relative_to(source)))
    # User calibration/window settings remain local; import only if compatible
    # and absent or byte-identical, never merge silently.
    names += [n for n in ('settings.local.json', 'servo3d.local.json') if (source/n).is_file()]
    planned = []
    for name in names:
        data = (source/name).read_bytes()
        if len(data) > 65536:
            raise ValueError('Oversized local configuration: '+name)
        path = root/name
        if path.exists() and path.read_bytes() != data:
            raise ValueError('Existing local file preserved: '+name)
        planned.append((path, data))
    if not (root/SELECTOR).exists():
        # A directory can contain an old gate setting without a selector.
        # Importing a different person's template must never inherit it.
        configure(root, disable=True)
    for path, data in planned:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as f:
                f.write(data)
    selected_config(destination_core, original, manifest)
    return dict(target_id=selected['target_id'], files=names, re_enrolled=False, hardware_actions=0)


def check(root):
    core = Path(root)/'software/ps/speaker_core'
    if not (Path(root)/SELECTOR).is_file():
        raise ValueError('Import/select the real target first; implicit P01 fallback is disabled here')
    target = verify_assets(core)
    models = verify_candidates(core)
    models['enrollment_model'] = ('cp1/fixed98.onnx' if target.get('schema') == 2 else 'int8-head.onnx')
    # python -m zipfile does not restore Unix executable mode. Content is
    # verified above before enabling this local, non-hardware CPU executable.
    if os.name == 'posix':
        os.chmod(core/'pipeline_backend', 0o755)
    return dict(target_id=target.get('target_id', 'P01'), profile_score_only=target.get('score_only', False),
                settings=load_settings(root), models=models, hardware_actions=0)
