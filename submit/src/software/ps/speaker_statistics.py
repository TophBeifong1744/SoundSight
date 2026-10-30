"""Opt-in, constant-space inference counters and end-of-session reporting.

Only the inference thread updates counters. No file IO, clock reads, locks or
per-result messages are added to capture; persistence happens after hardware STOP.
"""
import json
import math
import os
from pathlib import Path
import tempfile

LAST_FILE = 'speaker-last-stats.json'


class SpeakerStatistics:
    def __init__(self, threshold):
        self.threshold = threshold
        self.count = self.passes = 0
        self.total = self.maximum = 0.

    def observe(self, score, seconds):
        """Count a completed numeric inference, regardless of its match outcome."""
        if (type(score) not in (int, float) or not math.isfinite(score) or not -1 <= score <= 1 or
                type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0):
            return
        self.count += 1
        self.total += seconds
        self.maximum = max(self.maximum, seconds)
        self.passes += self.threshold is not None and score >= self.threshold

    def snapshot(self):
        return dict(enabled=True, threshold=self.threshold, successful_calculations=self.count,
                    threshold_passes=None if self.threshold is None else self.passes,
                    total_compute_seconds=self.total,
                    average_compute_seconds=self.total/self.count if self.count else None,
                    max_compute_seconds=self.maximum if self.count else None,
                    scope='all_successful_numeric_inferences_in_session',
                    meaning='Scores meeting threshold, not servo movements or permission refreshes')


def save_last(root, report, report_path, enabled):
    """Save one small summary after the main session report has been saved."""
    root = Path(root)
    value = dict(schema=1, enabled=bool(enabled), available=False,
                 report=Path(report_path).relative_to(root).as_posix(),
                 session_result=report.get('result'), error=report.get('error'),
                 target_id=report.get('settings', {}).get('target_id'), statistics=None)
    stats = report.get('speaker_worker', {}).get('statistics')
    if enabled and isinstance(stats, dict) and stats.get('enabled') is True:
        value.update(available=True, statistics=stats)
    logs = root/'logs'
    logs.mkdir(exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.speaker-stats-', dir=str(logs))
    try:
        with os.fdopen(fd, 'w', encoding='ascii') as stream:
            json.dump(value, stream, ensure_ascii=True, allow_nan=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, logs/LAST_FILE)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return value


def show_last(root):
    """Read the last saved session, even if board wall-clock time moved backward."""
    path = Path(root)/'logs'/LAST_FILE
    if not path.exists():
        print('SPEAKER_STATS=NO_SAVED_SESSION HELP=run speaker with --speaker-stats')
        return
    value = json.loads(path.read_text(encoding='ascii'))
    print('SPEAKER_STATS='+json.dumps(value, ensure_ascii=True, allow_nan=False))
    if not value['enabled']:
        print('STATS_DISABLED_FOR_LAST_SESSION ENABLE_WITH=--speaker-stats')
    elif not value['available']:
        print('STATS_UNAVAILABLE: worker summary was not received; no zero-count claim')
    else:
        stats = value['statistics']
        def number(x):
            return 'N/A' if x is None else '%.6f' % x
        print('SUCCESSFUL=%s PASSED=%s AVG_SECONDS=%s MAX_SECONDS=%s' % (
            stats['successful_calculations'],
            'N/A' if stats['threshold_passes'] is None else stats['threshold_passes'],
            number(stats['average_compute_seconds']), number(stats['max_compute_seconds'])))
