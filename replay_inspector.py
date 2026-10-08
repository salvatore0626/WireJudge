"""Live replay aircraft attitude and selectable historical diagnostics."""
import tkinter as tk
from tkinter import ttk
from dataclasses import asdict
import numpy as np
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from engine import (full_track,quaternion_candidate,rotate,inverse,velocity_from_positions,
                    approach_reference,glide_origin_msl_ft,interpolate_quaternions)
from plots import BG,PANEL,TEXT,MUTED
from toolbar import DeferredFigureCanvasTkAgg

METRICS={'speed':('Speed','kt','#69b7ff'),'aoa':('AoA','°','#8dd8ff'),
         'vs':('Vertical Speed','ft/min','#f4a1cf'),'altitude':('Altitude','ft MSL','#d5b28a'),
         'bank':('Bank','°','#ffb2b8'),'pitch':('Pitch','°','#ffe879'),
         'loc':('Loc Offset','°','#ff9850'),'glide':('Glide Offset','°','#b491ff')}
WINDOWS={'30 seconds':30,'2 min':120,'5 min':300,'10 min':600}

def diagnostic_samples(track,carrier,settings):
    data=full_track(track,carrier,settings);rows=data['rows'];t=data['time']
    q=quaternion_candidate(rows[:,7]);forward=rotate(q,np.broadcast_to([0.,0.,1.],(len(t),3)))
    right=rotate(q,np.broadcast_to([1.,0.,0.],(len(t),3)));up=rotate(q,np.broadcast_to([0.,1.,0.],(len(t),3)))
    velocity=velocity_from_positions(rows,max_gap=np.inf)
    body=rotate(inverse(q),velocity-np.array([settings.wind_x,settings.wind_y,settings.wind_z]))
    aoa=np.degrees(np.arctan2(-body[:,1],body[:,2]));aoa[(np.linalg.norm(body,axis=1)<25)|(body[:,2]<10)]=np.nan
    reference=approach_reference(settings,data['distance'],glide_origin_msl_ft(carrier,settings))
    origin=glide_origin_msl_ft(carrier,settings)/3.280839895
    glide=np.degrees(np.arctan2(data['world_altitude']-origin,data['distance'])-
                     np.arctan2(reference['center']-origin,data['distance']))
    # Carrier approach offsets apply only on the inbound side of the glide origin.
    loc=-np.degrees(np.arctan2(data['lateral'],data['distance']));glide[data['distance']<=0]=np.nan;loc[data['distance']<=0]=np.nan
    return dict(time=t,rotation=q,speed=np.linalg.norm(velocity[:,[0,2]],axis=1)*3600/1852,aoa=aoa,
                vs=velocity[:,1]*3.280839895*60,altitude=data['world_altitude']*3.280839895,
                bank=np.degrees(np.arctan2(-right[:,1],up[:,1])),
                pitch=np.degrees(np.arcsin(np.clip(forward[:,1],-1,1))),loc=loc,glide=glide)

class ReplayInspector(ttk.Frame):
    def __init__(self,page,parent):
        super().__init__(parent,padding=(0,8,0,0));self.page=page;self.selected=None;self.samples=None;self.signature=None
        self.metrics={'speed'};self.lines={};self.axes={};self.last_values=None
        self.title=tk.StringVar(value='Inspector');ttk.Label(self,textvariable=self.title,font=('Helvetica',11,'bold')).pack(anchor='w')
        self.attitude=tk.Canvas(self,height=92,background=BG,highlightthickness=0)
        self.attitude.pack(fill='x');self.attitude.bind('<Configure>',lambda event:self.draw_attitude())
        values=ttk.Frame(self);values.pack(fill='x',pady=(0,4));values.columnconfigure(0,weight=1);values.columnconfigure(1,weight=1)
        style=ttk.Style(self)
        for name in ('Inspector.TButton','Inspector.Selected.TButton'):
            style.configure(name,padding=(4,3),font=('Helvetica',9))
        self.buttons={}
        for index,(key,(label,unit,color)) in enumerate(METRICS.items()):
            button=ttk.Button(values,text=label+': —',command=lambda metric=key:self.toggle_metric(metric),style='Inspector.Selected.TButton' if key in self.metrics else 'Inspector.TButton')
            button.grid(row=index//2,column=index%2,sticky='ew',padx=(0,3) if index%2==0 else (3,0),pady=2);self.buttons[key]=button
        controls=ttk.Frame(self);controls.pack(fill='x',pady=(0,4));ttk.Label(controls,text='Look back:').pack(side='left',padx=(0,6))
        self.window=tk.StringVar(value='2 min');self.selector=ttk.Combobox(controls,textvariable=self.window,values=tuple(WINDOWS),state='readonly',width=12)
        self.selector.pack(side='left');self.selector.bind('<<ComboboxSelected>>',lambda event:self.update(self.page.cursor))
        self.fig=Figure(figsize=(3,2),dpi=100,facecolor=BG)
        self.canvas=DeferredFigureCanvasTkAgg(self.fig,master=self);self.canvas.get_tk_widget().pack(fill='both',expand=True)
        self.build_graph();self.draw_attitude()

    def select(self,key):
        self.selected=key;self.signature=None;self.update(self.page.cursor)

    def toggle_metric(self,key):
        if key in self.metrics:self.metrics.remove(key)
        else:self.metrics.add(key)
        self.buttons[key].configure(style='Inspector.Selected.TButton' if key in self.metrics else 'Inspector.TButton')
        self.build_graph();self.update(self.page.cursor)

    def build_graph(self):
        self.fig.clear();self.axes={};self.lines={}
        keys=[key for key in METRICS if key in self.metrics]
        if not keys:
            self.fig.text(.5,.5,'Select a stat to graph',ha='center',va='center',color=MUTED,fontsize=9)
        else:
            axes=np.atleast_1d(self.fig.subplots(len(keys),1,sharex=True))
            for index,(key,ax) in enumerate(zip(keys,axes)):
                label,unit,color=METRICS[key];ax.set_facecolor(PANEL);ax.tick_params(colors=MUTED,labelsize=7,pad=1)
                ax.grid(color='#334357',alpha=.4,lw=.5)
                for spine in ax.spines.values():spine.set_color('#344258')
                short_label={'loc':'Loc','glide':'Glide','vs':'V/S','altitude':'Alt'}.get(key,label)
                ax.set_ylabel(short_label+'\n'+unit,color=color,fontsize=7,labelpad=14,rotation=0,ha='right',va='center')
                ax.yaxis.set_major_locator(MaxNLocator(nbins=2))
                ax.tick_params(labelbottom=index==len(keys)-1)
                self.lines[key],=ax.plot([],[],color=color,lw=1.1);self.axes[key]=ax
            axes[-1].set_xlabel('Seconds before cursor',color=MUTED,fontsize=7,labelpad=2)
            self.fig.subplots_adjust(left=.25,right=.96,bottom=.19,top=.96,hspace=.35)
        self.canvas.draw_idle()

    def update(self,cursor):
        matches=[d for d in self.page.data if self.selected is not None and d.get('inspect_key')==self.selected]
        active=next((d for d in matches if d['time'][0]<=cursor<=d['time'][-1]),None)
        chosen=active or (min(matches,key=lambda d:min(abs(cursor-d['time'][0]),abs(cursor-d['time'][-1]))) if matches else None)
        signature=(chosen['entity'] if chosen else None,id(self.page.app.carrier),asdict(self.page.app.settings))
        if signature!=self.signature:
            self.signature=signature;self.samples=None
            if chosen:
                try:self.samples=diagnostic_samples(chosen['track'],self.page.app.carrier,self.page.app.settings)
                except (ValueError,IndexError):pass
        username=chosen['player'] if chosen and '(' in chosen['track']['name'] else 'AI'
        self.title.set(username+' - '+chosen['callsign'] if chosen else 'Inspector')
        values={key:np.nan for key in METRICS};values['dme']=np.nan
        if self.samples is not None and active:
            t=self.samples['time'];i=min(max(1,int(np.searchsorted(t,cursor))),len(t)-1)
            if i not in active['breaks'] or cursor in (t[i-1],t[i]):
                for key in METRICS:
                    v=self.samples[key];values[key]=float(np.interp(cursor,t[i-1:i+1],v[i-1:i+1]))
                # Interpolate attitude as a quaternion, so crossing +/-180° bank
                # cannot swing the wings through a false level attitude.
                q=interpolate_quaternions(t[i-1:i+1],self.samples['rotation'][i-1:i+1],np.array([cursor]))
                forward=rotate(q,np.array([[0.,0.,1.]]))[0]
                right=rotate(q,np.array([[1.,0.,0.]]))[0];up=rotate(q,np.array([[0.,1.,0.]]))[0]
                values['bank']=float(np.degrees(np.arctan2(-right[1],up[1])))
                values['pitch']=float(np.degrees(np.arcsin(np.clip(forward[1],-1,1))))
                values['speed']=float(active['speed'][i-1])
                values['dme']=float(np.hypot(np.interp(cursor,t,active['x']),np.interp(cursor,t,active['y'])))
        self.last_values=values;self.draw_attitude()
        for key,(label,unit,color) in METRICS.items():
            value=values[key];self.buttons[key].configure(text=f'{label}: {value:.1f} {unit}' if np.isfinite(value) else label+': —')
        window=WINDOWS[self.window.get()]
        for key,ax in self.axes.items():
            x=[];y=[]
            if self.samples is not None:
                t=self.samples['time'];keep=np.flatnonzero((t>=cursor-window)&(t<=cursor))
                start=max(t[0],cursor-window);end=min(t[-1],cursor)
                if end>=start:
                    keep=keep[np.unique(np.linspace(0,len(keep)-1,min(600,len(keep)),dtype=int))] if len(keep) else keep
                    times=np.unique(np.r_[start,t[keep],end])
                    y=np.interp(times,t,self.samples[key])
                    for index in chosen['breaks']:
                        y[(times>t[index-1])&(times<t[index])]=np.nan
                        following=np.flatnonzero(times>=t[index])
                        if len(following):y[following[0]]=np.nan
                    x=times-cursor
            self.lines[key].set_data(x,y);ax.set_xlim(-window,0);ax.relim();ax.autoscale_view(scalex=False,scaley=True)
        self.canvas.draw_idle()

    def draw_attitude(self):
        canvas=self.attitude;canvas.delete('all');width=max(canvas.winfo_width(),260)
        bank=(self.last_values or {}).get('bank',np.nan);pitch=(self.last_values or {}).get('pitch',np.nan)
        x=width*.125;y=39;r=min(27,width/8-5)
        canvas.create_oval(x-r,y-r,x+r,y+r,outline=MUTED,width=1)
        canvas.create_line(x-r-5,y,x-r+3,y,fill=MUTED);canvas.create_line(x+r-3,y,x+r+5,y,fill=MUTED)
        if np.isfinite(bank):
            a=np.radians(bank);dx=r*.9*np.cos(a);dy=r*.9*np.sin(a)
            canvas.create_line(x-dx,y-dy,x+dx,y+dy,fill=TEXT,width=3)
            canvas.create_line(x,y,x+8*np.sin(a),y-8*np.cos(a),fill=TEXT,width=2)
        canvas.create_oval(x-3,y-3,x+3,y+3,fill=TEXT,outline='')
        canvas.create_text(x,80,text='Bank',fill=MUTED,font=('Helvetica',9))
        x=width*.375
        # Vertical back and right semicircle form the pitch indicator's D outline.
        canvas.create_line(x,y-r,x,y+r,fill=MUTED)
        canvas.create_arc(x-r,y-r,x+r,y+r,start=-90,extent=180,style='arc',outline=MUTED)
        canvas.create_line(x+r-2,y,x+r+3,y,fill=MUTED)
        if np.isfinite(pitch):
            a=np.radians(np.clip(pitch,-90,90))
            canvas.create_line(x,y,x+r*.9*np.cos(a),y-r*.9*np.sin(a),fill=TEXT,width=2,arrow=tk.LAST)
        canvas.create_text(x+8,80,text='Pitch',fill=MUTED,font=('Helvetica',9))
        x=width*.625
        canvas.create_oval(x-r,y-r,x+r,y+r,outline=MUTED,width=1)
        for offset in (-.6,-.3,.3,.6):
            canvas.create_oval(x+r*offset-1,y-1,x+r*offset+1,y+1,fill=MUTED,outline='')
            canvas.create_oval(x-1,y+r*offset-1,x+1,y+r*offset+1,fill=MUTED,outline='')
        values=self.last_values or {};loc=values.get('loc',np.nan);glide=values.get('glide',np.nan)
        settings=self.page.app.settings
        if np.isfinite(loc):
            needle=x+r*.8*np.clip(loc/settings.localizer_tolerance_deg,-1,1)
            canvas.create_line(needle,y-r*.7,needle,y+r*.7,fill=METRICS['loc'][2],width=2,tags='loc-needle')
        if np.isfinite(glide):
            needle=y+r*.8*np.clip(glide/settings.glide_tolerance_deg,-1,1)
            canvas.create_line(x-r*.7,needle,x+r*.7,needle,fill=METRICS['glide'][2],width=2,tags='glide-needle')
        canvas.create_oval(x-2,y-2,x+2,y+2,fill=TEXT,outline='')
        canvas.create_text(x,80,text='HSI',fill=MUTED,font=('Helvetica',9))
        x=width*.875;half=width/8-7
        canvas.create_rectangle(x-half,y-26,x+half,y+26,outline=MUTED)
        canvas.create_text(x,y-16,text='DME',fill=TEXT,font=('Helvetica',9))
        canvas.create_rectangle(x-half+4,y-6,x+half-4,y+16,fill=PANEL,outline=MUTED)
        dme=values.get('dme',np.nan)
        canvas.create_text(x,y+5,text=f'{dme:.2f}' if np.isfinite(dme) else '—',fill=TEXT,font=('Helvetica',11,'bold'),tags='dme-value')
        canvas.create_text(x,80,text='NM',fill=MUTED,font=('Helvetica',9))
