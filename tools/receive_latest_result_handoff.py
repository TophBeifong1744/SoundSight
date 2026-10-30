"""Receive the user's LAT1 build without opening Vivado or touching hardware."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', type=Path, required=True)
    p.add_argument('--xsa', type=Path, required=True)
    a = p.parse_args()
    project = a.project.resolve()
    handoff = project/'handoff/latest'
    out = ROOT/'project/reports/ps_3d/latest_result'
    assets = ROOT/'release/output/ps_3d_latest_result'
    run = project/(project.name+'.runs')/'impl_1'
    inputs = []; comment_differences = []
    for rel in (handoff/'source_files.txt').read_text('utf-8').splitlines():
        f = handoff/rel
        f.resolve().relative_to(handoff)
        raw = f.read_bytes()
        origin = project/Path(rel).relative_to('payload')
        assert origin.read_bytes() == raw, 'Export differs from installed source: '+rel
        if f.parent.name == 'dual_axis_sources':
            repo = ROOT/'project/rtl'/f.name
            repo_text, actual_text = repo.read_text('utf-8-sig'), f.read_text('utf-8-sig')
            if repo_text != actual_text:
                assert f.name == 'bd_ps_link.v' and repo_text.replace('垂直W16', '垂直W15') == actual_text, 'Repository source mismatch: '+f.name
                comment_differences.append(dict(file=f.name, detail='Installed comment says W15; routed I/O and repository comment correctly say W16; logic unchanged'))
        inputs.append(dict(path=rel, bytes=len(raw), sha256=digest(raw)))
    assert len([r for r in inputs if '/dual_axis_sources/' in r['path']]) == 32
    for name in ('ss_snapshot_queue.sv','ss_ps_control_regs.sv'):
        raw = (project/'dual_axis_sources'/name).read_bytes()
        assert digest(raw) == digest((ROOT/'project/rtl'/name).read_bytes()), name
    assert b"32'h4c415431" in (project/'dual_axis_sources/ss_ps_control_regs.sv').read_bytes()
    bit = next(run.glob('*.bit'))
    hwhs = list((project/(project.name+'.gen')).glob('sources_1/bd/*/hw_handoff/*.hwh'))
    assert len(hwhs) == 1
    hwh = hwhs[0]
    with ZipFile(a.xsa) as z:
        assert z.testzip() is None
        for suffix, local in (('.bit', bit), ('.hwh', hwh)):
            names = [n for n in z.namelist() if n.endswith(suffix)]
            assert len(names) == 1 and z.read(names[0]) == local.read_bytes(), 'XSA mismatch: '+suffix
    timing = next(run.glob('*_timing_summary_routed.rpt'))
    text = timing.read_text('utf-8')
    match = re.search(r'^\s*WNS\(ns\).*\n\s*-+.*\n\s*([^\n]+)', text, re.M)
    values = match[1].split()
    wns, whs, wpws = (float(values[i]) for i in (0,4,8))
    assert min(wns,whs,wpws) >= 0 and all(int(values[i]) == 0 for i in (2,6,10))
    missing_output = int(re.search(r'checking no_output_delay \((\d+)\)',text)[1])
    io = next(run.glob('*_io_placed.rpt')).read_text('utf-8')
    for pin, port in (('T15','servo_pwm'),('W16','servo_vertical_pwm')):
        assert re.search(r'\|\s*'+pin+r'\s*\|\s*'+port+r'\s*\|[^\n]*LVCMOS33',io)
    drc = next(run.glob('*_drc_routed.rpt')).read_text('utf-8')
    assert not re.search(r'\|\s*(Error|Critical Warning)\s*\|', drc)
    # Require installed input timestamps to precede the implementation report;
    # this complements, but does not replace, same-build provenance.
    assert all((project/Path(r['path']).relative_to('payload')).stat().st_mtime <= timing.stat().st_mtime
               for r in inputs if '/dual_axis_sources/' in r['path'])
    out.mkdir(parents=True, exist_ok=True);assets.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    for kind, path in (('bit',bit),('hwh',hwh),('xsa',a.xsa)):
        target = assets/('soundsight.'+kind)
        shutil.copy2(path,target)
        artifacts[kind] = dict(path=target.relative_to(ROOT).as_posix(), bytes=target.stat().st_size,
                               sha256=digest(target.read_bytes()))
    original = out/'original';original.mkdir(exist_ok=True)
    for suffix in ('timing_summary_routed','utilization_placed','io_placed','drc_routed','route_status'):
        for report in run.glob('*_'+suffix+'.rpt'):shutil.copy2(report,original/report.name)
    with ZipFile(out/'handoff.zip','w',ZIP_DEFLATED) as z:
        for f in sorted(handoff.rglob('*')):
            if f.is_file():z.write(f,f.relative_to(handoff).as_posix())
    review = dict(result='SCOPED_PASS', scope='User routed timing and XSA/source receipt; initial axes-off board retest',
                  wns_ns=wns, whs_ns=whs, wpws_ns=wpws, no_output_delay=missing_output,
                  horizontal_pin='T15',vertical_pin='W16',latest_result_cap='0x4c415431',
                  hardware_board_test='NOT_RUN', cdc_new_report='NOT_EXPORTED',
                  warnings='DRC/methodology warnings remain; one output delay missing; old supplemental STA not reused',
                  independent_design_signoff=False)
    receipt = dict(scope='User-generated LAT1 candidate; no AI synthesis/implementation/download',
                   artifacts=artifacts, registered_files=inputs, xsa_bit_hwh_equal=True,
                   repository_product_logic_equal=True, comment_differences=comment_differences, handoff='handoff.zip')
    (out/'user-build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    (out/'hardware-review.json').write_text(json.dumps(review,indent=2)+'\n',encoding='utf-8')
    (out/'audit_status.txt').write_text('LAT1_SOURCE_MATCH=1\nXSA_BIT_HWH_EQUAL=1\nROUTED_TIMING_MET=1\n'
                                     'NO_OUTPUT_DELAY_COUNT='+str(missing_output)+'\nBOARD_RETEST_NOT_RUN=1\n',encoding='utf-8')
    print(json.dumps(dict(inputs=len(inputs),review=review,hardware_actions=0)))


if __name__ == '__main__':
    main()
