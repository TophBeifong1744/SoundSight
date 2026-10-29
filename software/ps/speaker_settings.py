"""Local window selection and explicit, non-overwriting settings migration."""
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

WINDOWS=(1.,1.5,2.)


def window_value(value):
    if type(value) not in (int,float) or not math.isfinite(value) or value not in WINDOWS:
        raise ValueError('Speaker window must be 1, 1.5 or 2 seconds')
    return float(value)


def get_window(root):
    p=Path(root)/'speaker.local.json'
    if not p.exists():return 1.5
    config=json.loads(p.read_text(encoding='utf-8'))
    if not isinstance(config,dict) or set(config)!={'window_seconds'}:
        raise ValueError('Invalid speaker.local.json')
    return window_value(config['window_seconds'])


def set_window(root,value):
    root=Path(root);value=window_value(value)
    fd,tmp=tempfile.mkstemp(prefix='.speaker-',dir=str(root))
    try:
        with os.fdopen(fd,'w',encoding='ascii') as f:
            json.dump({'window_seconds':value},f);f.write('\n');f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o644);os.replace(tmp,root/'speaker.local.json')
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return value


def capture_blocks(seconds,window):
    window_value(window)
    if type(seconds) not in (int,float) or not math.isfinite(seconds) or not window+1<=seconds<=10:
        raise ValueError('Capture seconds must be window+1 through 10; duration is not the identity window')
    return math.ceil(seconds*48000/512)


def import_settings(source,destination):
    import board_tools
    from horizontal_motion import load_calibration
    source,destination=Path(source).resolve(),Path(destination).resolve()
    if source==destination or not source.is_dir():raise ValueError('Use a different existing old package directory')
    files=('settings.local.json','horizontal.local.json','pcm_epoch.local.json','speaker.local.json')
    planned=[];result={}
    for name in files:
        p=source/name;out=destination/name
        if not p.exists():result[name]='NOT_PRESENT';continue
        if p.stat().st_size>65536:raise ValueError('Settings file too large: '+name)
        data=p.read_bytes();config=json.loads(data.decode('utf-8'))
        if not isinstance(config,dict):raise ValueError('Settings must be JSON objects')
        if name=='settings.local.json':board_tools.get_settings(source)
        elif name=='horizontal.local.json':load_calibration(p)
        elif name=='speaker.local.json':get_window(source)
        else:
            n=config.get('last_epoch')
            if type(n) is not int or not 0<=n<=0xffffffff:raise ValueError('Invalid PCM epoch')
        if out.exists():
            if out.read_bytes()!=data:raise ValueError('Destination differs; preserve existing '+name)
            result[name]='ALREADY_IDENTICAL'
        else:planned.append((out,data));result[name]='COPIED'
    # All conflicts are rejected before the first write. Never replace local settings.
    for out,data in planned:
        with out.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(out,0o644)
    return result


def verify_assets(core, use_selected=True):
    core=Path(core);cfg=json.loads((core/'live-assets.json').read_text())
    expected={'pipeline_backend','models/int8-head.onnx','models/silero_vad.onnx','frontend.f32','speaker-template.json'}
    if set(cfg['sha256'])!=expected:raise ValueError('Live asset manifest names')
    for name,h in cfg['sha256'].items():
        if hashlib.sha256((core/name).read_bytes()).hexdigest()!=h:raise ValueError('Live asset hash: '+name)
    template=json.loads((core/'speaker-template.json').read_text())
    vec=template['template']
    if len(vec)!=192 or not all(type(v) in (int,float) and math.isfinite(v) for v in vec):raise ValueError('Invalid template')
    if abs(sum(v*v for v in vec)-1)>1e-4:raise ValueError('Template norm')
    low,high=template['low'],template['high']
    if not all(type(v) in (int,float) and math.isfinite(v) for v in (low,high)) or not -1<=low<high<=1:
        raise ValueError('Template thresholds')
    if use_selected:
        from speaker_targets import selected_config
        return selected_config(core, template, cfg['sha256'])
    return template
