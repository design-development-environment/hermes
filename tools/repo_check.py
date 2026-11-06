"""Fail on accidental private files, common credential formats, or duplicated code."""
import re
from pathlib import Path
from assemble import SHARED_MODULES

ROOT = Path(__file__).resolve().parent.parent
SHARED = set(SHARED_MODULES)
VERSION = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()

if not re.fullmatch(r'\d+\.\d+\.\d+', VERSION):
    raise SystemExit(f'Invalid release version: {VERSION!r}')

# These sources embed the product version in runtime metadata or native package
# defaults.  Native builders override some of them, but a stale fallback makes
# manual and offline builds disagree with CI.
for relative in (
    'client/desktop-package.json', 'client/desktop/package.json',
    'client/windows-user.nsi', 'core/app.py', 'core/backup_manager.py',
    'core/hermes_tools.py', 'core/model_instructions.txt',
    'packaging/hermes_setup.py', 'platforms/windows/installer.nsi',
    'platforms/windows/source/backup_manager.py',
    'platforms/windows/source/ui.py', 'platforms/windows/source/windows_setup.py',
    'platforms/macos/source/backup_manager.py',
    'platforms/macos/source/ui.py', 'platforms/macos/source/mac_setup.py',
):
    if VERSION not in (ROOT / relative).read_text(encoding='utf-8'):
        raise SystemExit(f'Version drift in {relative}: expected {VERSION}')

for platform in ('windows', 'macos'):
    source = ROOT / 'platforms' / platform / 'source'
    duplicate = SHARED & {p.name for p in source.glob('*.py')}
    if duplicate:
        raise SystemExit(f'{platform} duplicates shared modules: {sorted(duplicate)}')

for path in ROOT.rglob('*'):
    if '.git' in path.parts or 'node_modules' in path.parts or 'dist' in path.parts:
        continue
    if path.is_symlink():
        raise SystemExit(f'Symlink in source tree: {path.relative_to(ROOT)}')
    if not path.is_file():
        continue
    if path.suffix in {'.db', '.sqlite', '.pem', '.key', '.env', '.zip', '.deb', '.exe'}:
        raise SystemExit(f'Private or built file in source tree: {path.relative_to(ROOT)}')
    if path.stat().st_size > 10_000_000:
        raise SystemExit(f'Oversized source file: {path.relative_to(ROOT)}')
    if path.suffix not in {'.py', '.sh', '.ps1', '.md', '.txt', '.yaml', '.yml', '.json', '.in', '.lock'}:
        continue
    content = path.read_text(encoding='utf-8', errors='replace')
    for pattern in (r'nvapi-[A-Za-z0-9_-]{12,}', r'sk-[A-Za-z0-9_-]{20,}',
                    r'AIza[0-9A-Za-z_-]{20,}', r'gh[pousr]_[A-Za-z0-9]{20,}'):
        for match in re.finditer(pattern, content):
            if path == ROOT / 'core/test_v6.py' and match.group() == 'sk-' + 'abcdefghijklmnopqrstuvwxyz123456':
                continue
            raise SystemExit(f'Possible credential in {path.relative_to(ROOT)}')

print('Repository structure and credential scan: OK')
