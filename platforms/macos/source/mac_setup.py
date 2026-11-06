"""Hermes macOS setup; native privacy permissions remain owner-controlled."""
import os
import platform
import shutil
import subprocess
import webbrowser
from pathlib import Path
from ui import Setup,RoundedButton
from platform_support import CONFIG_DIR,DATA_DIR,PROJECT_ROOT
from mac_runtime import PYTHON,environment

class MacSetup(Setup):
    def __init__(self):
        super().__init__()
        self.mode.set('secure')
        if not PYTHON.with_name('open-webui').exists(): self.go(0)

    def preflight(self):
        if platform.system()!='Darwin' or platform.machine()!='arm64':
            self.dialog('Unsupported computer','Use native Apple Silicon Python on macOS 14 or newer.'); return
        if int(platform.mac_ver()[0].split('.')[0])<14 or shutil.disk_usage(Path.home()).free<12*1024**3:
            self.dialog('Requirements','macOS 14 or newer and 12 GB free space are required.'); return
        self.go(1)

    def install(self):
        self.command([str(PYTHON),str(PROJECT_ROOT/'mac_runtime.py'),'install'],lambda:self.go(2))

    def bootstrap(self):
        self.command([str(PYTHON),str(PROJECT_ROOT/'bootstrap_openwebui.py')],lambda:self.go(3))

    def tailscale(self):
        webbrowser.open('https://tailscale.com/download/mac')
        self.dialog('Connect Tailscale','Install Tailscale from its official site, open it and sign in. Return here to enable Serve. Hermes does not collect your login credentials.')

    def serve(self):
        executable=shutil.which('tailscale')
        if not executable:
            candidate=Path('/Applications/Tailscale.app/Contents/MacOS/Tailscale')
            executable=str(candidate) if candidate.exists() else None
        if not executable:
            self.dialog('Install Tailscale first','Open Tailscale and complete its setup before enabling Serve.'); return
        self.command([executable,'serve','--bg','--yes','3000'])

    def permissions(self):
        subprocess.run(['/usr/bin/open','x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'],check=True)
        self.dialog('Desktop permissions','Grant Accessibility and Screen Recording to the Python runtime used by Hermes. Relaunch Hermes after changes if macOS requests it. Microphone access is granted to your browser for Open WebUI voice. The exact permission identity needs testing on a Mac.')

    def terminal(self):
        target=CONFIG_DIR/'allow-terminal'
        if target.exists(): target.unlink(); self.dialog('Terminal disabled','Command execution is now disabled.'); return
        if self.dialog('Enable command execution?','Commands run with your Mac account permissions. macOS does not provide the Linux command sandbox used by Hermes. Enable only for your trusted Hermes account.',confirm=True):
            target.parent.mkdir(parents=True,exist_ok=True); target.write_text('Explicit owner consent\n'); target.chmod(0o600)

    def startup(self): self.go(5)
    def check(self): self.command([str(PYTHON),str(PROJECT_ROOT/'mac_runtime.py'),'verify'],self.complete)

    def uninstall(self):
        from tkinter import messagebox
        if not messagebox.askyesno('Uninstall Hermes','Remove the Hermes runtime and automatic startup?',parent=self): return
        delete=messagebox.askyesno('Delete personal data?','Also permanently delete chats, API keys, settings and backups? Choose No to keep them. Your documents elsewhere are kept.',default='no',parent=self)
        argv=[str(PYTHON),str(PROJECT_ROOT/'mac_uninstall.py')]
        if delete: argv.append('--delete-data')
        self.command(argv,lambda:self.after(200,self.destroy))

    def advance(self):
        if self.step==3:
            self.command([str(PYTHON),str(PROJECT_ROOT/'bootstrap_openwebui.py')],lambda:self.go(4))
        else: super().advance()

    def render(self):
        super().render()
        descriptions={0:'Set up Hermes 2.0.2 on Apple Silicon with macOS 14 or newer. Internet and at least 12 GB free space are required.',
          1:'Install pinned dependencies, Open WebUI and Hermes in your user account. Cloud AI only; no local model weights are downloaded.',
          4:'Hermes starts after you log into your Mac. Grant desktop permissions, then connect Tailscale for remote access. Automatic Mac login is not configured.',
          5:'Verify local services, agent tools and presets, then test cloud chat, goals, files, browser control, screenshots and voice on this Mac.',
          6:'Hermes 2.0.2 is configured for startup at login. Keep your Mac awake and unlocked for desktop actions. Cloud services require your own API keys.'}
        if self.step in descriptions: self.body.configure(text=descriptions[self.step])
        if self.step==4:
            for child in self.choice.winfo_children(): child.destroy()
            RoundedButton(self.choice,text='Desktop permissions',command=self.permissions).pack(anchor='w',pady=3)
            RoundedButton(self.choice,text='Enable Tailscale Serve',command=self.serve).pack(anchor='w',pady=3)
            RoundedButton(self.choice,text='Terminal permission',command=self.terminal).pack(anchor='w',pady=3)
        if self.step==6:
            self.extra.configure(text='Uninstall',command=self.uninstall); self.extra.pack(side='right',padx=8)

if __name__=='__main__':
    os.environ.update(environment())
    MacSetup().mainloop()
