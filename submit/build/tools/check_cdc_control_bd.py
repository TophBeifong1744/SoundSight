"""Audit the existing PCM BD upgrade: exactly two control-net migrations."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence', type=Path, required=True)
    ap.add_argument('--sources', type=Path, required=True)
    args = ap.parse_args()
    folder = args.evidence
    a, b, c = [json.loads((folder/n).read_text('utf-8'))['design']
               for n in ('before.bd', 'after-first.bd', 'after-repeat.bd')]
    assert b == c, 'Repeat update changed BD'
    expected = copy.deepcopy(a)
    comp = expected['components']['compute']['ports']
    comp.update(audio_run={'direction': 'O'}, audio_draining={'direction': 'O'})
    audio = expected['components']['audio_capture']['ports']
    for old, new in [('run_enable_async', 'run_enable'),
                     ('compute_draining_async', 'compute_draining')]:
        audio[new] = audio.pop(old)
    for net, sink, new_net, source, new_sink in [
        ('ps_link_run_enable', 'audio_capture/run_enable_async', 'compute_audio_run',
         'compute/audio_run', 'audio_capture/run_enable'),
        ('compute_draining', 'audio_capture/compute_draining_async', 'compute_audio_draining',
         'compute/audio_draining', 'audio_capture/compute_draining')]:
        expected['nets'][net]['ports'].remove(sink)
        expected['nets'][new_net] = {'ports': [source, new_sink]}
    # Vivado serializes previously implicit defaults. Every explicit original
    # PS value must remain identical; effective HWH values are checked below.
    old_ps = a['components']['ps7']['parameters']
    new_ps = b['components']['ps7']['parameters']
    assert all(new_ps[k] == v for k, v in old_ps.items())
    expected['components']['ps7']['parameters'] = new_ps
    assert expected == b, 'Unexpected BD change outside the two control paths'
    ps = json.loads((folder/'ps-parameters.json').read_text('utf-8'))
    allowed = {'PCW_FTM_CTI_'+d+str(i) for d in ('IN', 'OUT') for i in range(4)}
    diffs = {k: [ps['before'].get(k), ps['after'].get(k)]
             for k in ps['before'].keys() | ps['after'].keys()
             if ps['before'].get(k) != ps['after'].get(k)}
    assert set(diffs) <= allowed
    assert all(v == ['DISABLED', '<Select>'] for v in diffs.values())
    for p in ('before', 'after'):
        assert ps[p]['PCW_USE_CROSS_TRIGGER'] == '0'
        assert all(ps[p]['PCW_EN_CLKTRIG'+str(i)+'_PORT'] == '0' for i in range(4))
    entry = ROOT/'project/bd/update_ps_reliaze.tcl'
    names = re.search(r'variable names \{([^}]+)\}', entry.read_text('utf-8')).group(1).split()
    hashes = {'project/bd/update_ps_reliaze.tcl': hashlib.sha256(entry.read_bytes()).hexdigest()}
    for name in names:
        src = ROOT/'project/rtl'/name
        assert src.read_bytes() == (args.sources/name).read_bytes(), name
        hashes['project/rtl/'+name] = hashlib.sha256(src.read_bytes()).hexdigest()
    report = dict(result='PASS', scope='saved BD, HWH parameters and copied RTL only',
                  migrated_control_nets=2, added_ips=0, repeat_identical=True,
                  other_bd_fields_preserved=True, explicit_ps_parameters_preserved=len(old_ps),
                  effective_ps_parameters_equal=len(ps['before'])-len(diffs),
                  disabled_cross_trigger_selector_normalization=diffs,
                  candidate_files=hashes, synthesis='NOT_RUN', implementation='NOT_RUN',
                  routed_cdc='NOT_RUN', board='NOT_RUN')
    (folder/'bd-audit.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print('CDC_CONTROL_BD_AUDIT_PASS: two nets, zero new IPs, repeat identical')


if __name__ == '__main__':
    main()
