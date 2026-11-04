"""Explicit compatibility boundary for existing desktop calls; no shell evaluation."""
import subprocess as native
import os
import time
from pathlib import Path
from subprocess import *

ALIASES = {'xed':'notepad.exe','nemo':'explorer.exe','gnome-calculator':'calc.exe','google-chrome':'msedge.exe'}

def windows():
    import win32gui, win32process, psutil
    result=[]
    def collect(handle, _):
        if win32gui.IsWindowVisible(handle) and win32gui.GetWindowText(handle):
            try:
                name=psutil.Process(win32process.GetWindowThreadProcessId(handle)[1]).name().lower()
            except psutil.Error:
                name=win32gui.GetClassName(handle)
            alias={'notepad.exe':'xed.xed','explorer.exe':'nemo','msedge.exe':'google-chrome'}.get(name,name)
            result.append({'id':hex(handle),'class':alias,'title':win32gui.GetWindowText(handle)})
    win32gui.EnumWindows(collect,None)
    return result

def focus(handle):
    import win32gui, win32con
    win32gui.ShowWindow(handle, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(handle)
    for _ in range(20):
        if win32gui.GetForegroundWindow()==handle:
            return
        time.sleep(.05)
    raise RuntimeError('Windows refused focus. No text was sent.')

def type_unicode(text):
    from pywinauto.keyboard import send_keys
    # VK_PACKET sends Unicode directly without changing the clipboard.
    escapes={'{':'{{}','}':'{}}','+':'{+}','^':'{^}','%':'{%}','~':'{~}','(':'{(}',')':'{)}'}
    send_keys(''.join(escapes.get(c,c) for c in text), with_spaces=True, with_tabs=True, with_newlines=True, pause=.001, vk_packet=True)

def key(shortcut):
    import pyautogui
    mapping={'return':'enter','super':'win','control':'ctrl','escape':'esc','prior':'pageup','next':'pagedown'}
    keys=[mapping.get(k.lower(),k.lower()) for k in shortcut.split('+')]
    if any(k not in pyautogui.KEYBOARD_KEYS for k in keys):
        raise ValueError('Unsupported keyboard shortcut')
    pyautogui.hotkey(*keys)

def desktop_call(argv):
    import win32gui, win32con, pyautogui
    from platform_support import require_x11_automation
    require_x11_automation()
    program, *args=argv
    if program=='wmctrl':
        if args==['-lx']:
            return '\n'.join(f"{w['id']} 0 {w['class']} windows {w['title']}" for w in windows())
        if '-ia' in args:
            focus(int(args[1],16)); return ''
        if '-ic' in args:
            win32gui.PostMessage(int(args[1],16),win32con.WM_CLOSE,0,0); return ''
        if '-ir' in args:
            handle=int(args[1],16)
            if '-e' in args:
                _,x,y,w,h=map(int,args[-1].split(',')); win32gui.MoveWindow(handle,x,y,w,h,True)
            elif '-b' in args:
                win32gui.ShowWindow(handle,win32con.SW_MAXIMIZE if args[-1].startswith('add') else win32con.SW_RESTORE)
            else:
                raise RuntimeError('Virtual desktop movement is not available through the supported Windows API')
            return ''
    if program=='xdotool':
        action=args[0]
        if action=='getactivewindow': return str(win32gui.GetForegroundWindow())
        if action=='getdisplaygeometry': return '%s %s' % tuple(pyautogui.size())
        if action=='getmouselocation':
            x,y=pyautogui.position(); return f'X={x}\nY={y}'
        if action=='windowactivate': focus(int(args[-1],0)); return ''
        if action=='windowminimize': win32gui.ShowWindow(int(args[-1]),win32con.SW_MINIMIZE); return ''
        if action=='type': type_unicode(args[-1]); return ''
        if action=='key': key(args[-1]); return ''
        if action=='mousemove': pyautogui.moveTo(int(args[-2]),int(args[-1]),duration=.1); return ''
        if action in ('mousedown','mouseup'):
            getattr(pyautogui,'mouseDown' if action=='mousedown' else 'mouseUp')(button={1:'left',2:'middle',3:'right'}[int(args[-1])]); return ''
        if action=='click':
            button=int(args[-1]); count=int(args[args.index('--repeat')+1]) if '--repeat' in args else 1
            if button in (4,5): pyautogui.scroll(count if button==4 else -count)
            else: pyautogui.click(button={1:'left',2:'middle',3:'right'}[button],clicks=count,interval=.08)
            return ''
    raise RuntimeError(f'Unsupported Windows desktop operation: {program} {args}')

def run(argv, **kwargs):
    if isinstance(argv,(list,tuple)) and argv[0] in ('wmctrl','xdotool'):
        try:
            return native.CompletedProcess(argv,0,desktop_call(argv),'')
        except Exception as exc:
            if kwargs.get('check'): raise native.CalledProcessError(1,argv,stderr=str(exc)) from exc
            return native.CompletedProcess(argv,1,'',str(exc))
    if isinstance(argv,(list,tuple)) and argv[0]=='notify-send':
        from windows_native import notify
        notify(argv[1],argv[2]); return native.CompletedProcess(argv,0,'','')
    if isinstance(argv,(list,tuple)) and argv[:2]==['gio','trash']:
        from send2trash import send2trash
        send2trash(argv[2]); return native.CompletedProcess(argv,0,'','')
    return native.run(argv,**kwargs)

def Popen(argv, **kwargs):
    if isinstance(argv,(list,tuple)):
        argv=list(argv)
        if argv[0] in ALIASES:
            argv[0]=ALIASES[argv[0]]
            argv=[a for a in argv if a!='--new-window']
        kwargs.pop('start_new_session',None)
    return native.Popen(argv,**kwargs)
