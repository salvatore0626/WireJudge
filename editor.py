"""Player timeline and carrier-relative map for editing approach intervals."""
import copy,uuid
import tkinter as tk
from tkinter import ttk,messagebox
import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Circle,Polygon
from matplotlib.colors import to_rgba
from matplotlib.ticker import FuncFormatter,MaxNLocator
from toolbar import DeferredFigureCanvasTkAgg
from scoring import score_attempt
from engine import full_track,attempt_from_range,player_label,clock,glide_origin_msl_ft,glide_start_nm,approach_reference
from plots import BG,PANEL,TEXT,MUTED,BLUE,GREEN,START_END_COLOR
from carrier_stencil import draw_carrier_stencil,stencil_geometry

ORANGE='#f5a65b'
CURSOR='#ff8c8c'

def draw_localizer_reference(ax,settings,origin_msl_ft):
    """Render-distance localizer with grading gates in carrier-local coordinates."""
    distance=10 if settings.recovery_case==3 else settings.graph_range_nm
    angle=np.radians(settings.runway_deg)
    origin=np.array([settings.offset_x,settings.offset_z])/1852
    aft=np.array([-np.sin(angle),-np.cos(angle)])
    right=np.array([np.cos(angle),-np.sin(angle)])
    center=origin+aft*distance
    half_width=np.tan(np.radians(settings.localizer_tolerance_deg))*distance
    vertices=[origin,center-right*half_width,center+right*half_width]
    triangle=Polygon(vertices,closed=True,facecolor=to_rgba(GREEN,settings.limit_shading_opacity),
                     edgecolor=to_rgba(GREEN,settings.limit_outline_opacity),lw=1.3,zorder=.5,label='Localizer envelope')
    triangle.set_gid('localizer-envelope');ax.add_patch(triangle)
    ax.plot([origin[0],center[0]],[origin[1],center[1]],color=GREEN,alpha=settings.limit_center_opacity,lw=1.1,ls='--',zorder=3)
    if settings.recovery_case==3:
        along=float(np.dot(origin,aft))
        holding=origin+aft*(-along+np.sqrt(along**2+21**2-float(np.dot(origin,origin))))
        marker=ax.scatter([holding[0]],[holding[1]],marker='^',s=100,color=START_END_COLOR,alpha=settings.replay_procedure_opacity,zorder=10)
        marker.set_gid('case3-marshal-21dme')
        ax.annotate('IAF',holding,xytext=(8,8),textcoords='offset points',color=START_END_COLOR,
                    alpha=settings.replay_procedure_opacity,fontsize=9,in_layout=False)
        forward=-aft
        projection=float(np.dot(origin,forward))
        outbound=-projection+np.sqrt(projection**2+4**2-float(np.dot(origin,origin)))
        turn_start=origin+forward*outbound
        radius=.75;turn_center=turn_start-right*radius
        phase=np.linspace(0,np.pi,121)
        turn=turn_center+radius*(np.cos(phase)[:,None]*right+np.sin(phase)[:,None]*forward)
        path=np.vstack((origin,turn,turn[-1]+aft*2.5))
        missed,=ax.plot(path[:,0],path[:,1],color=START_END_COLOR,
                        alpha=settings.replay_procedure_opacity,lw=1.3,ls='--',zorder=.45)
        missed.set_gid('case3-missed-approach')
        label_anchor=(float(np.max(turn[:,0])),float(np.max(turn[:,1])))
        label=ax.annotate('Missed Approach',label_anchor,xytext=(8,8),textcoords='offset points',
                          ha='left',va='bottom',color=START_END_COLOR,
                          alpha=settings.replay_procedure_opacity,fontsize=9,in_layout=False)
        label.set_gid('case3-missed-approach-label')
        arrow=ax.annotate('',xy=path[-1],xytext=path[-1]-aft*.18,
                          arrowprops=dict(arrowstyle='-|>',color=START_END_COLOR,
                                          alpha=settings.replay_procedure_opacity,lw=1.3,mutation_scale=12),
                          zorder=.45,in_layout=False)
        arrow.set_gid('case3-missed-approach-arrow')
    else:
        geometry=stencil_geometry()
        starboard=max(point[0] for point in geometry['deck_vertices_xz'])*geometry['deck_width_m']/95+geometry['lateral_center_m']
        right_edge=(starboard+800*.3048)/1852
        marshal=Circle((right_edge-3,0),3,fill=False,edgecolor=START_END_COLOR,
                       alpha=settings.replay_procedure_opacity,lw=1.3,zorder=.4)
        marshal.set_gid('case1-marshal');ax.add_patch(marshal)
        ax.annotate('Marshal Stack',(right_edge-3,3),xytext=(0,8),textcoords='offset points',
                    ha='center',va='bottom',color=START_END_COLOR,alpha=settings.replay_procedure_opacity,
                    fontsize=9,in_layout=False)
    gates=[(glide_start_nm(settings,origin_msl_ft),'Glide Start'),(settings.scoring_changeover_nm,'Glide End')]
    if settings.recovery_case==3:
        gates.extend(((settings.case3_platform_start_nm,'Platform Start'),(settings.case3_platform_end_nm,'Platform End')))
    for nm,label in gates:
        if nm is None or not 0<nm<=distance:continue
        mid=origin+aft*nm;span=right*np.tan(np.radians(settings.localizer_tolerance_deg))*nm
        line,=ax.plot([mid[0]-span[0],mid[0]+span[0]],[mid[1]-span[1],mid[1]+span[1]],
                     color=START_END_COLOR,alpha=settings.start_end_opacity,lw=1.2,ls='--',zorder=4,label=label)
        line.set_gid('map-'+label.lower().replace(' ','-'))



class PlayerEditor(ttk.Frame):
    def __init__(self,app,player,parent=None):
        super().__init__(parent if parent is not None else app);self.app=app;self.player=player
        self.working=copy.deepcopy([a for a in app.attempts if a.player.casefold()==player.casefold()])
        self.saved_ranges=self.range_signature()
        self.ignore_selection_id=None
        self.map_view_aspect=1.0
        self.data={};self.dragging=None;self.dirty=False;self.selected_id=None;self.cursor=None;self.timeline_window=None
        for tr in app.tracks:
            if tr['type']==0 and player_label(tr['name']).casefold()==player.casefold():
                try:self.data[tr['id']]=full_track(tr,app.carrier,app.settings)
                except ValueError:pass
        if not self.data:
            ttk.Label(self,text='No usable motion samples for this player and carrier.',padding=16).pack(anchor='w');return
        self.track_ids=sorted(self.data,key=lambda key:self.data[key]['time'][0]);self.track_id=self.track_ids[0]
        self.map_radius=2.0;self.map_center=np.array([0.,0.]);self.map_drag=None;self.timeline_drag=None
        self.show_full_trails=True
        self.interpolated=tk.BooleanVar(value=True)
        self.flight_visible={entity:tk.BooleanVar(value=True) for entity in self.track_ids}
        self.visible_track_ids=list(self.track_ids)
        footer=ttk.Frame(self,padding=16);footer.pack(side='bottom',fill='x')
        self.notice=tk.StringVar(value='Map: drag to pan, wheel to zoom. Timeline: drag to pan, click to set cursor; drag Start/Stop to trim.')
        self.reset_btn=ttk.Button(footer,text='Reset Changes',command=self.close);self.reset_btn.pack(side='right')
        self.save_btn=ttk.Button(footer,text='Save & Apply',command=self.save);self.save_btn.pack(side='right',padx=8)
        body=ttk.Panedwindow(self,orient='horizontal');body.pack(fill='both',expand=True,padx=16,pady=6)
        left=ttk.Frame(body,padding=(0,0,12,0));right=ttk.Frame(body);body.add(left,weight=1);body.add(right,weight=4)
        ttk.Label(left,text='ATTEMPTS',font=('Helvetica',11,'bold')).pack(anchor='w',pady=(0,8))
        editbar=ttk.Frame(left);editbar.pack(side='bottom',fill='x')
        ttk.Button(editbar,text='Add Attempt',command=self.add_attempt).pack(fill='x',pady=1)
        ttk.Button(editbar,text='Delete Attempt',command=self.delete_attempt).pack(fill='x',pady=1)
        ttk.Label(editbar,text='Drag either timeline handle left/right.\nEach attempt stays within one aircraft life.',foreground=MUTED,wraplength=280).pack(anchor='w',pady=4)
        table=ttk.Frame(left);table.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(table,columns=('start','stop'),show='tree headings',selectmode='browse')
        self.tree.heading('#0',text='Aircraft / attempt');self.tree.column('#0',width=160,minwidth=120)
        for name in ('start','stop'):self.tree.heading(name,text=name.title());self.tree.column(name,width=80,minwidth=70,stretch=False)
        self.tree.pack(side='left',fill='both',expand=True);scroll=ttk.Scrollbar(table,command=self.tree.yview)
        scroll.pack(side='right',fill='y');self.tree.configure(yscrollcommand=scroll.set);self.tree.bind('<<TreeviewSelect>>',self.select_attempt)
        self.tree.bind('<ButtonRelease-1>',lambda event:self.select_attempt() if self.tree.identify_row(event.y) else None)
        controls=ttk.Frame(right);controls.pack(fill='x',pady=(0,6))
        self.flight_menu_text=tk.StringVar()
        self.flight_menu_btn=ttk.Menubutton(controls,textvariable=self.flight_menu_text)
        self.flight_menu_btn.pack(side='left',padx=(0,8))
        self.flight_menu=tk.Menu(self.flight_menu_btn,tearoff=False,bg=PANEL,fg=TEXT,activebackground='#355372',activeforeground=TEXT)
        self.flight_menu_btn.configure(menu=self.flight_menu)
        self.flight_menu.add_command(label='Show all',command=lambda:self.set_flights_visible(True))
        self.flight_menu.add_command(label='Hide all',command=lambda:self.set_flights_visible(False))
        self.flight_menu.add_separator()
        for i,entity in enumerate(self.track_ids):
            self.flight_menu.add_checkbutton(label=f'Flight {i+1}',variable=self.flight_visible[entity],
                                             foreground=MUTED,command=self.flight_visibility_changed)
        self.update_flight_menu()
        centered=ttk.Frame(controls);centered.pack(anchor='center')
        for label,command in (('-',lambda:self.zoom_timeline(2)),('+',lambda:self.zoom_timeline(.5)),
                              ('Center on cursor',self.center_timeline),('Focus attempt',self.focus_attempt),('Full timeline',self.full_timeline)):
            ttk.Button(centered,text=label,width=3 if label in ('-','+') else None,command=command).pack(side='left',padx=2)
        self.fig=Figure(figsize=(9,8),dpi=100,facecolor=BG)
        self.canvas=DeferredFigureCanvasTkAgg(self.fig,master=right);self.canvas.get_tk_widget().pack(fill='both',expand=True)
        self.canvas.mpl_connect('button_press_event',self.press)
        self.canvas.mpl_connect('motion_notify_event',self.motion)
        self.canvas.mpl_connect('button_release_event',self.release)
        self.canvas.mpl_connect('scroll_event',self.scroll)
        self.canvas.mpl_connect('resize_event',lambda event:self.update_figure_layout())
        ttk.Style(self).configure('Small.TButton',padding=(5,3),font=('Helvetica',9))
        self.home_btn=ttk.Button(self.canvas.get_tk_widget(),text='Home',width=5,style='Small.TButton',command=self.home_map)
        self.map_trails_btn=ttk.Button(self.canvas.get_tk_widget(),text='Hide',width=5,style='Small.TButton',command=self.toggle_map_trails)
        self.map_zoom_out_btn=ttk.Button(self.canvas.get_tk_widget(),text='-',width=2,style='Small.TButton',command=lambda:self.zoom_map(2))
        self.map_zoom_in_btn=ttk.Button(self.canvas.get_tk_widget(),text='+',width=2,style='Small.TButton',command=lambda:self.zoom_map(.5))
        self.canvas.mpl_connect('draw_event',self.place_home)
        self.populate()
        if self.working:self.tree.selection_set(self.working[0].edit_id);self.select_attempt()
        else:self.cursor=float(self.data[self.track_id]['time'][0]);self.draw()

    def resize(self):
        self.canvas.request_resize()

    def update_figure_layout(self):
        """Reserve stable pixel margins; tick labels must not move the map edges."""
        width,height=self.fig.get_size_inches()*self.fig.dpi
        left=min(96,width*.3);right=min(40,width*.15)
        top=min(20,height*.08);bottom=min(58,height*.2);gap=min(62,height*.2)
        self.fig.subplots_adjust(left=left/width,right=1-right/width,
                                 bottom=bottom/height,top=1-top/height,
                                 hspace=2*gap/max(height-top-bottom-gap,1))

    def toggle_map_trails(self):
        self.show_full_trails=not self.show_full_trails
        self.map_trails_btn.configure(text='Hide' if self.show_full_trails else 'Show')
        self.draw()

    def current(self):
        return next((a for a in self.working if a.edit_id==self.selected_id),None)

    def populate(self):
        self.tree.delete(*self.tree.get_children())
        self.tree.tag_configure('provisional',foreground='#ffce76')
        origin=glide_origin_msl_ft(self.app.carrier,self.app.settings)
        for i,a in enumerate(sorted(self.working,key=lambda a:a.start)):
            score=score_attempt(a,self.app.get_wire(a),self.app.settings,origin)
            self.tree.insert('','end',iid=a.edit_id,text=f'{i+1} · {a.aircraft}',values=(clock(a.start),clock(a.end)),tags=('provisional',) if not score.complete else ())
        if self.selected_id and self.tree.exists(self.selected_id):self.tree.selection_set(self.selected_id)

    def refresh_highlights(self):
        origin=glide_origin_msl_ft(self.app.carrier,self.app.settings)
        for a in self.working:
            if self.tree.exists(a.edit_id):
                score=score_attempt(a,self.app.get_wire(a),self.app.settings,origin)
                self.tree.item(a.edit_id,tags=('provisional',) if not score.complete else ())

    def select_attempt(self,*_):
        choices=self.tree.selection()
        if not choices:return
        if _ and self.ignore_selection_id==choices[0]:
            self.ignore_selection_id=None;return
        self.selected_id=choices[0];a=self.current()
        self.track_id=a.entity_id
        self.flight_visible[a.entity_id].set(True);self.update_flight_menu()
        self.cursor=a.start
        self.draw()

    def update_flight_menu(self):
        self.visible_track_ids=[entity for entity in self.track_ids if self.flight_visible[entity].get()]
        self.flight_menu_text.set(f'Flights ({len(self.visible_track_ids)}/{len(self.track_ids)}) ▾')
        for i,entity in enumerate(self.track_ids):
            self.flight_menu.entryconfigure(i+3,foreground=BLUE if entity==self.track_id else MUTED)

    def set_flights_visible(self,value):
        for variable in self.flight_visible.values():variable.set(value)
        self.flight_visibility_changed()

    def flight_visibility_changed(self):
        self.update_flight_menu()
        if self.visible_track_ids and self.track_id not in self.visible_track_ids:
            self.track_id=self.visible_track_ids[0];self.cursor=float(self.data[self.track_id]['time'][0])
        self.draw()

    def focus_attempt(self):
        a=self.current()
        if not a:return
        margin=max(10,(a.end-a.start)*.2)
        self.timeline_window=(a.start-margin,a.end+margin);self.draw()

    def full_timeline(self):
        self.timeline_window=None;self.draw()

    def home_map(self):
        self.map_center=np.array([0.,0.]);self.map_radius=2.0;self.map_drag=None
        self.update_map_view()

    def sync_map_limits(self):
        x,y=self.map_center;r=self.map_radius
        ratio=self.map.bbox.width/max(self.map.bbox.height,1)
        self.map_view_aspect=ratio
        limits=(x-r*ratio,x+r*ratio,y-r,y+r)
        if not np.allclose(limits,(*self.map.get_xlim(),*self.map.get_ylim()),rtol=0,atol=1e-8):
            self.map.set_xlim(*limits[:2]);self.map.set_ylim(*limits[2:])
            return True
        return False

    def update_map_view(self):
        self.sync_map_limits();self.canvas.draw_idle()

    def timeline_limits(self):
        return self.timeline_window or (min(d['time'][0] for d in self.data.values())-2,
                                       max(d['time'][-1] for d in self.data.values())+2)

    def zoom_map(self,factor):
        self.map_radius=float(np.clip(self.map_radius*factor,.05,200))
        self.update_map_view()

    def zoom_timeline(self,factor,anchor=None):
        low,high=self.timeline_limits()
        full=max(d['time'][-1] for d in self.data.values())-min(d['time'][0] for d in self.data.values())+4
        span=float(np.clip((high-low)*factor,min(.5,full),full))
        if anchor is None:
            anchor=self.cursor if self.cursor is not None and low<=self.cursor<=high else (low+high)/2
        fraction=np.clip((anchor-low)/(high-low),0,1)
        self.timeline_window=(anchor-span*fraction,anchor+span*(1-fraction));self.draw()

    def center_timeline(self):
        if self.cursor is None:return
        low,high=self.timeline_limits();half=(high-low)/2
        self.timeline_window=(self.cursor-half,self.cursor+half);self.draw()

    def scroll(self,event):
        if self.dragging or self.map_drag is not None or self.timeline_drag is not None:return
        step=getattr(event,'step',0)
        if not step:return
        factor=1.2**(-float(np.clip(step,-20,20)))
        if event.inaxes is self.map and event.xdata is not None and event.ydata is not None:
            old=self.map_radius;new=float(np.clip(old*factor,.05,200))
            anchor=np.array([event.xdata,event.ydata])
            self.map_center=anchor+(self.map_center-anchor)*(new/old);self.map_radius=new
            self.update_map_view()
        elif event.inaxes is self.timeline and event.xdata is not None:
            self.zoom_timeline(factor,event.xdata)

    def draw(self):
        self.update_flight_menu()
        self.fig.clear();grid=self.fig.add_gridspec(2,1,height_ratios=(1,3.1))
        self.update_figure_layout()
        self.timeline=self.fig.add_subplot(grid[0]);self.map=self.fig.add_subplot(grid[1])
        for ax in (self.timeline,self.map):
            ax.set_facecolor(PANEL);ax.tick_params(colors=MUTED,labelsize=9)
            ax.xaxis.label.set_color(MUTED);ax.yaxis.label.set_color(MUTED)
            ax.grid(color='#334357',alpha=.4,lw=.6)
            for spine in ax.spines.values():spine.set_color('#344258')
        self.visible_track_ids=[entity for entity in self.track_ids if self.flight_visible[entity].get()]
        for lane,entity in enumerate(self.visible_track_ids):
            data=self.data[entity];t=data['time']
            color=BLUE if entity==self.track_id else MUTED
            line,=self.timeline.plot([t[0],t[-1]],[lane,lane],color=color,lw=5,alpha=.6)
            line.set_gid(f'flight-{entity}-timeline')
            self.timeline.scatter(t,np.full(len(t),lane),s=5,color=color,alpha=.7)
            if self.show_full_trails:
                sample=np.linspace(t[0],t[-1],min(10000,max(2,int(t[-1]-t[0])+1)))
                line,=self.map.plot(np.interp(sample,t,data['map_x']),np.interp(sample,t,data['map_y']),color=color,lw=.9,alpha=.6,marker='.',markersize=2.5)
                line.set_gid(f'flight-{entity}-map')
        for attempt in sorted(self.working,key=lambda item:item.edit_id==self.selected_id):
            if attempt.entity_id not in self.visible_track_ids:continue
            lane=self.visible_track_ids.index(attempt.entity_id);chosen=attempt.edit_id==self.selected_id
            color=GREEN if chosen else ORANGE
            line,=self.timeline.plot([attempt.start,attempt.end],[lane,lane],color=color,lw=10,alpha=.85,solid_capstyle='butt',zorder=5 if chosen else 4)
            line.set_gid('attempt-'+attempt.edit_id+'-timeline')
            if not chosen and self.show_full_trails:continue
            data=self.data[attempt.entity_id];t=data['time']
            sample=np.linspace(attempt.start,attempt.end,min(10000,max(2,int(attempt.end-attempt.start)+1)))
            line,=self.map.plot(np.interp(sample,t,data['map_x']),np.interp(sample,t,data['map_y']),color=color,lw=2.2,zorder=6 if chosen else 5,marker='.',markersize=3)
            line.set_gid('attempt-'+attempt.edit_id+'-map')
        a=self.current()
        if a and a.entity_id in self.visible_track_ids:
            for value,label in ((a.start,'Start'),(a.end,'Stop')):
                self.timeline.axvline(value,color=GREEN,alpha=self.app.settings.start_end_opacity,lw=1.5)
                low,high=self.timeline_limits()
                if low<=value<=high:
                    self.timeline.text(value,.96,label,transform=self.timeline.get_xaxis_transform(),color=GREEN,alpha=self.app.settings.start_end_opacity,fontsize=9,ha='center',va='top',in_layout=False,zorder=11)
        self.timeline.set_ylim(-.6,max(len(self.visible_track_ids),1)-.4)
        self.timeline.set_yticks(range(len(self.visible_track_ids)),[f'Flight {self.track_ids.index(entity)+1}' for entity in self.visible_track_ids])
        low=min(d['time'][0] for d in self.data.values());high=max(d['time'][-1] for d in self.data.values())
        self.timeline.set_xlim(*(self.timeline_window or (low-2,high+2)))
        self.timeline.xaxis.set_major_locator(MaxNLocator(nbins=6,min_n_ticks=3))
        self.timeline.xaxis.set_major_formatter(FuncFormatter(self.timeline_label))
        self.timeline.set_xlabel('')
        self.map.add_patch(Circle((0,0),10,fill=False,edgecolor=MUTED,lw=1,ls='--'))
        draw_carrier_stencil(self.map,self.app.settings)
        draw_localizer_reference(self.map,self.app.settings,glide_origin_msl_ft(self.app.carrier,self.app.settings))
        self.map.scatter([0],[0],marker='^',s=100,color=TEXT,zorder=10)
        self.map.annotate('Carrier',(0,0),xytext=(8,8),textcoords='offset points',color=TEXT,in_layout=False)
        radius=self.map_radius;x,y=self.map_center
        self.map.set_xlim(x-radius*self.map_view_aspect,x+radius*self.map_view_aspect);self.map.set_ylim(y-radius,y+radius);self.map.set_aspect('auto')
        self.map.set_xlabel('Carrier right / left (NM)');self.map.set_ylabel('Carrier forward / aft (NM)')
        if self.cursor is not None and self.track_id in self.visible_track_ids:
            self.timeline.axvline(self.cursor,color=CURSOR,lw=.9,ls=':',zorder=9)
            self.timeline.scatter([self.cursor],[self.visible_track_ids.index(self.track_id)],s=35,color=CURSOR,zorder=10)
            low,high=self.timeline.get_xlim()
            if low<=self.cursor<=high:
                stamp=self.timeline.annotate(clock(self.cursor),xy=(self.cursor,0),xycoords=('data','axes fraction'),
                                             xytext=(0,-28),textcoords='offset points',color=CURSOR,fontsize=9,
                                             ha='center',va='top',annotation_clip=True,
                                             bbox=dict(facecolor=PANEL,edgecolor='none',pad=1.5),zorder=12)
                stamp.set_gid('timeline-cursor-time')
            data=self.data[self.track_id];t=data['time']
            if self.interpolated.get():
                x,y=np.interp(self.cursor,t,data['map_x']),np.interp(self.cursor,t,data['map_y']);label='Cursor (interpolated)'
            else:
                i=int(np.argmin(abs(t-self.cursor)));x,y=data['map_x'][i],data['map_y'][i];label='Cursor (recorded)'
            self.map.scatter([x],[y],s=55,color='#ff8c8c',zorder=12,label=label)
        self.update_save_style();self.canvas.draw_idle()

    def change_range(self,start,end,quiet=False):
        a=self.current()
        if a is None:return False
        try:new=attempt_from_range(self.data[a.entity_id],start,end,a.anchor_time,a.edit_id,'Manual attempt' if a.edit_id.startswith('manual:') else 'Edited attempt')
        except ValueError as error:
            if not quiet:messagebox.showerror('Invalid interval',str(error),parent=self)
            return False
        index=next(i for i,item in enumerate(self.working) if item.edit_id==a.edit_id)
        self.working[index]=new;self.dirty=True
        self.draw();return True

    def timeline_label(self,value,position=None):
        span=self.timeline.get_xlim()[1]-self.timeline.get_xlim()[0]
        decimals=2 if span<5 else 1 if span<20 else 0
        seconds=round(abs(value),decimals);hours=int(seconds//3600);minutes=int(seconds%3600//60);seconds=seconds%60
        tail=f'{seconds:0{3+decimals}.{decimals}f}' if decimals else f'{int(seconds):02d}'
        return ('-' if value<0 else '')+f'{hours:02d}:{minutes:02d}:'+tail

    def place_home(self,event=None):
        if not hasattr(self,'map'):return
        if self.sync_map_limits():self.canvas.get_tk_widget().after_idle(self.canvas.draw_idle)
        widget=self.canvas.get_tk_widget()
        self.home_btn.place(x=self.map.bbox.x0+5,y=widget.winfo_height()-self.map.bbox.y1+5)
        self.home_btn.lift()
        x=self.map.bbox.x0+5+self.home_btn.winfo_reqwidth()+3
        y=widget.winfo_height()-self.map.bbox.y1+5
        for button in (self.map_trails_btn,self.map_zoom_out_btn,self.map_zoom_in_btn):
            button.place(x=x,y=y);button.lift();x+=button.winfo_reqwidth()+3

    def update_save_style(self):
        changed=self.has_changes()
        self.save_btn.configure(style='Selected.TButton' if changed else 'TButton')
        self.reset_btn.configure(style='NeedsInput.TButton' if changed else 'TButton')

    def set_cursor_at(self,xdata,ydata,center_map=False):
        if not self.visible_track_ids:return
        lane=int(np.clip(round(ydata),0,len(self.visible_track_ids)-1));self.track_id=self.visible_track_ids[lane]
        t=self.data[self.track_id]['time'];cursor=float(np.clip(xdata,t[0],t[-1]))
        matching=[a for a in self.working if a.entity_id==self.track_id and a.start<=cursor<=a.end]
        if matching and matching[0].edit_id!=self.selected_id:
            self.ignore_selection_id=matching[0].edit_id
            self.tree.selection_set(matching[0].edit_id);self.select_attempt()
        self.cursor=cursor
        if center_map:
            if not self.show_full_trails and not matching:
                self.show_full_trails=True;self.map_trails_btn.configure(text='Hide')
            data=self.data[self.track_id]
            if self.interpolated.get():
                self.map_center=np.array([np.interp(cursor,t,data['map_x']),np.interp(cursor,t,data['map_y'])])
            else:
                index=int(np.argmin(abs(t-cursor)))
                self.map_center=np.array([data['map_x'][index],data['map_y'][index]])
        self.draw()

    def pick_map_point(self,pixel_x,pixel_y):
        """Find the nearest visible flight segment and its interpolated replay time."""
        point=np.array([pixel_x,pixel_y]);best=None
        for entity in self.visible_track_ids:
            data=self.data[entity];times=data['time']
            positions=self.map.transData.transform(np.column_stack((data['map_x'],data['map_y'])))
            start=positions[:-1];delta=positions[1:]-start
            length=np.sum(delta*delta,axis=1)
            fraction=np.clip(np.divide(np.sum((point-start)*delta,axis=1),length,
                                       out=np.zeros_like(length),where=length>0),0,1)
            closest=start+fraction[:,None]*delta
            distance=np.linalg.norm(closest-point,axis=1)
            distance[~np.isfinite(distance)]=np.inf
            candidate_time=times[:-1]+fraction*np.diff(times)
            if not self.show_full_trails:
                included=np.zeros(len(candidate_time),dtype=bool)
                for attempt in self.working:
                    if attempt.entity_id==entity:included|=(candidate_time>=attempt.start)&(candidate_time<=attempt.end)
                distance[~included]=np.inf
            if not len(distance):continue
            minimum=float(distance.min())
            if minimum>8:continue
            near=np.flatnonzero(distance<=minimum+.25)
            preferred=self.cursor if self.cursor is not None and entity==self.track_id else times[0]
            index=int(near[np.argmin(abs(candidate_time[near]-preferred))])
            key=(float(distance[index]),0 if entity==self.track_id else 1)
            if best is None or key<best[0]:best=(key,entity,float(candidate_time[index]))
        if best is None:return False
        self.set_cursor_at(best[2],self.visible_track_ids.index(best[1]))
        low,high=self.timeline_limits()
        if not low<=self.cursor<=high:self.center_timeline()
        return True

    def press(self,event):
        if event.inaxes is self.map and event.button==1 and event.xdata is not None:
            self.map_drag=(event.x,event.y,self.map_center.copy(),self.map_radius,self.map.bbox.width,self.map.bbox.height,False);return
        if event.inaxes is not self.timeline or event.button!=1 or event.xdata is None:return
        a=self.current()
        if a and a.entity_id in self.visible_track_ids:
            distances=[abs(self.timeline.transData.transform((v,0))[0]-event.x) for v in (a.start,a.end)]
            if min(distances)<=12:
                self.dragging='start' if distances[0]<=distances[1] else 'stop';return
        self.timeline_drag=(event.x,self.timeline_limits(),self.timeline.bbox.width,event.xdata,event.ydata,False)

    def motion(self,event):
        if self.timeline_drag is not None and event.x is not None:
            x,(low,high),width,xdata,ydata,moved=self.timeline_drag
            if abs(event.x-x)>4 or moved:
                delta=(event.x-x)*(high-low)/width
                self.timeline_window=(low-delta,high-delta);self.timeline.set_xlim(*self.timeline_window)
                self.timeline_drag=(x,(low,high),width,xdata,ydata,True);self.canvas.draw_idle()
            return
        if self.map_drag is not None and event.x is not None and event.y is not None:
            x,y,center,radius,width,height,moved=self.map_drag
            if np.hypot(event.x-x,event.y-y)>4 or moved:
                self.map_center=center-np.array([(event.x-x)*(self.map.get_xlim()[1]-self.map.get_xlim()[0])/width,(event.y-y)*2*radius/height])
                self.map_drag=(x,y,center,radius,width,height,True)
                self.update_map_view()
            return
        if not self.dragging or event.x is None:return
        a=self.current()
        if a is None:return
        value=float(self.timeline.transData.inverted().transform((event.x,event.y))[0])
        t=self.data[a.entity_id]['time'];value=float(np.clip(value,t[0],t[-1]))
        if self.dragging=='start':self.change_range(min(value,a.end-.01),a.end,quiet=True)
        else:self.change_range(a.start,max(value,a.start+.01),quiet=True)

    def release(self,event):
        if self.timeline_drag is not None:
            x,limits,width,xdata,ydata,moved=self.timeline_drag;self.timeline_drag=None
            if not moved:self.set_cursor_at(xdata,ydata,center_map=True)
        if self.map_drag is not None:
            x,y,center,radius,width,height,moved=self.map_drag;self.map_drag=None
            if not moved and event.x is not None and event.y is not None and np.hypot(event.x-x,event.y-y)<=4:
                self.pick_map_point(event.x,event.y)
        if self.dragging:self.dragging=None;self.populate()

    def add_attempt(self):
        data=self.data[self.track_id];t=data['time'];cursor=self.cursor if self.cursor is not None else t[0]
        start=max(float(t[0]),float(cursor)-45);end=min(float(t[-1]),float(cursor)+15)
        try:a=attempt_from_range(data,start,end,edit_id='manual:'+uuid.uuid4().hex)
        except ValueError as error:messagebox.showerror('Cannot add attempt',str(error),parent=self);return
        self.working.append(a);self.selected_id=a.edit_id;self.dirty=True;self.populate();self.select_attempt()

    def delete_attempt(self):
        a=self.current()
        if a is None:return
        self.working=[item for item in self.working if item.edit_id!=a.edit_id];self.selected_id=None;self.dirty=True;self.populate()
        if self.working:self.tree.selection_set(self.working[0].edit_id);self.select_attempt()
        else:self.draw()

    def save(self):
        try:
            self.app.edits.save_player(self.app.carrier['id'],self.player,self.working,self.app.auto_attempts)
            self.app.settings.editor_radius_nm=self.map_radius
            self.app.settings.save(self.app.settings_path)
        except (OSError,ValueError) as error:messagebox.showerror('Could not save editor',str(error),parent=self);return
        self.dirty=False;self.saved_ranges=self.range_signature();self.app.apply_edits();self.app.status.set('Attempt edits saved for '+self.player+'.');self.notice.set('Saved attempts for '+self.player+'.');self.update_save_style()

    def range_signature(self):
        return sorted((a.edit_id,a.entity_id,a.start,a.end,a.anchor_time) for a in self.working)

    def has_changes(self):
        return self.range_signature()!=self.saved_ranges

    def close(self):
        if self.has_changes() and not messagebox.askyesno('Reset changes?','Discard unsaved attempt changes for '+self.player+'?',parent=self):return
        self.app.editor_page.reset_player(self.player)


class AttemptEditorPage(ttk.Frame):
    """Player selector and cached embedded editors preserve drafts across tabs."""
    def __init__(self,app,parent):
        super().__init__(parent);self.app=app;self.editors={};self.active=None
        bar=ttk.Frame(self,padding=(16,8));bar.pack(fill='x')
        ttk.Label(bar,text='Player:').pack(side='left',padx=(0,8))
        self.player=tk.StringVar()
        self.selector=ttk.Combobox(bar,textvariable=self.player,state='disabled',width=40)
        self.selector.pack(side='left');self.selector.bind('<<ComboboxSelected>>',lambda *_:self.select_player(self.player.get()))
        self.host=ttk.Frame(self);self.host.pack(fill='both',expand=True)
        self.empty=ttk.Label(self.host,text='Select a replay and carrier to edit player attempts.',padding=16)
        self.empty.pack(anchor='w')

    def refresh(self):
        players=sorted({player_label(t['name']) for t in self.app.tracks if t['type']==0 and '(' in t['name']},key=str.casefold) if self.app.carrier is not None else []
        self.selector.configure(values=players,state='readonly' if players and not self.app.busy else 'disabled')
        if players and self.active is None:self.select_player(players[0])
        elif self.active and hasattr(self.active,'tree'):self.active.refresh_highlights()

    def select_player(self,player):
        if self.app.busy or self.app.carrier is None:return
        if self.active:self.active.pack_forget()
        self.empty.pack_forget();self.player.set(player)
        if player not in self.editors:self.editors[player]=PlayerEditor(self.app,player,self.host)
        self.active=self.editors[player];self.active.pack(fill='both',expand=True)
        if hasattr(self.active,'canvas'):self.active.refresh_highlights();self.after_idle(self.active.resize)

    def reset_player(self,player):
        old=self.editors.pop(player,None)
        if old:old.destroy()
        self.active=None;self.select_player(player)

    def confirm_context_change(self):
        changed=[p for p,e in self.editors.items() if e.has_changes()]
        if not changed:return True
        return messagebox.askyesno('Unsaved attempt edits','Continuing will discard unsaved attempt edits for: '+', '.join(changed)+'. Continue?',parent=self)

    def reset(self):
        for editor in self.editors.values():editor.destroy()
        self.editors={};self.active=None;self.player.set('');self.empty.pack(anchor='w');self.refresh()
