"""Package current PYNQ software with a user's matching bit/HWH and XSA.

Only reads the external hardware project. Does not start Vivado or board actions.
Tool locations and workspaces are arguments, not public machine-specific defaults.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def one(paths, label):
    paths = list(paths)
    if len(paths) != 1:
        raise ValueError("Expected one %s, found %s" % (label, paths))
    return paths[0]


def horizontal_pins(report):
    """Check placed I/O, not a possibly unused/stale source XDC copy."""
    found = {}
    for line in report.splitlines():
        cols = [s.strip() for s in line.split('|')]
        if len(cols) > 7 and cols[2] in ('servo_pwm', 'servo_vertical_pwm'):
            if cols[2] in found:
                raise ValueError('Duplicate servo port in I/O report')
            found[cols[2]] = dict(pin=cols[1], standard=cols[6], bank=cols[7])
    expected = {'servo_pwm': dict(pin='T15', standard='LVCMOS33', bank='34'),
                'servo_vertical_pwm': dict(pin='W15', standard='LVCMOS33', bank='34')}
    if found != expected:
        raise ValueError('Placed servo pins do not match T15/W15: '+str(found))
    return found


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hardware-project", type=Path, required=True)
    p.add_argument("--xsa", type=Path, required=True)
    p.add_argument("--volume", action="store_true", help="Volume ABI, separate board directory and matching instructions")
    p.add_argument("--horizontal", action="store_true", help="Horizontal-capable hardware; motion remains explicitly opt-in")
    p.add_argument("--manual-calibration", action="store_true", help="Require the independent no-audio manual controller in the current implementation")
    p.add_argument("--pcm", action="store_true", help="Separate PCM diagnostic package; preserves the Servo package")
    p.add_argument("--pcm-cdc", action="store_true", help="Verified CDC control repair; separate package and board directory")
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if args.pcm_cdc:
        args.pcm = True
    if args.pcm:
        args.horizontal = args.manual_calibration = True
    if args.manual_calibration and not args.horizontal:
        p.error("--manual-calibration requires --horizontal")
    if args.horizontal:
        args.volume = True
    if args.output is None:
        args.output = ROOT / 'release/output' / ('soundsight_pynq_pcm.zip' if args.pcm else 'soundsight_pynq_servo.zip' if args.horizontal else 'soundsight_pynq_volume.zip' if args.volume else 'soundsight_pynq.zip')
        if args.pcm_cdc:
            args.output = ROOT/'release/output/soundsight_pynq_pcm_cdc.zip'
    board_dir = 'SoundSight_PYNQ_PCM' if args.pcm else 'SoundSight_PYNQ_Servo' if args.horizontal else 'SoundSight_PYNQ_Volume' if args.volume else 'SoundSight_PYNQ'
    if args.pcm_cdc:
        board_dir = 'SoundSight_PYNQ_PCM_CDC'
    hw = args.hardware_project.resolve()
    bit = one(hw.glob("*.runs/impl_1/*.bit"), "implemented bit")
    hwh = one(hw.glob("*.gen/sources_1/bd/*/hw_handoff/*.hwh"), "BD HWH")
    with zipfile.ZipFile(args.xsa) as xsa:
        embedded_bit = one((n for n in xsa.namelist() if n.endswith(".bit")), "XSA bit")
        embedded_hwh = one((n for n in xsa.namelist() if n.endswith(".hwh")), "XSA HWH")
        if xsa.read(embedded_bit) != bit.read_bytes() or xsa.read(embedded_hwh) != hwh.read_bytes():
            raise ValueError("External bit/HWH do not match the supplied XSA; do not mix builds.")
    manual_sources = []
    if args.manual_calibration:
        # Inspect registered imports, not stale source copies beside the project.
        xpr = one(hw.glob('*.xpr'), 'project file')
        project_tree = ET.parse(xpr)
        for name in ('ss_manual_servo.sv', 'ss_ps_control_regs.sv'):
            raw = one((f.get('Path') for fs in project_tree.iter('FileSet')
                       if fs.get('Name') == 'sources_1' for f in fs.iter('File')
                       if f.get('Path', '').replace('\\', '/').split('/')[-1] == name), name)
            actual = Path(raw.replace('$PSRCDIR', str(hw/(xpr.stem+'.srcs')))
                          .replace('$PPRDIR', str(hw)))
            if actual.read_bytes() != (ROOT/'project/rtl'/name).read_bytes():
                raise ValueError('Manual RTL differs from tested candidate: '+name)
            if actual.stat().st_mtime > bit.stat().st_mtime:
                raise ValueError('Manual RTL changed after bit generation: '+name)
            manual_sources.append(name)
        routed = bit.with_name(bit.stem+'_timing_summary_routed.rpt').read_text(encoding='utf-8')
        if '/manual/' not in routed or 'All user specified timing constraints are met.' not in routed:
            raise ValueError('Missing implemented manual hierarchy or passing routed timing')
    tree = ET.parse(hwh)
    module = one((m for m in tree.iter("MODULE") if m.get("INSTANCE") == "ps_link"
                  and m.get("MODTYPE") == "bd_ps_link"), "ps_link")
    params = {x.get("NAME"): x.get("VALUE") for x in module.iter("PARAMETER")}
    if args.horizontal:
        import sys
        sys.path.insert(0, str(ROOT / 'software/ps'))
        from horizontal_motion import check_hwh
        check_hwh(hwh)
        io_report = bit.with_name(bit.stem + '_io_placed.rpt')
        pins = horizontal_pins(io_report.read_text(encoding='utf-8'))
    elif params.get("ACTUATOR_BOUND") != "0":
        raise ValueError("This first-run package is for the no-motion hardware candidate.")
    if args.volume:
        compute = one((m for m in tree.iter('MODULE') if m.get('INSTANCE') == 'compute'
                       and m.get('MODTYPE') == 'bd_clean_compute'), 'compute')
        compute_params = {x.get('NAME'): x.get('VALUE') for x in compute.iter('PARAMETER')}
        if params.get('LEVEL_ENABLE') != '1' or compute_params.get('LEVEL_ENABLE') != '1':
            raise ValueError('Volume package requires LEVEL_ENABLE=1 in both modules.')
    software = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    source = dict(software_git=software, pr15="61e7303331641ec2353f89088b060aa81ffd6110",
                  pr16="0d388586af1dcd0355a2ab9d51360d4a9fb249cf",
                  hardware_project_name=hw.name, original_bit=bit.name,
                  original_hwh=hwh.name, xsa_byte_match=True,
                  bit_bytes=bit.stat().st_size, hwh_bytes=hwh.stat().st_size,
                  actuator_bound=int(args.horizontal), target_arm="NOT_RUN", board="NOT_RUN")
    source['software_source'] = 'current working tree; git value is the base commit'
    source['software_worktree_status'] = subprocess.check_output(
        ['git', 'status', '--porcelain', '--', 'software', 'tools/package_pynq.py'],
        cwd=ROOT, text=True).splitlines()
    source['board_directory'] = board_dir
    if args.volume:
        source.update(level_enable=1, expected_abi='0x00010001',
                      threshold='explicit PS argument; 1000 is an uncalibrated trial value',
                      online_angle_filter=True, angle_filter_activation='--angle-filter --min-level N',
                      angle_filter_parameters=dict(window=20, min_valid=12, radius_deg=10,
                                                   consensus='2/3', deadband_deg=3), servo_motion=False)
    entries = {}
    # An allowlist excludes compiler outputs, user logs and Windows executables.
    for folder, extensions in [
        ("software/common", {".c", ".h", ".md", ".txt"}),
        ("software/ps", {".c", ".py", ".sh", ".txt"}),
    ]:
        for f in (ROOT / folder).rglob("*"):
            if f.is_file() and f.suffix in extensions and "build" not in f.relative_to(ROOT).parts:
                entries[f.relative_to(ROOT).as_posix()] = f
    for name in [
        "software/tests/test_solver_migration.py",
        "software/tests/solver_migration_reference.c",
        "software/tests/test_smp.py",
        "software/tests/test_buffered.py",
        "software/tests/test_application.py",
        "document/evidence/ps-solver-migration-20261020/PC-RESULT.json",
        "document/evidence/inherited/ps/bd_preparation/interface.hwh",
        "tools/pynq_preflight.py",
        "tools/tool_config.py",
        "document/pynq-ram-queue.md",
        "LICENSE",
    ]:
        entries[name] = ROOT / name
    entries["README.md"] = ROOT / "document/pynq-first-run.md"
    if args.volume:
        entries['README.md'] = ROOT / 'document/pynq-volume-sd.md'
        entries['document/ps-volume-gate.md'] = ROOT / 'document/ps-volume-gate.md'
        entries['software/tests/test_volume_gate.py'] = ROOT / 'software/tests/test_volume_gate.py'
        entries['software/tests/test_online_angle_filter.py'] = ROOT / 'software/tests/test_online_angle_filter.py'
        entries['document/pynq-online-angle-filter.md'] = ROOT / 'document/pynq-online-angle-filter.md'
    if args.horizontal:
        from package_normal_update import TESTS
        for name in TESTS:
            entries['software/tests/' + name] = ROOT / 'software/tests' / name
        for name in ('soundsight.sh', 'tools/install_normal_update.py',
                     'document/pynq-horizontal.md', 'document/pynq-horizontal-sd.md',
                     'document/ps-manual-calibration.md', 'document/pynq-manual-status-fix.md',
                     'document/pynq-board-helper.md', 'document/pynq-normal-mode.md'):
            entries[name] = ROOT / name
        entries['README.md'] = ROOT / 'document/pynq-horizontal-sd.md'
        entries['reports/' + io_report.name] = io_report
        source.update(motion_default=False, motion_activation='soundsight.sh run normal --horizontal-motion',
                      actual_servo_io=pins,
                      calibration='horizontal.local.json; user must configure; not supplied',
                      threshold='settings.local.json or runtime default 7000; must be tuned on board',
                      mounting='fixed microphone array; configurable pivot XY cm; optional user-supplied horizontal range',
                      angle_filter_activation='normal mode includes volume gate and angle filter',
                      servo_motion='NOT_RUN; hardware capable, software default off')
    if args.manual_calibration:
        source.update(manual_calibration=True, manual_capability='0x4d534301',
                      manual_activation='soundsight.sh servo-angle DEG --seconds N',
                      manual_audio_required=False, manual_lease_ms=750,
                      manual_registered_sources_match=manual_sources)
    entries["soundsight.bit"] = bit
    entries["soundsight.hwh"] = hwh
    source['hardware_identity'] = {name: hashlib.sha256(path.read_bytes()).hexdigest()
                                   for name, path in [('bit_sha256', bit), ('hwh_sha256', hwh),
                                                      ('xsa_sha256', args.xsa)]}
    if args.pcm:
        from pcm_capture import check_hwh as check_pcm_hwh
        check_pcm_hwh(hwh)
        # Bind all delivered PCM RTL to the previously simulated candidate.
        audit_path = ROOT/'document/evidence/ps-pcm-integration-20261024/bd-audit.json'
        report_dir = ROOT/'document/evidence/ps-pcm-board-package-20261024/reports'
        pcm_readme = 'document/pynq-pcm-first-run.md'
        if args.pcm_cdc:
            evidence = ROOT/'document/evidence/ps-cdc-control-fix-20261024'
            audit_path = evidence/'bd-audit.json'
            report_dir = evidence/'board-package/reports'
            pcm_readme = 'document/pynq-pcm-cdc-first-run.md'
            review_path = evidence/'board-package/hardware-review.json'
            review = json.loads(review_path.read_text('utf-8'))
            if review['result'] != 'PASS_WITH_SCOPE' or review['cdc_critical'] != 0:
                raise ValueError('CDC repair has no passing scoped hardware review')
            for kind, path in [('bit', bit), ('hwh', hwh), ('xsa', args.xsa),
                               ('routed_dcp', bit.with_name(bit.stem+'_routed.dcp'))]:
                if hashlib.sha256(path.read_bytes()).hexdigest() != review['hardware'][kind]['sha256']:
                    raise ValueError('Hardware differs from CDC review: '+kind)
            for name, digest in review['report_hashes'].items():
                if hashlib.sha256((report_dir/name).read_bytes()).hexdigest() != digest:
                    raise ValueError('CDC review report changed: '+name)
            ports = {m.get('INSTANCE'): {port.get('NAME'): port.get('SIGNAME')
                     for port in m.findall('./PORTS/PORT')}
                     for m in tree.iter('MODULE') if m.get('INSTANCE') in ('compute', 'audio_capture')}
            for output, input_ in [('audio_run', 'run_enable'), ('audio_draining', 'compute_draining')]:
                if not ports['compute'].get(output) or ports['compute'][output] != ports['audio_capture'].get(input_):
                    raise ValueError('Missing shared CDC control connection: '+output)
            if any(name.endswith('_async') for name in ports['audio_capture']):
                raise ValueError('Obsolete audio control input remains')
            entries['reports/hardware-review.json'] = review_path
            entries['document/ps-cdc-control-fix.md'] = ROOT/'document/ps-cdc-control-fix.md'
        audit = json.loads(audit_path.read_text(encoding='utf-8'))
        xpr = one(hw.glob('*.xpr'), 'project file')
        project_tree = ET.parse(xpr)
        matched = []
        for rel, expected_hash in audit['candidate_files'].items():
            if not rel.startswith('project/rtl/'):
                continue
            name = Path(rel).name
            raw = one((f.get('Path') for fs in project_tree.iter('FileSet')
                       if fs.get('Name') == 'sources_1' for f in fs.iter('File')
                       if f.get('Path', '').replace('\\', '/').split('/')[-1] == name), name)
            actual = Path(raw.replace('$PSRCDIR', str(hw/(xpr.stem+'.srcs'))).replace('$PPRDIR', str(hw)))
            if hashlib.sha256(actual.read_bytes()).hexdigest() != expected_hash:
                raise ValueError('PCM RTL differs from simulated candidate: '+name)
            if actual.stat().st_mtime > bit.stat().st_mtime:
                raise ValueError('PCM RTL modified after bit generation: '+name)
            matched.append(name)
        entries['README.md'] = ROOT/pcm_readme
        for name in (pcm_readme, 'document/ps-pcm-integration.md',
                     'software/tests/test_pcm_capture.py'):
            entries[name] = ROOT/name
        for suffix in ('_utilization_placed.rpt', '_route_status.rpt', '_methodology_drc_routed.rpt'):
            report = bit.with_name(bit.stem+suffix)
            entries['reports/'+report.name] = report
        for report in report_dir.glob('*.rpt'):
            entries['reports/'+report.name] = report
        source.update(audio_enable=1, pcm_registered_sources_match=matched,
                      pcm_format='48kHz 4ch S24 in S32 LE; 512 samples; 8224 bytes',
                      pcm_entry='soundsight.sh pcm-check; soundsight.sh pcm --blocks 1',
                      pcm_board='NOT_RUN', speaker_verification='NOT_IMPLEMENTED',
                      independent_review='NOT_RUN', cdc_reset_review='OPEN; see reports and README')
        if args.pcm_cdc:
            source.update(cdc_control_revision=2, cdc_critical=0, cdc_warning=review['cdc_warning'],
                          routed_wns_ns=review['timing']['wns_ns'],
                          cdc_reset_review='Three CDC-10 issues closed; CDC-15 and other RDC/DRC warnings remain open')
    for suffix in ("_timing_summary_routed.rpt", "_drc_routed.rpt"):
        report = bit.with_name(bit.stem + suffix)
        entries["reports/" + report.name] = report
    for name, path in entries.items():
        if not path.is_file():
            raise FileNotFoundError(str(path))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Refuse overwriting an older delivery without the caller first retaining it.
    with zipfile.ZipFile(args.output, "x", zipfile.ZIP_DEFLATED) as package:
        for name, path in sorted(entries.items()):
            package.write(path, board_dir + '/' + name)
        package.writestr(board_dir + '/SOURCE.json',
                        json.dumps(source, ensure_ascii=False, indent=2) + "\n")
        package.writestr(board_dir + '/FILES.sha256.json', json.dumps(
            {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in sorted(entries.items())},
            indent=2) + '\n')
    with zipfile.ZipFile(args.output) as package:
        if package.testzip() or any(package.read(board_dir+'/'+name) != path.read_bytes()
                                   for name, path in entries.items()):
            raise ValueError('Package integrity or source copy mismatch.')
    print("PYNQ_PACKAGE_CREATED", args.output, "files=", len(entries) + 2)
    print("No ARM compilation, MMIO, download, reset or motion executed.")


if __name__ == "__main__":
    main()
