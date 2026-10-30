"""Shared Windows tool discovery: environment > ignored local config > PATH.

This module resolves files only. It never starts Vivado, changes system PATH,
or silently replaces an explicitly configured but invalid installation.
"""
from pathlib import Path
import os
import shutil

ROOT = Path(__file__).resolve().parents[1]
KEYS = {'VIVADO_ROOT', 'PYTHON_EXE', 'GCC_ROOT', 'SS_GCC'}


def local_settings(path=None):
    path = Path(path) if path is not None else ROOT / 'tools.local.env'
    values = {}
    if path.is_file():
        for number, line in enumerate(path.read_text('utf-8-sig').splitlines(), 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            key, sep, value = line.partition('=')
            if not sep or key not in KEYS:
                raise ValueError(f'{path.name}:{number}: expected a supported KEY=value')
            if value:
                values[key] = value
    return values


def _choice(keys, env, local):
    # All environment choices outrank all local choices, including GCC aliases.
    for source in (env, local):
        for key in keys:
            if source.get(key):
                return key, source[key]
    return None, None


def _file(path, label):
    path = Path(path)
    if not path.is_absolute() or not path.is_file():
        raise FileNotFoundError(f'{label}: invalid executable {path}; edit tools.local.env or environment')
    return path.resolve()


def vivado_root(env=None, local=None):
    env = os.environ if env is None else env
    local = local_settings() if local is None else local
    _, value = _choice(('VIVADO_ROOT',), env, local)
    if value:
        executable = _file(Path(value) / 'bin' / 'vivado.bat', 'VIVADO_ROOT')
    else:
        found = shutil.which('vivado.bat', path=env.get('PATH', ''))
        if not found:
            raise FileNotFoundError('Vivado not found; set VIVADO_ROOT in tools.local.env/environment or add bin to PATH')
        executable = _file(found, 'PATH Vivado')
    return executable.parent.parent


def gcc_executable(env=None, local=None):
    env = os.environ if env is None else env
    local = local_settings() if local is None else local
    key, value = _choice(('SS_GCC', 'GCC_ROOT'), env, local)
    if value:
        return _file(Path(value) / 'bin/gcc.exe' if key == 'GCC_ROOT' else value, key)
    found = shutil.which('gcc.exe', path=env.get('PATH', ''))
    if not found:
        raise FileNotFoundError('GCC not found; set SS_GCC/GCC_ROOT in tools.local.env/environment or add gcc to PATH')
    return _file(found, 'PATH GCC')


def simulation_tools(root):
    for name in ('xvlog', 'xvhdl', 'xelab', 'xsim'):
        _file(root / 'bin' / (name + '.bat'), name)
    return root
