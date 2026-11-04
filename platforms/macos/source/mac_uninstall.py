"""Remove only the fixed per-user Hermes installation; preserve shared software."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

def safe_tree(path):
    if path.is_symlink(): raise RuntimeError('Refusing linked folder: '+str(path))
    if not path.exists(): return
    # rmtree unlinks nested symlinks without following them (venvs contain these).
    shutil.rmtree(path)

def main():
    if sys.platform!='darwin': raise RuntimeError('Run this on macOS only')
    base=Path.home()/'Library/Application Support/Hermes'
    if Path(__file__).resolve().parent != base/'source': raise RuntimeError('Not running from the installed Hermes directory')
    agent=Path.home()/'Library/LaunchAgents/com.hermes.assistant.plist'
    result=subprocess.run(['/bin/launchctl','bootout',f'gui/{os.getuid()}/com.hermes.assistant'],capture_output=True,text=True)
    check=subprocess.run(['/bin/launchctl','print',f'gui/{os.getuid()}/com.hermes.assistant'],capture_output=True)
    if check.returncode==0: raise RuntimeError('Could not stop Hermes. No files were removed.')
    agent.unlink(missing_ok=True)
    for name in ('runtime','source'): safe_tree(base/name)
    if '--delete-data' in sys.argv:
        for name in ('data','config'): safe_tree(base/name)
    print('Hermes runtime removed. Python, Tailscale, your app bundle and documents were kept. Move Hermes.app to Trash to remove its launcher.',flush=True)

if __name__=='__main__': main()
