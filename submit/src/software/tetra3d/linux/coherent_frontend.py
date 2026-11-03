"""CF1A: bounded causal PCM spectral frontend; original C geometry and motion gates.

One DMA owner supplies validated immutable packets. No MMIO, files, threads,
device allocation or direction normalization to bypass physical acceptance.
"""
from collections import OrderedDict, deque
from pathlib import Path
import time
import numpy as np

PAIRS = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
SCANS = (6, 8, 6, 6, 8, 6)


class CoherentSolver:
    requires_pcm = True

    def __init__(self, native, epoch, hann_path, clock=time.monotonic):
        self.native, self.epoch, self.clock = native, epoch, clock
        self.hann = np.array([int(s, 16) for s in Path(hann_path).read_text().split()], dtype=np.float64)/131072.
        if self.hann.shape != (1024,) or not np.isfinite(self.hann).all():
            raise ValueError('CF1 requires the packaged 1024-point Q17 Hann table')
        self.blocks = OrderedDict()
        self.history = deque()
        # Only bins 7..85 are used. Do not restack 16 full 513-bin arrays per solve.
        self.hits = np.zeros((6, 79), dtype=np.int16)
        self.phase_sum = np.zeros((6, 79), dtype=np.complex128)
        self.spectrum = np.zeros((6, 513), dtype=np.complex128)
        self.lags = [np.arange(-n, n+1) for n in SCANS]
        self.lag_indices = [v % 1024 for v in self.lags]
        self.last_packet = self.last_sequence = self.last_start = None
        self.previous_observation = None
        self.seen_start = None  # Anti-replay watermark survives history resets.
        self.source_completed_at = None
        self.capture_started_at = None
        # Optional acquisition-owner callback. It may receive PCM, but must not
        # invoke solve() or change the spectral history. No worker/thread owns DMA.
        self.service_capture = None
        self.stats = dict(revision='CF1A', packets=0, solved=0, valid=0, missing_pcm=0,
                          resets=0, clipped_windows=0, max_solve_seconds=0., max_blocks=0,
                          total_solve_seconds=0., spectral_windows=0, backfilled_windows=0,
                          max_windows_per_solve=0, snapshot_gaps=0)

    def started(self, when):
        if self.last_packet is not None or not np.isfinite(when):
            raise ValueError('CF1 start origin must precede all packets')
        self.capture_started_at = float(when)

    def accept_packet(self, data, meta):
        # The acquisition owner called decode_packet before this method.
        if (len(data) != 8224 or meta['epoch'] != self.epoch or
                meta['sample_count'] != 512 or meta['sample_start'] != meta['block_seq']*512 or
                self.last_packet is not None and meta['block_seq'] != self.last_packet+1):
            raise ValueError('CF1 PCM session/continuity mismatch')
        self.last_packet = meta['block_seq']
        self.blocks[meta['sample_start']] = (data[32:], self.clock(), bool(meta['clipped']))
        while len(self.blocks) > 64:
            self.blocks.popitem(last=False)
        self.stats['packets'] += 1
        self.stats['max_blocks'] = max(self.stats['max_blocks'], len(self.blocks))

    def reset_history(self):
        self.history.clear()
        self.hits.fill(0)
        self.phase_sum.fill(0)
        self.last_sequence = self.last_start = None
        self.stats['resets'] += 1

    def has_window(self, frame):
        a = frame.get('audio', {})
        start = a.get('sample_start')
        return bool(a.get('valid') and a.get('epoch') == self.epoch and
                    start in self.blocks and start+512 in self.blocks)

    def invalid(self, frame, reason):
        self.previous_observation = None
        self.reset_history()
        result = self.native.solve(dict(frame, words=[v for i in range(6)
            for v in ((i << 8) | (2 << 24) | (6 << 28), 0, 0, 0, 0)]))
        result.update(direction_valid=0, azimuth_valid=0, elevation_valid=0,
                      frontend='CF1A', cf1_reset=reason, source_completed_at=self.source_completed_at)
        return result

    def append_window(self, start, blocks=None):
        blocks = [self.blocks[start], self.blocks[start+512]] if blocks is None else blocks
        pcm = np.frombuffer(blocks[0][0]+blocks[1][0], dtype='<i4').reshape(1024, 4)
        ft = np.fft.rfft(np.rint(pcm*self.hann[:, None]), axis=0)[7:86]
        cross = np.array([ft[:, x]*ft[:, y].conj() for x, y in PAIRS])
        power = np.abs(cross)**2
        mask = (power > 0) & (2500*power >= power.max(axis=1, keepdims=True))
        phase = np.zeros(cross.shape, dtype=np.complex128)
        phase[mask] = cross[mask]/np.abs(cross[mask])
        if len(self.history) == 16:
            old_mask, old_phase = self.history.popleft()
            self.hits -= old_mask
            self.phase_sum -= old_phase
        self.history.append((mask, phase))
        self.hits += mask
        self.phase_sum += phase
        self.stats['spectral_windows'] += 1
        # Bound roundoff drift during continuous sessions; short band only.
        if self.stats['spectral_windows'] % 256 == 0:
            self.phase_sum[:] = np.sum([v[1] for v in self.history], axis=0)
        self.last_start = start

    def solve(self, frame):
        began = self.clock()
        self.source_completed_at = None
        a = frame.get('audio', {})
        if (not a.get('valid') or a.get('epoch') != self.epoch or a.get('sample_count') != 1024 or
                type(a.get('sample_start')) is not int or a['sample_start'] % 512):
            return self.invalid(frame, 'pcm_frame_unavailable')
        start = a['sample_start']
        if self.seen_start is not None and start <= self.seen_start:
            return self.invalid(frame, 'pcm_window_repeated_or_reversed')
        self.seen_start = start
        blocks = [self.blocks.get(start), self.blocks.get(start+512)]
        if any(b is None for b in blocks):
            self.stats['missing_pcm'] += 1
            return self.invalid(frame, 'pcm_window_not_received')
        self.source_completed_at = blocks[1][1]
        if self.capture_started_at is not None:
            # START is issued after this host origin. The predicted end is an
            # earlier bound, so queued DMA cannot make old samples look fresh.
            self.source_completed_at = min(self.source_completed_at,
                self.capture_started_at+(start+1024)/48000.)
        if any(b[2] for b in blocks):
            self.stats['clipped_windows'] += 1
            return self.invalid(frame, 'pcm_clipped')
        if self.clock()-self.source_completed_at >= .75:
            return self.invalid(frame, 'pcm_window_stale')
        # Evidence for the spatial filter, computed before cooperative receipt can
        # evict blocks. Only a bounded, complete, unclipped PCM interval qualifies.
        previous = self.previous_observation
        linked = False
        if previous is not None:
            old_start, old_sequence = previous
            advance = start-old_start
            seq_advance = (frame['sequence']-old_sequence) & 0xffffffff
            linked = (0 < advance <= 16*512 and 0 < seq_advance <= 16 and
                      all(pos in self.blocks and not self.blocks[pos][2]
                          for pos in range(old_start, start+1024, 512)))
        continuity = dict(policy='CF1_PCM_GAPS_V1', epoch=self.epoch,
            sample_start=start, sequence=frame['sequence'], verified=linked,
            previous_start=None if previous is None else previous[0],
            previous_sequence=None if previous is None else previous[1])
        if self.last_sequence is not None and frame['sequence'] != (self.last_sequence+1) & 0xffffffff:
            self.stats['snapshot_gaps'] += 1
        # A missing PL snapshot is not missing audio. Reconstruct only preceding
        # windows already present in the validated PCM ring; never invent a frame
        # or a motion command. The downstream filter checks continuity evidence before bridging a gap.
        first = 0 if self.last_start is None else self.last_start+512
        if start-first >= 16*512:
            self.reset_history()
            first = start-15*512
        steps = 0
        # Pin only this solve's <=17 immutable blocks. Cooperative DMA receipt
        # may evict the rolling ring while we compute, never this exact window.
        pinned = {pos: self.blocks.get(pos) for pos in range(first, start+1024, 512)}
        for pos in range(first, start+1, 512):
            if self.service_capture is not None:
                self.service_capture()
            left, right = pinned.get(pos), pinned.get(pos+512)
            if left is None or right is None or left[2] or right[2]:
                self.reset_history()
                continue
            self.append_window(pos, (left, right))
            steps += 1
        if self.service_capture is not None:
            self.service_capture()
        self.last_sequence = frame['sequence']
        self.stats['backfilled_windows'] += max(0, steps-1)
        self.stats['max_windows_per_solve'] = max(self.stats['max_windows_per_solve'], steps)
        concentration = np.abs(self.phase_sum)/np.maximum(self.hits, 1)
        keep = (self.hits >= 4) & (concentration >= .7)
        band = self.phase_sum/len(self.history)*concentration**2
        band[~keep] = 0
        self.spectrum[:, 7:86] = band
        counts = keep.sum(axis=1)
        corr = np.fft.irfft(self.spectrum, n=1024, axis=1)
        if self.service_capture is not None:
            self.service_capture()
        words = []
        for i in range(6):
            if counts[i] < 12:
                words.extend([(i << 8) | (2 << 24) | (6 << 28), 0, 0, 0, 0])
                continue
            lag = int(self.lags[i][np.argmax(corr[i, self.lag_indices[i]])])
            values = np.rint(corr[i, np.array([lag, lag-1, lag+1]) % 1024]*2**24).astype(np.int64)
            word = (lag & 255) | (i << 8) | (1 << 11) | (1 << 13) | (int(counts[i]) << 16) | (1 << 24) | (1 << 28)
            words.extend([word]+[int(v) & 0xffffffff for v in values]+[0])
        # Only the numerical bridge receives these software features. The original
        # hardware snapshot, sequence, raw admission bits and CONSUME stay intact.
        if self.service_capture is not None:
            self.service_capture()
        result = self.native.solve(dict(frame, words=words))
        if result['valid_pairs'] < 4:
            result.update(direction_valid=0, azimuth_valid=0, elevation_valid=0, reason=1)
        self.previous_observation = (start, frame['sequence'])
        result.update(frontend='CF1A', history_frames=len(self.history),
                      source_completed_at=self.source_completed_at, pcm_continuity=continuity)
        self.stats['solved'] += 1
        self.stats['valid'] += int(bool(result['direction_valid']))
        elapsed = self.clock()-began
        self.stats['max_solve_seconds'] = max(self.stats['max_solve_seconds'], elapsed)
        self.stats['total_solve_seconds'] += elapsed
        return result

    def summary(self):
        return dict(self.stats, buffered_blocks=len(self.blocks), history_frames=len(self.history),
                    mean_solve_seconds=self.stats['total_solve_seconds']/max(1, self.stats['solved']),
                    audio_support_ms=181.333333, nominal_history_center_extra_ms=80,
                    freshness_basis='conservative_start_plus_sample_end',
                    physical_gates_unchanged=True, board_latency_measured=False)
