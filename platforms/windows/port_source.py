"""Apply the Windows-specific implementation to the isolated source snapshot."""
import ast
from pathlib import Path
ROOT=Path(__file__).parent/'source'

def replace_functions(name, replacements):
    path=ROOT/name; source=path.read_text(); lines=source.splitlines(keepends=True)
    nodes=[n for n in ast.parse(source).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in replacements]
    for n in reversed(nodes): lines[n.lineno-1:n.end_lineno]=[replacements[n.name].strip()+'\n']
    path.write_text(''.join(lines))

for path in ROOT.glob('*.py'):
    if path.name.startswith('windows_') or path.name=='platform_support.py': continue
    text=path.read_text().replace('import subprocess\n','import windows_commands as subprocess\n')
    text=text.replace('import subprocess as automation_subprocess','import windows_commands as automation_subprocess')
    text=text.replace('Path.home() / ".local/share/hermes"', '__import__("platform_support").DATA_DIR')
    text=text.replace('Path.home() / ".config/hermes/tool-token"', '__import__("pathlib").Path(__import__("os").environ["LOCALAPPDATA"]) / "Hermes/config/tool-token"')
    text=text.replace('Path.home() / ".local/share/hermes/managed-browser"','__import__("platform_support").DATA_DIR / "managed-browser"')
    path.write_text(text)
(ROOT/'platform_support.py').write_text('from windows_platform import *\n')

replace_functions('desktop.py',{'require_tool':'''def require_tool(name):
    if name in {'wmctrl','xdotool'}:
        require_x11_automation()
    elif not shutil.which(name):
        raise RuntimeError('Executable is not installed: ' + name)''',
 'get_windows':'''def get_windows():
    return subprocess.windows()'''})
p=ROOT/'desktop.py'; t=p.read_text(); t=t.replace('if not shutil.which(args.application):','if args.application not in subprocess.ALIASES and not shutil.which(args.application):'); p.write_text(t)
replace_functions('screenshot.py',{'capture_screen':'''def capture_screen():
    from PIL import ImageGrab
    from platform_support import require_x11_automation
    require_x11_automation()
    filename = 'hermes_' + uuid.uuid4().hex + '.png'
    destination = SCREENSHOT_DIR / filename
    ImageGrab.grab().save(destination)
    return {'success': True, 'filename': filename, 'path': str(destination), 'size_bytes':destination.stat().st_size, 'captured_at':datetime.now(timezone.utc).isoformat()}'''})

replace_functions('computer_control.py',{
'list_applications':'''def list_applications(query: str = '', limit: int = 100):
    from windows_native import applications
    return {'applications':[a for a in applications() if query.casefold() in a['name'].casefold()][:max(1,min(limit,200))]}''',
'launch_applications':'''def launch_applications(request: LaunchAppsRequest):
    from windows_native import applications
    available={a['id']:a for a in applications()}
    launched=[]
    for app_id in request.applications:
        if app_id in available:
            os.startfile(available[app_id]['path'])
        elif app_id in subprocess.ALIASES or app_id in {'notepad.exe','calc.exe','explorer.exe'}:
            subprocess.Popen([subprocess.ALIASES.get(app_id,app_id)])
        else:
            raise HTTPException(404,'Use an application ID from list_installed_applications')
        launched.append({'application':app_id})
    return {'success':True,'launched':launched}''',
'open_target':'''def open_target(request: OpenTargetRequest):
    parsed=urlparse(request.target)
    if parsed.scheme in {'https','http'}:
        import webbrowser
        webbrowser.open(request.target)
    else:
        target=writable_path(request.target)
        os.startfile(str(target))
    return {'success':True,'target':request.target}''',
'run_terminal':'''def run_terminal(request: TerminalRequest):
    from platform_support import CONFIG_DIR
    if not (CONFIG_DIR / 'allow-terminal').is_file():
        raise HTTPException(403,'Enable Windows command execution in the Hermes setup window first. Windows commands run with your account permissions and are not sandboxed.')
    cwd=writable_path(request.cwd)
    if not cwd.is_dir(): raise HTTPException(400,'Working directory is not a folder')
    name=Path(request.program).stem.lower()
    if name not in ALLOWED_COMMANDS | {'powershell','pwsh','cmd'}:
        raise HTTPException(403,'Program is not in the development allowlist')
    executable=shutil.which(request.program)
    if not executable: raise HTTPException(404,'Executable is not installed')
    if Path(executable).suffix.lower() in {'.cmd','.bat'}:
        raise HTTPException(403,'Batch wrappers are not accepted; invoke their underlying executable directly')
    import windows_native
    return windows_native.run_command([executable,*request.arguments],cwd,request.timeout_seconds)''',
'system_status':'''def system_status():
    import platform, psutil
    disk=shutil.disk_usage(HOME)
    return {'hostname':platform.node(),'system':'Windows','release':platform.release(),'uptime_seconds':int(time.time()-psutil.boot_time()),'disk':{'total':disk.total,'used':disk.used,'free':disk.free},'writable_roots':[str(p) for p in WRITE_ROOTS],'platform':platform_status()}''',
'running_processes':'''def running_processes(query: str = '', limit: int = 100):
    import psutil
    rows=[]
    for p in psutil.process_iter(['pid','name','memory_percent']):
        if query.casefold() in (p.info['name'] or '').casefold(): rows.append(p.info)
    return {'processes':rows[:max(1,min(limit,200))]}''',
'notify':'''def notify(title: str, message: str):
    from windows_native import notify
    notify(title,message)
    return {'success':True}'''})

# Browser orchestration uses an isolated Edge/Chrome profile in the user's session.
p=ROOT/'browser_control.py'; t=p.read_text(); start=t.index('    started = subprocess.run(',t.index('def start_or_reuse_managed_browser')); end=t.index('    for _ in range(30):',start)
t=t[:start]+'''    from managed_browser_launcher import command
    args, environment = command()
    subprocess.Popen(args, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
'''+t[end:]; p.write_text(t)
p=ROOT/'managed_browser_launcher.py'; t=p.read_text().replace('current_session != "x11"','current_session not in {"x11", "windows"}'); p.write_text(t)
replace_functions('maintenance_control.py',{'service_status':'''def service_status(name: str, *, user=True):
    from windows_native import service_status
    return service_status(name)'''})
# Clipboard and OS settings retain the existing API schemas.
replace_functions('graphical_control.py',{
'graphical_readiness':'''def graphical_readiness():
    return platform_status()''',
'read_clipboard':'''def read_clipboard(request: ClipboardReadRequest):
    import pyperclip
    return {'success':True,'text':pyperclip.paste()}''',
'write_clipboard':'''def write_clipboard(request: ClipboardWriteRequest):
    import pyperclip
    pyperclip.copy(request.text)
    return {'success':True}''',
'monitor_layout':'''def monitor_layout():
    import win32api
    return {'monitors':[win32api.GetMonitorInfo(m[0]) for m in win32api.EnumDisplayMonitors()]}''',
'network_status':'''def network_status():
    import psutil
    return {'interfaces':{k:v._asdict() for k,v in psutil.net_if_stats().items()}}''',
'open_settings':'''def open_settings(request: SettingsPanelRequest):
    os.startfile('ms-settings:')
    return {'success':True}''',
'lock_desktop':'''def lock_desktop(request: ConfirmedRequest):
    if not request.confirm: raise HTTPException(400,'Confirmation required')
    import ctypes
    if not ctypes.windll.user32.LockWorkStation(): raise HTTPException(500,'Windows could not lock the desktop')
    return {'success':True}''',
**{name:f'''def {name}({signature}):
    raise HTTPException(501, 'This Linux desktop feature has not yet been ported to Windows: {name}')''' for name,signature in {
'get_power_policy':'','enable_keep_awake':'request: ConfirmedRequest','audio_status':'','set_audio_volume':'request: VolumeRequest','set_audio_mute':'request: MuteRequest','media_players':'','control_media':'request: MediaRequest','list_workspaces':'','switch_workspace':'request: WorkspaceRequest','move_window_to_workspace':'request: WindowWorkspaceRequest'}.items()}})

p=ROOT/'model_instructions.txt'; p.write_text(p.read_text()+'''\nWINDOWS EDITION: The computer runs Windows. Use Windows paths returned by tools, Windows application IDs and PowerShell rather than Linux commands. List capabilities before attempting an OS-specific action. Terminal execution requires the owner's separate opt-in and is not sandboxed. Unsupported desktop tools return an explicit error; never claim they succeeded.\n''')
