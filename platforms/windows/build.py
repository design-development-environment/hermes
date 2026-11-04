"""Rebuild the isolated Windows package without modifying Linux artifacts."""
import hashlib
import json
import os
import subprocess
import shutil
from pathlib import Path

root=Path(__file__).resolve().parent
nsis=root/'build-tools/nsis'
environment=os.environ.copy()
makensis=shutil.which('makensis') or str(nsis/'usr/bin/makensis')
if not shutil.which('makensis'):
    environment['NSISDIR']=str(nsis/'usr/share/nsis')
subprocess.run([makensis,'-V2',str(root/'installer.nsi')],cwd=root,env=environment,check=True)
files=[root/'Hermes-Windows-Setup.exe', root/'build-tools/python-3.12.10-amd64.exe', root/'source/requirements-windows.lock']
(root/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(root)}\n' for p in files))
print('Built',files[0], 'bytes:',files[0].stat().st_size)
