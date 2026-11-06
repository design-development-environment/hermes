"""Per-user runtime, startup and health checks. Never exposes the tool server on LAN."""
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import closing
from pathlib import Path
from platform_support import PROJECT_ROOT, DATA_DIR, CONFIG_DIR, openwebui_data_dir

APP=PROJECT_ROOT.parent
PYTHON=APP/'runtime/Scripts/python.exe'

def environment():
    env=os.environ.copy()
    env.update({'HERMES_ROOT':str(PROJECT_ROOT),'HERMES_DATA_DIR':str(DATA_DIR),'HERMES_CONFIG_DIR':str(CONFIG_DIR),
                'PIP_CACHE_DIR':str(DATA_DIR/'cache/pip'),'DATA_DIR':str(openwebui_data_dir()),'HERMES_OPENWEBUI_DATA_DIR':str(openwebui_data_dir()),
                'AUDIO_STT_ENGINE':'deepgram','AUDIO_TTS_ENGINE':'elevenlabs','ENABLE_OLLAMA_API':'false','RAG_EMBEDDING_ENGINE':'openai',
                'RAG_EMBEDDING_MODEL':'nvidia/nemotron-3-embed-1b','RAG_OPENAI_API_BASE_URL':'https://integrate.api.nvidia.com/v1',
                'WHISPER_MODEL_AUTO_UPDATE':'false','RAG_EMBEDDING_MODEL_AUTO_UPDATE':'false',
                'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8','OMP_NUM_THREADS':'2','TOKENIZERS_PARALLELISM':'false'})
    if (CONFIG_DIR/'tool-token').exists(): env['HERMES_TOOL_TOKEN']=(CONFIG_DIR/'tool-token').read_text().strip()
    env['PATH']=str(APP/'runtime')+os.pathsep+str(APP/'runtime/Scripts')+os.pathsep+env.get('PATH','')
    for relative in ('Git/cmd','nodejs','Tailscale','Microsoft VS Code/bin'):
        for root in (os.environ.get('ProgramFiles',''),os.environ.get('LOCALAPPDATA','')+'/Programs'):
            env['PATH']+=os.pathsep+str(Path(root)/relative)
    return env

def check_url(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=3) as response:
            return response.status==200
    except OSError: return False

def prepare():
    for p in (DATA_DIR,CONFIG_DIR,openwebui_data_dir(),PROJECT_ROOT/'logs'): p.mkdir(parents=True,exist_ok=True)
    # Per-user ACL, not Unix chmod, protects token, settings, chats and backups.
    import win32api, win32security, ntsecuritycon
    sid=win32security.GetTokenInformation(win32security.OpenProcessToken(win32api.GetCurrentProcess(),win32security.TOKEN_QUERY),win32security.TokenUser)[0]
    for path in (DATA_DIR,CONFIG_DIR):
        acl=win32security.ACL()
        acl.AddAccessAllowedAceEx(win32security.ACL_REVISION,3,ntsecuritycon.FILE_ALL_ACCESS,sid)
        win32security.SetNamedSecurityInfo(str(path),win32security.SE_FILE_OBJECT,win32security.DACL_SECURITY_INFORMATION|win32security.PROTECTED_DACL_SECURITY_INFORMATION,None,None,acl,None)
    token=CONFIG_DIR/'tool-token'
    if not token.exists(): token.write_text(secrets.token_urlsafe(48))
    secret=CONFIG_DIR/'webui-secret'
    if not secret.exists(): secret.write_text(secrets.token_urlsafe(48))

def start():
    subprocess.Popen([str(APP/'runtime/Scripts/pythonw.exe'),str(PROJECT_ROOT/'windows_runtime.py'),'supervise'],cwd=PROJECT_ROOT,env=environment(),creationflags=subprocess.CREATE_NO_WINDOW)

def wait_until_stopped(timeout=30):
    import psutil
    try:
        state=json.loads((DATA_DIR/'supervisor.json').read_text())
        pid=int(state.get('pid',0))
    except (OSError,ValueError,TypeError):
        return
    deadline=time.monotonic()+timeout
    while pid and psutil.pid_exists(pid) and time.monotonic()<deadline:
        time.sleep(.25)
    if pid and psutil.pid_exists(pid):
        raise RuntimeError('The previous Hermes runtime did not stop safely.')

def install_dependencies():
    """Install or repair the complete pinned runtime before starting services."""
    subprocess.run([str(PYTHON),'-m','pip','install','--require-hashes','-r',str(PROJECT_ROOT/'requirements-windows.lock')],check=True)
    subprocess.run([str(PYTHON),'-m','pip','check'],check=True)

def upgrade():
    """Activate replaced source without resetting data, keys, or presets."""
    prepare()
    stop=CONFIG_DIR/'stop'
    stop.write_text('upgrade',encoding='utf-8')
    wait_until_stopped()
    install_dependencies()
    database=openwebui_data_dir()/'webui.db'
    if database.exists():
        from bootstrap_openwebui import readiness
        if readiness().get('owner_exists'):
            subprocess.run([str(PYTHON),str(PROJECT_ROOT/'sync_openwebui_tool.py')],check=True,env=environment())
    stop.unlink(missing_ok=True)
    startup(); start()
    for _ in range(120):
        if all(check_url(p) for p in (3000,8765,8766)):
            return
        time.sleep(1)
    raise RuntimeError('Hermes was upgraded but its local services did not become ready.')

def startup():
    import win32com.client
    folder=Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/Startup'
    folder.mkdir(parents=True,exist_ok=True)
    link=win32com.client.Dispatch('WScript.Shell').CreateShortcut(str(folder/'Hermes Background.lnk'))
    link.TargetPath=str(APP/'runtime/Scripts/pythonw.exe')
    link.Arguments=subprocess.list2cmdline([str(PROJECT_ROOT/'windows_runtime.py'),'supervise'])
    link.WorkingDirectory=str(PROJECT_ROOT)
    link.Save()

def supervise():
    import win32event, win32api, winerror
    mutex=win32event.CreateMutex(None,False,'Local\\HermesRuntime')
    if win32api.GetLastError()==winerror.ERROR_ALREADY_EXISTS: return
    prepare()
    commands={
      'hermes-action-bridge.service':[str(PYTHON),'-m','uvicorn','app:app','--host','127.0.0.1','--port','8765','--loop','asyncio'],
      'hermes-documents.service':[str(PYTHON),'-m','uvicorn','hermes_tools:app','--host','127.0.0.1','--port','8766','--loop','asyncio'],
      'open-webui.service':[str(APP/'runtime/Scripts/open-webui.exe'),'serve','--host','127.0.0.1','--port','3000']}
    children={}; restart_after={}; failures={}; last_backup=0
    env=environment(); env['WEBUI_SECRET_KEY']=(CONFIG_DIR/'webui-secret').read_text().strip()
    try:
        while not (CONFIG_DIR/'stop').exists():
            for name,args in commands.items():
                process=children.get(name)
                if (process is None or process.poll() is not None) and time.monotonic()>=restart_after.get(name,0):
                    log=DATA_DIR/(name+'.log')
                    if log.exists() and log.stat().st_size>5_000_000:
                        os.replace(log,log.with_suffix('.previous.log'))
                    with log.open('ab') as stream:
                        children[name]=subprocess.Popen(args,cwd=PROJECT_ROOT,env=env,stdout=stream,stderr=stream,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
                    failures[name]=failures.get(name,0)+1
                    restart_after[name]=time.monotonic()+min(60,3*failures[name])
            state={'pid':os.getpid(),'updated':time.time(),'children':{k:v.pid for k,v in children.items() if v.poll() is None}}
            temporary=DATA_DIR/'supervisor.next'; temporary.write_text(json.dumps(state)); os.replace(temporary,DATA_DIR/'supervisor.json')
            if time.time()-last_backup>86400:
                last_backup=time.time()
                if (openwebui_data_dir()/'webui.db').exists():
                    try:
                        from backup_manager import create_backup
                        create_backup()
                    except Exception as exc:
                        (DATA_DIR/'backup-error.log').write_text(str(exc))
            time.sleep(3)
    finally:
        for process in children.values():
            if process.poll() is None: process.terminate()
        for process in children.values():
            try: process.wait(timeout=15)
            except subprocess.TimeoutExpired: process.kill()
        win32api.CloseHandle(mutex)

def install():
    install_dependencies()
    # Install the desktop development tools using Windows' package manager.
    import shutil
    winget=shutil.which('winget')
    if not winget:
        raise RuntimeError('Windows App Installer (winget) is required. Install it from Microsoft Store, then retry Hermes setup.')
    for package in ('Git.Git','OpenJS.NodeJS.LTS','Microsoft.VisualStudioCode'):
        from windows_dependencies import install as install_dependency
        install_dependency(package)
    prepare(); startup(); (CONFIG_DIR/'stop').unlink(missing_ok=True); start()
    for _ in range(180):
        if all(check_url(p) for p in (3000,8765,8766)):
            print('Hermes services are ready.',flush=True); return
        time.sleep(2)
    raise RuntimeError('Services did not become ready. Open the logs in '+str(DATA_DIR))

def verify():
    failed=[]
    for port in (3000,8765,8766):
        okay=check_url(port); print(f'Port {port}: '+('ready' if okay else 'FAILED'),flush=True)
        if not okay: failed.append(port)
    from bootstrap_openwebui import readiness
    state=readiness(); print('Owner account: '+str(state['owner_exists']))
    if not state['owner_exists']: failed.append('owner')
    import sqlite3
    if state['owner_exists']:
        with closing(sqlite3.connect(openwebui_data_dir()/'webui.db')) as db, db:
            count=db.execute("SELECT count(*) FROM model WHERE id IN ('hermes-v4','hermes-cloud-preview','hermes-gamma')").fetchone()[0]
            specs=json.loads(db.execute("SELECT specs FROM tool WHERE id='hermes_v4'").fetchone()[0])
        print(f'Model presets: {count}/3')
        if count!=3: failed.append('presets')
        names={item['name'] for item in specs}
        required={'create_personal_goal','draft_personal_mission','create_agent_routine','get_personal_command_center'}
        print(f'Hermes tools: {len(names)}')
        if not required <= names: failed.append('v8-tools')
    if failed: raise RuntimeError('Verification failed: '+str(failed))
    print('Local checks passed. Cloud chat, voice and phone access require your provider keys and hands-on testing.')

if __name__=='__main__':
    try:
        {'install':install,'upgrade':upgrade,'verify':verify,'supervise':supervise,'start':start}[sys.argv[1]]()
    except Exception as exc:
        print(str(exc),flush=True); raise
