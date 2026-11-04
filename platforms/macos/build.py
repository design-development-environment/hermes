"""Package a script-based preview app on Linux; sign/notarize later on a Mac."""
import ast
import hashlib
import json
import plistlib
import shutil
import zipfile
from pathlib import Path
from PIL import Image

root=Path(__file__).resolve().parent
bundle=root/'Hermes.app'
contents=bundle/'Contents'
resources=contents/'Resources'
(contents/'MacOS').mkdir(parents=True,exist_ok=True)
resources.mkdir(parents=True,exist_ok=True)
for p in (root/'source').glob('*.py'): ast.parse(p.read_text(),str(p))
shutil.copytree(root/'source',resources/'source',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for name in ('bootstrap.command','python-package.sha256','README-MACOS.md'):
    shutil.copy2(root/name,resources/name)
shutil.copy2(root/'launcher',contents/'MacOS/Hermes')
(contents/'MacOS/Hermes').chmod(0o755)
(resources/'bootstrap.command').chmod(0o755)
Image.open(root/'source/branding/icon-dark.png').save(resources/'Hermes.icns')
info={'CFBundleName':'Hermes','CFBundleDisplayName':'Hermes','CFBundleIdentifier':'com.hermes.setup.preview',
      'CFBundleVersion':'1','CFBundleShortVersionString':'1.0.0','CFBundlePackageType':'APPL',
      'CFBundleExecutable':'Hermes','CFBundleIconFile':'Hermes.icns','LSMinimumSystemVersion':'14.0',
      'NSHighResolutionCapable':True,'NSAppleEventsUsageDescription':'Hermes opens Terminal to prepare its private Python runtime.'}
(contents/'Info.plist').write_bytes(plistlib.dumps(info))
archive=root/'Hermes-macOS-Preview.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as output:
    for p in sorted(bundle.rglob('*')):
        output.write(p,p.relative_to(root))
    output.write(root/'README-MACOS.md','README-MACOS.md')
(root/'SHA256SUMS').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
print('Created',archive,'bytes:',archive.stat().st_size)
