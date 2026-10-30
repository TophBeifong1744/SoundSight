"""Analyze exported speaker session JSON without models, PYNQ or hardware."""
import argparse
import json
import math
from pathlib import Path
from statistics import mean
from zipfile import ZipFile


def analyze(archive):
    runs = []
    live_times = []
    with ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError('ZIP integrity failure')
        for name in sorted(z.namelist()):
            if not Path(name).name.startswith('speaker-3d-') or not name.endswith('.json'):
                continue
            d = json.loads(z.read(name))
            worker = d.get('speaker_worker', {})
            rows = worker.get('results', [])
            counts = worker.get('statistics', {})
            stop_at = d['at']
            threshold = d['settings']['speaker']['threshold']
            scored = [r for r in rows if type(r.get('score')) in (int, float)
                      and math.isfinite(r['score'])]
            live = [r for r in scored if r['completed_at'] <= stop_at]
            live_times.extend(r['compute_seconds'] for r in live)
            passed = [r for r in live if threshold is not None and r['score'] >= threshold]
            complete = len(scored) == counts.get('successful_calculations')
            if complete:
                assert sum(r['score'] >= threshold for r in scored) == counts['threshold_passes']
                assert abs(sum(r['compute_seconds'] for r in scored)-counts['total_compute_seconds']) < 1e-6
            runs.append(dict(log=name, result=d['result'], error=d.get('error'),
                elapsed_seconds=d['elapsed_seconds'], target=d['settings']['target_id'],
                threshold=threshold, ttl_seconds=d['settings']['speaker']['permit_seconds'],
                consumed=d['stats']['consumed'], motion_commits=d['stats']['motion_commits'],
                sequence_gaps=d['stats']['sequence_gaps'], runtime_fault_or=d['stats']['fault_or'],
                drops_delta=d['stats']['drops_last']-d['stats']['drops_first'],
                statistics=counts, all_scores_retained=complete,
                completed_before_stop=len(live), passed_before_stop=len(passed),
                completed_after_stop=len(scored)-len(live),
                pass_intervals_before_stop_seconds=[b['completed_at']-a['completed_at']
                    for a, b in zip(passed, passed[1:])],
                completion_intervals_before_stop_seconds=[b['completed_at']-a['completed_at']
                    for a, b in zip(live, live[1:])],
                successful_source_ages_seconds=[r['source_age_seconds'] for r in scored]))
    if not runs or not live_times:
        raise ValueError('No completed live inference records')
    worst = max(live_times)
    # Explicit engineering choice: tolerate one unsuccessful round, then add 20%
    # scheduling margin and round up to a two-second setting. Not a confidence bound.
    budget = 2*worst*1.2
    ttl = math.ceil(budget/2)*2
    return dict(runs=runs, live_compute_count=len(live_times),
                live_compute_mean_seconds=mean(live_times), live_compute_max_seconds=worst,
                design_assumption='one nonpassing inference between passes, 20% margin, 2-second rounding',
                calculated_budget_seconds=budget, recommended_trial_ttl_seconds=ttl,
                limitation='Small same-target sample; speech pauses and repeated low scores can exceed TTL. '
                           'No identity accuracy or hard real-time guarantee; post-STOP results excluded from timing budget.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = analyze(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
