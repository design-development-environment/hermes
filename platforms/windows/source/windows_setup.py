"""Hermes V8 Windows setup and repair application."""
import os
import sys
import subprocess
import webbrowser
from pathlib import Path
from ui import Setup, RoundedButton
from platform_support import PROJECT_ROOT, CONFIG_DIR, DATA_DIR
from windows_runtime import environment, APP, PYTHON

class WindowsSetup(Setup):
    def __init__(self):
        super().__init__()
        # Kept personal data is not evidence that the runtime survived uninstall.
        if not (APP/'runtime/Scripts/open-webui.exe').is_file():
            self.go(0)

    def preflight(self):
        import platform, shutil
        if platform.system()!='Windows' or platform.machine().lower() not in ('amd64','x86_64'):
            self.dialog('Unsupported computer','This build requires 64-bit Windows 10 or Windows 11.'); return
        if shutil.disk_usage(APP).free<12*1024**3:
            self.dialog('More space needed','Please free at least 12 GB before continuing.'); return
        self.go(1)

    def install(self):
        self.command([str(PYTHON),str(PROJECT_ROOT/'windows_runtime.py'),'install'],lambda:self.go(2))

    def bootstrap(self):
        self.command([str(PYTHON),str(PROJECT_ROOT/'bootstrap_openwebui.py')],lambda:self.go(3))

    def tailscale(self):
        if (Path(os.environ['ProgramFiles'])/'Tailscale/tailscale.exe').exists():
            self.login_tailscale(); return
        self.command([str(PYTHON),str(PROJECT_ROOT/'windows_dependencies.py'),'install','Tailscale.Tailscale'],self.login_tailscale)

    def login_tailscale(self):
        self.command([str(Path(os.environ['ProgramFiles'])/'Tailscale/tailscale.exe'),'up'])

    def serve(self):
        self.command([str(Path(os.environ['ProgramFiles'])/'Tailscale/tailscale.exe'),'serve','--bg','--yes','3000'])

    def terminal(self):
        target=CONFIG_DIR/'allow-terminal'
        if target.exists():
            target.unlink(); self.dialog('Terminal disabled','Hermes can still manage files and applications.'); return
        if self.dialog('Enable Windows commands?','Commands can access everything your Windows account can access. The Linux command sandbox is not available in this build. Enable only for a trusted Hermes account.',confirm=True):
            target.parent.mkdir(parents=True,exist_ok=True); target.write_text('Explicit owner consent\n')

    def autologin(self):
        webbrowser.open('https://learn.microsoft.com/en-us/sysinternals/downloads/autologon')
        self.dialog('Automatic desktop login','Use Microsoft Autologon to enter your Windows credentials locally and enable automatic login. Hermes starts when you sign in. Windows credentials are never collected by this installer.')

    def startup(self):
        from windows_runtime import startup
        startup()
        if self.mode.get()=='appliance': self.autologin()
        self.go(5)

    def check(self):
        self.command([str(PYTHON),str(PROJECT_ROOT/'windows_runtime.py'),'verify'],self.complete)

    def advance(self):
        if self.step==3:
            self.command([str(PYTHON),str(PROJECT_ROOT/'bootstrap_openwebui.py')],lambda:self.go(4))
        else: super().advance()

    def render(self):
        super().render()
        text={0:'Set up Hermes V8 on Windows 10 or 11, 64-bit. Hermes uses cloud AI and authenticated tools on your Windows desktop. Allow at least 12 GB free space and a working internet connection.',
              1:'Install the pinned Python dependencies, Open WebUI and Hermes background processes. Downloads can take several minutes. Installation can be retried if a download fails.',
              4:'Hermes starts automatically when you sign into Windows. Connect Tailscale, then enable Tailscale Serve for phone access. Automatic login requires entering your Windows credentials in Microsoft Autologon.',
              5:'Check the local services, V8 agent tools and model presets. Then test cloud chat, goals, files, screenshots, browser control, voice and phone access.',
              6:'Hermes V8 is configured to start when you sign into Windows. Desktop control requires an unlocked session. Cloud services require your own API keys.'}
        if self.step in text: self.body.configure(text=text[self.step])
        if self.step==4:
            RoundedButton(self.choice,text='Terminal permission',command=self.terminal).pack(anchor='w',pady=4)
        if self.step==6:
            self.extra.configure(text='Open logs',command=lambda:os.startfile(str(DATA_DIR)))
            self.extra.pack(side='right',padx=8)

if __name__=='__main__':
    os.environ.update(environment())
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        for font in (PROJECT_ROOT/'branding').glob('*.otf'):
            ctypes.windll.gdi32.AddFontResourceExW(str(font),0x10,0)
    except Exception: pass
    WindowsSetup().mainloop()
