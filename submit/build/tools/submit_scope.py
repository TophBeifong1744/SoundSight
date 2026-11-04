"""Select the final S2/S3/CF1A submission, not the whole repository history.

The S2 source map is the hardware dependency closure. Some live ABI/BD names
contain 'stm32'; names alone must never override that closure.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARDWARE = {row['source'] for row in json.loads(
    (ROOT/'project/screen_s2/source-map.json').read_text('utf-8'))['files']}

TOOLS = set(('analyze_measurement_workbook analyze_release_session export_submit submit_scope check_submit prepare_screen_s2 '
             'check_current_software install_current_runtime install_normal_update '
             'pynq_preflight tool_config analyze_speaker_sessions '
             'collect_usb_gadget_inputs package_usb_network install_product package_product').split())
TESTS = set(('test_screen_rotation test_speaker_delete test_screen_quick_boot test_current_runtime test_normal test_volume_gate test_serial_english '
             'test_board_tools test_filter_controls test_manual_servo test_pcm_capture '
             'test_online_angle_filter test_speaker_follow test_speaker_display '
             'test_speaker_enrollment test_speaker_statistics test_latest_result '
             'test_speaker_process test_speaker_rx test_stream_scheduler '
             'test_speaker_live test_live_cpu_profile test_usb_network '
             'test_usb_input_collector test_tool_config test_screen_product').split())
DOCS = set(('runtime-update-log release-20261103 cf1-pcm-gap-filter screen-rotation screen-user-delete screen-quick-boot screen-speaker-capture-fix final-function-scope main-architecture pynq-final-runtime '
            'screen-readme screen-control follow-sound-af1 ps-dual-axis-interface '
            'ps-manual-calibration ps-latest-result ps-pcm-integration ps-volume-gate '
            'pynq-online-angle-filter pynq-speaker-enrollment pynq-speaker-statistics '
            'pynq-usb-network competition-skills-delivery competition-skills-ai-corrections '
            'submit-final-scope screen-product').split())
# Baselines and rejected optimization measurements are evidence, not deployable
# candidates. Retain their original data so the improvement claims remain auditable.
EVIDENCE = set(('final-board-20261103 report-measurements-20261103 runtime-release-20261103 screen-speaker-capture-fix-20261103 cf1-pcm-gap-filter-20261103 screen-rotation-20261103 screen-user-delete-20261103 screen-quick-boot-20261103 cf1-board-20261101 cf1a-20261102 cf1a-longrun-20261102 '
                'competition-skills-20261018 final-runtime-20261102 '
                'joint-peaks-20261101 p02-ttl-20261031 '
                'screen-s2-20261031 screen-s3-20261031 '
                'speaker-report-materials speaker-dual-axis-20261030 '
                'speaker-enrollment-20261029 speaker-score-display-20261030 '
                'speaker-statistics-20261030 speaker-ttl-20261030 '
                'usb-network-preflight-20261102 screen-product-p1-20261103').split())


def include(name):
    if name in {'software/ps/run-notes.txt', 'software/common/s1/PS-MIGRATION.md',
                'software/common/s1/README.md'}:
        return False
    if name.startswith('document/evidence/usb-network-preflight-20261102/') and name.endswith('.zip'):
        # Keep failure logs and diagnosis, not superseded installable candidates.
        return False
    if name in HARDWARE:
        return True
    if name in {'LICENSE', 'THIRD_PARTY.md', 'tools.local.env.example',
                'document/design-report.docx',
                'release/output/soundsight_screen_product_p1.zip',
                'report/README.md', 'handoff/README.md', 'handoff/source-map.json',
                'soundsight.sh', 'soundsight-3d.sh', 'soundsight-panel.sh',
                'soundsight-screen.sh', 'soundsight-screen-i2c.sh', 'soundsight-product.sh',
                'release/check_competition_skills.py',
                'project/screen_s2/source-map.json'}:
        return True
    if name.startswith(('software/ps/', 'software/common/', 'software/screen/',
                        'software/tetra3d/core/', 'software/tetra3d/linux/',
                        'software/tetra3d/tests/', 'release/output/screen_s2/',
                        'handoff/screen_s2/', 'handoff/tools/', 'report/screen_s2_20261103/',
                        'project/reports/ps_3d/screen_s2/',
                        'research/competition-skills/')):
        return '/.git' not in name
    # Current PS testbenches and fixtures remain useful independent HDL assets;
    # legacy STM32/system runners are not advertised as current S2 reproduction.
    if name.startswith(('simulation/tb/ps/', 'simulation/models/')):
        return True
    if name.startswith('tools/'):
        return Path(name).stem in TOOLS and name.endswith('.py')
    if name.startswith('software/tests/'):
        return Path(name).stem in TESTS and name.endswith('.py')
    if name.startswith('document/evidence/'):
        return name.split('/')[2] in EVIDENCE
    if name.startswith('document/') and name.count('/') == 1:
        return Path(name).stem in DOCS and name.endswith('.md')
    if name.startswith(('document/requirements/', 'document/handoff/report-update-20261103/')):
        return True
    if name.startswith('hardware/reference/'):
        return not name.startswith('hardware/reference/camera/') and not name.endswith(('README.md', 'pg308-i2s.pdf'))
    if name.startswith('hardware/evidence/'):
        return name.split('/')[2] in {'board-2026-09-07', 'microphone-c-2026-09-09', 'servo-c-20260928'}
    return False
