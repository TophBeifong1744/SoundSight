"""Render poster PPTX through isolated LibreOffice and real Poppler executables."""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time


def render(source, output, dependencies):
    source, output = Path(source).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    soffice_value = os.environ.get('CODEX_SOFFICE_EXE') or shutil.which('soffice.exe')
    if not soffice_value:
        raise RuntimeError('Set CODEX_SOFFICE_EXE or put soffice.exe on PATH.')
    soffice = Path(soffice_value)
    poppler = Path(dependencies) / 'native/poppler/Library/bin'
    with tempfile.TemporaryDirectory(prefix='soundsight_poster_') as tmp:
        root = Path(tmp)
        profile = root / 'profile'
        profile.mkdir()
        copied = root / 'poster.pptx'
        shutil.copy2(source, copied)
        env = os.environ.copy()
        for key in ['HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP']:
            target = root / key.lower()
            target.mkdir()
            env[key] = str(target)
        cmd = [str(soffice), '--headless', '--invisible', '--norestore', '--nolockcheck',
               '-env:UserInstallation=' + profile.as_uri(), '--convert-to', 'pdf:impress_pdf_Export',
               '--outdir', str(root), str(copied)]
        p = subprocess.run(cmd, env=env, capture_output=True, timeout=90, creationflags=0x08000000)
        pdf = root / 'poster.pdf'
        deadline, previous, stable = time.monotonic()+60, -1, 0
        while time.monotonic() < deadline:
            size = pdf.stat().st_size if pdf.exists() else 0
            stable = stable+1 if size > 0 and size == previous else 0
            previous = size
            if stable >= 3 and pdf.read_bytes()[:5] == b'%PDF-':
                break
            time.sleep(0.5)
        else:
            raise RuntimeError(f'No stable PDF: exit={p.returncode}, size={previous}, stdout={p.stdout!r}, stderr={p.stderr!r}')
        final_pdf = output / (source.stem + '.pdf')
        shutil.copy2(pdf, final_pdf)
        info = subprocess.run([str(poppler/'pdfinfo.exe'), str(final_pdf)], capture_output=True, check=True, creationflags=0x08000000)
        subprocess.run([str(poppler/'pdftoppm.exe'), '-png', '-scale-to', '2560', '-singlefile', str(final_pdf), str(output/source.stem)], check=True, timeout=90, creationflags=0x08000000)
        return {'source':str(source), 'pdf':str(final_pdf), 'png':str(output/(source.stem+'.png')), 'pdfinfo':info.stdout.decode(errors='replace'), 'engine':'LibreOffice Impress / Poppler', 'launcher_exit':p.returncode}


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('source')
    parser.add_argument('output')
    parser.add_argument('--dependencies', required=True)
    a = parser.parse_args()
    print(json.dumps(render(a.source, a.output, a.dependencies), ensure_ascii=False, indent=2))
