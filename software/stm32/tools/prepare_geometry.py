"""Validate JSON with the firmware C validator, then emit a cold-config header.
No board I/O; no output replacement. GCC is discovered via tools/tool_config.py.
"""
from pathlib import Path
import argparse
import json
import math
import subprocess
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from tool_config import gcc_executable


def unique(items):
    obj = {}
    for key, value in items:
        if key in obj:
            raise ValueError('Duplicate JSON key: ' + key)
        obj[key] = value
    return obj


def keys(value, expected):
    if type(value) is not dict or set(value) != set(expected.split()):
        raise ValueError('Unexpected/missing JSON fields; expected: ' + expected)


def integer(v, lo, hi):
    if type(v) is not int or not lo <= v <= hi:
        raise ValueError('Integer out of range')
    return str(v) + 'U'


def number(v):
    if type(v) not in (float, int) or not math.isfinite(v) or abs(v) > 1e9:
        raise ValueError('Invalid finite numeric field')
    s = format(float(v), '.9g')
    if '.' not in s and 'e' not in s:
        s += '.0'
    return s + 'f'


def header(obj):
    keys(obj, 'schema revision provenance source_id sample_rate_hz sound_speed_m_s position_error_mm microphones')
    schema = integer(obj['schema'], 1, 1)
    rev = integer(obj['revision'], 1, 0xffffffff)
    provenance = obj['provenance']
    if type(provenance) is not str or provenance not in ('NOMINAL', 'MEASURED', 'SYNTHETIC'):
        raise ValueError('Invalid provenance')
    source = obj['source_id']
    if type(source) is not str or not 1 <= len(source) <= 63 or any(not 33 <= ord(c) <= 126 for c in source):
        raise ValueError('source_id: 1..63 printable non-space ASCII characters')
    # Octal escaping avoids quote, backslash and C99 trigraph interpretation.
    source_c = '"' + ''.join('\\%03o' % ord(c) for c in source) + '"'
    rows = obj['microphones']
    if type(rows) is not list or len(rows) != 4:
        raise ValueError('Exactly four microphone rows required')
    mics = []
    for row in rows:
        keys(row, 'channel xyz_mm')
        ch = integer(row['channel'], 0, 3)
        xyz = row['xyz_mm']
        if type(xyz) is not list or len(xyz) != 3:
            raise ValueError('xyz_mm must have three coordinates')
        mics.append('    {' + ch + ', {' + ', '.join(number(v) for v in xyz) + '}}')
    return ('/* Generated local geometry; declaration is not verified calibration. */\n'
            '#ifndef SS_GEOMETRY_SELECTED_H\n#define SS_GEOMETRY_SELECTED_H\n'
            '#include "doa_geometry.h"\nstatic const doa_geometry_record_t ss_geometry_selected = {\n'
            f'    {schema}, {rev}, DOA_GEOMETRY_{provenance}, {source_c},\n'
            '    {\n' + ',\n'.join(mics) + '\n    },\n    ' +
            ', '.join(number(obj[k]) for k in ('sample_rate_hz', 'sound_speed_m_s', 'position_error_mm')) +
            '\n};\n#endif\n')


CHECKER = r'''#include "candidate.h"
#include <stdio.h>
int main(void) {
    doa3d_config_t c; doa_geometry_report_t r; unsigned int i;
    doa_geometry_status_t s=doa_geometry_build(&ss_geometry_selected,&c,&r);
    printf("GEOMETRY,status=%d,valid=%u,uncertainty_known=%u,condition=%.6f,bad_pair=%u\n",
        (int)s,(unsigned)r.valid,(unsigned)r.uncertainty_known,(double)r.normal_condition,(unsigned)r.bad_pair);
    if(s!=DOA_GEOMETRY_OK) return 1;
    for(i=0U;i<6U;++i) printf("PAIR,%u,mm=%.6f,nominal_samples=%.6f,bounded_samples=%.6f\n",
        i,(double)r.distance_mm[i],(double)r.nominal_delay_samples[i],(double)r.bounded_delay_samples[i]);
    return 0;
}
'''


def prepare(src, out):
    if out.exists():
        raise ValueError('Output already exists; choose a new output path')
    if src.stat().st_size > 16384:
        raise ValueError('Geometry JSON exceeds 16 KiB')
    obj = json.loads(src.read_text(encoding='utf-8'), object_pairs_hook=unique,
                     parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON: ' + x)))
    text = header(obj)
    build = ROOT / 'software/stm32/build/geometry-d2'
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='check-', dir=build) as d:
        tmp = Path(d)
        (tmp / 'candidate.h').write_text(text, encoding='ascii')
        (tmp / 'check.c').write_text(CHECKER, encoding='ascii')
        cmd = [str(gcc_executable()), '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror', '-pedantic',
               '-D__USE_MINGW_ANSI_STDIO=1', '-Isoftware/common', '-Isoftware/common/s1',
               '-Isoftware/common/s1_3d', str(tmp / 'check.c'),
               'software/common/s1_3d/doa_geometry.c', 'software/common/s1_3d/doa_solver_3d.c',
               '-lm', '-o', str(tmp / 'check.exe')]
        for command in (cmd, [str(tmp / 'check.exe')]):
            p = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            print(p.stdout + p.stderr, end='')
            if p.returncode:
                raise ValueError('C geometry validation failed; output not written')
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='ascii') as f:
        f.write(text)
    print('HEADER_CREATED,' + str(out))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    args = ap.parse_args()
    try:
        prepare(args.input, args.out)
    except (ValueError, OSError, OverflowError) as e:
        print('GEOMETRY_REJECT,' + str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
