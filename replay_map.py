"""Carrier-relative replay playback, independent of approach scoring and edits."""
import colorsys
import queue
import re
import threading
import time
from collections import defaultdict
from dataclasses import asdict
import tkinter as tk
from tkinter import ttk,messagebox
import numpy as np
from matplotlib.figure import Figure
from matplotlib.collections import LineCollection
from carrier_stencil import draw_carrier_stencil
from editor import draw_localizer_reference
from engine import clean_rows,interpolate_quaternions,rotate,inverse,player_label,clock,glide_origin_msl_ft,velocity_from_positions
from reader import quaternion_candidate
from plots import BG,PANEL,TEXT,MUTED
from toolbar import DeferredFigureCanvasTkAgg
from replay_trails import trail_segments,trail_colors
from replay_render import ReplayRenderer
from replay_inspector import ReplayInspector
from replay_glide import ReplayGlide,aoa_outline,SPEED_ON,SPEED_FAST,SPEED_SLOW

from replay_style import (PALETTE,ENEMY_COLOR,MISSILE_COLOR,BULLET_COLOR,AIRCRAFT_SIZE,
                          AIRCRAFT_TRAIL_WIDTH,MISSILE_TRAIL_WIDTH,aircraft_marker,
                          missile_color,missile_size,missile_path,update_explosions,EXPLOSION_DURATION)

TRAIL_LENGTHS={'None':-1,'30 sec':30,'1 min':60,'2 min':120,'3 min':180,'5 min':300,'10 min':600,
               '15 min':900,'30 min':1800,'45 min':2700,'1 hour':3600,'All':0}

def missile_role(name):
    """Classify named missiles without treating bombs or surface launches as AAMs."""
    name=re.sub(r'[^A-Z0-9]','',name.upper())
    if name.startswith(('AIM','AIRST','ASMRM')):return 'air_to_air'
    return None

def is_bullet(track):
    name=re.sub(r'[^A-Z0-9]','',track['name'].upper())
    return track.get('pooled_projectile',False) or track['type']==6 and name.startswith(('BULLET','CANNON','GUNROUND','GAU','20MM','30MM'))

def approach_outline(settings,x,y,speed,aoa=np.nan):
    """Case 1 AoA or Case 3 platform speed/final AoA inside the localizer."""
    angle=np.radians(settings.runway_deg)
    x-=settings.offset_x/1852;y-=settings.offset_z/1852
    distance=-(np.sin(angle)*x+np.cos(angle)*y)
    lateral=np.cos(angle)*x-np.sin(angle)*y
    render_distance=10 if settings.recovery_case==3 else settings.graph_range_nm
    if not 0<distance<=render_distance or abs(lateral)>np.tan(np.radians(settings.localizer_tolerance_deg))*distance:return None
    if settings.recovery_case==1 or distance<3:
        return aoa_outline(aoa)
    if not np.isfinite(speed):return None
    target=settings.case3_leg1_speed_knots if distance>=6 else settings.case3_leg2_speed_knots
    difference=speed-target
    return SPEED_FAST if difference>20 else SPEED_SLOW if difference<-20 else SPEED_ON

def missile_sources(tracks):
    """Infer launchers conservatively from 3D launch proximity, including surface units."""
    missiles=[track for track in tracks if track['type']==6 or is_bullet(track)]
    units=[track for track in tracks if track['type']!=6 and not is_bullet(track)]
    if not missiles or not units:return {}
    times=np.array([track['rows'][0,0] for track in missiles])
    positions=np.array([track['rows'][0,1:4] for track in missiles])
    distances=[]
    for unit in units:
        rows=clean_rows(unit['rows'])
        location=np.column_stack([np.interp(times,rows[:,0],rows[:,axis]) for axis in (1,2,3)])
        distance=np.linalg.norm(location-positions,axis=1)
        distance[(times<rows[0,0])|(times>rows[-1,0])]=np.inf
        distances.append(distance)
    distances=np.array(distances);order=np.argsort(distances,axis=0);result={}
    for column,missile in enumerate(missiles):
        closest=order[0,column];distance=distances[closest,column]
        second=distances[order[1,column],column] if len(units)>1 else np.inf
        if distance<=150 and second-distance>=5 and units[closest]['type'] in (0,1,7):
            result[missile['id']]=units[closest]['id']
    return result


def map_samples(track,carrier,settings=None):
    """Playback needs positions, including weapons without aircraft attitude data."""
    cr=clean_rows(carrier['rows']);rows=clean_rows(track['rows'])
    rows=rows[(rows[:,0]>=cr[0,0])&(rows[:,0]<=cr[-1,0])]
    if len(rows)<2:raise ValueError('Not enough overlapping motion samples.')
    t=rows[:,0];position=np.column_stack([np.interp(t,cr[:,0],cr[:,j]) for j in (1,2,3)])
    rotation=interpolate_quaternions(cr[:,0],quaternion_candidate(cr[:,7]),t)
    local=rotate(inverse(rotation),rows[:,1:4]-position)
    speed=np.hypot(np.diff(rows[:,1]),np.diff(rows[:,3]))/np.diff(t)*3600/1852
    aoa=np.full(len(t),np.nan)
    if track['type'] in (0,1,7):
        try:
            velocity=velocity_from_positions(rows,max_gap=np.inf)
            if settings is not None:velocity-=np.array([settings.wind_x,settings.wind_y,settings.wind_z])
            body=rotate(inverse(quaternion_candidate(rows[:,7])),velocity)
            aoa=np.degrees(np.arctan2(-body[:,1],body[:,2]))
            aoa[(np.linalg.norm(body,axis=1)<25)|(body[:,2]<10)]=np.nan
        except ValueError:pass
    return dict(time=t,map_x=local[:,0]/1852,map_y=local[:,2]/1852,speed=speed,aoa=aoa,altitude=rows[:,2])

def callsign_group(name,entity):
    match=re.search(r'\b([A-Z])(\d+)-(\d+)\b',name,re.I)
    if match:
        return match[1].upper(),match[0].upper()
    return 'Other Aircraft',name or 'Aircraft'

def prepare_tracks(tracks,carrier,settings):
    result=[];sources=missile_sources(tracks)
    for track in tracks:
        bullet=is_bullet(track)
        if track['type'] not in (0,1,6,7) and not bullet:continue
        if bullet and track['id'] not in sources:continue
        # Pooled records also contain slower rockets/shells; a cannon round
        # leaves its launcher at high speed rather than accelerating later.
        if track.get('pooled_projectile') and np.linalg.norm(track['rows'][0,4:7])<400:continue
        if track['type']==6 and not bullet and missile_role(track['name'])!='air_to_air':continue
        category='bullet' if bullet else 'missile' if track['type']==6 else 'enemy' if track['type']==1 else 'friendly'
        try:data=map_samples(track,carrier,settings)
        except (ValueError,IndexError):continue
        t=data['time'];x=data['map_x'];y=data['map_y']
        # Sparse steady-flight keyframes can be far apart; interpolate them.
        # Break only physically implausible jumps, with a higher limit for weapons.
        dt=np.diff(t);speed=np.hypot(np.diff(x),np.diff(y))*1852/np.maximum(dt,1e-9)
        breaks=np.flatnonzero(speed>(4000 if category in ('missile','bullet') else 650))+1
        indices=np.unique(np.concatenate((np.linspace(0,len(t)-1,min(5000,len(t)),dtype=int),
                                           breaks,np.maximum(breaks-1,0))))
        trail_x=x[indices].copy();trail_y=y[indices].copy()
        trail_x[np.isin(indices,breaks)]=np.nan;trail_y[np.isin(indices,breaks)]=np.nan
        flight,callsign=callsign_group(track['name'],track['id'])
        result.append(dict(entity=track['id'],category=category,flight=flight,callsign=callsign,
                           track=track,
                           source=sources.get(track['id']),
                           missile_role='air_to_air' if category=='bullet' else missile_role(track['name']) if category=='missile' else None,
                           player=player_label(track['name']),time=t,x=x,y=y,
                           speed=data['speed'],aoa=data['aoa'],altitude=data['altitude'],
                           trail_time=t[indices],trail_x=trail_x,trail_y=trail_y,
                           breaks=set(breaks.tolist())))
    return result

class ReplayMapPage(ttk.Frame):
    def __init__(self,app,parent):
        super().__init__(parent);self.app=app;self.active=False;self.playing=False
        self.speed=1;self.cursor=0.;self.start=0.;self.end=0.;self.data=[]
        self.signature=None;self.settings_signature=None;self.generation=0;self.loading=False
        self.glide_visible=False;self.glide_occupied=False;self.glide_flash=False;self.glide_blink_job=None
        self.results=queue.Queue();self.play_job=None;self.poll_job=None
        self.center=np.array([0.,0.]);self.radius=2.;self.drag=None;self.follow=False
        self.members={};self.groups={};self.row_members={};self.member_rows={};self.colors={}
        body=ttk.Panedwindow(self,orient='horizontal');body.pack(fill='both',expand=True,padx=12,pady=8)
        left=ttk.Frame(body,padding=(0,0,12,0));right=ttk.Frame(body)
        body.add(left,weight=1);body.add(right,weight=4)
        left.columnconfigure(0,weight=1);left.rowconfigure(0,weight=1,uniform='sidebar');left.rowconfigure(1,weight=1,uniform='sidebar')
        aircraft=ttk.Frame(left);aircraft.grid(row=0,column=0,sticky='nsew')
        ttk.Label(aircraft,text='FLIGHTS & AIRCRAFT',font=('Helvetica',11,'bold')).pack(anchor='w',pady=(0,8))
        layers=ttk.Frame(aircraft);layers.pack(fill='x',pady=(0,8))
        self.enemy_visible=True;self.missile_layers={'air_to_air':True};self.missile_buttons={}
        self.enemy_btn=ttk.Button(layers,text='Enemy Aircraft',style='Selected.TButton',command=lambda:self.toggle_layer('enemy'))
        self.enemy_btn.pack(fill='x',pady=(0,4))
        for role,label in (('air_to_air','Air-to-Air Missiles'),):
            button=ttk.Button(layers,text=label,style='Selected.TButton',command=lambda value=role:self.toggle_layer(value))
            button.pack(fill='x',pady=(0,4));self.missile_buttons[role]=button
        table=ttk.Frame(aircraft);table.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(table,columns=('visibility',),show='tree',selectmode='browse',height=6)
        self.tree.column('#0',width=210,minwidth=120);self.tree.column('visibility',width=38,minwidth=38,stretch=False,anchor='center')
        self.tree.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(table,command=self.tree.yview);scroll.pack(side='right',fill='y');self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind('<Button-1>',self.tree_click)
        self.tree.bind('<space>',lambda event:(self.toggle_row(self.tree.focus()),'break')[-1])
        self.tree.bind('<<TreeviewSelect>>',self.inspect_selection)
        self.inspector=ReplayInspector(self,left);self.inspector.grid(row=1,column=0,sticky='nsew')
        controls=ttk.Frame(right);controls.pack(fill='x',pady=(0,6))
        self.play_btn=ttk.Button(controls,text='Play',command=self.toggle_play,state='disabled',width=8)
        self.play_btn.pack(side='left',padx=(0,12));self.speed_buttons={}
        for speed in (.25,.5,1,2,4,10):
            button=ttk.Button(controls,text=f'{speed:g}x'.lstrip('0'),width=4,command=lambda value=speed:self.set_speed(value))
            button.pack(side='left',padx=2);self.speed_buttons[speed]=button
        self.set_speed(1)
        ttk.Label(controls,text='Trail:').pack(side='left',padx=(12,5))
        self.trail_length=tk.StringVar(value=next((label for label,seconds in TRAIL_LENGTHS.items() if seconds==app.settings.replay_trail_length_sec),'3 min'))
        self.trail_selector=ttk.Combobox(controls,textvariable=self.trail_length,values=tuple(TRAIL_LENGTHS),state='readonly',width=7)
        self.trail_selector.pack(side='left');self.trail_selector.bind('<<ComboboxSelected>>',self.change_trail_length)
        self.clock_value=tk.StringVar(value=clock(0));ttk.Label(controls,textvariable=self.clock_value).pack(side='right',padx=8)
        timeline=ttk.Frame(right);timeline.pack(fill='x',pady=(0,6))
        self.start_label=ttk.Label(timeline,text=clock(0));self.start_label.pack(side='left',padx=(0,8))
        self.time_value=tk.DoubleVar(value=0)
        self.timeline=ttk.Scale(timeline,from_=0,to=1,orient='horizontal',variable=self.time_value,command=self.seek,state='disabled')
        self.timeline.pack(side='left',fill='x',expand=True)
        self.timeline.bind('<Button-1>',self.scrub);self.timeline.bind('<B1-Motion>',self.scrub)
        self.end_label=ttk.Label(timeline,text=clock(0));self.end_label.pack(side='right',padx=(8,0))
        self.message=tk.StringVar(value='Select a replay and carrier to view playback.')
        self.message_label=ttk.Label(right,textvariable=self.message,padding=(8,4));self.message_label.pack(anchor='w')
        map_frame=ttk.Frame(right);map_frame.pack(fill='both',expand=True)
        self.fig=Figure(figsize=(9,8),dpi=100,facecolor=BG)
        self.canvas=DeferredFigureCanvasTkAgg(self.fig,master=map_frame);self.canvas.get_tk_widget().pack(fill='both',expand=True)
        self.glide_page=ReplayGlide(self,self.canvas.get_tk_widget())
        self.canvas.mpl_connect('button_press_event',self.press)
        self.canvas.mpl_connect('motion_notify_event',self.motion)
        self.canvas.mpl_connect('button_release_event',self.release)
        self.canvas.mpl_connect('scroll_event',self.scroll)
        self.canvas.mpl_connect('resize_event',lambda event:self.layout())
        self.canvas.mpl_connect('draw_event',self.after_draw)
        self.renderer=ReplayRenderer(self.canvas)
        widget=self.canvas.get_tk_widget()
        ttk.Style(self).configure('Small.TButton',padding=(5,3),font=('Helvetica',9))
        ttk.Style(self).configure('Follow.Small.TButton',background='#25694f')
        ttk.Style(self).map('Follow.Small.TButton',background=[('active','#2e8060')])
        ttk.Style(self).configure('Flash.Small.TButton',background='#286fc3')
        ttk.Style(self).map('Flash.Small.TButton',background=[('active','#3689dc')])
        self.map_buttons=[]
        for label,command in (('Home',self.home),('Follow',self.toggle_follow),('-',lambda:self.zoom(2)),('+',lambda:self.zoom(.5)),('Glide Window',self.toggle_glide)):
            button=ttk.Button(widget,text=label,width=12 if label=='Glide Window' else 6 if label=='Follow' else 5 if label=='Home' else 2,style='Small.TButton',command=command)
            self.map_buttons.append(button)
            if label=='Follow':self.follow_btn=button
            if label=='Glide Window':self.glide_btn=button
        self.bind('<Destroy>',self.destroyed,add='+');self.build_map()

    def set_active(self,active):
        self.active=active
        if not active:self.pause()
        else:self.refresh()

    def refresh(self):
        signature=(id(self.app.tracks),id(self.app.carrier))
        if signature!=self.signature:
            self.signature=signature;self.generation+=1;self.loading=False;self.pause();self.data=[]
            self.tree.delete(*self.tree.get_children());self.play_btn.configure(state='disabled');self.timeline.configure(state='disabled')
            self.center=np.array([0.,0.]);self.radius=2.;self.cursor=0
            self.clock_value.set(clock(0));self.build_map()
            if not self.app.tracks or self.app.carrier is None:
                self.message.set('Select a replay and carrier to view playback.');return
            self.message.set('Loading aircraft…')
            self.loading=True
            generation=self.generation;tracks=self.app.tracks;carrier=self.app.carrier;settings=self.app.settings
            def load():
                try:self.results.put((generation,prepare_tracks(tracks,carrier,settings),None))
                except Exception as error:self.results.put((generation,[],str(error)))
            threading.Thread(target=load,daemon=True).start()
            if self.poll_job is None:self.poll_job=self.after(80,self.poll_results)
        elif self.settings_signature!=asdict(self.app.settings):self.build_map()

    def poll_results(self):
        self.poll_job=None
        try:
            while True:
                generation,data,error=self.results.get_nowait()
                if generation!=self.generation:continue
                self.data=data;self.loading=False
                if error:self.message.set('Could not load playback: '+error)
                elif not data:self.message.set('No aircraft motion overlaps this carrier log.')
                else:
                    self.message.set('');self.start=min(d['time'][0] for d in data);self.end=max(d['time'][-1] for d in data)
                    self.cursor=float(self.start);self.timeline.configure(from_=self.start,to=self.end,state='normal')
                    self.start_label.configure(text=clock(self.start));self.end_label.configure(text=clock(self.end))
                    self.play_btn.configure(state='normal');self.populate();self.build_map()
                return
        except queue.Empty:
            if self.loading:self.poll_job=self.after(80,self.poll_results)

    def populate(self):
        self.members={};self.groups=defaultdict(list);self.row_members={};self.member_rows={}
        for data in self.data:
            if data['category']=='enemy':
                data['inspect_key']=('enemy',data['entity']);continue
            if data['category']!='friendly':continue
            key=(data['flight'],data['callsign'],data['player'])
            if data['flight']=='Other Aircraft':key=(*key,data['entity'])
            if key not in self.members:
                self.members[key]=True;self.groups[data['flight']].append(key)
            data['member']=key
            data['inspect_key']=key
        self.colors={}
        for index,flight in enumerate(sorted(self.groups)):
            if index<len(PALETTE):color=PALETTE[index]
            else:
                rgb=colorsys.hls_to_rgb(.12+((index*.61803398875)%1)*.60,.68,.75)
                color='#'+''.join(f'{round(value*255):02x}' for value in rgb)
            self.colors[flight]=color;tag=f'flight-{index}';self.tree.tag_configure(tag,foreground=color)
            parent=f'group:{index}';self.row_members[parent]=self.groups[flight]
            self.tree.insert('','end',iid=parent,text='',open=True,tags=(tag,))
            for number,key in enumerate(sorted(self.groups[flight],key=lambda key:key[1:])):
                row=f'member:{index}:{number}';self.row_members[row]=[key];self.member_rows[key]=row
                self.tree.insert(parent,'end',iid=row,text='',tags=(tag,))
        self.update_tree()
        enemies=[data for data in self.data if data['category']=='enemy']
        if enemies:
            self.tree.insert('','end',iid='enemies',text='Enemy Aircraft',open=True)
            for data in enemies:self.tree.insert('enemies','end',iid=f"enemy:{data['entity']}",text=data['callsign'])

    def inspect_selection(self,event=None):
        rows=self.tree.selection()
        if not rows:return
        row=rows[0]
        keys=self.row_members.get(row,[])
        key=keys[0] if row.startswith('member:') and keys else ('enemy',int(row.split(':')[1])) if row.startswith('enemy:') else None
        if key is not None and key!=self.inspector.selected:self.select_aircraft(key,center=True)

    def select_aircraft(self,key,center=False):
        if key[0]=='enemy':
            self.enemy_visible=True
            self.enemy_btn.configure(style='Selected.TButton')
        elif key in self.members:
            self.members[key]=True
            self.update_tree()
        self.inspector.select(key)
        row=f'enemy:{key[1]}' if key[0]=='enemy' else self.member_rows.get(key)
        if row and self.tree.exists(row):
            self.tree.selection_set(row);self.tree.focus(row);self.tree.see(row)
        if center:
            data=next((d for d in self.data if d.get('inspect_key')==key and d['time'][0]<=self.cursor<=d['time'][-1]),None)
            if data is not None:
                self.center=np.array([np.interp(self.cursor,data['time'],data['x']),np.interp(self.cursor,data['time'],data['y'])])
                self.sync_limits()
        self.update_frame()

    def update_tree(self):
        for row,keys in self.row_members.items():
            count=sum(self.members[key] for key in keys)
            mark='[x]' if count==len(keys) else '[-]' if count else '[ ]'
            if row.startswith('group:'):label=keys[0][0] if keys[0][0]=='Other Aircraft' else 'Flight '+keys[0][0]
            else:
                key=keys[0];label=key[1]+(' · '+key[2] if key[2]!=key[1] and key[0]!='Other Aircraft' else '')
            self.tree.item(row,text=label);self.tree.set(row,'visibility',mark)

    def tree_click(self,event):
        if self.tree.identify_element(event.x,event.y).endswith('indicator'):return
        row=self.tree.identify_row(event.y)
        if row and (row.startswith('group:') or self.tree.identify_column(event.x)=='#1'):
            self.tree.focus(row);self.toggle_row(row);return 'break'
        if row.startswith(('member:','enemy:')):
            key=self.row_members[row][0] if row.startswith('member:') else ('enemy',int(row.split(':')[1]))
            self.select_aircraft(key,center=True);return 'break'

    def toggle_row(self,row):
        keys=self.row_members.get(row,[])
        if not keys:return
        visible=not all(self.members[key] for key in keys)
        for key in keys:self.members[key]=visible
        self.update_tree();self.update_frame()

    def toggle_layer(self,layer):
        if layer=='enemy':
            self.enemy_visible=not self.enemy_visible
            self.enemy_btn.configure(style='Selected.TButton' if self.enemy_visible else 'TButton')
        elif layer in self.missile_layers:
            self.missile_layers[layer]=not self.missile_layers[layer]
            self.missile_buttons[layer].configure(style='Selected.TButton' if self.missile_layers[layer] else 'TButton')
        self.update_frame()

    def change_trail_length(self,event=None):
        previous=self.app.settings.replay_trail_length_sec
        self.app.settings.replay_trail_length_sec=TRAIL_LENGTHS[self.trail_length.get()]
        try:self.app.settings.save(self.app.settings_path)
        except OSError as error:
            self.app.settings.replay_trail_length_sec=previous
            self.trail_length.set(next((label for label,value in TRAIL_LENGTHS.items() if value==previous),'3 min'))
            messagebox.showerror('Could not save trail length',str(error),parent=self)
        self.update_frame()

    def layout(self):
        width,height=self.fig.get_size_inches()*self.fig.dpi
        self.fig.subplots_adjust(left=min(84,width*.3)/width,right=1-min(35,width*.15)/width,
                                 bottom=min(55,height*.2)/height,top=1-min(20,height*.08)/height)

    def build_map(self):
        self.trail_length.set(next((label for label,seconds in TRAIL_LENGTHS.items() if seconds==self.app.settings.replay_trail_length_sec),'3 min'))
        self.settings_signature=asdict(self.app.settings);self.fig.clear();self.map=self.fig.subplots();self.layout()
        ax=self.map;ax.set_facecolor(PANEL);ax.tick_params(colors=MUTED,labelsize=9)
        ax.grid(color='#334357',alpha=.4,lw=.6)
        for spine in ax.spines.values():spine.set_color('#344258')
        ax.set_xlabel('Carrier right / left (NM)',color=MUTED);ax.set_ylabel('Carrier forward / aft (NM)',color=MUTED)
        self.north_arrow=ax.annotate('',xy=(.94,.95),xytext=(.94,.89),xycoords='axes fraction',
                                     arrowprops=dict(arrowstyle='-|>',color='#ff5555',lw=2),zorder=20,in_layout=False)
        self.north_label=ax.text(.94,.87,'N',transform=ax.transAxes,color='#ff5555',fontsize=10,
                                fontweight='bold',ha='center',va='center',zorder=20,in_layout=False)
        self.north_arrow.set_visible(not self.glide_visible);self.north_label.set_visible(not self.glide_visible)
        self.north_times=None;self.carrier_marker=None;self.carrier_deck=None
        if self.app.carrier is not None:
            rows=clean_rows(self.app.carrier['rows']);self.north_times=rows[:,0];self.north_rotations=quaternion_candidate(rows[:,7])
            draw_carrier_stencil(ax,self.app.settings)
            draw_localizer_reference(ax,self.app.settings,glide_origin_msl_ft(self.app.carrier,self.app.settings))
            self.carrier_marker=ax.scatter([0],[0],marker='^',s=100,color=TEXT,zorder=10)
            self.carrier_deck=next(patch for patch in ax.patches if patch.get_gid()=='carrier-deck')
            ax.annotate('Carrier',(0,0),xytext=(8,8),textcoords='offset points',color=TEXT,in_layout=False)
        for data in self.data:
            if data['category'] in ('missile','bullet'):continue
            color=ENEMY_COLOR if data['category']=='enemy' else self.colors[data['flight']]
            data['line']=LineCollection([],linewidths=AIRCRAFT_TRAIL_WIDTH,zorder=3);ax.add_collection(data['line'])
            data['marker'],=ax.plot([],[],color=color,marker='^',markersize=AIRCRAFT_SIZE,ls='',zorder=11)
            label=data['callsign']
            data['label']=ax.annotate(label,(0,0),xytext=(6,5),textcoords='offset points',color=color,fontsize=8,in_layout=False)
        self.missile_trails=LineCollection([],colors=MISSILE_COLOR,linewidths=MISSILE_TRAIL_WIDTH,linestyles='dashed',zorder=4)
        ax.add_collection(self.missile_trails)
        self.missile_markers=ax.scatter([],[],s=7,marker='D',color=MISSILE_COLOR,zorder=12)
        self.missile_explosions=ax.scatter([],[],s=[],marker='o',facecolors='none',edgecolors=[],linewidths=2,zorder=13)
        self.bullet_markers=ax.scatter([],[],s=8,marker='D',color=BULLET_COLOR,edgecolors='none',zorder=12)
        self.selection_horizontal=ax.axhline(0,color=TEXT,lw=.8,alpha=.55,zorder=9,visible=False)
        self.selection_vertical=ax.axvline(0,color=TEXT,lw=.8,alpha=.55,zorder=9,visible=False)
        moving=[self.north_arrow,self.north_label,self.missile_trails,self.missile_markers,self.bullet_markers,self.missile_explosions,
                self.selection_horizontal,self.selection_vertical]
        for data in self.data:
            if data['category'] in ('friendly','enemy'):moving.extend((data['line'],data['marker'],data['label']))
        moving.extend(artist for artist in ax.collections if artist not in moving and artist.get_zorder()>=5)
        self.renderer.configure(ax,moving)
        self.sync_limits();self.update_frame()

    def sync_limits(self):
        ratio=self.map.bbox.width/max(self.map.bbox.height,1);x,y=self.center
        limits=(x-self.radius*ratio,x+self.radius*ratio,y-self.radius,y+self.radius)
        if np.allclose(limits,(*self.map.get_xlim(),*self.map.get_ylim()),atol=1e-8,rtol=0):return False
        self.map.set_xlim(*limits[:2]);self.map.set_ylim(*limits[2:]);return True

    def update_carrier_marker(self):
        if self.carrier_marker is None:return
        deck_pixels=self.map.transData.transform(self.carrier_deck.get_xy())
        self.carrier_marker.set_visible(np.max(np.ptp(deck_pixels,axis=0))<24)

    def after_draw(self,event):
        self.update_carrier_marker()
        if self.sync_limits():self.canvas.draw_idle()
        widget=self.canvas.get_tk_widget();x=self.map.bbox.x0+5;y=widget.winfo_height()-self.map.bbox.y1+5
        for button in self.map_buttons:
            button.place(x=x,y=y);button.lift();x+=button.winfo_reqwidth()+3
        self.place_glide()

    def place_glide(self):
        if not self.glide_visible:return
        widget=self.canvas.get_tk_widget()
        size=int(max(80,min(340,self.map.bbox.width*.48,self.map.bbox.height*.65)))
        x=max(0,int(self.map.bbox.x1-size-8));y=max(0,int(widget.winfo_height()-self.map.bbox.y1+8))
        self.glide_page.place(x=x,y=y,width=size,height=size);self.glide_page.lift()

    def update_frame(self):
        self.update_carrier_marker()
        self.clock_value.set(clock(self.cursor));self.time_value.set(self.cursor)
        length=self.app.settings.replay_trail_length_sec;fade=self.app.settings.replay_trail_fade_sec
        missile_points=[];missile_lines=[];missile_colors=[];bullet_points=[];bursts=[]
        # Suppress tiny rounds when a 20 m reference occupies less than one pixel.
        bullets_in_view=20/(2*self.radius*1852/max(self.map.bbox.height,1))>=1
        self.selection_horizontal.set_visible(False);self.selection_vertical.set_visible(False)
        if self.north_times is not None:
            rotation=interpolate_quaternions(self.north_times,self.north_rotations,np.array([self.cursor]))
            north=rotate(inverse(rotation),np.array([[0.,0.,1.]]))[0][[0,2]]
            norm=np.linalg.norm(north)
            if norm>1e-8:north/=norm
            arrow_length=min(32,self.map.bbox.width*.045,self.map.bbox.height*.065)
            self.north_arrow.xy=(.94+north[0]*arrow_length/max(self.map.bbox.width,1),.89+north[1]*arrow_length/max(self.map.bbox.height,1))
            self.north_label.set_position((.94-north[0]*12/max(self.map.bbox.width,1),
                                           .89-north[1]*12/max(self.map.bbox.height,1)))
        sources={data['entity']:data for data in self.data if data['category'] in ('friendly','enemy')}
        for data in self.data:
            t=data['time'];index=int(np.searchsorted(t,self.cursor,side='right'))
            active=0<index<=len(t) and t[0]<=self.cursor<=t[-1]
            if active and index<len(t) and index in data['breaks'] and self.cursor>t[index-1]:active=False
            if data['category'] in ('missile','bullet'):
                source=sources.get(data.get('source'))
                source_visible=source is not None and (self.enemy_visible if source['category']=='enemy' else self.members.get(source['member'],False))
                visible=source_visible and self.missile_layers.get(data['missile_role'],False)
                if data['category']=='bullet':
                    if active and visible and bullets_in_view:
                        x=float(np.interp(self.cursor,t,data['x']));y=float(np.interp(self.cursor,t,data['y']))
                        if self.map.get_xlim()[0]<=x<=self.map.get_xlim()[1] and self.map.get_ylim()[0]<=y<=self.map.get_ylim()[1]:bullet_points.append((x,y))
                    continue
                if visible:
                    segments,alpha=trail_segments(data,self.cursor,length,fade)
                    missile_lines.extend(segments);missile_colors.extend(trail_colors(MISSILE_COLOR,alpha,.65))
                if visible and t[-1]<self.end-1e-6 and 0<=self.cursor-t[-1]<EXPLOSION_DURATION:
                    bursts.append((data['x'][-1],data['y'][-1],self.cursor-t[-1]))
                if active and visible:
                    x=float(np.interp(self.cursor,t,data['x']));y=float(np.interp(self.cursor,t,data['y']))
                    missile_points.append((x,y))
                continue
            enabled=self.enemy_visible if data['category']=='enemy' else self.members.get(data['member'],True)
            color=ENEMY_COLOR if data['category']=='enemy' else self.colors[data['flight']]
            data['marker'].set_markeredgecolor(color);data['marker'].set_markeredgewidth(1)
            data['marker'].set_visible(enabled)
            if active and enabled:
                x=float(np.interp(self.cursor,t,data['x']));y=float(np.interp(self.cursor,t,data['y']))
                data['marker'].set_data([x],[y]);data['label'].xy=(x,y);data['label'].set_visible(enabled)
                before=max(0,min(index-1,len(t)-2));after=before+1
                data['marker'].set_marker(aircraft_marker(data['x'][after]-data['x'][before],data['y'][after]-data['y'][before]))
                aoa=float(np.interp(self.cursor,t,data['aoa']))
                outline=approach_outline(self.app.settings,x,y,data['speed'][before],aoa)
                if outline is not None:
                    data['marker'].set_markeredgecolor(outline);data['marker'].set_markeredgewidth(2)
                if data.get('inspect_key')==self.inspector.selected:
                    self.selection_horizontal.set_ydata([y,y]);self.selection_horizontal.set_visible(True)
                    self.selection_vertical.set_xdata([x,x]);self.selection_vertical.set_visible(True)
                    if self.follow:self.center=np.array([x,y]);self.sync_limits()
            else:data['marker'].set_data([],[]);data['label'].set_visible(False)
            data['line'].set_visible(enabled)
            if enabled:
                segments,alpha=trail_segments(data,self.cursor,length,fade)
                color=ENEMY_COLOR if data['category']=='enemy' else self.colors[data['flight']]
                data['line'].set_segments(segments)
                data['line'].set_colors(trail_colors(color,alpha,.7))
        self.missile_markers.set_offsets(np.asarray(missile_points).reshape(-1,2))
        self.bullet_markers.set_offsets(np.asarray(bullet_points).reshape(-1,2))
        self.missile_markers.set_paths([missile_path(self.cursor)])
        self.missile_markers.set_sizes([missile_size(self.cursor)])
        self.missile_markers.set_color(missile_color(self.cursor))
        update_explosions(self.missile_explosions,bursts,self.fig.dpi)
        self.missile_trails.set_segments(missile_lines);self.missile_trails.set_colors(missile_colors)
        self.inspector.update(self.cursor)
        self.glide_occupied=self.glide_page.update();self.update_glide_button()
        self.renderer.paint()

    def toggle_glide(self):
        self.glide_visible=not self.glide_visible
        if self.glide_visible:self.place_glide()
        else:self.glide_page.place_forget()
        self.north_arrow.set_visible(not self.glide_visible);self.north_label.set_visible(not self.glide_visible)
        self.update_frame()

    def update_glide_button(self):
        blinking=self.active and self.glide_occupied and not self.glide_visible
        if blinking and self.glide_blink_job is None:self.glide_blink_job=self.after(450,self.blink_glide)
        if not blinking:
            if self.glide_blink_job is not None:self.after_cancel(self.glide_blink_job);self.glide_blink_job=None
            self.glide_flash=False
        self.glide_btn.configure(style='Follow.Small.TButton' if self.glide_visible else 'Flash.Small.TButton' if self.glide_flash else 'Small.TButton')

    def blink_glide(self):
        self.glide_blink_job=None;self.glide_flash=not self.glide_flash;self.update_glide_button()

    def seek(self,value):
        if not self.data:return
        self.cursor=float(np.clip(float(value),self.start,self.end));self.last_tick=time.monotonic();self.update_frame()

    def scrub(self,event):
        if self.data:
            fraction=np.clip((event.x-10)/max(self.timeline.winfo_width()-20,1),0,1)
            self.seek(self.start+fraction*(self.end-self.start))
        return 'break'

    def set_speed(self,speed):
        self.speed=speed;self.last_tick=time.monotonic()
        for value,button in self.speed_buttons.items():button.configure(style='Selected.TButton' if value==speed else 'TButton')

    def toggle_play(self):
        if self.playing:self.pause();return
        if not self.data or not self.active:return
        if self.cursor>=self.end:self.seek(self.start)
        self.playing=True;self.play_btn.configure(text='Pause',style='Selected.TButton');self.last_tick=time.monotonic();self.tick()

    def pause(self):
        self.playing=False
        if self.play_job is not None:self.after_cancel(self.play_job);self.play_job=None
        self.play_btn.configure(text='Play',style='TButton')

    def tick(self):
        self.play_job=None
        if not self.playing or not self.active:return
        now=time.monotonic();self.cursor=min(self.end,self.cursor+(now-self.last_tick)*self.speed);self.last_tick=now
        self.update_frame()
        if self.cursor>=self.end:self.pause()
        else:self.play_job=self.after(67,self.tick)

    def home(self):
        self.set_follow(False)
        self.center=np.array([0.,0.]);self.radius=2.;self.sync_limits();self.canvas.draw_idle()

    def set_follow(self,enabled):
        self.follow=enabled
        self.follow_btn.configure(style='Follow.Small.TButton' if enabled else 'Small.TButton')

    def toggle_follow(self):
        self.set_follow(not self.follow);self.update_frame()

    def zoom(self,factor,anchor=None):
        old=self.radius;self.radius=float(np.clip(old*factor,.05,200))
        if anchor is not None:self.center=anchor+(self.center-anchor)*(self.radius/old)
        self.sync_limits();self.update_frame()

    def press(self,event):
        if event.inaxes is self.map and event.button==1:self.drag=(event.x,event.y,self.center.copy())

    def motion(self,event):
        if self.drag is None or event.x is None or event.y is None:return
        x,y,center=self.drag
        if np.hypot(event.x-x,event.y-y)<4:return
        self.set_follow(False)
        self.center=center-np.array([(event.x-x)*np.diff(self.map.get_xlim())[0]/max(self.map.bbox.width,1),
                                     (event.y-y)*2*self.radius/max(self.map.bbox.height,1)])
        self.sync_limits();self.canvas.draw_idle()

    def release(self,event):
        drag=self.drag;self.drag=None
        if drag is None or event.inaxes is not self.map or event.x is None or event.y is None:return
        if np.hypot(event.x-drag[0],event.y-drag[1])>5:return
        closest=None;distance=13
        for data in self.data:
            if data['category'] in ('missile','bullet') or not data['marker'].get_visible():continue
            x,y=data['marker'].get_data()
            if not len(x):continue
            px,py=self.map.transData.transform((x[0],y[0]));gap=np.hypot(event.x-px,event.y-py)
            if gap<distance:closest=data;distance=gap
        if closest is not None:self.select_aircraft(closest['inspect_key'])

    def scroll(self,event):
        if event.inaxes is self.map and event.xdata is not None and event.ydata is not None:
            self.zoom(1/1.2 if event.button=='up' else 1.2,np.array([event.xdata,event.ydata]))

    def destroyed(self,event):
        if event.widget is not self:return
        for job in (self.play_job,self.poll_job,self.glide_blink_job):
            if job is not None:self.after_cancel(job)
        self.generation+=1
