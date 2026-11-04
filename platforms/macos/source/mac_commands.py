"""Native macOS implementation of the desktop command boundary."""
import subprocess as native
from subprocess import *
import time

ALIASES={'xed':'TextEdit','nemo':'Finder','gnome-calculator':'Calculator','google-chrome':'Google Chrome','firefox':'Firefox'}

def windows():
    import Quartz as Q
    rows=Q.CGWindowListCopyWindowInfo(Q.kCGWindowListOptionOnScreenOnly|Q.kCGWindowListExcludeDesktopElements,Q.kCGNullWindowID)
    return [{'id':hex(w[Q.kCGWindowNumber]),'class':w.get(Q.kCGWindowOwnerName,''),
             'title':w.get(Q.kCGWindowName,''),'pid':w[Q.kCGWindowOwnerPID]}
            for w in rows if w.get(Q.kCGWindowLayer)==0 and w.get(Q.kCGWindowName)]

def ax_get(element,name):
    import ApplicationServices as A
    error,value=A.AXUIElementCopyAttributeValue(element,name,None)
    if error: raise RuntimeError('Accessibility attribute unavailable: '+name)
    return value

def window_ref(handle):
    import ApplicationServices as A
    from platform_support import require_x11_automation
    require_x11_automation()
    record=next((w for w in windows() if int(w['id'],16)==handle),None)
    if record is None: raise RuntimeError('Window no longer exists')
    app=A.AXUIElementCreateApplication(record['pid'])
    matches=[w for w in ax_get(app,'AXWindows') if ax_get(w,'AXTitle')==record['title']]
    if len(matches)!=1: raise RuntimeError('Ambiguous window title; no input was sent')
    return app,matches[0],record

def focus(handle):
    import ApplicationServices as A
    from AppKit import NSRunningApplication, NSApplicationActivateIgnoringOtherApps, NSWorkspace
    app,window,record=window_ref(handle)
    NSRunningApplication.runningApplicationWithProcessIdentifier_(record['pid']).activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
    if A.AXUIElementPerformAction(window,'AXRaise'): raise RuntimeError('Could not raise window')
    for _ in range(20):
        if NSWorkspace.sharedWorkspace().frontmostApplication().processIdentifier()==record['pid'] and ax_get(app,'AXFocusedWindow')==window: return
        time.sleep(.05)
    raise RuntimeError('Window focus could not be verified; no text was sent')

def key(shortcut):
    import Quartz as Q
    mapping={'q':12,'a':0,'s':1,'c':8,'v':9,'x':7,'z':6,'f':3,'l':37,'t':17,'w':13,'n':45,
             'return':36,'enter':36,'tab':48,'space':49,'escape':53,'esc':53,'backspace':51,
             'delete':117,'left':123,'right':124,'down':125,'up':126,'home':115,'end':119}
    modifiers={'ctrl':Q.kCGEventFlagMaskControl,'control':Q.kCGEventFlagMaskControl,'alt':Q.kCGEventFlagMaskAlternate,
               'shift':Q.kCGEventFlagMaskShift,'super':Q.kCGEventFlagMaskCommand,'cmd':Q.kCGEventFlagMaskCommand,'command':Q.kCGEventFlagMaskCommand}
    parts=shortcut.lower().split('+'); flags=0
    for part in parts[:-1]:
        if part not in modifiers: raise ValueError('Unsupported key modifier')
        flags|=modifiers[part]
    if parts[-1] not in mapping: raise ValueError('Unsupported key')
    for down in (True,False):
        event=Q.CGEventCreateKeyboardEvent(None,mapping[parts[-1]],down)
        Q.CGEventSetFlags(event,flags); Q.CGEventPost(Q.kCGHIDEventTap,event)

def type_unicode(text):
    import Quartz as Q
    for chunk in (text[i:i+20] for i in range(0,len(text),20)):
        event=Q.CGEventCreateKeyboardEvent(None,0,True)
        Q.CGEventKeyboardSetUnicodeString(event,len(chunk.encode('utf-16-le'))//2,chunk)
        Q.CGEventPost(Q.kCGHIDEventTap,event)
        release=Q.CGEventCreateKeyboardEvent(None,0,False)
        Q.CGEventKeyboardSetUnicodeString(release,len(chunk.encode('utf-16-le'))//2,chunk)
        Q.CGEventPost(Q.kCGHIDEventTap,release)

def desktop_call(argv):
    import Quartz as Q
    import ApplicationServices as A
    from AppKit import NSWorkspace
    from platform_support import require_x11_automation
    require_x11_automation()
    program,*args=argv
    if program=='wmctrl':
        if args==['-lx']: return '\n'.join(f"{w['id']} 0 {w['class'].replace(' ','-')} mac {w['title']}" for w in windows())
        if '-ia' in args: focus(int(args[1],16)); return ''
        if '-ic' in args:
            _,window,_=window_ref(int(args[1],16))
            if A.AXUIElementPerformAction(ax_get(window,'AXCloseButton'),'AXPress'): raise RuntimeError('Close failed')
            return ''
        if '-ir' in args:
            _,window,_=window_ref(int(args[1],16))
            if '-e' in args:
                _,x,y,w,h=map(int,args[-1].split(','))
                for name,kind,value in [('AXPosition',A.kAXValueCGPointType,(x,y)),('AXSize',A.kAXValueCGSizeType,(w,h))]:
                    if A.AXUIElementSetAttributeValue(window,name,A.AXValueCreate(kind,value)): raise RuntimeError('Window layout rejected')
                return ''
            if '-b' in args:
                zoom=ax_get(window,'AXZoomButton')
                if A.AXUIElementPerformAction(zoom,'AXPress'):
                    raise RuntimeError('The window rejected the zoom request')
                return ''
            raise RuntimeError('Unsupported macOS window operation')
    if program=='xdotool':
        action=args[0]
        if action=='getactivewindow':
            pid=NSWorkspace.sharedWorkspace().frontmostApplication().processIdentifier()
            focused=ax_get(A.AXUIElementCreateApplication(pid),'AXFocusedWindow'); title=ax_get(focused,'AXTitle')
            rows=[w for w in windows() if w['pid']==pid and w['title']==title]
            if len(rows)!=1: raise RuntimeError('Active window is ambiguous')
            return str(int(rows[0]['id'],16))
        if action=='windowactivate': focus(int(args[-1],0)); return ''
        if action=='windowminimize':
            _,window,_=window_ref(int(args[-1]))
            if A.AXUIElementSetAttributeValue(window,'AXMinimized',True): raise RuntimeError('Minimize failed')
            return ''
        if action=='getdisplaygeometry':
            bounds=Q.CGDisplayBounds(Q.CGMainDisplayID()); return f'{int(bounds.size.width)} {int(bounds.size.height)}'
        if action=='getmouselocation':
            p=Q.CGEventGetLocation(Q.CGEventCreate(None)); return f'X={int(p.x)}\nY={int(p.y)}'
        if action=='type': type_unicode(args[-1]); return ''
        if action=='key': key(args[-1]); return ''
        if action=='mousemove':
            p=(int(args[-2]),int(args[-1])); Q.CGEventPost(Q.kCGHIDEventTap,Q.CGEventCreateMouseEvent(None,Q.kCGEventMouseMoved,p,0)); return ''
        if action in ('click','mousedown','mouseup'):
            button=int(args[-1]); count=int(args[args.index('--repeat')+1]) if '--repeat' in args else 1
            if button in (4,5):
                Q.CGEventPost(Q.kCGHIDEventTap,Q.CGEventCreateScrollWheelEvent(None,Q.kCGScrollEventUnitLine,1,count if button==4 else -count)); return ''
            if button not in (1,3): raise ValueError('Only left/right mouse buttons supported')
            p=Q.CGEventGetLocation(Q.CGEventCreate(None)); right=button==3
            for _ in range(count):
                for down in ([True,False] if action=='click' else [action=='mousedown']):
                    kind=(Q.kCGEventRightMouseDown if down else Q.kCGEventRightMouseUp) if right else (Q.kCGEventLeftMouseDown if down else Q.kCGEventLeftMouseUp)
                    Q.CGEventPost(Q.kCGHIDEventTap,Q.CGEventCreateMouseEvent(None,kind,p,1 if right else 0))
            return ''
    raise RuntimeError('Unsupported macOS operation: '+str(argv))

def run(argv,**kwargs):
    if isinstance(argv,(list,tuple)) and argv[0] in ('wmctrl','xdotool'):
        try: return native.CompletedProcess(argv,0,desktop_call(argv),'')
        except Exception as exc:
            if kwargs.get('check'): raise native.CalledProcessError(1,argv,stderr=str(exc)) from exc
            return native.CompletedProcess(argv,1,'',str(exc))
    if isinstance(argv,(list,tuple)) and argv[:2]==['gio','trash']:
        from send2trash import send2trash
        send2trash(argv[2]); return native.CompletedProcess(argv,0,'','')
    if isinstance(argv,(list,tuple)) and argv[0]=='notify-send':
        from mac_native import notify
        notify(argv[1],argv[2]); return native.CompletedProcess(argv,0,'','')
    return native.run(argv,**kwargs)

def Popen(argv,**kwargs):
    if isinstance(argv,(list,tuple)) and argv[0] in ALIASES:
        argv=['/usr/bin/open','-a',ALIASES[argv[0]],*[a for a in argv[1:] if a!='--new-window']]
    return native.Popen(argv,**kwargs)
