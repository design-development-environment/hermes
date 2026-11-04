#!/usr/bin/env python3
"""Build a credential-free, reproducible Hermes setup package."""

from __future__ import annotations

import argparse
import platform
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


PACKAGING = Path(__file__).resolve().parent
SOURCE = PACKAGING.parent / 'core'
DESKTOP = Path.home() / 'Desktop'
FILES = [
    'agent_control.py', 'app.py', 'automation.py', 'backup_manager.py', 'bootstrap_openwebui.py',
    'browser_control.py', 'cdp_client.py', 'codebase_control.py',
    'computer_control.py', 'desktop.py', 'file_ops.py', 'governance_control.py',
    'graphical_control.py', 'hermes_health_monitor.py', 'hermes_tools.py',
    'install.sh', 'maintenance_control.py', 'managed_browser_launcher.py',
    'memory_control.py', 'model_runtime.py', 'openwebui_tool.py',
    'platform_commands.py',
    'persistent_workflow.py', 'planning_control.py', 'platform_support.py',
    'portable_preflight.py', 'screenshot.py', 'sync_openwebui_tool.py',
    'task_control.py', 'vision.py', 'workflow_engine.py', 'workflows.py',
    'workspace_preset.py', 'model_instructions.txt', 'appliance.env.example',
    'requirements-hermes.lock', 'requirements-openwebui-amd64.lock',
    'requirements-openwebui-arm64.lock', 'requirements-openwebui.in',
    'requirements-openwebui-core2.in', 'requirements-openwebui-core2-amd64.lock',
    'open-webui.service.portable', 'hermes-action-bridge.service',
    'hermes-documents.service', 'hermes-managed-browser.service',
    'hermes-backup.service', 'hermes-backup.timer',
    'hermes-health-monitor.service', 'hermes-health-monitor.timer',
    'README.md', 'PORTABILITY.md', 'MODEL_PROVIDERS.md',
]


def copy(source: Path, dest: Path, mode: int = 0o644):
    if not source.is_file() or source.is_symlink():
        raise FileNotFoundError(f'Missing or unsafe package input: {source}')
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    dest.chmod(mode)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=DESKTOP / 'Hermes-installer.deb')
    parser.add_argument('--architecture', choices=('amd64', 'arm64'), default={'x86_64': 'amd64', 'aarch64': 'arm64'}.get(platform.machine(), 'amd64'))
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='hermes-deb-', dir=output.parent) as folder:
        root = Path(folder) / 'package'
        payload = root / 'opt/hermes/payload'
        for name in FILES:
            copy(SOURCE / name, payload / name, 0o755 if name == 'install.sh' else 0o644)
        copy(PACKAGING / 'hermes_setup.py', root / 'usr/bin/hermes-setup', 0o755)
        copy(PACKAGING / 'hermes_setup_check.py', root / 'opt/hermes/hermes-setup-check', 0o755)
        copy(PACKAGING / 'hermes-open', root / 'usr/bin/hermes-open', 0o755)
        copy(PACKAGING / 'askpass.sh', root / 'opt/hermes/askpass.sh', 0o755)
        copy(PACKAGING / 'hermes-autologin', root / 'opt/hermes/hermes-autologin', 0o755)
        for name in ('hermes.desktop',):
            copy(PACKAGING / name, root / 'usr/share/applications' / name)
        copy(PACKAGING / 'branding/icon-dark.png', root / 'usr/share/icons/hicolor/1024x1024/apps/hermes.png')
        copy(PACKAGING / 'branding/icon-light.png', root / 'usr/share/hermes/branding/hermes-light.png')
        copy(PACKAGING / 'branding/hermes-dark.svg', root / 'usr/share/hermes/branding/hermes-dark.svg')
        copy(PACKAGING / 'branding/hermes-light.svg', root / 'usr/share/hermes/branding/hermes-light.svg')
        for theme in ('dark', 'light'):
            copy(PACKAGING / f'logo-{theme}.png', root / 'usr/share/hermes/branding' / f'logo-{theme}.png')
        control = root / 'DEBIAN/control'
        control.parent.mkdir(parents=True)
        control.write_text('''Package: hermes-installer
Version: 1.0.0
Section: utils
Priority: optional
Architecture: {architecture}
Maintainer: Anshul & Miheer <anshul.pandhare@mitwpu.edu.in>
Depends: python3, python3-tk, python3-pil, python3-pil.imagetk, fonts-inter, zenity, sudo, xdg-utils, bash, ca-certificates
Description: Hermes graphical setup
 Highly Efficient Real-time Machine for Everyday Support.
 Installs the Hermes cloud assistant and guides first-run configuration.
Support: anshul.pandhare@mitwpu.edu.in, miheer.sabnis@mitwpu.edu.in
'''.format(architecture=args.architecture))
        copyright_file = root / 'usr/share/doc/hermes-installer/copyright'
        copyright_file.parent.mkdir(parents=True, exist_ok=True)
        copyright_file.write_text('Copyright: Anshul & Miheer\nLicense: All rights reserved.\n')
        built = Path(folder) / 'Hermes-installer.deb'
        subprocess.run(['dpkg-deb', '--build', '--root-owner-group', str(root), str(built)], check=True)
        os.replace(built, output)
    print(output)


if __name__ == '__main__':
    main()
