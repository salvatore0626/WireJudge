"""Embedded real-time vertical approach slice for replay playback."""
from dataclasses import asdict
import tkinter as tk
from tkinter import ttk
import numpy as np
from matplotlib.figure import Figure
from matplotlib.collections import LineCollection
from matplotlib.colors import to_rgba
from plots import BG,PANEL,TEXT,MUTED,GREEN,START_END_COLOR
from engine import glide_origin_msl_ft,glide_start_nm
from toolbar import DeferredFigureCanvasTkAgg
from replay_trails import trail_segments,trail_colors
from replay_render import ReplayRenderer

SPEED_ON='#ffe05c';SPEED_FAST='#ff5555';SPEED_SLOW='#62d98a'

def aoa_outline(aoa):
    if not np.isfinite(aoa):return None
    return SPEED_FAST if aoa<7 else SPEED_SLOW if aoa>9 else SPEED_ON


def slice_geometry(data,settings):
    angle=np.radians(settings.runway_deg)
    x=data['x']-settings.offset_x/1852;z=data['y']-settings.offset_z/1852
    distance=-(np.sin(angle)*x+np.cos(angle)*z)
    lateral=np.cos(angle)*x-np.sin(angle)*z
    return distance,lateral,data['altitude']*3.280839895


def slice_limits(distance,settings,origin):
    metres=distance*1852
    center=origin+np.tan(np.radians(settings.glide_deg))*metres*3.280839895
    lower=origin+np.tan(np.radians(settings.glide_deg-settings.glide_tolerance_deg))*metres*3.280839895
    upper=origin+np.tan(np.radians(settings.glide_deg+settings.glide_tolerance_deg))*metres*3.280839895
    if settings.recovery_case==3:
        center=np.minimum(center,1200);lower=np.minimum(lower,1200-settings.case3_platform_alt_ft);upper=np.minimum(upper,1200+settings.case3_platform_alt_ft)
    return center,lower,upper


class ReplayGlide(ttk.Frame):
    def __init__(self,page,parent):
        super().__init__(parent,borderwidth=1,relief='solid');self.page=page;self.signature=None;self.artists={};self.geometry={}
        self.fig=Figure(figsize=(3.4,3.4),dpi=100,facecolor=BG)
        self.canvas=DeferredFigureCanvasTkAgg(self.fig,master=self)
        self.canvas.get_tk_widget().pack(fill='both',expand=True)
        self.canvas.mpl_connect('resize_event',lambda event:self.layout())
        self.canvas.mpl_connect('button_press_event',self.select_aircraft)
        self.renderer=ReplayRenderer(self.canvas)

    def select_aircraft(self,event):
        if not self.page.glide_visible or event.button!=1 or event.inaxes is not getattr(self,'ax',None):return
        if event.x is None or event.y is None:return
        closest=None;distance=13
        tracks={data['entity']:data for data in self.page.data}
        for entity,(_,marker,_) in self.artists.items():
            if not marker.get_visible():continue
            x,y=marker.get_data()
            if not len(x) or not len(y):continue
            px,py=self.ax.transData.transform((x[0],y[0]))
            if not self.ax.bbox.contains(px,py):continue
            gap=np.hypot(event.x-px,event.y-py)
            if gap<distance:closest=tracks[entity];distance=gap
        if closest is not None:self.page.select_aircraft(closest['inspect_key'])

    def layout(self):
        width,height=self.fig.get_size_inches()*self.fig.dpi
        self.fig.subplots_adjust(left=min(43,width*.23)/width,right=1-8/width,
                                 bottom=min(35,height*.2)/height,top=1-min(25,height*.15)/height)

    def build(self):
        settings=self.page.app.settings;self.signature=(asdict(settings),id(self.page.app.carrier),id(self.page.data),self.page.generation)
        self.range=3 if settings.recovery_case==3 else settings.graph_range_nm
        self.origin=glide_origin_msl_ft(self.page.app.carrier,settings)
        self.fig.clear();self.ax=self.fig.subplots();ax=self.ax;ax.set_facecolor(PANEL)
        ax.tick_params(colors=MUTED,labelsize=7,pad=1);ax.grid(color='#334357',alpha=.4,lw=.5)
        for spine in ax.spines.values():spine.set_color('#344258')
        x=np.linspace(0,self.range,300);center,lower,upper=slice_limits(x,settings,self.origin)
        ax.fill_between(x,lower,upper,color=GREEN,alpha=settings.limit_shading_opacity)
        for values in (lower,upper):ax.plot(x,values,color=GREEN,alpha=settings.limit_outline_opacity,lw=1)
        ax.plot(x,center,color=GREEN,alpha=settings.limit_center_opacity,lw=1,ls='--')
        for distance,label in ((glide_start_nm(settings,self.origin),'Start'),(settings.scoring_changeover_nm,'End')):
            if distance is not None and 0<distance<=self.range:
                ax.axvline(distance,color=START_END_COLOR,alpha=settings.start_end_opacity,lw=1,ls='--')
                ax.text(distance,.98,label,transform=ax.get_xaxis_transform(),color=START_END_COLOR,
                        alpha=settings.start_end_opacity,fontsize=7,ha='center',va='top',in_layout=False)
        ax.set_xlim(self.range,0);ax.set_ylim(min(self.origin-50,0),max(upper)*1.25+50)
        ax.set_xlabel('Distance (NM)',color=MUTED,fontsize=7,labelpad=1)
        ax.set_ylabel('Altitude MSL (ft)',color=MUTED,fontsize=7,labelpad=1)
        ax.set_title(f'Case {settings.recovery_case} · Live Glide',color=TEXT,loc='left',fontsize=10)
        self.layout()
        self.artists={};self.geometry={}
        for data in self.page.data:
            if data['category'] in ('missile','bullet'):continue
            color='#ff5575' if data['category']=='enemy' else self.page.colors[data['flight']]
            line=LineCollection([],linewidths=settings.graph_line_width);ax.add_collection(line)
            marker,=ax.plot([],[],color=color,marker='^',markersize=6,ls='')
            label=ax.annotate(data['callsign'],(0,0),xytext=(5,5),textcoords='offset points',color=color,fontsize=7,in_layout=False)
            self.artists[data['entity']]=(line,marker,label)
            self.geometry[data['entity']]=slice_geometry(data,settings)
        self.renderer.configure(ax,[artist for items in self.artists.values() for artist in items])

    def update(self):
        signature=(asdict(self.page.app.settings),id(self.page.app.carrier),id(self.page.data),self.page.generation)
        if signature!=self.signature:self.build()
        settings=self.page.app.settings;cursor=self.page.cursor;occupied=False
        for data in self.page.data:
            if data['category'] in ('missile','bullet'):continue
            distance,lateral,altitude=self.geometry[data['entity']];t=data['time']
            enabled=self.page.enemy_visible if data['category']=='enemy' else self.page.members.get(data['member'],True)
            current=enabled and t[0]<=cursor<=t[-1]
            index=min(max(1,int(np.searchsorted(t,cursor))),len(t)-1)
            if index in data['breaks'] and t[index-1]<cursor<t[index]:current=False
            d=float(np.interp(cursor,t,distance));l=float(np.interp(cursor,t,lateral));h=float(np.interp(cursor,t,altitude))
            in_slice=current and 0<d<=self.range and abs(l)<=np.tan(np.radians(settings.localizer_tolerance_deg))*d
            _,lo,hi=slice_limits(d,settings,self.origin)
            occupied|=bool(in_slice and lo<=h<=hi)
            if not self.page.glide_visible:continue
            line,marker,label=self.artists[data['entity']]
            marker.set_data([d],[h]) if in_slice else marker.set_data([],[])
            marker.set_markeredgecolor(data['marker'].get_markeredgecolor())
            marker.set_markeredgewidth(data['marker'].get_markeredgewidth())
            if settings.recovery_case==1 and in_slice:
                outline=aoa_outline(float(np.interp(cursor,t,data['aoa'])))
                if outline is not None:marker.set_markeredgecolor(outline);marker.set_markeredgewidth(2)
            label.xy=(d,h);label.set_visible(in_slice)
            valid=(distance>0)&(distance<=self.range)&(np.abs(lateral)<=np.tan(np.radians(settings.localizer_tolerance_deg))*distance)
            values=np.where(valid,altitude,np.nan)
            projected=dict(time=t,trail_time=data['trail_time'],x=distance,y=values,breaks=data['breaks'],category=data['category'],speed=data['speed'])
            segments,alpha=trail_segments(projected,cursor,settings.replay_trail_length_sec,settings.replay_trail_fade_sec)
            if not enabled:segments=np.empty((0,2,2));alpha=np.empty(0)
            color='#ff5575' if data['category']=='enemy' else self.page.colors[data['flight']]
            line.set_segments(segments);line.set_colors(trail_colors(color,alpha,.65))
        if self.page.glide_visible:self.renderer.paint()
        return occupied
