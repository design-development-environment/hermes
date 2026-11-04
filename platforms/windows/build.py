"""Build the native Hermes Windows installer."""
import hashlib
import os
import subprocess
import shutil
from pathlib import Path

root=Path(__file__).resolve().parent
version=(root/'VERSION').read_text(encoding='utf-8').strip()
nsis=root/'build-tools/nsis'
environment=os.environ.copy()
makensis=shutil.which('makensis')
if not makensis and os.name == 'nt':
    for candidate in (
        Path(os.environ.get('ProgramFiles(x86)', ''))/'NSIS/makensis.exe',
        Path(os.environ.get('ProgramFiles', ''))/'NSIS/makensis.exe',
    ):
        if candidate.is_file():
            makensis=str(candidate)
            break
if not makensis:
    makensis=str(nsis/'usr/bin/makensis')
    environment['NSISDIR']=str(nsis/'usr/share/nsis')
if not Path(makensis).is_file() and not shutil.which(makensis):
    raise SystemExit('NSIS makensis was not found. Install NSIS or provide build-tools/nsis.')
output=root/f'Hermes-{version}-Windows-x64-Setup.exe'
define='/' if os.name == 'nt' else '-'
subprocess.run([makensis,'-V2',f'{define}DPRODUCT_VERSION={version}',f'{define}DPRODUCT_VERSION_QUAD={version}.0',str(root/'installer.nsi')],cwd=root,env=environment,check=True)
files=[output, root/'build-tools/python-3.12.10-amd64.exe', root/'source/requirements-windows.lock']
(root/'SHA256SUMS-windows-x64.txt').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(root)}\n' for p in files))
print('Built',output, 'bytes:',output.stat().st_size)
