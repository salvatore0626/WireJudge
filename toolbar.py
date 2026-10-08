"""Three themed controls using Matplotlib's existing pan/zoom behavior."""
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk,FigureCanvasTkAgg

class DeferredFigureCanvasTkAgg(FigureCanvasTkAgg):
    """Coalesce native Tk resize events before running expensive figure layout."""
    def __init__(self,*args,**kwargs):
        self._resize_job=None
        self._resize_size=None
        super().__init__(*args,**kwargs)
        self._tkcanvas.bind('<Destroy>',self._cancel_resize,add='+')

    def _cancel_resize(self,event=None):
        if self._resize_job is not None:
            self._tkcanvas.after_cancel(self._resize_job);self._resize_job=None

    def resize(self,event):
        self._resize_size=(event.width,event.height)
        self._cancel_resize()
        self._resize_job=self._tkcanvas.after(120,self._finish_resize)

    def request_resize(self):
        self.resize(SimpleNamespace(width=self._tkcanvas.winfo_width(),height=self._tkcanvas.winfo_height()))

    def _finish_resize(self):
        self._resize_job=None
        width,height=self._resize_size
        if width>1 and height>1:
            super().resize(SimpleNamespace(width=width,height=height))


class GraphToolbar(NavigationToolbar2Tk):
    toolitems = (
        ('Reset view', 'Restore the original graph limits and leave pan/zoom mode.', 'home', 'reset_view'),
        ('Zoom', 'Drag a rectangle to zoom. Click again to leave zoom mode.', 'zoom_to_rect', 'zoom'),
        ('Pan', 'Drag to move the graph view. Click again to leave pan mode.', 'move', 'pan'),
    )

    def __init__(self, canvas, parent):
        super().__init__(canvas, parent, pack_toolbar=False)
        self.configure(background='#111a28',borderwidth=0,padx=6,pady=4)
        # The stock toolbar reserves two lines for coordinate readouts.
        for child in self.winfo_children():
            if isinstance(child, tk.Label):child.pack_forget()

    def _Button(self, text, image_file, toggle, command):
        button=ttk.Button(self,text=text,command=command,width=12 if text=='Reset view' else 8)
        button.pack(side='left',padx=(0,6))
        return button

    def _update_buttons_checked(self):
        for text in ('Zoom','Pan'):
            button=self._buttons.get(text)
            if button is not None:
                active=getattr(self.mode,'name','')==text.upper()
                button.configure(style='Selected.TButton' if active else 'TButton')

    def stop_navigation(self):
        mode=getattr(self.mode,'name','')
        if mode=='ZOOM':self.zoom()
        elif mode=='PAN':self.pan()

    def reset_view(self):
        self.stop_navigation()
        self.home()

    def new_graph(self):
        self.stop_navigation()
        self.update()
