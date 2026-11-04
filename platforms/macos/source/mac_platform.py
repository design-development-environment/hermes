"""Apple Silicon paths and real macOS permission checks."""
import os
import platform
import shutil
from pathlib import Path
PROJECT_ROOT=Path(__file__).resolve().parent
BASE=Path.home()/'Library/Application Support/Hermes'
DATA_DIR=BASE/'data'
CONFIG_DIR=BASE/'config'

def normalized_arch(machine=None):
    value=(machine or platform.machine()).lower()
    return {'aarch64':'arm64','x86_64':'amd64'}.get(value,value)

def graphical_environment(base=None): return dict(os.environ if base is None else base)
def session_type(environ=None): return 'macos'
def supported_debian_family(release=None): return False

def require_x11_automation():
    import ApplicationServices as AX
    import Quartz
    state=Quartz.CGSessionCopyCurrentDictionary() or {}
    if not AX.AXIsProcessTrusted() or state.get('CGSSessionScreenIsLocked',False):
        raise RuntimeError('Grant Accessibility permission to the Hermes Python runtime and unlock your Mac.')
    return graphical_environment()

def find_browser(preference='chromium'):
    choices=['Firefox.app/Contents/MacOS/firefox'] if preference=='firefox' else [
        'Google Chrome.app/Contents/MacOS/Google Chrome','Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
        'Chromium.app/Contents/MacOS/Chromium']
    for root in (Path('/Applications'),Path.home()/'Applications'):
        for relative in choices:
            if (root/relative).is_file(): return str(root/relative)
    return None

def xdg_user_directory(name):
    return Path.home()/({'DOWNLOAD':'Downloads','VIDEOS':'Movies'}.get(name,name.title()))

def writable_roots():
    return tuple(xdg_user_directory(n) for n in ('DESKTOP','DOCUMENTS','DOWNLOAD','PICTURES','MUSIC','VIDEOS'))+(PROJECT_ROOT,)

def openwebui_data_dir(): return DATA_DIR/'open-webui'
def screenshot_backend(environ=None): return 'macOS screencapture'

def platform_status():
    import psutil
    import Quartz
    import ApplicationServices as AX
    return {'distribution':{'id':'macos','name':platform.platform(),'version':platform.mac_ver()[0],'debian_family':False},
            'architecture':normalized_arch(),'architecture_supported':normalized_arch()=='arm64',
            'memory_bytes':psutil.virtual_memory().total,'storage_free_bytes':shutil.disk_usage(Path.home()).free,
            'cpu_count':os.cpu_count(),'session':'macos','desktop':'macOS','browser':find_browser(),
            'capabilities':{'cloud_ai':True,'files_terminal_code':True,'web_and_managed_browser':bool(find_browser()),
                            'desktop_screenshot':bool(Quartz.CGPreflightScreenCaptureAccess()),
                            'global_window_keyboard_mouse':bool(AX.AXIsProcessTrusted())},
            'project_root':str(PROJECT_ROOT),'data_dir':str(DATA_DIR),'openwebui_data_dir':str(openwebui_data_dir())}
