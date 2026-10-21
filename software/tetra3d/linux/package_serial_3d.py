"""生成独立三维串口软件包，不连接COM、不加载位流。

python software/tetra3d/linux/package_serial_3d.py
输出release/output/soundsight-tetra3d-serial.zip，步骤见本目录三维接合步骤.txt。
"""
import argparse
import base64
import gzip
import io
from pathlib import Path
import tarfile
import zipfile

ROOT=Path(__file__).resolve().parents[3]
BASE_FILES=('LICENSE','software/common/fpga_stm32_abi_frozen.h',
            'software/common/s1/doa_solver.c','software/common/s1/doa_solver.h',
            'software/ps/ps_client.py','software/ps/run_capture.py','software/ps/run_smp.py',
            'software/ps/run_buffered.py','software/ps/ram_queue.py',
            'software/ps/recover_ram.py','software/ps/volume_gate.py',
            'software/tests/test_buffered.py','software/tests/test_smp.py')
EVIDENCE='document/evidence/ps-tetra3d-migration-20261021/'
C_REPORT='document/evidence/pynq-tetra3d-integration-20261021/REPORT.txt'


def commands_for(payload):
    """沿用此前短ASCII命令方式，每块可重发；新三维目录独立保留。"""
    encoded=base64.b64encode(payload).decode('ascii')
    chunks=[encoded[index:index+2048] for index in range(0,len(encoded),2048)]
    if len(chunks)>9999:raise ValueError('too many serial chunks')
    lines=['ss3_stage="$HOME/soundsight-tetra3d-inbox"',
           'ss3_dest="$HOME/soundsight-tetra3d"','mkdir -p "$ss3_stage"']
    for index,chunk in enumerate(chunks):
        lines.append("printf '%s' '"+chunk+"' > \"$ss3_stage/%04d.b64\" && printf 'CHUNK_%04d_OK\\n'"%(index,index))
    lines.append(': > "$ss3_stage/payload.tar.gz" && (ss3_i=0; while [ "$ss3_i" -lt %d ]; do cat "$ss3_stage/$(printf \'%%04d\' "$ss3_i").b64" || exit 1; ss3_i=$((ss3_i+1)); done) > "$ss3_stage/payload.b64" && base64 -d "$ss3_stage/payload.b64" > "$ss3_stage/payload.tar.gz"'%len(chunks))
    lines.append('test "$(wc -c < "$ss3_stage/payload.tar.gz")" -eq %d && gzip -t "$ss3_stage/payload.tar.gz" && printf \'PAYLOAD_3D_OK bytes=%d\\n\''%(len(payload),len(payload)))
    lines.append('if [ -e "$ss3_dest" ]; then printf \'DEST_EXISTS: set ss3_dest to a new directory\\n\'; false; elif ! test "$(wc -c < "$ss3_stage/payload.tar.gz")" -eq %d || ! gzip -t "$ss3_stage/payload.tar.gz"; then printf \'BAD_PAYLOAD\\n\'; false; else mkdir "$ss3_dest" && tar -xzf "$ss3_stage/payload.tar.gz" -C "$ss3_dest" && printf \'UNPACK_3D_OK\\n\'; fi'%len(payload))
    if any(len(line.encode('ascii'))>=3800 or '\n' in line or '\r' in line for line in lines):
        raise ValueError('serial command exceeds previous 3800-byte line limit')
    return lines


def selected_files():
    paths=list(BASE_FILES)+[C_REPORT]+[EVIDENCE+name for name in ('PC-RESULT.json','EXAMPLE-FRAMES.jsonl','REPORT.md')]
    for path in sorted((ROOT/'software/tetra3d').rglob('*')):
        if path.is_file() and path.suffix in ('.py','.c','.h','.sh','.json','.md','.txt','.ps1'):
            paths.append(path.relative_to(ROOT).as_posix())
    return {name:(ROOT/name).read_bytes().replace(b'\r\n',b'\n') for name in paths}


def build(output):
    files=selected_files()
    manifest=('SoundSight tetrahedral 3D direction software\n'
              'CPU1 C solve/MMIO; CPU0 durable save/display; motion DISABLED.\n'
              'Tetra40 coordinates are NOMINAL, not measured calibration.\n'
              'No bit/HWH/ARM.so/Windows DLL/bare-metal ELF. ARM/board NOT_RUN.\n\n'
              +'\n'.join('%s  %d bytes'%(name,len(data)) for name,data in sorted(files.items()))+'\n')
    files['PACKAGE.txt']=manifest.encode('utf-8')
    raw=io.BytesIO()
    with tarfile.open(fileobj=raw,mode='w',format=tarfile.PAX_FORMAT) as archive:
        for name,data in sorted(files.items()):
            entry=tarfile.TarInfo(name);entry.size=len(data);entry.mode=0o644
            archive.addfile(entry,io.BytesIO(data))
    compressed=io.BytesIO()
    with gzip.GzipFile(fileobj=compressed,mode='wb',mtime=0,filename='') as handle:handle.write(raw.getvalue())
    payload=compressed.getvalue();lines=commands_for(payload)
    members={'payload.tar.gz':payload,'serial_commands.txt':('\n'.join(lines)+'\n').encode('ascii'),
             'copy_serial_step.ps1':files['software/tetra3d/linux/copy_serial_step.ps1'],
             '三维接合步骤.txt':files['software/tetra3d/linux/三维接合步骤.txt'],
             'CONTENTS.txt':manifest.encode('utf-8')}
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w') as archive:
        for name,data in sorted(members.items()):
            entry=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
            entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o644<<16
            archive.writestr(entry,data)
    print('SERIAL_3D_PACKAGE_READY files=%d payload_bytes=%d steps=%d max_line=%d'%(
        len(files),len(payload),len(lines),max(map(len,lines))))
    print(output)
    return payload,lines


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'release/output/soundsight-tetra3d-serial.zip')
    args=parser.parse_args(argv);build(args.output)


if __name__=='__main__':main()
