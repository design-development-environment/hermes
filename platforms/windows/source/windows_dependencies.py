"""Install Windows helpers without confusing ownership with availability.

Hermes may remove a dependency only when it can prove that it installed the
exact unchanged package.  Failure to create that uninstall receipt must never
turn a successful third-party installation into a failed Hermes setup.
"""
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
NOT_FOUND=0x8A150014

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

def code(result):
    return result.returncode & 0xffffffff

def winget_run(arguments,attempts=3):
    """Retry transient winget failures while preserving the final exit code."""
    result=None
    for attempt in range(attempts):
        result=subprocess.run(arguments,capture_output=True)
        if result.returncode==0 or code(result)==NOT_FOUND:
            return result
        if attempt+1<attempts:
            print(f'winget failed (attempt {attempt+1}/{attempts}); retrying...',flush=True)
    return result

def inspect(package):
    """Return registry inventory or None when Windows cannot enumerate it."""
    try:
        return inventory(package)
    except (OSError,ValueError) as exc:
        print(package+': Windows package inventory is unavailable ('+str(exc)+')',flush=True)
        return None

def save_receipt(package,owned,entries=None,reason=''):
    STATE.mkdir(parents=True,exist_ok=True)
    target=STATE/(package+'.json'); temporary=target.with_suffix('.next')
    receipt={'package':package,'owned':bool(owned),'entries':entries or []}
    if reason: receipt['reason']=reason
    temporary.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    os.replace(temporary,target)

def install(package):
    if package not in PACKAGES: raise ValueError('Unknown package')
    before=inspect(package)
    if before:
        print(package+': using existing installation',flush=True)
        return
    winget=shutil.which('winget')
    if not winget: raise RuntimeError('Install Windows App Installer (winget), then retry.')
    # No registry match does not prove absence. A successful winget match is also preserved.
    probe=winget_run([winget,'list','--id',package,'--exact','--accept-source-agreements'])
    if probe.returncode==0:
        print(package+': existing package preserved',flush=True); return
    # APPINSTALLER_CLI_ERROR_NO_APPLICATIONS_FOUND. Network/source errors are not absence.
    if code(probe)!=NOT_FOUND:
        raise RuntimeError('Could not determine whether '+package+' is already installed; retry after fixing winget.')
    installed=winget_run([winget,'install','--id',package,'--exact','--source','winget',
                          '--accept-package-agreements','--accept-source-agreements'])
    if installed.returncode:
        raise subprocess.CalledProcessError(installed.returncode,installed.args,
                                            output=installed.stdout,stderr=installed.stderr)
    after=inspect(package)
    if after and before==[]:
        save_receipt(package,True,after)
        print(package+': installed with verified Hermes ownership',flush=True)
        return
    # Registry display names differ between package revisions. Verify actual
    # availability through winget, then continue without ever claiming removal.
    verified=winget_run([winget,'list','--id',package,'--exact','--accept-source-agreements'])
    if verified.returncode:
        raise RuntimeError(package+' reported a successful install but could not be detected afterward.')
    reason='installed successfully; automatic removal disabled because ownership could not be proven'
    save_receipt(package,False,after,reason)
    print(package+': '+reason,flush=True)

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
