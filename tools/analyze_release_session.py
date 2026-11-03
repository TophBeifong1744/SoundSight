"""Extract report metrics from an existing board summary; never access hardware."""
import argparse
import csv
import json
from pathlib import Path


def analyze(report):
    stats = report['stats']
    worker = report['speaker_worker']
    result = {
        'result': report['result'], 'stop_reason': report['stop_reason'],
        'elapsed_seconds': report['elapsed_seconds'],
        'elapsed_minutes': report['elapsed_seconds'] / 60,
        'axes': report['settings']['axes'],
        'target_id': report['settings']['target_id'],
        'level_threshold': report['settings']['min_level'],
        'window_frames': report['settings']['window_frames'],
        'min_valid': report['settings']['min_valid'],
        'speaker_threshold': report['settings']['speaker']['threshold'],
        'permit_seconds': report['settings']['speaker']['permit_seconds'],
        'pcm_packets': report['packets'],
        'pcm_tail_packets': report['tail_packets'],
        'snapshot_consumed': stats['consumed'],
        'snapshot_tail_drained': stats['drained'],
        'snapshot_drop_counter_delta': stats['drops_last'] - stats['drops_first'],
        'snapshot_sequence_gap_events': stats['sequence_gaps'],
        'raw_valid': stats['raw_valid'],
        'accepted_windows': stats['accepted_windows'],
        'motion_commits': stats['motion_commits'],
        'running_fault_or': stats['fault_or'],
        'first_fault': report['first_fault'],
        'cleanup_errors': report['cleanup_errors'],
        'stop_fault': report['hardware']['fault'],
        'stop_audio_errors': report['hardware']['audio']['errors'],
        'worker_status': worker['status'],
        'worker_jobs_consumed': worker['consumed'],
        'permission_results': report['speaker_permission']['results'],
        'retained_score_records': len(worker.get('results', [])),
        'whole_session_speaker_statistics_enabled': report['settings']['speaker_statistics_enabled'],
        'policy': report['direction_diagnostics']['policy'],
        'capture_revision': report['capture_service']['revision'],
        'snapshot_semantics': 'Latest-result replacement counter; not PCM packet loss or zero-loss capture.',
        'motion_semantics': 'Accepted software commands, not measured mechanical arrival.',
        'source': 'original/speaker-3d-20211119-121119-401147.json',
    }
    assert result['elapsed_seconds'] > 0
    assert sum(report['solver_reasons'].values()) == result['snapshot_consumed']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = analyze(json.loads(args.report.read_text('utf-8')))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'analysis.json').write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
    with (args.output/'metrics.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle); writer.writerow(['metric', 'value'])
        writer.writerows((k, json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in value.items())
    print(json.dumps(value))


if __name__ == '__main__':
    main()
