"""Fixed-size direction diagnostics, independent of voiceprint permission."""
import copy
import math

REASONS = ('VALID', 'PAIRS', 'SINGULAR', 'RESIDUAL', 'NORM', 'LEGACY_BIST',
           'CANCELLED', 'SOURCE', 'CONFIG', 'CONDITION')


def reason_name(code):
    return REASONS[code] if type(code) is int and 0 <= code < len(REASONS) else 'OTHER'


class DirectionDiagnostics:
    def __init__(self):
        self.data = dict(policy='CF1_PCM_GAPS_V1', frames=0, above_volume=0,
            raw_valid_above_volume=0, raw_hardware_qualified=0, bridged_gaps=0,
            completed_groups=0, accepted_groups=0, resets={}, output_reasons={},
            motion_reasons={}, by_solver_reason={})

    @staticmethod
    def count(table, key):
        # Unexpected text must never create an unbounded log/key dictionary.
        key = str(key)[:64]
        if key not in table and len(table) >= 24:
            key = 'OTHER'
        table[key] = table.get(key, 0)+1

    def accept(self, record, hardware_qualified):
        d = self.data
        frame, result = record['frame'], record['result']
        detail, out, volume = record['angle_filter'], record['direction_output'], record['volume']
        above = bool(volume['measured'] and volume['level_counts'] >= volume['threshold_counts'])
        d['frames'] += 1
        d['above_volume'] += int(above)
        d['raw_valid_above_volume'] += int(above and bool(result['direction_valid']))
        d['raw_hardware_qualified'] += int(hardware_qualified)
        d['bridged_gaps'] += int(detail.get('gap_bridged', False))
        d['completed_groups'] += int(detail['complete'])
        d['accepted_groups'] += int(out['valid'])
        if detail['reset_reason']:
            self.count(d['resets'], detail['reset_reason'])
        self.count(d['output_reasons'], out['reason'])
        self.count(d['motion_reasons'], record.get('motion', {}).get('reason', 'OFF'))
        key = reason_name(result['reason'])
        row = d['by_solver_reason'].setdefault(key, dict(count=0, above_volume=0,
            norm={}, residual_rms_samples={}, examples=[]))
        row['count'] += 1
        row['above_volume'] += int(above)
        if above:
            for name in ('norm', 'residual_rms_samples'):
                value = result.get(name)
                if type(value) in (int, float) and math.isfinite(value):
                    m = row[name]
                    m.update(count=m.get('count', 0)+1, total=m.get('total', 0.)+value,
                             minimum=min(m.get('minimum', value), value),
                             maximum=max(m.get('maximum', value), value))
            if len(row['examples']) < 2:
                row['examples'].append(dict(sequence=frame['sequence'], level=volume['level_counts'],
                    valid_pairs=result.get('valid_pairs'), norm=result.get('norm'),
                    residual_rms_samples=result.get('residual_rms_samples'),
                    hardware_qualified=bool(hardware_qualified)))

    def snapshot(self):
        return copy.deepcopy(self.data)
