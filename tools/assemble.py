"""Create an isolated platform build tree from shared core and OS overlays."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARED_MODULES = (
    'agent_control.py', 'app.py', 'automation.py', 'bootstrap_openwebui.py', 'cdp_client.py',
    'codebase_control.py', 'file_ops.py', 'governance_control.py',
    'hermes_health_monitor.py', 'hermes_tools.py', 'managed_browser_launcher.py',
    'memory_control.py', 'model_runtime.py', 'openwebui_tool.py',
    'persistent_workflow.py', 'planning_control.py', 'portable_preflight.py',
    'sync_openwebui_tool.py', 'task_control.py', 'vision.py',
    'workflow_engine.py', 'workflows.py', 'workspace_preset.py',
)
SHARED_FILES = ('model_instructions.txt',)
RELEASE_FILES = ('LICENSE', 'VERSION', 'RELEASE_NOTES.md')


def assemble(platform: str, destination: Path) -> None:
    if platform not in {'windows', 'macos'}:
        raise ValueError('Unsupported platform')
    source = ROOT / 'platforms' / platform
    if destination.exists():
        raise FileExistsError(destination)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in SHARED_MODULES:
        target = destination / 'source' / name
        if target.exists():
            raise RuntimeError(f'Duplicate shared module: {target}')
        shutil.copy2(ROOT / 'core' / name, target)
    # These files are intentionally identical on every platform.  Overwrite
    # stale port snapshots so model behavior and release identity cannot drift.
    for name in SHARED_FILES:
        shutil.copy2(ROOT / 'core' / name, destination / 'source' / name)
    for name in RELEASE_FILES:
        shutil.copy2(ROOT / name, destination / name)
    shutil.copytree(
        ROOT / 'client', destination / 'client',
        ignore=shutil.ignore_patterns('node_modules', '__pycache__', '*.pyc'),
    )
    for name in ('icon-dark.png', 'hermes-dark.svg', 'hermes-light.svg'):
        shutil.copy2(ROOT / 'packaging' / 'branding' / name, destination / 'client' / 'desktop' /
                     ('icon.png' if name == 'icon-dark.png' else name))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('platform', choices=('windows', 'macos'))
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    assemble(args.platform, args.destination)
