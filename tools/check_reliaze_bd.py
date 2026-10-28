"""Read-only audit of the saved before/after BD and copied candidate RTL."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--before', type=Path, required=True)
    ap.add_argument('--after', type=Path, required=True)
    ap.add_argument('--sources', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    a, b = [json.loads(p.read_text('utf-8'))['design'] for p in (args.before, args.after)]
    for key in ('ports', 'interface_ports'):
        assert a[key] == b[key], key
    changed = {'ps7', 'compute', 'ps_link', 'control_bus', 'irq_concat', 'irq_zero'}
    assert set(b['components']) - set(a['components']) == {'audio_capture', 'axi_dma_audio', 'audio_mem_bus'}
    for key, value in a['components'].items():
        if key not in changed:
            assert b['components'][key] == value, key
    ps_a, ps_b = [d['components']['ps7']['parameters'] for d in (a, b)]
    for key, value in ps_a.items():
        assert ps_b[key] == value, key
    assert ps_b['PCW_USE_S_AXI_HP0']['value'] == '1'
    assert ps_b['PCW_S_AXI_HP0_DATA_WIDTH']['value'] == '64'
    for key, value in a['interface_nets'].items():
        assert value == b['interface_nets'][key], key
    for key, value in a['nets'].items():
        old = set(value['ports'])
        if 'irq_zero/dout' in old:
            old.remove('irq_concat/In1')
            old.add('irq_concat/In2')
        assert old <= set(b['nets'][key]['ports']), key
    params = b['components']['axi_dma_audio']['parameters']
    expected = dict(c_include_sg=0, c_include_mm2s=0, c_include_s2mm=1,
                    c_include_s2mm_dre=0, c_micro_dma=0, c_sg_length_width=16,
                    c_s_axis_s2mm_tdata_width=32, c_m_axi_s2mm_data_width=64)
    for key, value in expected.items():
        assert int(params[key]['value']) == value, key
    segs = b['addressing']['/ps7']['address_spaces']['Data']['segments']
    for name, addr in [('ps_link_reg0', '0x40000000'), ('audio_capture_reg0', '0x43C00000'),
                       ('axi_dma_audio_Reg', '0x40400000')]:
        assert segs['SEG_'+name]['offset'] == addr, name
    for name in ('compute', 'ps_link'):
        assert b['components'][name]['parameters']['AUDIO_ENABLE']['value'] == '1'
    script = ROOT/'project/bd/update_ps_reliaze.tcl'
    names = re.search(r'variable names \{([^}]+)\}', script.read_text('utf-8')).group(1).split()
    hashes = {}
    for name in names:
        src = ROOT/'project/rtl'/name
        assert src.read_bytes() == (args.sources/name).read_bytes(), name
        hashes['project/rtl/'+name] = hashlib.sha256(src.read_bytes()).hexdigest()
    hashes['project/bd/update_ps_reliaze.tcl'] = hashlib.sha256(script.read_bytes()).hexdigest()
    report = dict(result='PASS', scope='saved BD and source audit only',
                  prior_explicit_ps_parameters_preserved=len(ps_a),
                  external_ports_preserved=True, original_interfaces_preserved=True,
                  original_nets_preserved_except_irq_zero_reposition=True,
                  unchanged_other_components=len(a['components'])-len(changed),
                  new_components=3, candidate_files=hashes,
                  synthesis='NOT_RUN', implementation='NOT_RUN', board='NOT_RUN')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print('RELIAZE_AUDIT_PASS', len(hashes), 'candidate files', args.output)


if __name__ == '__main__':
    main()
