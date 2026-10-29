"""Read a completed user 3-D project and archive its actual handoff; no EDA actions."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from zipfile import ZipFile, ZIP_DEFLATED

from package_pynq import horizontal_pins

ROOT = Path(__file__).resolve().parents[1]


def record(path):
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', type=Path, required=True)
    p.add_argument('--xsa', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    hw, out = a.project.resolve(), a.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    run = hw/(hw.name+'.runs')/'impl_1'
    old = json.loads((ROOT/'document/evidence/ps-dual-axis-20261028/user-build-receipt.json').read_text('utf-8'))
    artifacts = {k: record(Path(v['path'])) for k, v in old['artifacts'].items()}
    artifacts['xsa'] = record(a.xsa.resolve())
    with ZipFile(a.xsa) as z:
        assert z.testzip() is None
        for kind in ('bit', 'hwh'):
            names = [n for n in z.namelist() if n.endswith('.'+kind)]
            assert len(names) == 1
            assert z.read(names[0]) == Path(artifacts[kind]['path']).read_bytes(), 'XSA mismatch: '+kind
    registered, changed = [], []
    for item in old['registered_files']:
        f = Path(item['path']); r = record(f)
        r['fileset'] = item['fileset']
        if r['sha256'] != item['sha256']: changed.append(str(f))
        registered.append(r)
    expected = hw/'dual_axis_constraints/04/horizontal_reserved.xdc'
    old_xdc = next(r for r in old['registered_files'] if Path(r['path']) == expected)
    assert hashlib.sha256(expected.read_bytes().replace(b'PACKAGE_PIN W16', b'PACKAGE_PIN W15')).hexdigest() == old_xdc['sha256'], 'More than the pin assignment changed'
    # utils_1 holds generated checkpoints; only product source/constraint changes matter.
    product_changes = [r['path'] for r in registered if r['path'] in changed and r['fileset'] != 'utils_1']
    assert product_changes == [str(expected)], product_changes
    def active_xdc(path):
        return [s.strip() for s in path.read_text('utf-8-sig').splitlines()
                if s.strip() and not s.lstrip().startswith('#')]
    # Imported user's old comments may still name U7/Bank13; compare executed constraints.
    assert active_xdc(expected) == active_xdc(ROOT/'project/sdc/ps/horizontal_reserved.xdc')
    assert artifacts['bd']['sha256'] == old['artifacts']['bd']['sha256'], 'BD changed'
    assert artifacts['hwh']['sha256'] == old['artifacts']['hwh']['sha256'], 'HWH changed'
    reports = out/'original'; reports.mkdir(exist_ok=True)
    for suffix in ('timing_summary_routed', 'utilization_placed', 'io_placed', 'drc_routed', 'route_status'):
        matches = list(run.glob('soundsight_stm32_bd_wrapper_'+suffix+'.rpt'))
        if suffix != 'route_status': assert len(matches) == 1
        for f in matches: shutil.copy2(f, reports/f.name)
    io = horizontal_pins(next(reports.glob('*_io_placed.rpt')).read_text())
    export = hw/'handoff/latest'
    # Raw vendor export is preserved as evidence; not advertised as a standalone relocatable project.
    with ZipFile(out/'original-export.zip', 'w', ZIP_DEFLATED) as z:
        for f in sorted(export.iterdir()):
            if f.is_file(): z.write(f, f.name)
    body = (export/'soundsight_stm32_bd.tcl').read_text('utf-8-sig')
    body = body[body.index('proc create_root_design {'):body.index('# End of create_root_design()')]
    body = body.replace('proc create_root_design {', 'proc ss_create_ps_3d_export {', 1)
    # Keep this as an explicit, sourceable reference alongside the existing update recipe.
    assert 'F:/' not in body and 'E:/' not in body
    (ROOT/'project/bd/ps_3d_export.tcl').write_text(
        '# Actual user-exported 3-D PS/BD/IP configuration. Vivado 2025.2.\n'
        '# Define only; caller creates the BD and adds the repository RTL/FFT IP first.\n'+body+'\n', encoding='utf-8')
    receipt = dict(scope='User completed build, read-only receipt; W15 to W16 only in product inputs',
                   artifacts=artifacts, registered_files=registered, product_changes=product_changes,
                   servo_io=io, bd_and_hwh_unchanged=True, xsa_bit_hwh_equal=True,
                   board_w16='NOT_RUN', raw_export='original-export.zip',
                   raw_export_usage='Historical paths retained; not a standalone rebuild kit')
    (out/'user-build-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(product_changes=product_changes, io=io, xsa_match=True, output=str(out))))


if __name__ == '__main__':
    main()
