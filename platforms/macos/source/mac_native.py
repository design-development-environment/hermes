import hashlib
import os
import subprocess
import tempfile
import time
from pathlib import Path

def applications():
    roots=[Path('/Applications'),Path('/System/Applications'),Path.home()/'Applications']
    return [{'id':hashlib.sha256(str(p).encode()).hexdigest()[:20],'name':p.stem,'path':str(p)}
            for root in roots for p in list(root.glob('*.app'))+list((root/'Utilities').glob('*.app'))]

def applescript(script,*values):
    # Data is passed as argv, never interpolated into AppleScript source.
    return subprocess.run(['/usr/bin/osascript','-e',script,*values],check=True,capture_output=True,text=True,timeout=15).stdout.strip()

def notify(title,message):
    applescript('on run argv\ndisplay notification (item 2 of argv) with title (item 1 of argv)\nend run',title[:100],message[:500])

def run_command(command,cwd,timeout):
    import signal
    with tempfile.TemporaryFile() as out,tempfile.TemporaryFile() as err:
        p=subprocess.Popen(command,cwd=cwd,stdout=out,stderr=err,stdin=subprocess.DEVNULL,start_new_session=True)
        timed_out=False
        try: p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out=True
            os.killpg(p.pid,signal.SIGKILL); p.wait()
        def tail(f):
            size=f.tell(); f.seek(max(0,size-40000)); return f.read().decode('utf-8',errors='replace'),size>40000
        stdout,a=tail(out); stderr,b=tail(err)
    return {'success':p.returncode==0 and not timed_out,'exit_code':p.returncode,'timed_out':timed_out,
            'stdout':stdout,'stderr':stderr,'output_truncated':a or b,'sandboxed':False,'cwd':str(cwd),'command':command}

def service_status(name):
    import json,psutil
    from platform_support import DATA_DIR
    try:
        state=json.loads((DATA_DIR/'supervisor.json').read_text())
        if time.time()-state['updated']>30: return 'inactive'
        if name in {'hermes-health-monitor.timer','hermes-backup.timer'}: return 'active' if psutil.pid_exists(state['pid']) else 'inactive'
        pid=state['children'].get(name)
        return 'active' if pid and psutil.pid_exists(pid) else 'inactive'
    except (OSError,ValueError,KeyError): return 'unknown'
