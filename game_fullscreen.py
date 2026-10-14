"""Fullscreen presentation of an existing Game tab without recreating its widgets."""
import tkinter as tk
from tkinter import ttk


class GameFullscreen:
    def __init__(self,page):
        self.page=page;self.active=False;self.snapshot=None;self.escape_binding=None

    def toggle(self):
        if self.active:self.exit()
        else:self.enter()

    def enter(self):
        if self.active:return
        root=self.page.winfo_toplevel();notebook=self.page.master
        # Retain pack order/options for every ancestor and its application chrome.
        packs=[];branch=notebook
        while branch is not root:
            parent=branch.master
            children=[(widget,dict(widget.pack_info())) for widget in parent.pack_slaves()]
            packs.append((branch,children));branch=parent
        self.snapshot={'root':root,'notebook':notebook,'packs':packs,'style':notebook.cget('style'),
                       'fullscreen':root.attributes('-fullscreen'),'geometry':root.geometry(),'state':root.state()}
        self.active=True
        try:
            notebook.select(self.page)
            style=ttk.Style(root)
            style.layout('GameFullscreen.TNotebook.Tab',[])
            style.configure('GameFullscreen.TNotebook',borderwidth=0,padding=0)
            notebook.configure(style='GameFullscreen.TNotebook')
            for branch,children in packs:
                for widget,info in children:
                    if widget is not branch:widget.pack_forget()
                branch.pack_configure(fill='both',expand=True,padx=0,pady=0,ipadx=0,ipady=0)
            root.attributes('-fullscreen',True)
            self.escape_binding=root.bind('<Escape>',self.escape,add='+')
            self.page.fullscreen_button.configure(text='Exit Fullscreen')
            self.page.canvas.focus_set()
        except tk.TclError:
            self.exit();raise

    def escape(self,event=None):
        if self.active:
            self.exit();return 'break'

    def exit(self):
        if not self.active:return
        snapshot=self.snapshot;self.active=False;self.snapshot=None
        root=snapshot['root'];notebook=snapshot['notebook']
        try:
            if self.escape_binding:root.unbind('<Escape>',self.escape_binding)
        except tk.TclError:pass
        self.escape_binding=None
        try:
            root.attributes('-fullscreen',snapshot['fullscreen'])
            notebook.configure(style=snapshot['style'])
            # Insert each original packed sibling before its successor, preserving order.
            for branch,children in reversed(snapshot['packs']):
                successor=None
                for widget,info in reversed(children):
                    if not widget.winfo_exists():continue
                    widget.pack(**info)
                    if successor is not None:widget.pack_configure(before=successor)
                    successor=widget
            if not snapshot['fullscreen']:
                root.geometry(snapshot['geometry'])
                root.state(snapshot['state'])
            if self.page.fullscreen_button.winfo_exists():self.page.fullscreen_button.configure(text='Fullscreen')
        except tk.TclError:
            # Closing the application can destroy the window during widget cleanup.
            pass
