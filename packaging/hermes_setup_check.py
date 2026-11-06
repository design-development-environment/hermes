#!/usr/bin/env python3
"""Non-secret acceptance checks for a configured Hermes installation."""

import json
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path

sys.path.insert(0, '/opt/hermes/payload')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from platform_support import openwebui_data_dir


def health(url):
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def main():
    checks = {
        'Open WebUI': health('http://127.0.0.1:3000/health'),
        'Hermes action bridge': health('http://127.0.0.1:8765/health'),
        'Hermes documents': health('http://127.0.0.1:8766/health'),
    }
    db_path = openwebui_data_dir() / 'webui.db'
    if db_path.is_file():
        try:
            with closing(sqlite3.connect(f'file:{db_path}?mode=ro', uri=True, timeout=5)) as db, db:
                checks['Owner account'] = db.execute('SELECT 1 FROM user LIMIT 1').fetchone() is not None
                models = {row[0] for row in db.execute('SELECT name FROM model')}
                checks['Alpha, Beta and Gamma presets'] = {'Hermes Alpha', 'Hermes Beta', 'Hermes Gamma'} <= models
        except sqlite3.Error:
            checks['Owner account'] = False
            checks['Alpha, Beta and Gamma presets'] = False
    else:
        checks['Owner account'] = False
        checks['Alpha, Beta and Gamma presets'] = False
    try:
        result = subprocess.run(['tailscale', 'status', '--json'], capture_output=True, text=True, timeout=8)
        checks['Tailscale connected'] = result.returncode == 0 and json.loads(result.stdout).get('BackendState') == 'Running'
        served = subprocess.run(['tailscale', 'serve', 'status'], capture_output=True, text=True, timeout=8)
        checks['Tailscale Serve'] = served.returncode == 0 and '3000' in served.stdout
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        checks['Tailscale connected'] = False
        checks['Tailscale Serve'] = False
    for name, passed in checks.items():
        print(f'{"PASS" if passed else "FAIL"}: {name}')
    if not all(checks.values()):
        print('Finish the missing setup steps above and run this check again.')
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
