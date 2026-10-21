"""Python 3.8+ offline 3D solver. No PYNQ import, MMIO, consume or motion.

Use explicit geometry and the same locked snapshot frame as ps_client.Client.
The result schema is deliberately distinct from the planar motion API.
"""
import argparse
import copy
import ctypes as C
import json
import math
from pathlib import Path
import time

INFO = ('api_status direction_valid reason azimuth_valid elevation_valid '
        'azimuth_q8 elevation_q8 valid_pairs valid_pair_mask coordinates_measured '
        'first_error bad_pair geometry_status geometry_bad_pair').split()
VALUES = 'ux uy uz norm residual_rms_samples normal_condition azimuth_deg elevation_deg'.split()
PAIR = 'delta_q12 tau_q12 margin_q15 qualified reason'.split()


def _uint(value, name):
    if type(value) is not int or not 0 <= value <= 0xffffffff:
        raise ValueError(name + ' must be uint32 (not bool)')
    return value


def _number(value):
    if type(value) not in (float, int) or not math.isfinite(value) or abs(value) > 3.4e38:
        raise ValueError('geometry must contain finite float32 numbers')
    return value


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def read_json(text):
    return json.loads(text, object_pairs_hook=_unique)


class Solver3D:
    def __init__(self, library, geometry):
        if set(geometry) != {'schema', 'revision', 'provenance', 'source_id',
                             'sample_rate_hz', 'sound_speed_m_s',
                             'position_error_mm', 'microphones'}:
            raise ValueError('geometry fields do not match schema 1')
        self._geometry = copy.deepcopy(geometry)
        rows = geometry['microphones']
        if len(rows) != 4 or any(set(row) != {'channel', 'xyz_mm'} for row in rows):
            raise ValueError('four microphones with explicit channels are required')
        if any(len(row['xyz_mm']) != 3 for row in rows):
            raise ValueError('each microphone needs xyz_mm')
        provenance = {'NOMINAL': 0, 'MEASURED': 1, 'SYNTHETIC': 2}
        if geometry['provenance'] not in provenance:
            raise ValueError('unknown geometry provenance')
        source = geometry['source_id']
        if not isinstance(source, str) or not 1 <= len(source) <= 63 or any(
                not 33 <= ord(ch) <= 126 for ch in source):
            raise ValueError('source_id must be 1..63 printable ASCII characters without spaces')
        self._source = C.create_string_buffer(source.encode('ascii'), 64)
        values = [v for row in rows for v in row['xyz_mm']] + [
            geometry['sample_rate_hz'], geometry['sound_speed_m_s'], geometry['position_error_mm']]
        self._geo = (C.c_float * 15)(*map(_number, values))
        meta = [_uint(geometry[k], k) for k in ('schema', 'revision')]
        meta += [provenance[geometry['provenance']]] + [_uint(r['channel'], 'channel') for r in rows]
        self._meta = (C.c_uint32 * 7)(*meta)
        self.lib = C.CDLL(str(Path(library).resolve()))
        self.lib.ss3d_bridge_version.restype = C.c_uint32
        self.lib.ss3d_bridge_version.argtypes = []
        if self.lib.ss3d_bridge_version() != 0x10000:
            raise ValueError('3D bridge version mismatch')
        self.call = self.lib.ss3d_solve_words
        self.call.restype = C.c_int
        self.call.argtypes = [C.c_uint32, C.c_uint32, C.POINTER(C.c_uint32),
                              C.POINTER(C.c_float), C.POINTER(C.c_uint32),
                              C.POINTER(C.c_char), C.POINTER(C.c_int32),
                              C.POINTER(C.c_float), C.POINTER(C.c_int64)]
        # Validate geometry through the production C validator, no fake result
        # is published. This all-zero feature frame is only a preflight call.
        check = self.solve(dict(sequence=1, status=0x11,
                                words=[v for i in range(6) for v in (i << 8, 0, 0, 0, 0)]))
        if check['bridge_status'] < 0:
            raise ValueError('geometry rejected: status=%d pair=%d' % (
                check['geometry_status'], check['geometry_bad_pair']))

    @property
    def geometry(self):
        return copy.deepcopy(self._geometry)

    def solve(self, frame):
        sequence = _uint(frame['sequence'], 'sequence')
        status = _uint(frame['status'], 'status')
        if len(frame['words']) != 30:
            raise ValueError('six complete pairs (30 uint32 words) required')
        words = (C.c_uint32 * 30)(*[_uint(w, 'word') for w in frame['words']])
        info, values, pairs = (C.c_int32 * 14)(), (C.c_float * 8)(), (C.c_int64 * 30)()
        rc = self.call(sequence, status, words, self._geo, self._meta, self._source,
                       info, values, pairs)
        result = dict(zip(INFO, info))
        result.update(zip(VALUES, values))
        result.update(bridge_status=rc, sequence=sequence, profile='TETRA40_3D',
                      geometry_revision=self._geometry['revision'],
                      geometry_source=self._geometry['source_id'],
                      pairs=[dict(zip(PAIR, pairs[i*5:i*5+5])) for i in range(6)],
                      servo_cmd_valid=0)
        return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--library', required=True)
    ap.add_argument('--geometry', required=True)
    ap.add_argument('--input', required=True, help='JSONL: one locked frame dictionary per line')
    ap.add_argument('--output', required=True, help='new JSONL file, will not overwrite')
    args = ap.parse_args()
    solver = Solver3D(args.library, read_json(Path(args.geometry).read_text(encoding='utf-8')))
    count = 0
    with open(args.input, encoding='utf-8') as source, open(args.output, 'x', encoding='utf-8') as sink:
        for line in source:
            frame = read_json(line)
            start = time.perf_counter_ns()
            result = solver.solve(frame)
            elapsed = time.perf_counter_ns() - start
            sink.write(json.dumps(dict(frame=frame, result=result, geometry=solver.geometry,
                                       call_ns=elapsed), allow_nan=False) + '\n')
            count += 1
            if result['bridge_status']:
                raise RuntimeError('invalid input/API result saved; stopped at frame %d' % count)
    if not count:
        raise ValueError('empty input; no validation performed')
    print('REPLAY_3D_COMPLETE frames=%d motion=DISABLED' % count)


if __name__ == '__main__':
    main()
