"""Package the single Reliaze Tcl entry and its exact RTL dependencies. No EDA."""
import hashlib
import argparse
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cdc', action='store_true', help='Create a separate CDC repair package; preserve old ZIPs')
    args = ap.parse_args()
    entry = 'project/bd/update_ps_reliaze.tcl'
    text = (ROOT/entry).read_text('utf-8')
    names = re.search(r'variable names \{([^}]+)\}', text).group(1).split()
    assert all(re.fullmatch(r'[A-Za-z0-9_]+\.(sv|v)', n) for n in names)
    assert len(names) == len(set(names))
    paths = [entry, *('project/rtl/'+n for n in names), 'document/ps-pcm-integration.md',
             'document/evidence/ps-pcm-integration-20261024/README.md']
    evidence = 'document/evidence/ps-pcm-integration-20261024'
    if args.cdc:
        evidence = 'document/evidence/ps-cdc-control-fix-20261024'
        paths = [entry, *('project/rtl/'+n for n in names), 'document/ps-cdc-control-fix.md',
                 evidence+'/README.md', evidence+'/bd-audit.json', evidence+'/validation.json']
    payload = {name: (ROOT/name).read_bytes() for name in paths}
    audit = json.loads((ROOT/evidence/'bd-audit.json').read_text('utf-8'))
    if args.cdc:
        validation = json.loads((ROOT/evidence/'validation.json').read_text('utf-8'))
        assert audit['result'] == validation['result'] == 'PASS'
        assert validation['candidate_files'] == audit['candidate_files']
        assert validation['rtl_simulations_passed'] == 6
        assert validation['canary_expected_failures_detected'] == 2
    for path, digest in audit['candidate_files'].items():
        assert hashlib.sha256(payload[path]).hexdigest() == digest, 'Candidate changed after audit: '+path
    payload['manifest.json'] = (json.dumps({name: hashlib.sha256(data).hexdigest()
                                for name, data in payload.items()}, indent=2)+'\n').encode()
    payload['README.txt'] = (
        'SoundSight Reliaze update: manual calibration + four-mic PCM DMA\n'
        'Extract the COMPLETE folder. Open your existing SoundSight_PS_Reliaze.xpr in Vivado 2025.2.\n'
        'In Tcl Console, source the extracted project/bd/update_ps_reliaze.tcl by its full path.\n'
        'Do not first run update_ps_manual.tcl; its changes are included.\n'
        'Backups are created inside the working project under handoff/before_pcm_*.\n'
        'No synthesis, implementation, bitstream or board actions are launched.\n'
        'This package contains NO new bitstream and NO board acceptance claim.\n'
        'See document/ps-pcm-integration.md for protocol, controls and remaining validation.\n'
    ).encode()
    output = ROOT/'release/output/soundsight_reliaze_update.zip'
    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = 'SoundSight_Reliaze_Update/'
    if args.cdc:
        output = output.with_name('soundsight_reliaze_cdc_update.zip')
        prefix = 'SoundSight_Reliaze_CDC_Update/'
        payload['README.txt'] = (
            'SoundSight Reliaze CDC control repair, Vivado 2025.2\n'
            'Extract the COMPLETE folder. Open SoundSight_PS_Reliaze.xpr.\n'
            'Source project/bd/update_ps_reliaze.tcl from this extracted package.\n'
            'Do not run the old manual/PCM update first.\n'
            'Backups: working project/handoff/before_pcm_*.\n'
            'Only preparation/BD validation/output generation; no physical build or board actions.\n'
            'No bit/HWH supplied. User must rebuild and inspect routed CDC/timing reports.\n'
            'Read document/ps-cdc-control-fix.md for instructions and test boundaries.\n'
        ).encode()
        payload['manifest.json'] = (json.dumps({name: hashlib.sha256(data).hexdigest()
                                    for name, data in payload.items() if name != 'manifest.json'},
                                    indent=2)+'\n').encode()
    with zipfile.ZipFile(output, 'x' if args.cdc else 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in payload.items():
            z.writestr(prefix+name, data)
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == len(payload)
        for name, data in payload.items():
            assert z.read(prefix+name) == data, name
    print('RELIAZE_PACKAGE_PASS', len(payload), 'files', output)


if __name__ == '__main__':
    main()
