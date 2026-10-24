"""Offline/reference tetrahedral DAS, Python 3.8+, NumPy. No hardware access.

Source-facing vectors; x_i[n-d_i], d_i=fs/c dot(r_i-r_0, unit_direction).
All stream indices count PCM samples from zero, NOT solver frame sequences.
"""
import argparse
import json
import math
from pathlib import Path
import wave

import numpy as np

if __package__:
    from .dynamic_das import DynamicDAS, Q, integer
else:
    from dynamic_das import DynamicDAS, Q, integer


def finite_vector(value):
    if len(value) != 3 or any(isinstance(v, (bool, np.bool_)) for v in value):
        raise ValueError('three finite numeric coordinates required')
    if any(not isinstance(v, (int, float, np.integer, np.floating)) for v in value):
        raise ValueError('numeric coordinates required')
    vector = np.asarray(value, dtype=np.float64)
    if not np.all(np.isfinite(vector)):
        raise ValueError('nonfinite vector')
    return vector


def positive(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError('positive finite rate/speed required')
    return float(value)


class Geometry:
    """Explicit channel order 0..3; millimetres in the solver geometry schema."""
    def __init__(self, config):
        if config.get('schema') != 1 or type(config.get('schema')) is not int:
            raise ValueError('geometry schema 1 required')
        if type(config.get('revision')) is not int or config['revision'] < 1:
            raise ValueError('positive geometry revision required')
        if config.get('provenance') not in ('NOMINAL', 'MEASURED', 'SYNTHETIC'):
            raise ValueError('geometry provenance required')
        if not isinstance(config.get('source_id'), str) or not config['source_id']:
            raise ValueError('geometry source_id required')
        rows = config['microphones']
        if len(rows) != 4 or any(type(r['channel']) is not int for r in rows) or sorted(r['channel'] for r in rows) != list(range(4)):
            raise ValueError('exactly channels 0,1,2,3 required')
        xyz = np.array([finite_vector(r['xyz_mm']) for r in sorted(rows, key=lambda r: r['channel'])])
        self.sample_rate = positive(config['sample_rate_hz'])
        if not self.sample_rate.is_integer():
            raise ValueError('integer PCM sample rate required')
        self.speed = positive(config['sound_speed_m_s'])
        self._offsets = (xyz - xyz[0]) / 1000.0
        if not np.all(np.isfinite(self._offsets)):
            raise ValueError('geometry arithmetic overflow')
        singular = np.linalg.svd(self._offsets[1:], compute_uv=False)
        if singular[0] == 0 or singular[-1] <= singular[0] * 1e-6:
            raise ValueError('geometry must span three dimensions')
        self.max_delay_samples = float(np.max(np.linalg.norm(self._offsets, axis=1)) * self.sample_rate / self.speed)
        if not math.isfinite(self.max_delay_samples) or self.max_delay_samples > 8:
            raise ValueError('geometry/rate exceeds DAS +/-8 sample capacity')
        self.source_id, self.revision = config['source_id'], config['revision']

    def delays(self, direction):
        v = finite_vector(direction)
        # Scale first, avoiding overflow from an otherwise finite fitted vector.
        scale = float(np.max(np.abs(v)))
        if scale == 0:
            raise ValueError('zero direction')
        v = v / scale
        unit = v / np.linalg.norm(v)
        delays = self._offsets @ unit * self.sample_rate / self.speed
        return tuple(int(round(float(d) * Q)) for d in delays)


class TetraDAS:
    """One object per contiguous PCM session; discard/recreate after any gap.

    Call controls at chunk boundaries. Invalid solver results clear the target.
    Malformed controls raise ValueError: caller must stop processing or explicitly
    call fallback; they never silently extend the previous target's TTL.
    """
    def __init__(self, geometry, fade_samples=480):
        self.geometry = Geometry(geometry)
        self._core = DynamicDAS(fade_samples)

    @property
    def next_sample(self):
        return self._core.time

    def steer(self, direction, *, valid_through):
        """Manual/synthetic direction, expiry in physical PCM sample time."""
        delays = self.geometry.delays(direction)
        self._core.control(state='LOCKED', delays=delays, valid_through=valid_through)
        return delays

    def from_solver(self, result, *, valid_through):
        """Accept Solver3D.solve result, with explicit external time association.

        Undefined azimuth at a pole does not invalidate a valid 3D direction.
        Full geometry equality and PCM/frame association are caller obligations;
        source/revision checks detect accidental profile/config mixups.
        """
        if result.get('profile') != 'TETRA40_3D' or result.get('geometry_source') != self.geometry.source_id or result.get('geometry_revision') != self.geometry.revision:
            raise ValueError('solver geometry/profile mismatch')
        for name in ('bridge_status', 'api_status', 'direction_valid'):
            if type(result.get(name)) is not int:
                raise ValueError('missing/noninteger solver status')
        if result['direction_valid'] not in (0, 1):
            raise ValueError('invalid direction flag')
        if result['bridge_status'] != 0 or result['api_status'] != 0 or not result['direction_valid']:
            self.fallback()
            return None
        vector = finite_vector([result[k] for k in ('ux', 'uy', 'uz')])
        norm = positive(result['norm'])
        actual = math.hypot(*map(float, vector))
        if not math.isfinite(actual) or not math.isclose(actual, norm, rel_tol=1e-4, abs_tol=1e-7):
            raise ValueError('inconsistent solver vector/norm')
        return self.steer(vector, valid_through=valid_through)

    def hold(self):
        self._core.control(state='HOLD')

    def fallback(self):
        """Fade to mic0, not silence and not a hardware emergency stop."""
        self._core.control(state='SEARCH')

    def push(self, pcm, *, start_sample, final=False):
        if not integer(start_sample) or start_sample != self.next_sample:
            raise ValueError('PCM gap/reorder: start a new session')
        output, _ = self._core.push(pcm, final=final)
        # Reference core diagnostics are per-call, not a lifetime-growing log.
        self._core.events.clear()
        return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--geometry', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True, help='NPY integer S24 PCM, shape (4,N), channels 0..3')
    parser.add_argument('--output', type=Path, required=True, help='new mono 24-bit WAV')
    parser.add_argument('--direction', type=float, nargs=3, required=True, metavar=('X', 'Y', 'Z'))
    parser.add_argument('--chunk', type=int, default=1024)
    args = parser.parse_args()
    if args.chunk < 1:
        parser.error('--chunk must be positive')
    geometry = json.loads(args.geometry.read_text(encoding='utf-8'))
    das = TetraDAS(geometry)
    pcm = np.load(args.input, mmap_mode='r', allow_pickle=False)
    if pcm.ndim != 2 or pcm.shape[0] != 4 or pcm.shape[1] == 0 or not np.issubdtype(pcm.dtype, np.integer):
        raise ValueError('nonempty (4,N) integer PCM required')
    # Validate before creating output. Large recordings are checked in chunks.
    for start in range(0, pcm.shape[1], args.chunk):
        block = pcm[:, start:start+args.chunk]
        if np.any(block < -2**23) or np.any(block >= 2**23):
            raise ValueError('PCM exceeds signed 24-bit range')
    delay = das.steer(args.direction, valid_through=pcm.shape[1]+7)
    # Keep the 8-sample startup latency and EOF tail, matching streaming time.
    with args.output.open('xb') as destination:
        with wave.open(destination, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(3)
            wav.setframerate(int(das.geometry.sample_rate))
            for start in range(0, pcm.shape[1], args.chunk):
                end = min(start+args.chunk, pcm.shape[1])
                y = das.push(pcm[:, start:end], start_sample=start, final=end == pcm.shape[1])
                raw = y.astype('<i4').view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
                wav.writeframes(raw)
    print(json.dumps(dict(input_samples=pcm.shape[1], output_samples=pcm.shape[1]+8,
                          delays_q12=delay, geometry_source=das.geometry.source_id,
                          mode='OFFLINE_REFERENCE', latency_samples=8)))


if __name__ == '__main__':
    main()
