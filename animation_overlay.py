"""Transparent, non-interactive animation window above application controls."""
import ctypes
import ctypes.util
import sys
import platform
import tkinter as tk
import numpy as np
from PIL import ImageTk
from plots import BG

class AnimationOverlay:
    def __init__(self,app,parent):
        self.app=app;self.parent=parent;self.photo=None
        # Cocoa owns its pixels directly; do not put a Tk canvas behind them.
        if sys.platform=='darwin':
            self.setup_mac();return
        self.window=tk.Toplevel(parent);self.window.withdraw();self.window.overrideredirect(True)
        self.window.title(f'Wire Judge Animation Layer {id(self)}')
        self.canvas=tk.Canvas(self.window,bg=BG,highlightthickness=0,borderwidth=0,takefocus=False)
        self.canvas.pack(fill='both',expand=True);self.item=self.canvas.create_image(0,0,anchor='nw')
        self.window.update_idletasks()
        self.native=int(self.window.tk.call('wm','frame',str(self.window)),0)
        if sys.platform=='win32':self.setup_windows()
        else:self.setup_x11()

    def setup_windows(self):
        from ctypes import wintypes as w
        self.w=w;self.user=ctypes.WinDLL('user32',use_last_error=True);self.gdi=ctypes.WinDLL('gdi32',use_last_error=True)
        self.user.GetWindowLongW.argtypes=[w.HWND,ctypes.c_int];self.user.GetWindowLongW.restype=ctypes.c_long
        self.user.SetWindowLongW.argtypes=[w.HWND,ctypes.c_int,ctypes.c_long];self.user.SetWindowLongW.restype=ctypes.c_long
        self.user.GetDC.argtypes=[w.HWND];self.user.GetDC.restype=w.HDC
        self.user.ReleaseDC.argtypes=[w.HWND,w.HDC]
        self.gdi.CreateCompatibleDC.argtypes=[w.HDC];self.gdi.CreateCompatibleDC.restype=w.HDC
        self.gdi.SelectObject.argtypes=[w.HDC,w.HANDLE];self.gdi.SelectObject.restype=w.HANDLE
        self.gdi.DeleteObject.argtypes=[w.HANDLE];self.gdi.DeleteDC.argtypes=[w.HDC]
        class Header(ctypes.Structure):
            _fields_=[('size',w.DWORD),('width',w.LONG),('height',w.LONG),('planes',w.WORD),('bits',w.WORD),('compression',w.DWORD),('image_size',w.DWORD),('xppm',w.LONG),('yppm',w.LONG),('used',w.DWORD),('important',w.DWORD)]
        class BitmapInfo(ctypes.Structure):_fields_=[('header',Header),('colors',w.DWORD*3)]
        class Blend(ctypes.Structure):_fields_=[('op',ctypes.c_ubyte),('flags',ctypes.c_ubyte),('alpha',ctypes.c_ubyte),('format',ctypes.c_ubyte)]
        self.BitmapInfo=BitmapInfo;self.Blend=Blend
        self.gdi.CreateDIBSection.argtypes=[w.HDC,ctypes.POINTER(BitmapInfo),w.UINT,ctypes.POINTER(ctypes.c_void_p),w.HANDLE,w.DWORD];self.gdi.CreateDIBSection.restype=w.HBITMAP
        self.user.UpdateLayeredWindow.argtypes=[w.HWND,w.HDC,ctypes.POINTER(w.POINT),ctypes.POINTER(w.SIZE),w.HDC,ctypes.POINTER(w.POINT),w.DWORD,ctypes.POINTER(Blend),w.DWORD]
        style=self.user.GetWindowLongW(self.native,-20)
        # Per-pixel alpha, pass through mouse input, and never take keyboard focus.
        self.user.SetWindowLongW(self.native,-20,style|0x80000|0x20|0x8000000|0x80)

    def setup_mac(self):
        # Tk's transparent Canvas can accumulate old frames on macOS. A native
        # layer replaces the entire RGBA image, including transparent pixels.
        self.mac_window=None;self.mac_bitmap=None;self.mac_parent=None
        self.mac_appkit=ctypes.CDLL('/System/Library/Frameworks/AppKit.framework/AppKit')
        self.mac_quartz=ctypes.CDLL('/System/Library/Frameworks/QuartzCore.framework/QuartzCore')
        objc=self.mac_objc=ctypes.CDLL(ctypes.util.find_library('objc'))
        objc.objc_getClass.argtypes=[ctypes.c_char_p];objc.objc_getClass.restype=ctypes.c_void_p
        objc.sel_registerName.argtypes=[ctypes.c_char_p];objc.sel_registerName.restype=ctypes.c_void_p
        class Point(ctypes.Structure):_fields_=[('x',ctypes.c_double),('y',ctypes.c_double)]
        class Size(ctypes.Structure):_fields_=[('width',ctypes.c_double),('height',ctypes.c_double)]
        class Rect(ctypes.Structure):_fields_=[('origin',Point),('size',Size)]
        self.MacRect=Rect
        def send(obj,selector,result=ctypes.c_void_p,args=(),values=()):
            fn=ctypes.CFUNCTYPE(result,ctypes.c_void_p,ctypes.c_void_p,*args)(('objc_msgSend',objc))
            return fn(obj,objc.sel_registerName(selector.encode()),*values)
        self.mac_send=send
        def frame(obj):
            # Intel returns a 32-byte NSRect through objc_msgSend_stret; Apple
            # Silicon uses the normal message entry point for this structure.
            if platform.machine().lower() in ('x86_64','amd64'):
                value=Rect()
                fn=ctypes.CFUNCTYPE(None,ctypes.POINTER(Rect),ctypes.c_void_p,ctypes.c_void_p)(('objc_msgSend_stret',objc))
                fn(ctypes.byref(value),obj,objc.sel_registerName(b'frame'));return value
            return send(obj,'frame',Rect)
        self.mac_frame=frame
        self.parent.update_idletasks()
        nsapp=send(objc.objc_getClass(b'NSApplication'),'sharedApplication');windows=send(nsapp,'windows')
        count=send(windows,'count',ctypes.c_ulong)
        for index in range(count):
            window=send(windows,'objectAtIndex:',args=(ctypes.c_ulong,),values=(index,))
            title=send(send(window,'title'),'UTF8String',ctypes.c_char_p)
            if title and title.decode()==self.parent.title():
                self.mac_parent=window
                break
        if not self.mac_parent:raise RuntimeError('Could not find the animation parent window.')
        window=send(send(objc.objc_getClass(b'NSWindow'),'alloc'),
                    'initWithContentRect:styleMask:backing:defer:',
                    args=(Rect,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_bool),
                    values=(Rect(Point(0,0),Size(1,1)),0,2,False))
        if not window:raise RuntimeError('Could not create the animation window.')
        self.mac_window=window;self.mac_visible=False
        for selector,value in (('setOpaque:',False),('setHasShadow:',False),
                               ('setIgnoresMouseEvents:',True),('setReleasedWhenClosed:',False)):
            send(window,selector,None,(ctypes.c_bool,),(value,))
        color=send(objc.objc_getClass(b'NSColor'),'clearColor')
        send(window,'setBackgroundColor:',None,(ctypes.c_void_p,),(color,))
        view=send(window,'contentView')
        # Host our own layer so AppKit never paints a backing view over it.
        self.mac_layer=send(objc.objc_getClass(b'CALayer'),'layer')
        send(view,'setLayer:',None,(ctypes.c_void_p,),(self.mac_layer,))
        send(view,'setWantsLayer:',None,(ctypes.c_bool,),(True,))
        send(self.mac_layer,'setOpaque:',None,(ctypes.c_bool,),(False,))
        self.mac_transaction=objc.objc_getClass(b'CATransaction')

    def draw_mac(self,image,x,y):
        send=self.mac_send;objc=self.mac_objc;width,height=image.size
        pool=send(send(objc.objc_getClass(b'NSAutoreleasePool'),'alloc'),'init')
        bitmap=None
        try:
            # Tk's desktop origin is at the primary screen's top left; Cocoa's
            # is at its bottom left, even with additional monitors attached.
            screens=send(objc.objc_getClass(b'NSScreen'),'screens')
            screen=send(screens,'objectAtIndex:',args=(ctypes.c_ulong,),values=(0,))
            frame=self.mac_frame(screen)
            rect=self.MacRect();rect.origin.x=x;rect.origin.y=frame.origin.y+frame.size.height-y-height
            rect.size.width=width;rect.size.height=height
            send(self.mac_window,'setFrame:display:',None,(self.MacRect,ctypes.c_bool),(rect,False))
            pixels=np.ascontiguousarray(image.convert('RGBA'),dtype=np.uint8)
            name=send(objc.objc_getClass(b'NSString'),'stringWithUTF8String:',args=(ctypes.c_char_p,),values=(b'NSDeviceRGBColorSpace',))
            bitmap=send(send(objc.objc_getClass(b'NSBitmapImageRep'),'alloc'),
                        'initWithBitmapDataPlanes:pixelsWide:pixelsHigh:bitsPerSample:samplesPerPixel:hasAlpha:isPlanar:colorSpaceName:bitmapFormat:bytesPerRow:bitsPerPixel:',
                        args=(ctypes.c_void_p,ctypes.c_long,ctypes.c_long,ctypes.c_long,ctypes.c_long,
                              ctypes.c_bool,ctypes.c_bool,ctypes.c_void_p,ctypes.c_ulong,ctypes.c_long,ctypes.c_long),
                        values=(None,width,height,8,4,True,False,name,2,width*4,32))
            if not bitmap:raise RuntimeError('Could not create the animation frame.')
            ctypes.memmove(send(bitmap,'bitmapData'),pixels.ctypes.data,pixels.nbytes)
            # Format 2 is non-premultiplied RGBA, matching the renderer's PIL image.
            send(self.mac_transaction,'begin',None)
            try:
                send(self.mac_transaction,'setDisableActions:',None,(ctypes.c_bool,),(True,))
                layer_rect=self.MacRect();layer_rect.size.width=width;layer_rect.size.height=height
                send(self.mac_layer,'setFrame:',None,(self.MacRect,),(layer_rect,))
                send(self.mac_layer,'setContents:',None,(ctypes.c_void_p,),(send(bitmap,'CGImage'),))
            finally:send(self.mac_transaction,'commit',None)
            previous=self.mac_bitmap;self.mac_bitmap=bitmap;bitmap=None
            if previous:send(previous,'release',None)
            if not self.mac_visible:
                send(self.mac_parent,'addChildWindow:ordered:',None,(ctypes.c_void_p,ctypes.c_long),(self.mac_window,1))
                send(self.mac_window,'orderFront:',None,(ctypes.c_void_p,),(None,));self.mac_visible=True
        finally:
            if bitmap:send(bitmap,'release',None)
            send(pool,'drain',None)

    def setup_x11(self):
        self.window.attributes('-type','tooltip')
        self.x=ctypes.CDLL(ctypes.util.find_library('X11'));self.shape=ctypes.CDLL(ctypes.util.find_library('Xext'))
        self.x.XOpenDisplay.argtypes=[ctypes.c_char_p];self.x.XOpenDisplay.restype=ctypes.c_void_p
        self.display=self.x.XOpenDisplay(None)
        if not self.display:raise RuntimeError('Could not open animation display.')
        self.x.XCreateBitmapFromData.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_char_p,ctypes.c_uint,ctypes.c_uint];self.x.XCreateBitmapFromData.restype=ctypes.c_ulong
        self.x.XFreePixmap.argtypes=[ctypes.c_void_p,ctypes.c_ulong];self.x.XFlush.argtypes=[ctypes.c_void_p];self.x.XCloseDisplay.argtypes=[ctypes.c_void_p]
        self.shape.XShapeCombineMask.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_ulong,ctypes.c_int]
        self.shape.XShapeCombineRectangles.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int]
        # Empty input region lets clicks, wheel events and hover reach real widgets.
        self.shape.XShapeCombineRectangles(self.display,self.native,2,0,0,None,0,0,0)

    def draw(self,image,x,y):
        if sys.platform=='darwin':
            self.draw_mac(image,x,y);return
        width,height=image.size;self.window.geometry(f'{width}x{height}+{x}+{y}')
        if sys.platform=='win32':
            pixels=np.asarray(image,dtype=np.uint8);alpha=pixels[:,:,3:4].astype(np.uint16)
            rgba=pixels.copy();rgba[:,:,:3]=(pixels[:,:,:3].astype(np.uint16)*alpha//255).astype(np.uint8)
            bgra=rgba[:,:,[2,1,0,3]].copy();w=self.w
            screen=self.user.GetDC(None);memory=self.gdi.CreateCompatibleDC(screen);bitmap=None;previous=None
            try:
                info=self.BitmapInfo();info.header.size=ctypes.sizeof(info.header);info.header.width=width;info.header.height=-height;info.header.planes=1;info.header.bits=32
                bits=ctypes.c_void_p();bitmap=self.gdi.CreateDIBSection(screen,ctypes.byref(info),0,ctypes.byref(bits),None,0)
                if not bitmap:raise OSError('Could not create animation bitmap.')
                previous=self.gdi.SelectObject(memory,bitmap);ctypes.memmove(bits,bgra.ctypes.data,bgra.nbytes)
                point=w.POINT(x,y);size=w.SIZE(width,height);origin=w.POINT(0,0);blend=self.Blend(0,0,255,1)
                if not self.user.UpdateLayeredWindow(self.native,screen,ctypes.byref(point),ctypes.byref(size),memory,ctypes.byref(origin),0,ctypes.byref(blend),2):raise ctypes.WinError(ctypes.get_last_error())
            finally:
                if previous:self.gdi.SelectObject(memory,previous)
                if bitmap:self.gdi.DeleteObject(bitmap)
                self.gdi.DeleteDC(memory);self.user.ReleaseDC(None,screen)
        else:
            self.photo=ImageTk.PhotoImage(image,master=self.app);self.canvas.itemconfigure(self.item,image=self.photo)
            if sys.platform!='darwin':
                mask=np.packbits(np.asarray(image)[:,:,3]>2,axis=1,bitorder='little').tobytes()
                bitmap=self.x.XCreateBitmapFromData(self.display,self.native,mask,width,height)
                self.shape.XShapeCombineMask(self.display,self.native,0,0,0,bitmap,0);self.x.XFreePixmap(self.display,bitmap);self.x.XFlush(self.display)
        if self.window.state()=='withdrawn':
            self.window.deiconify();self.window.lift(self.parent)

    def close(self):
        if getattr(self,'mac_window',None):
            send=self.mac_send
            if self.mac_visible:send(self.mac_parent,'removeChildWindow:',None,(ctypes.c_void_p,),(self.mac_window,))
            send(self.mac_window,'orderOut:',None,(ctypes.c_void_p,),(None,))
            send(self.mac_layer,'setContents:',None,(ctypes.c_void_p,),(None,))
            if self.mac_bitmap:send(self.mac_bitmap,'release',None);self.mac_bitmap=None
            send(self.mac_window,'close',None);send(self.mac_window,'release',None)
            self.mac_window=None;return
        if not hasattr(self,'window'):return
        try:
            if self.window.winfo_exists():self.window.destroy()
        except tk.TclError:pass
        if getattr(self,'display',None):self.x.XCloseDisplay(self.display);self.display=None
