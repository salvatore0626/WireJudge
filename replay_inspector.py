"""Live replay aircraft attitude and selectable historical diagnostics."""
import tkinter as tk
from tkinter import ttk
from dataclasses import asdict
import numpy as np
from matplotlib.figure import Figure
from matplotlib.ticker import MultipleLocator
from engine import (full_track,quaternion_candidate,rotate,inverse,velocity_from_positions,
                    approach_reference,glide_origin_msl_ft,interpolate_quaternions,BLACK_BOX_METRICS)
from plots import BG,PANEL,TEXT,MUTED,PITCH_BELOW_COLOR,HSI_COLOR,pitch_line_data,diagnostic_reference_line
from toolbar import DeferredFigureCanvasTkAgg
from replay_glide import aoa_outline,localizer_corridor_distance,SPEED_ON,SPEED_FAST,SPEED_SLOW

METRICS={('vs' if key=='vertical_speed' else key):value for key,value in BLACK_BOX_METRICS.items()}
WINDOWS={'30 seconds':30,'2 min':120,'5 min':300,'10 min':600}
AXIS_MINIMUMS={'speed':(1,10),'aoa':(.5,4),'vs':(50,200),'altitude':(10,200),
               'bank':(1,10),'pitch':(1,10),'loc':(1,10),'glide':(1,10)}

def metric_axis_range(key,values):
    minimum_step,minimum_range=AXIS_MINIMUMS[key]
    finite=np.asarray(values)[np.isfinite(values)]
    low=float(np.min(finite)) if len(finite) else 0.
    high=float(np.max(finite)) if len(finite) else 0.
    spread=max(minimum_range,(high-low)*1.1)
    center=(low+high)/2
    target=max(minimum_step,spread/4)
    magnitude=10**np.floor(np.log10(target/minimum_step))
    step=next(factor*minimum_step*magnitude for factor in (1,2,2.5,5,10)
              if factor*minimum_step*magnitude>=target)
    return center-spread/2,center+spread/2,step

def diagnostic_samples(track,carrier,settings):
    data=full_track(track,carrier,settings);rows=data['rows'];t=data['time']
    q=quaternion_candidate(rows[:,7]);forward=rotate(q,np.broadcast_to([0.,0.,1.],(len(t),3)))
    right=rotate(q,np.broadcast_to([1.,0.,0.],(len(t),3)));up=rotate(q,np.broadcast_to([0.,1.,0.],(len(t),3)))
    velocity=velocity_from_positions(rows,max_gap=np.inf,max_speed=4000 if track['type']==6 else 650)
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
        self.popout_window=None;self.docked_inspector=None
        self.metrics={'speed'};self.lines={};self.axes={};self.last_values=None
        self.graph_background=None;self.axis_scale_times={};self.axis_steps={};self.graph_window=None
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
        self.page.register_dropdown(self.selector)
        self.selector.pack(side='left');self.selector.bind('<<ComboboxSelected>>',lambda event:self.update(self.page.cursor))
        self.fig=Figure(figsize=(3,2),dpi=100,facecolor=BG)
        footer=ttk.Frame(self);footer.pack(side='bottom',fill='x',pady=(4,0))
        self.popout_button=ttk.Button(footer,text='Pop Out',command=self.pop_out,style='Inspector.TButton')
        self.popout_button.pack(side='left')
        self.canvas=DeferredFigureCanvasTkAgg(self.fig,master=self);self.canvas.get_tk_widget().pack(fill='both',expand=True)
        self.canvas.mpl_connect('resize_event',lambda event:self.graph_margins())
        self.canvas.mpl_connect('draw_event',self.graph_drawn)
        self.build_graph();self.draw_attitude()

    def copy_state_from(self,other):
        self.metrics=set(other.metrics);self.window.set(other.window.get())
        for key,button in self.buttons.items():
            button.configure(style='Inspector.Selected.TButton' if key in self.metrics else 'Inspector.TButton')
        self.build_graph();self.select(other.selected)

    def pop_out(self):
        if self.popout_window is not None:
            self.popout_window.lift();return
        window=tk.Toplevel(self.page.app);window.title('Wire Judge · Inspector')
        window.configure(background=BG);window.geometry('460x650');window.minsize(340,420)
        inspector=ReplayInspector(self.page,window)
        inspector.pack(fill='both',expand=True,padx=10,pady=10)
        inspector.docked_inspector=self;inspector.popout_window=window
        inspector.popout_button.configure(text='Pop In',command=inspector.pop_in)
        inspector.copy_state_from(self)
        self.sidebar_split=self.master.sashpos(0);self.popout_window=window;self.master.forget(self)
        self.page.inspector=inspector
        window.protocol('WM_DELETE_WINDOW',inspector.pop_in)

    def pop_in(self):
        dock=self.docked_inspector
        if dock is None:return
        dock.copy_state_from(self);self.page.inspector=dock
        dock.popout_window=None;dock.master.add(dock,weight=1)
        dock.master.update_idletasks()
        dock.master.sashpos(0,dock.sidebar_split)
        for attribute in ('_idle_draw_id','_resize_job'):
            job=getattr(self.canvas,attribute,None)
            if job is not None:
                self.canvas.get_tk_widget().after_cancel(job);setattr(self.canvas,attribute,None)
        self.popout_window.destroy()
        self.page.update_frame()

    def select(self,key):
        self.selected=key;self.signature=None;self.update(self.page.cursor)

    def toggle_metric(self,key):
        if key in self.metrics:self.metrics.remove(key)
        else:self.metrics.add(key)
        self.buttons[key].configure(style='Inspector.Selected.TButton' if key in self.metrics else 'Inspector.TButton')
        self.build_graph();self.update(self.page.cursor)

    def build_graph(self):
        self.graph_background=None;self.axis_scale_times={};self.axis_steps={};self.graph_window=None
        self.fig.clear();self.axes={};self.lines={};self.pitch_below=None
        keys=[key for key in METRICS if key in self.metrics]
        if not keys:
            self.fig.text(.5,.5,'Select a stat to graph',ha='center',va='center',color=MUTED,fontsize=9)
        else:
            axes=np.atleast_1d(self.fig.subplots(len(keys),1,sharex=True))
            for index,(key,ax) in enumerate(zip(keys,axes)):
                label,unit,color=METRICS[key];ax.set_facecolor(PANEL);ax.tick_params(colors=MUTED,labelsize=7,pad=1)
                ax.grid(color='#334357',alpha=.4,lw=.5)
                diagnostic_reference_line(ax,key)
                for spine in ax.spines.values():spine.set_color('#344258')
                short_label={'loc':'Loc','glide':'Glide','vs':'V/S','altitude':'Alt'}.get(key,label)
                ax.text(.02,.96,short_label+' · '+unit,transform=ax.transAxes,color=color,fontsize=7,
                        ha='left',va='top',bbox=dict(facecolor=PANEL,edgecolor='none',alpha=.8,pad=1))
                low,high,step=metric_axis_range(key,[])
                ax.set_ylim(low,high);ax.yaxis.set_major_locator(MultipleLocator(step))
                self.axis_steps[key]=step
                ax.tick_params(labelbottom=index==len(keys)-1)
                self.lines[key],=ax.plot([],[],color=color,ls='--' if unit=='°' else '-',lw=1.1,animated=True);self.axes[key]=ax
                if key=='pitch':
                    self.pitch_below,=ax.plot([],[],color=PITCH_BELOW_COLOR,ls='--',lw=1.1,animated=True)
            axes[-1].set_xlabel('Seconds before cursor',color=MUTED,fontsize=7,labelpad=2)
            self.graph_margins()
        self.canvas.draw_idle()

    def graph_margins(self):
        self.graph_background=None
        width,height=self.fig.bbox.width,self.fig.bbox.height
        self.fig.subplots_adjust(left=min(.3,45/max(width,1)),right=1-min(.08,8/max(width,1)),
                                 bottom=min(.3,35/max(height,1)),top=1-min(.08,10/max(height,1)),hspace=.35)

    def graph_drawn(self,event):
        self.graph_background=self.canvas.copy_from_bbox(self.fig.bbox)
        self.paint_graph()

    def paint_graph(self):
        if self.graph_background is None:
            self.canvas.draw_idle();return
        self.canvas.restore_region(self.graph_background)
        for key,line in self.lines.items():self.axes[key].draw_artist(line)
        if self.pitch_below is not None:self.axes['pitch'].draw_artist(self.pitch_below)
        self.canvas.blit(self.fig.bbox)

    def set_graph_scale(self,key,y,cursor,reset):
        ax=self.axes[key];low,high,step=metric_axis_range(key,y)
        low=np.floor(low/step)*step;high=np.ceil(high/step)*step
        previous=ax.get_ylim();finite=np.asarray(y)[np.isfinite(y)]
        outside=len(finite) and (np.min(finite)<previous[0] or np.max(finite)>previous[1])
        shrink=previous[1]-previous[0]>2*(high-low) and abs(cursor-self.axis_scale_times.get(key,cursor))>=2
        if reset or outside or shrink:
            if previous!=(low,high):
                ax.set_ylim(low,high);self.graph_background=None
            if self.axis_steps[key]!=step:
                ax.yaxis.set_major_locator(MultipleLocator(step));self.graph_background=None
                self.axis_steps[key]=step
            self.axis_scale_times[key]=cursor

    def update(self,cursor):
        if self.page.dropdown_busy:return
        matches=[d for d in self.page.data if self.selected is not None and d.get('inspect_key')==self.selected]
        active=next((d for d in matches if d['time'][0]<=cursor<=d['time'][-1]),None)
        chosen=active or (min(matches,key=lambda d:min(abs(cursor-d['time'][0]),abs(cursor-d['time'][-1]))) if matches else None)
        signature=(chosen['entity'] if chosen else None,id(self.page.app.carrier),asdict(self.page.app.settings))
        reset_scale=signature!=self.signature
        if signature!=self.signature:
            self.signature=signature;self.samples=None
            if chosen:
                try:self.samples=diagnostic_samples(chosen['track'],self.page.app.carrier,self.page.app.settings)
                except (ValueError,IndexError):pass
        username=chosen['player'] if chosen and '(' in chosen['track']['name'] else 'AI'
        if chosen and chosen['category'] in ('missile','sam'):title=chosen['track']['name']
        elif chosen:
            model=chosen.get('airframe') or 'Unknown Aircraft'
            title=username+' - '+chosen['callsign']
            if model.upper() not in title.upper():title+=' - '+model
        else:title='Inspector'
        self.title.set(title)
        values={key:np.nan for key in METRICS};values['dme']=np.nan;values['in_localizer']=False
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
                x=float(np.interp(cursor,t,active['x']));y=float(np.interp(cursor,t,active['y']))
                values['dme']=float(np.hypot(x,y))
                distance=localizer_corridor_distance(self.page.app.settings,x,y)
                values['in_localizer']=active['category'] in ('friendly','enemy') and distance is not None and values['dme']<=3
        self.last_values=values;self.draw_attitude()
        for key,(label,unit,color) in METRICS.items():
            value=values[key];self.buttons[key].configure(text=f'{label}: {value:.1f} {unit}' if np.isfinite(value) else label+': —')
        window=WINDOWS[self.window.get()]
        reset_scale=reset_scale or window!=self.graph_window
        self.graph_window=window
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
            if key=='pitch':
                px,above,below=pitch_line_data(x,y)
                self.lines[key].set_data(px,above);self.pitch_below.set_data(px,below)
            else:self.lines[key].set_data(x,y)
            if ax.get_xlim()!=(-window,0):ax.set_xlim(-window,0);self.graph_background=None
            self.set_graph_scale(key,y,cursor,reset_scale)
        self.paint_graph()

    def draw_attitude(self):
        canvas=self.attitude;canvas.delete('all');width=max(canvas.winfo_width(),260)
        bank=(self.last_values or {}).get('bank',np.nan);pitch=(self.last_values or {}).get('pitch',np.nan)
        x=width*.1;y=39;r=min(27,width/10-5)
        canvas.create_oval(x-r,y-r,x+r,y+r,outline=MUTED,width=1)
        canvas.create_line(x-r-5,y,x-r+3,y,fill=MUTED);canvas.create_line(x+r-3,y,x+r+5,y,fill=MUTED)
        if np.isfinite(bank):
            a=np.radians(bank);dx=r*.9*np.cos(a);dy=r*.9*np.sin(a)
            canvas.create_line(x-dx,y-dy,x+dx,y+dy,fill=TEXT,width=3)
            canvas.create_line(x,y,x+8*np.sin(a),y-8*np.cos(a),fill=TEXT,width=2)
        canvas.create_oval(x-3,y-3,x+3,y+3,fill=TEXT,outline='')
        canvas.create_text(x,80,text='Bank',fill=MUTED,font=('Helvetica',9))
        x=width*.3
        # Vertical back and right semicircle form the pitch indicator's D outline.
        canvas.create_line(x,y-r,x,y+r,fill=MUTED)
        canvas.create_arc(x-r,y-r,x+r,y+r,start=-90,extent=180,style='arc',outline=MUTED)
        canvas.create_line(x+r-2,y,x+r+3,y,fill=MUTED)
        if np.isfinite(pitch):
            a=np.radians(np.clip(pitch,-90,90))
            canvas.create_line(x,y,x+r*.9*np.cos(a),y-r*.9*np.sin(a),fill=TEXT,width=2,arrow=tk.LAST)
        canvas.create_text(x+8,80,text='Pitch',fill=MUTED,font=('Helvetica',9))
        x=width*.5
        values=self.last_values or {}
        active=aoa_outline(values.get('aoa',np.nan)) if values.get('in_localizer',False) else None
        inactive='#686e78';size=min(9,r*.4)
        canvas.create_line(x-size,y-21,x,y-13,x+size,y-21,
                           fill=SPEED_SLOW if active==SPEED_SLOW else inactive,
                           width=3,tags='aoa-high')
        canvas.create_oval(x-size,y-size,x+size,y+size,
                           outline=SPEED_ON if active==SPEED_ON else inactive,
                           width=3,tags='aoa-on')
        canvas.create_line(x-size,y+21,x,y+13,x+size,y+21,
                           fill=SPEED_FAST if active==SPEED_FAST else inactive,
                           width=3,tags='aoa-low')
        canvas.create_text(x,80,text='AoA',fill=MUTED,font=('Helvetica',9),tags='aoa-label')
        x=width*.7
        canvas.create_oval(x-r,y-r,x+r,y+r,outline=MUTED,width=1)
        for offset in (-.6,-.3,.3,.6):
            canvas.create_oval(x+r*offset-1,y-1,x+r*offset+1,y+1,fill=MUTED,outline='')
            canvas.create_oval(x-1,y+r*offset-1,x+1,y+r*offset+1,fill=MUTED,outline='')
        values=self.last_values or {};loc=values.get('loc',np.nan);glide=values.get('glide',np.nan)
        settings=self.page.app.settings
        if np.isfinite(loc):
            needle=x+r*.8*np.clip(loc/settings.localizer_tolerance_deg,-1,1)
            canvas.create_line(needle,y-r*.7,needle,y+r*.7,fill=HSI_COLOR,width=2,tags='loc-needle')
        if np.isfinite(glide):
            needle=y+r*.8*np.clip(glide/settings.glide_tolerance_deg,-1,1)
            canvas.create_line(x-r*.7,needle,x+r*.7,needle,fill=HSI_COLOR,width=2,tags='glide-needle')
        canvas.create_oval(x-2,y-2,x+2,y+2,fill=TEXT,outline='')
        canvas.create_text(x,80,text='HSI',fill=MUTED,font=('Helvetica',9))
        x=width*.9;half=width/10-7
        canvas.create_rectangle(x-half,y-26,x+half,y+26,outline=MUTED)
        canvas.create_text(x,y-16,text='DME',fill=TEXT,font=('Helvetica',9))
        canvas.create_rectangle(x-half+4,y-6,x+half-4,y+16,fill=PANEL,outline=MUTED)
        dme=values.get('dme',np.nan)
        canvas.create_text(x,y+5,text=f'{dme:.2f}' if np.isfinite(dme) else '—',fill=TEXT,font=('Helvetica',11 if half>=25 else 9,'bold'),tags='dme-value')
        canvas.create_text(x,80,text='NM',fill=MUTED,font=('Helvetica',9))
