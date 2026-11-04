import os
import hashlib
import subprocess
import tempfile
import time
from pathlib import Path

def applications():
    roots=[Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs',Path(os.environ['PROGRAMDATA'])/'Microsoft/Windows/Start Menu/Programs']
    result=[]
    for root in roots:
        for p in root.rglob('*.lnk'):
            result.append({'id':hashlib.sha256(str(p).encode()).hexdigest()[:20],'name':p.stem,'path':str(p)})
    return result

def notify(title,message):
    from plyer import notification
    notification.notify(title=title[:64],message=message[:256],app_name='Hermes',timeout=5)

def run_command(command,cwd,timeout):
    import psutil
    # File-backed output bounds memory even for noisy commands.
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        p=subprocess.Popen(command,cwd=cwd,stdout=out,stderr=err,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        timed_out=False
        try: p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out=True
            try:
                for child in psutil.Process(p.pid).children(recursive=True): child.kill()
            except psutil.Error: pass
            p.kill(); p.wait()
        def tail(f):
            size=f.tell(); f.seek(max(0,size-40000)); return f.read().decode('utf-8',errors='replace'),size>40000
        stdout,a=tail(out); stderr,b=tail(err)
        return {'success':p.returncode==0 and not timed_out,'exit_code':p.returncode,'timed_out':timed_out,'stdout':stdout,'stderr':stderr,'output_truncated':a or b,'sandboxed':False,'cwd':str(cwd),'command':command}

def service_status(name):
    import json, psutil
    from platform_support import DATA_DIR
    try:
        state=json.loads((DATA_DIR/'supervisor.json').read_text())
        if time.time()-state['updated']>30: return 'inactive'
        if name in {'hermes-health-monitor.timer','hermes-backup.timer'}: return 'active' if psutil.pid_exists(state['pid']) else 'inactive'
        pid=state['children'].get(name)
        return 'active' if pid and psutil.pid_exists(pid) else 'inactive'
    except (OSError,ValueError,KeyError): return 'unknown'
