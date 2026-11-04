"""Record ownership only after a proven fresh package installation."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

STATE=Path(__file__).resolve().parent.parent/'install-state'
PACKAGES={'Git.Git':r'Git(?: version)? \d.*', 'OpenJS.NodeJS.LTS':r'Node\.js',
          'Microsoft.VisualStudioCode':r'Microsoft Visual Studio Code(?: \(User\))?',
          'Tailscale.Tailscale':r'Tailscale'}

def inventory(package):
    import winreg
    entries=[]
    base=r'Software\Microsoft\Windows\CurrentVersion\Uninstall'
    for hive,label in ((winreg.HKEY_CURRENT_USER,'user'),(winreg.HKEY_LOCAL_MACHINE,'machine')):
        for view in (winreg.KEY_WOW64_64KEY,winreg.KEY_WOW64_32KEY):
            try: root=winreg.OpenKey(hive,base,0,winreg.KEY_READ|view)
            except FileNotFoundError: continue
            with root:
                for index in range(winreg.QueryInfoKey(root)[0]):
                    name=winreg.EnumKey(root,index)
                    with winreg.OpenKey(root,name) as key:
                        def value(field):
                            try: return str(winreg.QueryValueEx(key,field)[0])
                            except FileNotFoundError: return ''
                        display=value('DisplayName')
                        if re.fullmatch(PACKAGES[package],display,re.I):
                            entries.append({'hive':label,'view':view,'key':name,'name':display,
                                            'version':value('DisplayVersion'),'location':value('InstallLocation')})
    return sorted(entries,key=lambda e:(e['hive'],e['view'],e['key']))

def load_receipt(package):
    try:
        receipt=json.loads((STATE/(package+'.json')).read_text(encoding='utf-8'))
        if receipt.get('package')==package and receipt.get('owned') is True and receipt.get('entries'):
            return receipt
    except (OSError,ValueError,AttributeError): pass
    return None

def eligible(receipt,current):
    return bool(receipt and receipt.get('owned') is True and receipt.get('entries')==current and current)

def install(package):
    if package not in PACKAGES: raise ValueError('Unknown package')
    before=inventory(package)  # Any inventory error aborts rather than guessing ownership.
    if before:
        print(package+': using existing installation',flush=True)
        return
    winget=shutil.which('winget')
    if not winget: raise RuntimeError('Install Windows App Installer (winget), then retry.')
    # No registry match does not prove absence. A successful winget match is also preserved.
    probe=subprocess.run([winget,'list','--id',package,'--exact','--accept-source-agreements'],capture_output=True)
    if probe.returncode==0:
        print(package+': existing package preserved',flush=True); return
    # APPINSTALLER_CLI_ERROR_NO_APPLICATIONS_FOUND. Network/source errors are not absence.
    if probe.returncode & 0xffffffff != 0x8A150014:
        raise RuntimeError('Could not determine whether '+package+' is already installed; retry after fixing winget.')
    subprocess.run([winget,'install','--id',package,'--exact','--source','winget',
                    '--accept-package-agreements','--accept-source-agreements'],check=True)
    after=inventory(package)
    if not after: raise RuntimeError(package+' installed, but ownership could not be verified; automatic removal will be unavailable.')
    STATE.mkdir(parents=True,exist_ok=True)
    target=STATE/(package+'.json'); temporary=target.with_suffix('.next')
    temporary.write_text(json.dumps({'package':package,'owned':True,'entries':after},indent=2),encoding='utf-8')
    os.replace(temporary,target)

def remove(package):
    if package not in PACKAGES: raise ValueError('Unknown package')
    receipt=load_receipt(package)
    if not receipt:
        print(package+': no verified ownership record; kept',flush=True); return
    current=inventory(package)
    if not current:
        (STATE/(package+'.json')).unlink(); return
    if not eligible(receipt,current):
        print(package+': changed since installation; kept. Remove manually in Windows Settings if wanted.',flush=True)
        return
    winget=shutil.which('winget')
    if not winget: raise RuntimeError('winget is unavailable; dependencies were kept.')
    subprocess.run([winget,'uninstall','--id',package,'--exact','--source','winget',
                    '--accept-source-agreements','--disable-interactivity'],check=True)
    if inventory(package): raise RuntimeError(package+' remains installed. Removal was not confirmed.')
    (STATE/(package+'.json')).unlink()
    print(package+': removed',flush=True)

if __name__=='__main__':
    operation=sys.argv[1]
    if operation not in ('install','remove'): raise SystemExit('Invalid operation')
    for package in sys.argv[2:]:
        (install if operation=='install' else remove)(package)
