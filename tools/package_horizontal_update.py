"""Package the exact external-copy updater; never packages a Vivado cache/bit."""
import argparse
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
FILES = ['project/bd/update_ps_horizontal.tcl', 'project/bd/update_ps_volume.tcl',
         'project/bd/update_ps_servo_pins.tcl',
         'project/bd/update_ps_manual.tcl', 'project/rtl/ss_manual_servo.sv',
         'project/sdc/ps/horizontal_reserved.xdc', 'document/pynq-horizontal.md', 'document/ps-manual-calibration.md', 'document/pynq-manual-status-fix.md']
FILES += ['project/rtl/'+name for name in ('bd_ps_link.v','ss_ps_link.sv',
          'ss_ps_control_regs.sv','ss_actuator_control.sv','motor_drive.v','i17_turntable_pwm_guard.sv')]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=ROOT/'release/output/soundsight_horizontal_project_update.zip')
    args = p.parse_args()
    with ZipFile(args.output, 'x', ZIP_DEFLATED) as z:
        for name in FILES: z.write(ROOT/name, name)
        z.writestr('README.txt',
                   'Update an existing PL+PS Volume project COPY created by the user.\n'
                   'Name the external project *_Servo. Open that copy in Vivado.\n'
                   'Source project/bd/update_ps_horizontal.tcl from this extracted package.\n'
                   'Already prepared Servo project: use project/bd/update_ps_servo_pins.tcl for pins only (T15/W15).\n'
                   'Audio-independent calibration update for existing T15/W15 Servo: source project/bd/update_ps_manual.tcl.\n'
                   'No project creation, synthesis, implementation or hardware actions.\n'
                   'See document/pynq-horizontal.md. PS software is a separate SD update.\n')
    with ZipFile(args.output) as z:
        assert z.testzip() is None
        for name in FILES: assert z.read(name) == (ROOT/name).read_bytes(), name
    print('HORIZONTAL_PROJECT_UPDATE=', args.output, 'INPUT_FILES=', len(FILES), 'BIT_INCLUDED=False')


if __name__ == '__main__': main()
