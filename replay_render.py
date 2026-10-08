"""Cached static backgrounds for moving replay artists."""
class ReplayRenderer:
    def __init__(self,canvas):
        self.canvas=canvas;self.background=None;self.artists=[];self.axes=None;self.axis_connections=[]
        canvas.mpl_connect('draw_event',self.after_draw)
        canvas.mpl_connect('resize_event',lambda event:self.invalidate())

    def configure(self,axes,artists):
        if self.axes is not None:
            for connection in self.axis_connections:self.axes.callbacks.disconnect(connection)
        self.axes=axes;self.artists=list(artists)
        for artist in self.artists:artist.set_animated(True)
        self.axis_connections=[axes.callbacks.connect(event,lambda ax:self.invalidate()) for event in ('xlim_changed','ylim_changed')]
        self.background=None

    def invalidate(self):
        self.background=None;self.canvas.draw_idle()

    def after_draw(self,event):
        if self.axes is None:return
        self.background=self.canvas.copy_from_bbox(self.canvas.figure.bbox)
        self.paint()

    def paint(self):
        if self.background is None:
            self.canvas.draw_idle();return
        self.canvas.restore_region(self.background)
        for artist in sorted(self.artists,key=lambda artist:artist.get_zorder()):
            if artist.get_visible():self.axes.draw_artist(artist)
        self.canvas.blit(self.canvas.figure.bbox)
