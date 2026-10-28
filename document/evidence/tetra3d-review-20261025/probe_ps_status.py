"""Reproduce the PS capability-bit incompatibility without hardware access.

Pass a checkout/extracted source snapshot of B's fixed candidate and a C99
compiler. This test compiles that candidate unchanged in a temporary folder.
The capability-cleared case is diagnostic only, not a production workaround.
"""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--cc', default=os.environ.get('CC', 'gcc'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.source.resolve()
    common = root / 'software/common'
    core = root / 'software/tetra3d/core'
    entry = root / 'software/tetra3d/tests/test_solver_3d_migration.py'
    spec = importlib.util.spec_from_file_location('candidate_tests', entry)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    flags = ['-std=c99', '-O2', '-Wall', '-Wextra', '-Wconversion',
             '-Wshadow', '-Werror', '-pedantic', '-shared']
    if os.name != 'nt':
        flags.append('-fPIC')
    sources = [common / 's1/doa_solver.c']
    sources += [core / name for name in ('doa_solver_3d.c', 'doa_geometry.c',
                                         'doa_target_3d.c')]
    sources += [root / 'software/tetra3d/linux/ss_solver_3d_bridge.c']
    results = []
    with tempfile.TemporaryDirectory(prefix='ss3d-status-') as temporary:
        library = Path(temporary) / ('solver.dll' if os.name == 'nt' else 'solver.so')
        command = [args.cc, *flags]
        command += ['-I' + str(p) for p in (common, common / 's1', core)]
        command += [*map(str, sources), '-lm', '-o', str(library)]
        build = subprocess.run(command, capture_output=True, text=True)
        if build.returncode:
            raise RuntimeError(build.stdout + build.stderr)
        geometry = json.loads((core / 'tetra40-nominal.json').read_text())
        solver = module.Solver3D(library, geometry)
        try:
            base = module.wire(module.synthetic(45, 30))
            cases = [('baseline', 0x11, 0),
                     ('manual_capability', 0x40011, -2),
                     ('board_status_shape', 0xf7f31, -2),
                     ('board_shape_without_capability_diagnostic_only', 0xb7f31, 0),
                     ('reserved_bit_negative', 0x51, -2)]
            for name, status, expected in cases:
                frame = copy.deepcopy(base)
                frame['status'] = status
                result = solver.solve(frame)
                assert result['bridge_status'] == expected, (name, result)
                if expected == 0:
                    assert result['direction_valid'] == 1, (name, result)
                results.append(dict(name=name, frame=frame, result=result))
        finally:
            module.close_lib(solver.lib)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(
        candidate='3347989eb03488a33c88c241c75eed517d3a30f0',
        scope='PC synthetic same-frame transport check; no board or motion',
        interpretation='Reproduced integration failure; candidate not repaired',
        compiler=args.cc, cases=results), indent=2) + '\n', encoding='utf-8')
    for case in results:
        print(case['name'], hex(case['frame']['status']),
              'bridge_status=', case['result']['bridge_status'],
              'direction_valid=', case['result']['direction_valid'])


if __name__ == '__main__':
    main()
