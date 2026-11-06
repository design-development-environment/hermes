#!/usr/bin/env python3
"""Graphical first-run and repair flow for the Hermes Debian package."""

from __future__ import annotations

import os
import queue
import mac_commands as subprocess
import threading
import tkinter as tk
import webbrowser
import re
from pathlib import Path
from tkinter import scrolledtext, ttk
from tkinter import font as tkfont
from PIL import Image, ImageDraw, ImageTk


PAYLOAD = Path('/opt/hermes/payload')
ROOT = Path(__file__).resolve().parent
ASKPASS = '/opt/hermes/askpass.sh'
VERSION = '2.0.6'


class SummaryCard(tk.Canvas):
    """Compact grouped rows, using the same surface geometry as the controls."""
    def __init__(self, master, text=''):
        super().__init__(master, bg='#0d0d0d', highlightthickness=0, borderwidth=0, height=148)
        self.copy = text
        self.bind('<Configure>', lambda event: self.draw())

    def configure(self, cnf=None, **kwargs):
        self.copy = kwargs.pop('text', self.copy)
        kwargs.pop('wraplength', None)
        if kwargs or cnf:
            super().configure(cnf, **kwargs)
        self.draw()

    def draw(self):
        self.delete('all')
        width = max(200, self.winfo_width())
        rows = self.copy.split('\n\n')
        row_height = 50
        super().configure(height=len(rows)*row_height)
        rounded_rect(self, 0, 0, width, len(rows)*row_height, 12, '#19191b')
        for index, text in enumerate(rows):
            if index:
                self.create_line(18, index*row_height, width-18, index*row_height, fill='#29292c')
            self.create_text(18, index*row_height+25, text=text, width=width-36,
                             anchor='w', font=('Inter', 10), fill='#c7c7cc')


def rounded_rect(canvas, x, y, width, height, radius, color):
    """Antialiased UI surfaces shared by every rounded control."""
    width, height = max(1, round(width)), max(1, round(height))
    radius = min(radius, width / 2, height / 2)
    key = (width, height, radius, color)
    cache = getattr(canvas, '_surfaces', {})
    if key not in cache:
        surface = Image.new('RGBA', (width*4, height*4))
        ImageDraw.Draw(surface).rounded_rectangle((0, 0, width*4-1, height*4-1), radius=radius*4, fill=color)
        cache[key] = ImageTk.PhotoImage(surface.resize((width, height), Image.Resampling.LANCZOS), master=canvas)
        # Resizing windows must not retain an unbounded collection of surfaces.
        if len(cache) > 40:
            cache = {key: cache[key]}
        canvas._surfaces = cache
    canvas.create_image(round(x), round(y), image=cache[key], anchor='nw')


class CapsuleProgress(tk.Canvas):
    """Rounded indeterminate progress; never implies a fabricated percentage."""
    def __init__(self, master):
        super().__init__(master, height=12, bg='#0d0d0d', highlightthickness=0, borderwidth=0)
        self.timer = None
        self.position = 0.0
        self.direction = 1
        self.bind('<Configure>', lambda event: self.draw())
        self.bind('<Destroy>', lambda event: self.stop())

    def draw(self):
        self.delete('all')
        width = max(20, self.winfo_width())
        rounded_rect(self, 1, 3, width-2, 6, 3, '#29292b')
        if self.timer is not None:
            length = max(10, (width-8)*0.23)
            start = 4 + self.position * (width-8-length)
            rounded_rect(self, start, 3, length, 6, 3, '#0a84ff')

    def start(self, interval=30):
        if self.timer is None:
            self.timer = self.after(30, self.tick)
            self.draw()

    def tick(self):
        self.position = max(0, min(1, self.position + 0.018*self.direction))
        if self.position in (0, 1):
            self.direction *= -1
        self.timer = self.after(30, self.tick)
        self.draw()

    def stop(self):
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None
        if self.winfo_exists():
            self.draw()


class StepIndicator(tk.Canvas):
    def __init__(self, master, title):
        super().__init__(master, height=38, width=200, bg='#151515', highlightthickness=0, borderwidth=0)
        self.title = title

    def set_state(self, active, complete):
        self.delete('all')
        if active:
            rounded_rect(self, 0, 0, 200, 38, 10, '#29292b')
        self.create_oval(13, 15, 21, 23, fill='#0a84ff' if active else '#777777' if complete else '#39393b', outline='')
        self.create_text(34, 19, text=self.title, anchor='w', font=('Inter', 10),
                         fill='#f4f4f6' if active or complete else '#858589')


class StartupToggle(tk.Canvas):
    def __init__(self, master, variable):
        super().__init__(master, bg='#0d0d0d', height=54, highlightthickness=0, borderwidth=0, takefocus=1, cursor='hand2')
        self.variable = variable
        self.bind('<Configure>', lambda event: self.draw())
        self.bind('<Button-1>', self.toggle)
        self.bind('<space>', self.toggle)
        self.bind('<Return>', self.toggle)
        self.bind('<FocusIn>', lambda event: self.draw())
        self.bind('<FocusOut>', lambda event: self.draw())

    def toggle(self, event=None):
        self.focus_set()
        self.variable.set('secure' if self.variable.get() == 'appliance' else 'appliance')
        self.draw()
        return 'break'

    def draw(self):
        self.delete('all')
        width = max(240, self.winfo_width())
        enabled = self.variable.get() == 'appliance'
        rounded_rect(self, 0, 0, width, 54, 12, '#19191b')
        self.create_text(16, 18, text='Automatic desktop login', anchor='w', font=('Inter', 10), fill='#f4f4f6')
        self.create_text(16, 37, text='On · appliance mode' if enabled else 'Off · sign into macOS after boot', anchor='w', font=('Inter', 9), fill='#929296')
        if self.focus_get() == self:
            rounded_rect(self, width-64, 12, 50, 30, 15, '#80bdff')
        rounded_rect(self, width-62, 14, 46, 26, 13, '#0a84ff' if enabled else '#48484a')
        rounded_rect(self, width-40 if enabled else width-60, 16, 22, 22, 11, '#f4f4f6')


class RoundedButton(tk.Canvas):
    """Keyboard-accessible rounded button with distinct interaction states."""
    def __init__(self, master, text='', command=None, style=None, primary=False):
        super().__init__(master, height=36, bg='#0d0d0d', highlightthickness=0,
                         borderwidth=0, takefocus=1)
        self.label, self.callback = text, command
        self.primary, self.disabled = primary, False
        self.hovered, self.pressed = False, False
        self.typeface = tkfont.Font(family='Inter', size=10)
        self.bind('<Enter>', lambda e: self.interact(hovered=True))
        self.bind('<Leave>', lambda e: self.interact(hovered=False, pressed=False))
        self.bind('<ButtonPress-1>', self.press)
        self.bind('<ButtonRelease-1>', self.release)
        self.bind('<space>', self.keyboard)
        self.bind('<Return>', self.keyboard)
        self.bind('<FocusIn>', lambda e: self.draw())
        self.bind('<FocusOut>', lambda e: self.draw())
        self.draw()

    def interact(self, **values):
        for key, value in values.items():
            setattr(self, key, value)
        self.draw()

    def press(self, event):
        if not self.disabled:
            self.focus_set()
            self.interact(pressed=True)

    def release(self, event):
        activate = self.pressed and not self.disabled and 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height()
        self.interact(pressed=False)
        if activate and self.callback:
            self.callback()

    def keyboard(self, event):
        if not self.disabled and self.callback:
            self.callback()
        return 'break'

    def configure(self, cnf=None, **kwargs):
        if 'text' in kwargs:
            self.label = kwargs.pop('text')
        if 'command' in kwargs:
            self.callback = kwargs.pop('command')
        if 'state' in kwargs:
            self.disabled = kwargs.pop('state') == 'disabled'
            self.pressed = False
            super().configure(takefocus=not self.disabled)
        kwargs.pop('style', None)
        if kwargs or cnf:
            super().configure(cnf, **kwargs)
        if hasattr(self, 'typeface'):
            self.draw()

    def draw(self):
        width = max(88, self.typeface.measure(self.label) + 34)
        super().configure(width=width, cursor='' if self.disabled else 'hand2')
        self.delete('all')
        fill = '#0a84ff' if self.primary else '#29292b'
        if self.hovered:
            fill = '#2997ff' if self.primary else '#3a3a3c'
        if self.pressed:
            fill = '#0063cc'
        if self.disabled:
            fill = '#202022'
        if self.focus_get() == self and not self.disabled:
            rounded_rect(self, 0, 0, width, 36, 12, '#80bdff')
        rounded_rect(self, 2, 2, width-4, 32, 10, fill)
        self.create_text(width/2,18,text=self.label,font=self.typeface,
                         fill='#666668' if self.disabled else '#ffffff')


class Setup(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Hermes')
        self.geometry('1000x720')
        self.minsize(940, 700)
        self.configure(bg='#0d0d0d')
        icon_path = ROOT / 'branding/icon-dark.png'
        if icon_path.is_file():
            self.app_icon = tk.PhotoImage(file=str(icon_path)).subsample(8, 8)
            self.iconphoto(True, self.app_icon)
        self.events = queue.Queue()
        self.busy = False
        self.marker = __import__('platform_support').CONFIG_DIR / 'setup-complete'
        self.step = 6 if self.marker.exists() else 0
        self.mode = tk.StringVar(value='appliance')
        self.status = tk.StringVar(value='Ready to check this computer')
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Hermes.TFrame', background='#0d0d0d')
        self.option_add('*Font', ('Inter', 10))
        style.configure('Hermes.TLabel', background='#0d0d0d', foreground='#f4f4f6', font=('Inter', 10))
        style.configure('Hermes.TButton', background='#f4f4f6', foreground='#0d0d0d', padding=9)
        style.configure('Hermes.TRadiobutton', background='#0d0d0d', foreground='#f4f4f6', font=('Inter', 10))
        style.map('Hermes.TButton', background=[('active', '#dddddd'), ('disabled', '#343434')], foreground=[('disabled', '#888888')])
        style.configure('Horizontal.TProgressbar', background='#0a84ff', troughcolor='#222222', borderwidth=0, thickness=4)
        sidebar = tk.Frame(self, bg='#151515', width=235)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        brand = tk.Label(sidebar, text='HERMES', bg='#151515', fg='#f4f4f6', font=('Inter', 20, 'bold'))
        brand.pack(anchor='w', padx=26, pady=(36, 10))
        tk.Label(sidebar, text='Personal assistant', bg='#151515', fg='#888888', font=('Inter', 9)).pack(anchor='w', padx=26, pady=(0, 32))
        self.steps = []
        for name in ['Compatibility', 'Installation', 'Your account', 'Cloud connections', 'Startup & access', 'Verification', 'Ready']:
            label = StepIndicator(sidebar, name)
            label.pack(padx=16, pady=3)
            self.steps.append(label)
        tk.Label(sidebar, text='Anshul & Miheer\nAll rights reserved.', justify='left', bg='#151515', fg='#777777', font=('Inter', 9)).pack(side='bottom', anchor='w', padx=26, pady=28)
        main = tk.Frame(self, bg='#0d0d0d')
        main.pack(fill='both', expand=True)
        toolbar = tk.Frame(main, bg='#0d0d0d', height=54)
        toolbar.pack(fill='x')
        toolbar.pack_propagate(False)
        self.toolbar_title = tk.Label(toolbar, text='Hermes Installer', bg='#0d0d0d', fg='#d1d1d6', font=('Inter', 10, 'bold'))
        self.toolbar_title.pack(side='left', padx=30)
        RoundedButton(toolbar, text='About', command=self.about).pack(side='right', padx=24, pady=9)
        tk.Frame(main, height=1, bg='#222224').pack(fill='x')
        frame = ttk.Frame(main, padding=(30, 24, 30, 24), style='Hermes.TFrame')
        frame.pack(fill='both', expand=True)
        self.header = ttk.Label(frame, text='Welcome to Hermes', style='Hermes.TLabel', font=('Sans', 27, 'bold'))
        self.header.pack(anchor='w')
        logo_path = ROOT / 'logo-dark.png'
        if not logo_path.exists():
            logo_path = Path(__file__).resolve().parent / 'logo-dark.png'
        if logo_path.exists():
            self.wordmark = tk.PhotoImage(file=str(logo_path))
            self.header.configure(image=self.wordmark, text='')
            self.small_wordmark = self.wordmark.subsample(2, 2)
            brand.configure(image=self.small_wordmark, text='')
        ttk.Label(frame, text='Highly Efficient Real-time Machine for Everyday Support.', style='Hermes.TLabel').pack(anchor='w', pady=(0, 20))
        self.title_label = ttk.Label(frame, style='Hermes.TLabel', font=('Inter', 15, 'bold'))
        self.title_label.pack(anchor='w', pady=(0, 8))
        self.body = ttk.Label(frame, style='Hermes.TLabel', wraplength=620, justify='left')
        self.body.pack(anchor='w')
        self.choice = ttk.Frame(frame, style='Hermes.TFrame')
        self.choice.pack(fill='x', pady=10)
        self.content = ttk.Frame(frame, style='Hermes.TFrame')
        self.content.pack(fill='both', expand=True, pady=(14, 18))
        self.overview = SummaryCard(self.content, text='Desktop and applications\n\nFiles, documents and coding\n\nCloud models and remote access')
        self.overview.pack(fill='x', pady=8)
        self.log = scrolledtext.ScrolledText(self.content, height=6, bg='#0d0d0d', fg='#aaaaae', insertbackground='white', relief='flat', borderwidth=0, highlightthickness=0, padx=0, pady=12, font=('Inter', 10))
        self.log.vbar.configure(bg='#0d0d0d', troughcolor='#0d0d0d', activebackground='#555555', borderwidth=0, highlightthickness=0)
        self.log.configure(state='disabled')
        self.details_visible = False
        self.details = RoundedButton(frame, text='Show details', command=self.toggle_details)
        self.details.pack(anchor='w', pady=(0, 12))
        self.progress = CapsuleProgress(frame)
        self.progress.pack(fill='x', pady=(0, 14))
        ttk.Label(frame, textvariable=self.status, style='Hermes.TLabel').pack(anchor='w')
        row = ttk.Frame(frame, style='Hermes.TFrame')
        row.pack(fill='x', pady=(12, 0))
        self.back = RoundedButton(row, text='Back', command=self.previous)
        self.back.pack(side='left')
        self.action = RoundedButton(row, text='Continue', command=self.advance, primary=True)
        self.action.pack(side='right')
        self.extra = RoundedButton(row, text='')
        self.extra.pack(side='right', padx=8)
        self.after(100, self.poll)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.render()
        self.append('Your assistant, ready for everyday work.\n\n  Desktop and application control\n  Files, documents and coding tools\n  Alpha, Beta and Gamma cloud presets\n  Secure remote access with Tailscale\n  Automatic startup and maintenance\n\nInstallation details will appear here as setup progresses.')

    def dialog(self, title, message, confirm=False):
        """Window-modal sheet with native window management and safe dismissal."""
        sheet = tk.Toplevel(self)
        sheet.title(title)
        sheet.transient(self)
        sheet.configure(bg='#0d0d0d')
        sheet.resizable(False, False)
        accepted = [False]
        def finish(value=False):
            accepted[0] = value
            sheet.destroy()
        shell = tk.Frame(sheet, bg='#0d0d0d', padx=26, pady=24)
        shell.pack(fill='both', expand=True)
        if hasattr(self, 'small_wordmark'):
            tk.Label(shell, image=self.small_wordmark, bg='#0d0d0d').pack(anchor='w', pady=(0, 18))
        tk.Label(shell, text=title, bg='#0d0d0d', fg='#f4f4f6', font=('Inter', 12, 'bold'), anchor='w').pack(fill='x')
        tk.Label(shell, text=message, bg='#0d0d0d', fg='#b3b3b8', justify='left', wraplength=390, font=('Inter', 10)).pack(anchor='w', pady=(10, 22))
        actions = tk.Frame(shell, bg='#0d0d0d')
        actions.pack(fill='x')
        if confirm:
            RoundedButton(actions, text='Cancel', command=finish).pack(side='left')
        done = RoundedButton(actions, text='Enable' if confirm else 'Done', command=lambda: finish(True), primary=True)
        done.pack(side='right')
        sheet.protocol('WM_DELETE_WINDOW', finish)
        sheet.bind('<Escape>', lambda event: finish())
        sheet.update_idletasks()
        sheet.geometry(f'+{self.winfo_rootx()+(self.winfo_width()-sheet.winfo_reqwidth())//2}+{self.winfo_rooty()+100}')
        sheet.wait_visibility()
        sheet.grab_set()
        done.focus_set() if not confirm else sheet.focus_set()
        self.wait_window(sheet)
        return accepted[0]

    def about(self):
        self.dialog('Hermes · ' + VERSION,
                    'Highly Efficient Real-time Machine for Everyday Support.\n\n'
                    'Anshul & Miheer\nAll rights reserved.\n\n'
                    'anshul.pandhare@mitwpu.edu.in\nmiheer.sabnis@mitwpu.edu.in')

    def toggle_details(self):
        self.details_visible = not self.details_visible
        if self.details_visible:
            self.overview.pack_forget()
            self.log.pack(fill='both', expand=True)
        else:
            self.log.pack_forget()
            self.overview.pack(fill='x', pady=8)
        self.details.configure(text='Hide details' if self.details_visible else 'Show details')

    def close(self):
        if self.busy:
            self.dialog('Installation running', 'Please keep Hermes open until the current operation finishes.')
            return
        self.destroy()

    def append(self, line):
        self.log.configure(state='normal')
        self.log.insert('end', line.rstrip() + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def command(self, argv, on_success=None):
        if self.busy:
            return
        self.busy = True
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.configure(state='disabled', font=('Monospace', 9))
        self.progress.start(12)
        self.action.configure(state='disabled')
        self.back.configure(state='disabled')
        self.status.set('Working…')
        env = __import__('mac_runtime').environment()

        def run():
            try:
                proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, env=env)
                for line in proc.stdout:
                    self.events.put(('line', line))
                self.events.put(('done', proc.wait(), on_success))
            except Exception as exc:
                self.events.put(('error', str(exc)))

        threading.Thread(target=run, daemon=True).start()

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == 'line':
                    self.append(event[1])
                    if self.step == 4:
                        match = re.search(r'https://login\.tailscale\.com/\S+', event[1])
                        if match:
                            webbrowser.open(match.group(0))
                elif event[0] == 'done':
                    self.busy = False
                    self.progress.stop()
                    if event[1] == 0:
                        self.status.set('Completed')
                        if event[2]:
                            event[2]()
                    else:
                        self.status.set('Needs attention — see details above, then retry')
                        if not self.details_visible:
                            self.toggle_details()
                    self.render()
                else:
                    self.busy = False
                    self.progress.stop()
                    self.status.set('Error: ' + event[1])
                    if not self.details_visible:
                        self.toggle_details()
                    self.render()
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def go(self, step):
        self.step = step
        self.render()

    def previous(self):
        self.go(max(0, self.step - 1))

    def preflight(self):
        if not PAYLOAD.joinpath('install.sh').is_file():
            self.dialog('Setup files unavailable', 'The Hermes package payload is missing. Reinstall the .deb package.')
            return
        self.command(['python3', str(PAYLOAD / 'portable_preflight.py')], lambda: self.go(1))

    def install(self):
        self.command(['bash', str(PAYLOAD / 'install.sh'), '--with-tailscale', '--install-dir', str(ROOT)], lambda: self.go(2))

    def bootstrap(self):
        interpreter = ROOT / '.venv/bin/python'
        self.command([str(interpreter), str(ROOT / 'bootstrap_openwebui.py')], lambda: self.go(3))

    def tailscale(self):
        # Login URLs printed by Tailscale can be pasted into the browser.
        self.command(['sudo', '-A', 'tailscale', 'up'], self.serve)

    def serve(self):
        self.command(['sudo', '-A', 'tailscale', 'serve', '--bg', '--yes', '3000'])

    def startup(self):
        mode = 'enable' if self.mode.get() == 'appliance' else 'disable'
        if mode == 'enable' and not self.dialog('Enable automatic login?', 'Anyone with physical access to this computer will be able to use its desktop after boot.', confirm=True):
            return
        self.command(['sudo', '-A', '/opt/hermes/hermes-autologin', mode, os.environ['USER']], lambda: self.go(5))

    def check(self):
        self.command(['python3', '/opt/hermes/hermes-setup-check'], self.complete)

    def complete(self):
        self.marker.parent.mkdir(parents=True, exist_ok=True)
        self.marker.write_text('Verified installation\n')
        self.go(6)

    def advance(self):
        if self.step == 0:
            self.preflight()
        elif self.step == 1:
            self.install()
        elif self.step == 2:
            self.bootstrap()
        elif self.step == 3:
            self.command([str(ROOT / '.venv/bin/python'), str(ROOT / 'bootstrap_openwebui.py')], lambda: self.go(4))
        elif self.step == 4:
            self.startup()
        elif self.step == 5:
            self.check()
        else:
            webbrowser.open('http://127.0.0.1:3000')

    def render(self):
        pages = [
            ('Check your computer', 'Set up Hermes on your amd64 Linux desktop. We will check available storage, your desktop session and system requirements before installation.', 'Run check'),
            ('Install Hermes', 'This downloads and installs the required packages, Python runtime, Open WebUI, Hermes services and Tailscale. It can take time. Linux will ask for your administrator password in a graphical prompt.', 'Install'),
            ('Create your account', 'Open Hermes in your browser and create the first Open WebUI owner account. Return here and click Continue to add the Alpha, Beta and Gamma model presets and the Hermes tools.', 'Continue'),
            ('Cloud accounts', 'In Open WebUI Admin Settings → Connections, add an OpenAI-compatible connection using https://integrate.api.nvidia.com/v1, Bearer authentication, your NVIDIA key, and Chat Completions. In Audio settings, add Deepgram for speech recognition and ElevenLabs for spoken replies if wanted. Test a chat with each Hermes model before continuing.', 'Continue'),
            ('Remote access and startup', 'Connect Tailscale using the button below and approve its sign-in link. Then enable Tailscale Serve. Choose whether the desktop logs in automatically at boot.', 'Apply startup choice'),
            ('Final check', 'This rechecks this machine. Test a chat, file read, browser action, screenshot, voice and phone access in Open WebUI before relying on Hermes remotely.', 'Run check'),
            ('Hermes is installed', 'Hermes services are set to start at boot. Open the Hermes shortcut to use it. Log into Tailscale on your phone to access its Tailscale address. Desktop control requires an active unlocked desktop session.', 'Finish'),
        ]
        title, body, button = pages[self.step]
        self.toolbar_title.configure(text=f'Hermes Installer   ·   {self.step+1} of 7')
        if self.step == 6:
            button = 'Open Hermes'
        for index, label in enumerate(self.steps):
            label.set_state(index == self.step, index < self.step)
        summaries = [
            'Desktop and applications\n\nFiles, documents and coding\n\nCloud models and remote access',
            'Keep this window open during installation.\n\nYou can view technical details at any time.',
            'Your account keeps your conversations and settings together.',
            'Connect your provider accounts in Open WebUI.\n\nNever paste API keys into chat.',
            'Your assistant will start automatically when you sign in.',
            'We will check services, presets and remote access.',
            'Your workspace is ready.']
        self.overview.configure(text=summaries[self.step], wraplength=620)
        self.title_label.configure(text=title)
        self.body.configure(text=body)
        self.action.configure(text=button, state='disabled' if self.busy else 'normal')
        self.back.configure(state='disabled' if self.busy or self.step == 0 else 'normal')
        for child in self.choice.winfo_children():
            child.destroy()
        self.choice.pack_forget()
        if self.step == 4:
            self.choice.pack(fill='x', pady=10, before=self.content)
            StartupToggle(self.choice, self.mode).pack(fill='x')
        self.extra.pack_forget()
        if self.step == 2:
            self.extra.configure(text='Open Hermes', command=lambda: webbrowser.open('http://127.0.0.1:3000'))
            self.extra.pack(side='right', padx=8)
        elif self.step == 3:
            self.extra.configure(text='Open settings', command=lambda: webbrowser.open('http://127.0.0.1:3000'))
            self.extra.pack(side='right', padx=8)
        elif self.step == 4:
            self.extra.configure(text='Connect Tailscale', command=self.tailscale)
            self.extra.pack(side='right', padx=8)
            RoundedButton(self.choice, text='Enable Tailscale Serve', command=self.serve).pack(anchor='w', pady=8)


if __name__ == '__main__':
    Setup().mainloop()
