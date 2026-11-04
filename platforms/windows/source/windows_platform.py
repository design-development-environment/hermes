"""Native Windows paths and interactive desktop capability discovery."""
import os
import platform
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'Hermes/data'
CONFIG_DIR = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'Hermes/config'

def normalized_arch(machine=None):
    return 'amd64' if (machine or platform.machine()).lower() in ('amd64', 'x86_64') else (machine or platform.machine()).lower()

def graphical_environment(base=None):
    return dict(os.environ if base is None else base)

def session_type(environ=None):
    return 'windows'

def require_x11_automation():
    import ctypes
    from ctypes import wintypes
    user32=ctypes.WinDLL('user32',use_last_error=True)
    user32.OpenInputDesktop.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    user32.OpenInputDesktop.restype=wintypes.HANDLE
    user32.CloseDesktop.argtypes=[wintypes.HANDLE]
    desktop=user32.OpenInputDesktop(0,False,0x0001)
    if not desktop:
        raise RuntimeError('Windows desktop is locked or unavailable. Sign in and unlock it.')
    user32.CloseDesktop(desktop)
    return graphical_environment()

def find_browser(preference='chromium'):
    relatives = ['Mozilla Firefox/firefox.exe'] if preference == 'firefox' else ['Google/Chrome/Application/chrome.exe', 'Microsoft/Edge/Application/msedge.exe']
    for base in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA'):
        for relative in relatives:
            candidate = Path(os.environ.get(base, 'C:/Program Files')) / relative
            if candidate.is_file():
                return str(candidate)
    return shutil.which('chrome') or shutil.which('msedge')

def xdg_user_directory(name):
    import winreg
    aliases = {'DESKTOP':'Desktop', 'DOCUMENTS':'Personal', 'DOWNLOAD':'{374DE290-123F-4565-9164-39C4925E467B}', 'PICTURES':'My Pictures', 'MUSIC':'My Music', 'VIDEOS':'My Video'}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as key:
            value = winreg.QueryValueEx(key, aliases[name])[0]
            return Path(os.path.expandvars(value)).resolve()
    except OSError:
        return (Path.home() / ('Downloads' if name == 'DOWNLOAD' else name.title())).resolve()

def writable_roots():
    return tuple(xdg_user_directory(n) for n in ('DESKTOP','DOCUMENTS','DOWNLOAD','PICTURES','MUSIC','VIDEOS')) + (PROJECT_ROOT,)

def openwebui_data_dir():
    return DATA_DIR / 'open-webui'

def screenshot_backend(environ=None):
    return 'Pillow ImageGrab'

def platform_status():
    import psutil
    return {'distribution': {'id':'windows','name':platform.platform(),'version':platform.version(),'debian_family':False},
            'architecture':normalized_arch(), 'architecture_supported':normalized_arch() == 'amd64',
            'memory_bytes':psutil.virtual_memory().total, 'storage_free_bytes':shutil.disk_usage(Path.home()).free,
            'cpu_count':os.cpu_count(), 'session':'windows', 'desktop':'Windows', 'browser':find_browser(),
            'screenshot_backend':screenshot_backend(), 'capabilities': {'cloud_ai':True,'files_terminal_code':True,
            'web_and_managed_browser':bool(find_browser()),'desktop_screenshot':True,'global_window_keyboard_mouse':True},
            'project_root':str(PROJECT_ROOT),'data_dir':str(DATA_DIR),'openwebui_data_dir':str(openwebui_data_dir())}

def supported_debian_family(release=None):
    return False
