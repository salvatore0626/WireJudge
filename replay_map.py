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
from matplotlib.patches import Circle
from matplotlib.collections import LineCollection
from carrier_stencil import draw_carrier_stencil
from editor import draw_localizer_reference
from engine import clean_rows,interpolate_quaternions,rotate,inverse,player_label,aircraft_label,clock,glide_origin_msl_ft,velocity_from_positions
from reader import quaternion_candidate
from plots import BG,PANEL,TEXT,MUTED,CURSOR_COLOR
from toolbar import DeferredFigureCanvasTkAgg
from replay_trails import trail_segments,trail_colors
from replay_render import ReplayRenderer
from replay_sam import sam_missile_key,sam_range,sam_sources,threat_circle_segments,SAM_COLOR
from replay_inspector import ReplayInspector
from replay_glide import ReplayGlide,aoa_outline,localizer_corridor_distance,SPEED_ON,SPEED_FAST,SPEED_SLOW

from replay_style import (PALETTE,ENEMY_COLOR,MISSILE_COLOR,BULLET_COLOR,AIRCRAFT_SIZE,
                          AIRCRAFT_TRAIL_WIDTH,MISSILE_TRAIL_WIDTH,aircraft_marker,
                          missile_color,sam_missile_color,missile_size,missile_path,update_explosions,EXPLOSION_DURATION,
                          BOMB_COLOR,bomb_color,update_bomb_pulses)

TRAIL_LENGTHS={'None':-1,'30 sec':30,'1 min':60,'2 min':120,'3 min':180,'5 min':300,'10 min':600,
               '15 min':900,'30 min':1800,'45 min':2700,'1 hour':3600,'All':0}
SKIP_SECONDS={.25:3,.5:5,1:15,2:30,4:60,10:120}

def track_is_active(data,cursor,index=None):
    t=data['time']
    if cursor<t[0] or cursor>t[-1]:return False
    if index is None:index=int(np.searchsorted(t,cursor,side='right'))
    return bool(0<index<=len(t) and t[0]<=cursor<=t[-1] and
                not (index<len(t) and index in data['breaks'] and cursor>t[index-1]))

def visible_trail_edges(line):
    """Expand grouped polylines into adjacent edges for mouse hit testing."""
    if not line.get_visible():return np.empty((0,2,2))
    colors=line.get_colors();edges=[]
    for index,path in enumerate(line.get_segments()):
        if len(colors) and colors[index%len(colors),3]<=.01:continue
        if len(path)<2:continue
        pairs=np.stack((path[:-1],path[1:]),axis=1)
        pairs=pairs[np.isfinite(pairs).all(axis=(1,2))]
        if len(pairs):edges.append(pairs)
    return np.concatenate(edges) if edges else np.empty((0,2,2))

def flight_colors(flights):
    colors={}
    for index,flight in enumerate(sorted(flights)):
        if index<len(PALETTE):color=PALETTE[index]
        else:
            rgb=colorsys.hls_to_rgb(.12+((index*.61803398875)%1)*.60,.68,.75)
            color='#'+''.join(f'{round(value*255):02x}' for value in rgb)
        colors[flight]=color
    return colors

def replay_flight_colors(tracks,carrier):
    if carrier is None:return {}
    cr=clean_rows(carrier['rows']);flights=set()
    for track in tracks:
        if track['type'] not in (0,7) or is_bullet(track):continue
        rows=clean_rows(track['rows'])
        if np.count_nonzero((rows[:,0]>=cr[0,0])&(rows[:,0]<=cr[-1,0]))>=2:
            flights.add(callsign_group(track['name'],track['id'])[0])
    return flight_colors(flights)

def is_player_aircraft(data):
    return bool(re.search(r'\([^()]*\S[^()]*\)\s*$',data['track']['name']))

AIRFRAME_PATTERN=re.compile(r'(?<![A-Z0-9])(?:F/A-26B|F-45A|F-16|F-22A|T-55(?: Tyro)?|AV-42C|AH-94|EF-24G?|ASF-30|ASF-33|ASF-58|GAV-25(?: Bullshark)?|AEW-50|HB-106(?: Bomber)?|B-11(?: Bomber)?|E-4(?: Overlord)?|KC-49|MQ-31)(?![A-Z0-9])',re.I)

def named_airframe(name):
    # Remove player names before looking for a model in mission display text.
    match=AIRFRAME_PATTERN.search(aircraft_label(name))
    if match is None:return None
    model=match[0].upper()
    if model=='EF-24':return 'EF-24G'
    return model.split()[0]

def replay_airframes(tracks):
    """Metadata IDs are local to the replay; infer only unambiguous models."""
    candidates=defaultdict(set)
    for track in tracks:
        if track['type'] not in (0,1,7) or track.get('identity') is None:continue
        model=named_airframe(track['name'])
        if model:candidates[track['identity']].add(model)
    return {identity:next(iter(models)) for identity,models in candidates.items() if len(models)==1}

def aircraft_list_label(data):
    name=aircraft_label(data['track']['name'])
    match=re.search(r'\b[A-Z]\d+-\d+\b',name,re.I)
    player=data['player'] if is_player_aircraft(data) else ''
    model=data.get('airframe') or named_airframe(name) or 'Unknown Aircraft'
    custom=AIRFRAME_PATTERN.sub('',name)
    if match:custom=re.sub(r'\b[A-Z]\d+-\d+\b','',custom,flags=re.I)
    custom=custom.strip(' -–—')
    parts=(match[0].upper() if match else '',player,custom,model)
    return ' '.join(part for part in parts if part)

def is_bomb(name):
    name=re.sub(r'[^A-Z0-9]','',name.upper())
    return name.startswith(('GBU','CBU','MK82','MK83','MK84','BOMB'))

def missile_role(name):
    """Classify weapons for the shared missile/bomb layer."""
    name=re.sub(r'[^A-Z0-9]','',name.upper())
    if is_bomb(name):return 'other'
    if name.startswith(('AIM','AIRST','ASMRM','ASFSRM')):return 'air_to_air'
    if sam_missile_key(name):return 'ground_to_air'
    return 'other'


def is_bullet(track):
    name=re.sub(r'[^A-Z0-9]','',track['name'].upper())
    return track.get('pooled_projectile',False) or track['type']==6 and name.startswith(('BULLET','CANNON','GUNROUND','GAU','20MM','30MM'))

def approach_outline(settings,x,y,speed,aoa=np.nan):
    """Case 1 AoA or Case 3 platform speed/final AoA inside the localizer."""
    distance=localizer_corridor_distance(settings,x,y)
    if distance is None:return None
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
        if distance<=150 and second-distance>=5 and units[closest]['type'] in (0,1,2,3,4,5,7):
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
    result=[];airframes=replay_airframes(tracks);sources=missile_sources(tracks);ground_sources=sam_sources(tracks)
    all_units={t['id']:t for t in tracks}
    for missile in tracks:
        key=sam_missile_key(missile['name']) if missile['type']==6 else None
        if key and key!='ASMRM' and all_units.get(sources.get(missile['id']),{}).get('type') not in (4,5):sources.pop(missile['id'],None)
    sources.update(ground_sources)
    artillery_ids={t['id'] for t in tracks if t['type'] in (2,3) and
                   ('ARTILLERY' in re.sub(r'[^A-Z0-9]','',t['name'].upper()) or
                    re.sub(r'[^A-Z0-9]','',t['name'].upper()).startswith(('MLRS','MRLS')))}
    artillery_projectiles={projectile for projectile,source in sources.items() if source in artillery_ids}
    sources={projectile:source for projectile,source in sources.items() if source not in artillery_ids}
    units={t['id']:t for t in tracks if t['type'] in (2,3,4,5)}
    surface_ids={source for projectile,source in sources.items() if source in units}
    ranges={}
    for missile in tracks:
        launcher=ground_sources.get(missile['id'])
        if launcher is not None:ranges[launcher]=max(ranges.get(launcher,0),sam_range(missile['name']))
    for track in tracks:
        if track['id'] in artillery_ids or track['id'] in artillery_projectiles:continue
        pooled=track.get('pooled_projectile',False)
        launcher=all_units.get(sources.get(track['id']),{})
        rocket=pooled and 'ROCKET' in launcher.get('name','').upper()
        bullet=is_bullet(track) and not rocket
        if track['type'] not in (0,1,6,7) and track['id'] not in surface_ids and not pooled and not bullet:continue
        if (pooled or bullet) and track['id'] not in sources:continue
        # Pooled weapons begin with a reset velocity. Identify artillery rockets
        # by their launcher instead of discarding gun rounds by that first sample.
        if rocket:track=dict(track,name='Artillery Rocket')
        if track['type']==6 and not bullet and missile_role(track['name']) is None:continue
        category='sam' if track['id'] in surface_ids else 'bullet' if bullet else 'missile' if track['type']==6 or rocket else 'enemy' if track['type']==1 else 'friendly'
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
                           track=track,bomb=track['type']==6 and is_bomb(track['name']),
                           airframe=(named_airframe(track['name']) or airframes.get(track.get('identity'))) if category in ('friendly','enemy') else None,
                           source=sources.get(track['id']),
                           missile_role='ground_to_air' if track['id'] in ground_sources else 'air_to_air' if category=='bullet' else missile_role(track['name']) if category=='missile' else None,
                           threat_range_nm=ranges.get(track['id']),
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
        self.pending_attempt=None
        self.glide_visible=False;self.glide_occupied=False;self.glide_flash=False;self.glide_blink_job=None
        self.results=queue.Queue();self.play_job=None;self.poll_job=None
        self.dropdown_busy=False;self.dropdown_job=None;self.dropdown_finish_job=None;self.dropdown_widget=None
        self.dropdown_trace=None;self.dropdown_aqua=self.tk.call('tk','windowingsystem')=='aqua'
        if self.dropdown_aqua:
            self.dropdown_trace=self.register(self.dropdown_post_returned)
            self.tk.call('trace','add','execution','ttk::combobox::Post','leave',self.dropdown_trace)
        self.center=np.array([0.,0.]);self.radius=2.;self.drag=None;self.follow=False
        self.members={};self.groups={};self.row_members={};self.member_rows={};self.colors={}
        self.alive_only=False;self.only_landing=True;self.list_rows={};self.list_hidden=set();self.list_active={}
        self.missile_inspect_points=[]
        body=ttk.Panedwindow(self,orient='horizontal');body.pack(fill='both',expand=True,padx=12,pady=8)
        left=ttk.Frame(body,padding=(0,0,12,0));right=ttk.Frame(body)
        body.add(left,weight=1);body.add(right,weight=4)
        self.sidebar=ttk.Panedwindow(left,orient='vertical');self.sidebar.pack(fill='both',expand=True)
        aircraft=ttk.Frame(self.sidebar);self.sidebar.add(aircraft,weight=1)
        ttk.Label(aircraft,text='FLIGHTS & AIRCRAFT',font=('Helvetica',11,'bold')).pack(anchor='w',pady=(0,8))
        layers=ttk.Frame(aircraft);layers.pack(fill='x',pady=(0,8))
        self.enemy_visible=not self.only_landing;self.sam_visible=not self.only_landing;self.sam_ring_signature=None;self.sam_world_segments=np.empty((0,2,3))
        self.missile_layers={role:not self.only_landing for role in ('air_to_air','ground_to_air','other')};self.missile_buttons={}
        self.only_players_enabled=False;self.only_players_previous=None
        self.enemy_btn=ttk.Button(layers,text='Enemy Aircraft',style='Selected.TButton' if self.enemy_visible else 'TButton',command=lambda:self.toggle_layer('enemy'))
        layers.columnconfigure(0,weight=1);layers.columnconfigure(1,weight=1);layers.columnconfigure(2,weight=1)
        self.enemy_btn.grid(row=0,column=0,sticky='ew',padx=(0,3),pady=(0,4))
        self.sam_btn=ttk.Button(layers,text='SAM Sites',style='Selected.TButton' if self.sam_visible else 'TButton',command=lambda:self.toggle_layer('sam'))
        self.sam_btn.grid(row=0,column=1,sticky='ew',padx=3,pady=(0,4))
        button=ttk.Button(layers,text='Missiles',style='Selected.TButton' if self.missile_layers['air_to_air'] else 'TButton',command=lambda:self.toggle_layer('air_to_air'))
        button.grid(row=0,column=2,sticky='ew',padx=(3,0),pady=(0,4))
        self.missile_buttons={'air_to_air':button,'ground_to_air':button,'other':button}
        self.only_players_btn=ttk.Button(layers,text='Only Players',command=self.only_players)
        self.only_players_btn.grid(row=1,column=0,sticky='ew',padx=(0,3))
        self.alive_only_btn=ttk.Button(layers,text='Only Alive',command=self.toggle_alive_only)
        self.alive_only_btn.grid(row=1,column=1,sticky='ew',padx=(3,0))
        self.only_landing_btn=ttk.Button(layers,text='Only Landing',style='Selected.TButton',command=self.toggle_only_landing)
        self.only_landing_btn.grid(row=1,column=2,sticky='ew',padx=(3,0))
        table=ttk.Frame(aircraft);table.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(table,columns=('visibility',),show='tree',selectmode='browse',height=6)
        self.tree.column('#0',width=210,minwidth=120);self.tree.column('visibility',width=38,minwidth=38,stretch=False,anchor='center')
        self.tree.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(table,command=self.tree.yview);scroll.pack(side='right',fill='y');self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind('<Button-1>',self.tree_click)
        self.tree.bind('<Double-Button-1>',self.tree_double_click)
        self.empty_track_icon=tk.PhotoImage(master=self,width=12,height=12)
        self.inactive_track_icon=tk.PhotoImage(master=self,width=12,height=12)
        for x in range(12):
            for y in range(12):
                if 3<=np.hypot(x-5.5,y-5.5)<=4:
                    self.inactive_track_icon.put('#788492',to=(x,y))
        self.tree.bind('<space>',lambda event:(self.toggle_row(self.tree.focus()),'break')[-1])
        self.tree.bind('<<TreeviewSelect>>',self.inspect_selection)
        self.inspector=ReplayInspector(self,self.sidebar);self.sidebar.add(self.inspector,weight=1)
        self.sidebar.bind('<Map>',self.initialize_sidebar,add='+')
        controls=ttk.Frame(right);controls.pack(fill='x',pady=(0,6))
        style=ttk.Style(self)
        style.configure('ReplaySpeed.Selected.TButton',background='#286fc3',foreground='#ffffff')
        style.map('ReplaySpeed.Selected.TButton',background=[('active','#3689dc')])
        for name,base,hover in (('ReplayPlay','#27694e','#328563'),('ReplayPause','#e6bd48','#f6d369')):
            style.configure(name+'.TButton',background=base,foreground='#ffffff' if name=='ReplayPlay' else '#182436',font=('Helvetica',14,'bold'))
            style.map(name+'.TButton',background=[('active',hover)],foreground=[('disabled',MUTED)])
        self.skip_back_btn=ttk.Button(controls,text='-15 Sec',command=lambda:self.skip(-1),state='disabled',width=9)
        self.skip_back_btn.pack(side='left',padx=(0,4))
        # Draw actual pause bars instead of relying on a font's Roman numeral glyph.
        self.pause_icon=tk.PhotoImage(master=self,width=24,height=20)
        self.pause_icon.put('#182436',to=(5,2,10,18))
        self.pause_icon.put('#182436',to=(14,2,19,18))
        self.play_btn=ttk.Button(controls,text='    ',image=self.pause_icon,compound='center',style='ReplayPause.TButton',command=self.toggle_play,state='disabled',width=4)
        self.play_btn.pack(side='left',padx=(0,4))
        self.skip_forward_btn=ttk.Button(controls,text='+15 Sec',command=lambda:self.skip(1),state='disabled',width=9)
        self.skip_forward_btn.pack(side='left',padx=(0,12));self.speed_buttons={}
        for speed in (.25,.5,1,2,4,10):
            button=ttk.Button(controls,text=f'{speed:g}x'.lstrip('0'),width=4,command=lambda value=speed:self.set_speed(value))
            button.pack(side='left',padx=2);self.speed_buttons[speed]=button
        self.set_speed(1)
        ttk.Label(controls,text='Trail:').pack(side='left',padx=(12,5))
        self.trail_length=tk.StringVar(value=next((label for label,seconds in TRAIL_LENGTHS.items() if seconds==app.settings.replay_trail_length_sec),'3 min'))
        self.trail_selector=ttk.Combobox(controls,textvariable=self.trail_length,values=tuple(TRAIL_LENGTHS),state='readonly',width=7)
        self.register_dropdown(self.trail_selector)
        self.trail_selector.pack(side='left');self.trail_selector.bind('<<ComboboxSelected>>',self.change_trail_length)
        self.clock_value=tk.StringVar(value=clock(0))
        timeline=ttk.Frame(right);timeline.pack(fill='x',pady=(0,6))
        self.start_label=ttk.Label(timeline,text=clock(0));self.start_label.pack(side='left',padx=(0,8))
        self.time_value=tk.DoubleVar(value=0)
        timeline_track=ttk.Frame(timeline);timeline_track.pack(side='left',fill='x',expand=True)
        self.timeline=ttk.Scale(timeline_track,from_=0,to=1,orient='horizontal',variable=self.time_value,command=self.seek,state='disabled')
        self.timeline.pack(fill='x')
        self.timestamp_bar=ttk.Frame(timeline_track,height=22);self.timestamp_bar.pack(fill='x')
        self.current_timestamp=ttk.Label(self.timestamp_bar,textvariable=self.clock_value,foreground=CURSOR_COLOR,font=('Helvetica',9))
        self.timestamp_bar.bind('<Configure>',lambda event:self.layout_timestamp())
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

    def initialize_sidebar(self,event=None):
        if getattr(self,'sidebar_initialized',False) or len(self.sidebar.panes())<2:return
        if self.sidebar.winfo_height()>1:
            self.sidebar.sashpos(0,self.sidebar.winfo_height()//2);self.sidebar_initialized=True
        else:self.after_idle(self.initialize_sidebar)

    def refresh(self):
        signature=(id(self.app.tracks),id(self.app.carrier))
        if signature!=self.signature:
            self.pending_attempt=None
            self.signature=signature;self.generation+=1;self.loading=False;self.pause();self.data=[]
            # Detached rows are not descendants of their former flight groups.
            for row in self.list_rows:
                if self.tree.exists(row):self.tree.delete(row)
            self.list_rows={};self.list_hidden=set();self.list_active={}
            self.tree.delete(*self.tree.get_children());self.play_btn.configure(state='disabled');self.timeline.configure(state='disabled')
            self.skip_back_btn.configure(state='disabled');self.skip_forward_btn.configure(state='disabled')
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
                    self.skip_back_btn.configure(state='normal');self.skip_forward_btn.configure(state='normal')
                    self.focus_pending_attempt()
                return
        except queue.Empty:
            if self.loading:self.poll_job=self.after(80,self.poll_results)

    def open_attempt(self,entity_id,start):
        self.refresh();self.pause()
        self.pending_attempt=(entity_id,start)
        if not self.loading:self.focus_pending_attempt()

    def focus_pending_attempt(self):
        if self.pending_attempt is None:return
        entity_id,start=self.pending_attempt;self.pending_attempt=None
        data=next((d for d in self.data if d['entity']==entity_id and d.get('inspect_key') is not None and d['time'][0]<=start<=d['time'][-1]),None)
        if data is None:return
        self.set_only_landing(True)
        if not self.only_players_enabled:self.only_players()
        else:self.apply_only_players()
        self.set_follow(True)
        self.seek(start)
        self.select_aircraft(data['inspect_key'],center=True)

    def populate(self):
        self.members={};self.groups=defaultdict(list);self.row_members={};self.member_rows={};self.member_labels={}
        self.list_rows={};self.list_hidden=set();self.list_active={};member_tracks=defaultdict(list)
        for data in self.data:
            if data['category']=='missile':
                data['inspect_key']=('missile',data['entity']);continue
            if data['category'] in ('enemy','sam'):
                data['inspect_key']=(data['category'],data['entity']);continue
            if data['category']!='friendly':continue
            key=(data['flight'],data['callsign'],data['player'])
            if data['flight']=='Other Aircraft':key=(*key,data['entity'])
            if key not in self.members:
                self.members[key]=True;self.groups[data['flight']].append(key)
            data['member']=key
            data['inspect_key']=key
            self.member_labels[key]=aircraft_list_label(data)
            member_tracks[key].append(data)
        self.colors=flight_colors(self.groups)
        for index,flight in enumerate(sorted(self.groups)):
            color=self.colors[flight];tag=f'flight-{index}';self.tree.tag_configure(tag,foreground=color)
            parent=f'group:{index}';self.row_members[parent]=self.groups[flight]
            self.tree.insert('','end',iid=parent,text='',open=True,tags=(tag,))
            for number,key in enumerate(sorted(self.groups[flight],key=lambda key:key[1:])):
                row=f'member:{index}:{number}';self.row_members[row]=[key];self.member_rows[key]=row
                self.tree.insert(parent,'end',iid=row,text='',tags=(tag,))
                self.list_rows[row]=(parent,number,member_tracks[key])
        self.update_tree()
        enemies=[data for data in self.data if data['category']=='enemy']
        if enemies:
            self.tree.insert('','end',iid='enemies',text='Enemy Aircraft',open=True)
            for number,data in enumerate(enemies):
                row=f"enemy:{data['entity']}"
                self.tree.insert('enemies','end',iid=row,text=aircraft_list_label(data))
                self.list_rows[row]=('enemies',number,[data])
        sites=[data for data in self.data if data['category']=='sam']
        if sites:
            self.tree.insert('','end',iid='sam-sites',text='SAM Sites',open=False)
            for number,data in enumerate(sites):
                row=f"sam:{data['entity']}"
                self.tree.insert('sam-sites','end',iid=row,text=data['track']['name'])
                self.list_rows[row]=('sam-sites',number,[data])
        aircraft_ids={data['entity'] for data in self.data if data['category'] in ('friendly','enemy','sam')}
        missiles=[data for data in self.data if data['category']=='missile' and data.get('source') in aircraft_ids]
        if missiles:
            self.tree.insert('','end',iid='missiles',text='Missiles',open=False)
            for number,data in enumerate(missiles):
                row=f"missile:{data['entity']}"
                self.tree.insert('missiles','end',iid=row,text=data['track']['name'])
                self.list_rows[row]=('missiles',number,[data])
        self.update_list_visibility()
        if self.only_players_enabled:self.apply_only_players()

    def toggle_alive_only(self):
        self.alive_only=not self.alive_only
        self.alive_only_btn.configure(style='Selected.TButton' if self.alive_only else 'TButton')
        self.update_list_visibility()

    def update_list_visibility(self):
        for row,(parent,number,tracks) in self.list_rows.items():
            alive=any(track_is_active(data,self.cursor) for data in tracks)
            if self.list_active.get(row) is not alive:
                self.tree.item(row,image=self.empty_track_icon if alive else self.inactive_track_icon)
                self.list_active[row]=alive
            visible=not self.alive_only or alive
            if visible and row in self.list_hidden:
                self.tree.move(row,parent,number);self.list_hidden.remove(row)
            elif not visible and row not in self.list_hidden:
                self.tree.detach(row);self.list_hidden.add(row)

    def jump_to_track_start(self,data):
        self.seek(float(data['time'][0]))
        self.select_aircraft(data['inspect_key'],center=True)

    def tree_double_click(self,event):
        row=self.tree.identify_row(event.y)
        entry=self.list_rows.get(row)
        if entry is None:return
        tracks=entry[2]
        if not any(track_is_active(data,self.cursor) for data in tracks):
            data=min(tracks,key=lambda data:min(abs(self.cursor-data['time'][0]),abs(self.cursor-data['time'][-1])))
            self.jump_to_track_start(data)
        return 'break'

    def inspect_selection(self,event=None):
        rows=self.tree.selection()
        if not rows:return
        row=rows[0]
        keys=self.row_members.get(row,[])
        key=keys[0] if row.startswith('member:') and keys else (row.split(':')[0],int(row.split(':')[1])) if row.startswith(('enemy:','missile:','sam:')) else None
        if key is not None and key!=self.inspector.selected:self.select_aircraft(key,center=True)

    def select_aircraft(self,key,center=False):
        if key[0]=='missile':
            missile=next((d for d in self.data if d.get('inspect_key')==key),None)
            if missile is not None:
                self.missile_layers.update(air_to_air=True,ground_to_air=True,other=True)
                self.missile_buttons['air_to_air'].configure(style='Selected.TButton')
                source=next((d for d in self.data if d['entity']==missile.get('source')),None)
                if source is not None:
                    if source['category']=='sam':
                        self.sam_visible=True;self.sam_btn.configure(style='Selected.TButton')
                    elif source['category']=='enemy':
                        self.enemy_visible=True;self.enemy_btn.configure(style='Selected.TButton')
                    elif source.get('member') in self.members:
                        self.members[source['member']]=True;self.update_tree()
        if key[0]=='sam':
            self.sam_visible=True;self.sam_btn.configure(style='Selected.TButton')
        if key[0]=='enemy':
            self.enemy_visible=True
            self.enemy_btn.configure(style='Selected.TButton')
        elif key in self.members:
            self.members[key]=True
            self.update_tree()
        self.inspector.select(key)
        row=f'{key[0]}:{key[1]}' if key[0] in ('enemy','missile','sam') else self.member_rows.get(key)
        if row and self.tree.exists(row):
            self.tree.selection_set(row);self.tree.focus(row);self.tree.see(row)
        if center:
            data=next((d for d in self.data if d.get('inspect_key')==key and d['time'][0]<=self.cursor<=d['time'][-1]),None)
            if data is not None:
                if data['category']=='sam':
                    rows=data['track']['rows'];cr=self.app.carrier['rows']
                    world=np.array([np.interp(self.cursor,rows[:,0],rows[:,axis]) for axis in (1,2,3)])
                    origin=np.array([np.interp(self.cursor,cr[:,0],cr[:,axis]) for axis in (1,2,3)])
                    rotation=interpolate_quaternions(cr[:,0],quaternion_candidate(cr[:,7]),np.array([self.cursor]))
                    self.center=rotate(inverse(rotation),(world-origin)[None,:])[0][[0,2]]/1852
                else:self.center=np.array([np.interp(self.cursor,data['time'],data['x']),np.interp(self.cursor,data['time'],data['y'])])
                self.sync_limits()
        self.update_frame()

    def update_tree(self):
        for row,keys in self.row_members.items():
            count=sum(self.members[key] for key in keys)
            mark='[x]' if count==len(keys) else '[-]' if count else '[ ]'
            if row.startswith('group:'):label=keys[0][0] if keys[0][0]=='Other Aircraft' else 'Flight '+keys[0][0]
            else:
                key=keys[0];label=self.member_labels[key]
            self.tree.item(row,text=label);self.tree.set(row,'visibility',mark)

    def tree_click(self,event):
        if self.tree.identify_element(event.x,event.y).endswith('indicator'):return
        row=self.tree.identify_row(event.y)
        if row and (row.startswith('group:') or self.tree.identify_column(event.x)=='#1'):
            self.tree.focus(row);self.toggle_row(row);return 'break'
        if row.startswith(('member:','enemy:','missile:','sam:')):
            key=self.row_members[row][0] if row.startswith('member:') else (row.split(':')[0],int(row.split(':')[1]))
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
        elif layer=='sam':
            self.sam_visible=not self.sam_visible
            self.sam_btn.configure(style='Selected.TButton' if self.sam_visible else 'TButton')
        elif layer in self.missile_layers:
            enabled=not self.missile_layers[layer]
            self.missile_layers.update(air_to_air=enabled,ground_to_air=enabled,other=enabled)
            self.missile_buttons[layer].configure(style='Selected.TButton' if self.missile_layers[layer] else 'TButton')
        self.update_frame()

    def only_players(self):
        if self.only_players_enabled:
            previous=self.only_players_previous
            self.only_players_enabled=False;self.only_players_previous=None
            self.only_players_btn.configure(style='TButton')
            if previous is not None:
                members,enemy,sam=previous
                for key in self.members:self.members[key]=members.get(key,True)
                self.enemy_visible=enemy;self.enemy_btn.configure(style='Selected.TButton' if enemy else 'TButton')
                self.sam_visible=sam;self.sam_btn.configure(style='Selected.TButton' if sam else 'TButton')
            self.update_tree();self.update_frame();return
        self.only_players_previous=(dict(self.members),self.enemy_visible,self.sam_visible)
        self.only_players_enabled=True;self.only_players_btn.configure(style='Selected.TButton')
        self.apply_only_players();self.update_frame()

    def apply_only_players(self):
        players={data.get('member') for data in self.data if data['category']=='friendly' and is_player_aircraft(data)}
        for key in self.members:self.members[key]=key in players
        self.enemy_visible=False;self.enemy_btn.configure(style='TButton')
        self.sam_visible=False;self.sam_btn.configure(style='TButton')
        self.update_tree()

    def update_only_players_state(self):
        if self.only_players_enabled and (self.enemy_visible or self.sam_visible or any(
                data['category']=='friendly' and not is_player_aircraft(data) and self.members.get(data.get('member'),False)
                for data in self.data)):
            self.only_players_enabled=False;self.only_players_previous=None
            self.only_players_btn.configure(style='TButton')

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
        self.aircraft_data=[d for d in self.data if d['category'] in ('friendly','enemy')]
        self.weapon_data=[d for d in self.data if d['category'] in ('missile','bullet')]
        self.weapon_starts=np.array([d['time'][0] for d in self.weapon_data])
        self.weapon_ends=np.array([d['time'][-1] for d in self.weapon_data])
        self.weapon_bullets=np.array([d['category']=='bullet' for d in self.weapon_data],dtype=bool)
        self.render_sources={d['entity']:d for d in self.data if d['category'] in ('friendly','enemy','sam')}
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
            if data['category'] in ('missile','bullet','sam'):continue
            color=ENEMY_COLOR if data['category']=='enemy' else self.colors[data['flight']]
            data['line']=LineCollection([],linewidths=AIRCRAFT_TRAIL_WIDTH,zorder=3);ax.add_collection(data['line'])
            data['marker'],=ax.plot([],[],color=color,marker='^',markersize=AIRCRAFT_SIZE,ls='',zorder=11)
            label=data['callsign']
            model=data.get('airframe') or 'Unknown Aircraft'
            if named_airframe(label)!=model:label+=' - '+model
            data['label']=ax.annotate(label,(0,0),xytext=(6,5),textcoords='offset points',color=color,fontsize=8,in_layout=False)
        self.sam_rings=LineCollection([],colors=SAM_COLOR,linewidths=.9,alpha=.6,zorder=2)
        ax.add_collection(self.sam_rings)
        self.sam_centers=ax.scatter([],[],s=10,marker='o',color=SAM_COLOR,zorder=2)
        self.sam_ring_signature=None
        self.missile_trails=LineCollection([],colors=MISSILE_COLOR,linewidths=MISSILE_TRAIL_WIDTH,linestyles='dashed',zorder=4)
        ax.add_collection(self.missile_trails)
        self.missile_markers=ax.scatter([],[],s=7,marker='D',color=MISSILE_COLOR,zorder=12)
        self.missile_explosions=ax.scatter([],[],s=[],marker='o',facecolors='none',edgecolors=[],linewidths=2,zorder=13)
        self.bomb_pulses=ax.scatter([],[],s=[],marker='o',facecolors='none',edgecolors=[],linewidths=.8,zorder=13)
        self.landing_ring=Circle((0,0),35,fill=False,edgecolor='#c4c9cf',linewidth=.8,linestyle='--',alpha=.6,zorder=2,visible=self.only_landing)
        ax.add_patch(self.landing_ring)
        self.bullet_trails=LineCollection([],colors=BULLET_COLOR,linewidths=.6,zorder=4)
        ax.add_collection(self.bullet_trails)
        self.bullet_markers=ax.scatter([],[],s=4,marker='D',color=BULLET_COLOR,edgecolors='none',zorder=12)
        self.selection_horizontal=ax.axhline(0,color=TEXT,lw=.8,alpha=.55,zorder=9,visible=False)
        self.selection_vertical=ax.axvline(0,color=TEXT,lw=.8,alpha=.55,zorder=9,visible=False)
        moving=[self.north_arrow,self.north_label,self.missile_trails,self.missile_markers,self.bullet_trails,self.bullet_markers,self.missile_explosions,
                self.selection_horizontal,self.selection_vertical,self.sam_rings,self.sam_centers,self.bomb_pulses,self.landing_ring]
        for data in self.data:
            if data['category'] in ('friendly','enemy'):moving.extend((data['line'],data['marker'],data['label']))
        moving.extend(artist for artist in ax.collections if artist not in moving and artist.get_zorder()>=5)
        self.landing_clip=Circle((0,0),35,transform=ax.transData)
        self.apply_landing_clip()
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
            width=round(button.winfo_reqwidth()*1.15);height=round(button.winfo_reqheight()*1.15)
            button.place(x=x,y=y,width=width,height=height);button.lift();x+=width+3
        self.place_glide()

    def place_glide(self):
        if not self.glide_visible:return
        widget=self.canvas.get_tk_widget()
        size=int(max(80,min(340,self.map.bbox.width*.48,self.map.bbox.height*.65)))
        x=max(0,int(self.map.bbox.x1-size-8));y=max(0,int(widget.winfo_height()-self.map.bbox.y1+8))
        self.glide_page.place(x=x,y=y,width=size,height=size);self.glide_page.lift()

    def update_frame(self):
        if self.dropdown_busy:return
        self.update_only_players_state()
        self.update_list_visibility()
        self.update_carrier_marker()
        self.clock_value.set(clock(self.cursor));self.time_value.set(self.cursor);self.layout_timestamp()
        length=self.app.settings.replay_trail_length_sec;fade=self.app.settings.replay_trail_fade_sec
        missile_points=[];missile_point_colors=[];missile_lines=[];missile_colors=[];bullet_points=[];bullet_lines=[];bullet_colors=[];bursts=[];bomb_pulses=[]
        self.missile_inspect_points=[]
        # Gun rounds are visible only at the close half of the default 2 NM view.
        bullets_in_view=self.radius<=1.
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
        sources=self.render_sources
        self.update_sam_rings()
        weapons=[]
        if any(self.missile_layers.values()) and len(self.weapon_data):
            # Do not build trails for future weapons or trails that have expired.
            tail=max(length,EXPLOSION_DURATION) if length>0 else EXPLOSION_DURATION
            ends=np.where(self.weapon_bullets,self.weapon_ends+2,
                          np.inf if length==0 else self.weapon_ends+tail)
            eligible=(self.weapon_starts<=self.cursor)&(self.cursor<=ends)
            if not bullets_in_view:eligible&=~self.weapon_bullets
            weapons=[self.weapon_data[i] for i in np.flatnonzero(eligible)]
        for data in (*self.aircraft_data,*weapons):
            t=data['time']
            if data['category']=='bullet' and (not bullets_in_view or self.cursor<t[0] or self.cursor>t[-1]+2):continue
            index=int(np.searchsorted(t,self.cursor,side='right'))
            active=track_is_active(data,self.cursor,index)
            if active and self.only_landing:
                active=np.hypot(np.interp(self.cursor,t,data['x']),np.interp(self.cursor,t,data['y']))<=35
            if data['category']=='sam':continue
            if data['category'] in ('missile','bullet'):
                source=sources.get(data.get('source'))
                source_visible=source is not None and (self.sam_visible if source['category']=='sam' else self.enemy_visible if source['category']=='enemy' else self.members.get(source['member'],False))
                visible=source_visible and self.missile_layers.get(data['missile_role'],False)
                if data['category']=='bullet':
                    if visible and bullets_in_view:
                        segments,alpha=trail_segments(data,self.cursor,2,1)
                        bullet_lines.extend(segments);bullet_colors.extend(trail_colors(BULLET_COLOR,alpha,.7))
                    if active and visible and bullets_in_view:
                        x=float(np.interp(self.cursor,t,data['x']));y=float(np.interp(self.cursor,t,data['y']))
                        if self.map.get_xlim()[0]<=x<=self.map.get_xlim()[1] and self.map.get_ylim()[0]<=y<=self.map.get_ylim()[1]:bullet_points.append((x,y))
                    continue
                if visible:
                    segments,alpha=trail_segments(data,self.cursor,length,fade)
                    missile_lines.extend(segments)
                    trail_color=BOMB_COLOR if data.get('bomb') else '#ff5555' if data['missile_role']=='ground_to_air' else MISSILE_COLOR
                    missile_colors.extend(trail_colors(trail_color,alpha,.65))
                if visible and t[-1]<self.end-1e-6 and 0<=self.cursor-t[-1]<EXPLOSION_DURATION:
                    if data.get('bomb'):bomb_pulses.append((data['x'][-1],data['y'][-1],(self.cursor-t[-1])/EXPLOSION_DURATION,True))
                    else:bursts.append((data['x'][-1],data['y'][-1],self.cursor-t[-1]))
                if active and visible:
                    x=float(np.interp(self.cursor,t,data['x']));y=float(np.interp(self.cursor,t,data['y']))
                    missile_points.append((x,y))
                    missile_point_colors.append(bomb_color(self.cursor) if data.get('bomb') else sam_missile_color(self.cursor) if data['missile_role']=='ground_to_air' else missile_color(self.cursor))
                    if data.get('bomb'):bomb_pulses.append((x,y,((self.cursor-t[0])/.9)%1))
                    self.missile_inspect_points.append((data,x,y))
                    self.highlight_selection(data,x,y)
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
                self.highlight_selection(data,x,y)
            else:data['marker'].set_data([],[]);data['label'].set_visible(False)
            data['line'].set_visible(enabled)
            if enabled:
                segments,alpha=trail_segments(data,self.cursor,length,fade)
                color=ENEMY_COLOR if data['category']=='enemy' else self.colors[data['flight']]
                data['line'].set_segments(segments)
                data['line'].set_colors(trail_colors(color,alpha,.7))
        self.missile_markers.set_offsets(np.asarray(missile_points).reshape(-1,2))
        self.bullet_trails.set_segments(bullet_lines);self.bullet_trails.set_colors(bullet_colors)
        self.bullet_markers.set_offsets(np.asarray(bullet_points).reshape(-1,2))
        self.missile_markers.set_paths([missile_path(self.cursor)])
        self.missile_markers.set_sizes([missile_size(self.cursor)])
        self.missile_markers.set_color(np.asarray(missile_point_colors).reshape(-1,4))
        update_explosions(self.missile_explosions,bursts,self.fig.dpi)
        update_bomb_pulses(self.bomb_pulses,bomb_pulses,self.fig.dpi)
        self.missile_trails.set_segments(missile_lines);self.missile_trails.set_colors(missile_colors)
        self.inspector.update(self.cursor)
        self.glide_occupied=self.glide_page.update();self.update_glide_button()
        self.renderer.paint()

    def update_sam_rings(self):
        self.sam_inspect_points=[]
        visible=[d for d in self.data if d['category']=='sam' and self.sam_visible and track_is_active(d,self.cursor)]
        self.sam_rings.set_visible(bool(visible));self.sam_centers.set_visible(bool(visible))
        if not visible:return
        world=np.array([[np.interp(self.cursor,d['track']['rows'][:,0],d['track']['rows'][:,axis])/1852
                         for axis in (1,2,3)] for d in visible])
        signature=(tuple(d['entity'] for d in visible),world.tobytes())
        if signature!=self.sam_ring_signature:
            self.sam_ring_signature=signature
            ring_sites=[i for i,d in enumerate(visible) if d['threat_range_nm'] is not None]
            self.sam_world_segments=threat_circle_segments(world[ring_sites],[visible[i]['threat_range_nm'] for i in ring_sites])
        rows=self.app.carrier['rows']
        origin=np.array([np.interp(self.cursor,rows[:,0],rows[:,axis])/1852 for axis in (1,2,3)])
        rotation=interpolate_quaternions(rows[:,0],quaternion_candidate(rows[:,7]),np.array([self.cursor]))
        inverse_rotation=inverse(rotation)
        centers=rotate(inverse_rotation,world-origin)
        self.sam_centers.set_offsets(centers[:,[0,2]])
        for data,(x,y) in zip(visible,centers[:,[0,2]]):
            if self.only_landing and np.hypot(x,y)>35:continue
            self.sam_inspect_points.append((data,x,y));self.highlight_selection(data,x,y)
        local=rotate(inverse_rotation,self.sam_world_segments.reshape(-1,3)-origin)
        self.sam_rings.set_segments(local[:,[0,2]].reshape(-1,2,2))

    def apply_landing_clip(self):
        self.landing_ring.set_visible(self.only_landing)
        artists=[self.sam_rings,self.sam_centers,self.missile_trails,self.missile_markers,
                 self.missile_explosions,self.bullet_markers,self.bullet_trails,self.bomb_pulses]
        for data in self.data:
            if data['category'] in ('friendly','enemy'):artists.extend((data['line'],data['marker'],data['label']))
        for artist in artists:artist.set_clip_path(self.landing_clip if self.only_landing else None)

    def toggle_only_landing(self):
        self.set_only_landing(not self.only_landing)

    def set_only_landing(self,enabled):
        self.only_landing=bool(enabled)
        self.only_landing_btn.configure(style='Selected.TButton' if self.only_landing else 'TButton')
        if self.only_landing:
            self.enemy_visible=False;self.sam_visible=False
            self.missile_layers.update(air_to_air=False,ground_to_air=False,other=False)
            for button in (self.enemy_btn,self.sam_btn,self.missile_buttons['air_to_air']):button.configure(style='TButton')
        self.apply_landing_clip();self.update_tree();self.update_frame()

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
        seconds=SKIP_SECONDS[speed]
        self.skip_back_btn.configure(text=f'-{seconds} Sec');self.skip_forward_btn.configure(text=f'+{seconds} Sec')
        for value,button in self.speed_buttons.items():button.configure(style='ReplaySpeed.Selected.TButton' if value==speed else 'TButton')

    def skip(self,direction):
        self.seek(self.cursor+direction*SKIP_SECONDS[self.speed])

    def toggle_play(self):
        if self.playing:
            self.app.play_sound('wire');self.pause();return
        if not self.data or not self.active:return
        self.app.play_sound('wire')
        if self.cursor>=self.end:self.seek(self.start)
        self.playing=True;self.play_btn.configure(text='▶',image='',style='ReplayPlay.TButton');self.last_tick=time.monotonic();self.tick()

    def pause(self):
        self.playing=False
        if self.play_job is not None:self.after_cancel(self.play_job);self.play_job=None
        self.play_btn.configure(text='    ',image=self.pause_icon,style='ReplayPause.TButton')

    def register_dropdown(self,widget):
        widget.configure(postcommand=lambda:self.dropdown_opened(widget))

    def dropdown_opened(self,widget):
        # Native menus run a nested event loop on macOS. Avoid canvas blits
        # and follow-camera redraws until that menu has returned control.
        self.dropdown_busy=True;self.dropdown_widget=widget
        self.dropdown_started=time.monotonic();self.dropdown_seen=False
        self.last_tick=self.dropdown_started
        if self.play_job is not None:self.after_cancel(self.play_job);self.play_job=None
        if self.dropdown_job is not None:self.after_cancel(self.dropdown_job);self.dropdown_job=None
        if not self.dropdown_aqua:self.dropdown_job=self.after(40,self.poll_dropdown)

    def dropdown_post_returned(self,command,code,result,operation):
        # Aqua's Post returns after the native menu closes, including cancel.
        words=self.tk.splitlist(command)
        if self.dropdown_busy and self.dropdown_widget is not None and len(words)>1 and words[1]==str(self.dropdown_widget):
            self.dropdown_closed()

    def poll_dropdown(self):
        self.dropdown_job=None
        if not self.dropdown_busy:return
        widget=self.dropdown_widget;popup=str(widget)+'.popdown'
        try:mapped=bool(int(self.tk.call('winfo','ismapped',popup))) if widget.winfo_exists() and int(self.tk.call('winfo','exists',popup)) else False
        except tk.TclError:mapped=False
        self.dropdown_seen|=mapped
        if mapped or not self.dropdown_seen and time.monotonic()-self.dropdown_started<.25:
            self.dropdown_job=self.after(40,self.poll_dropdown)
        else:self.dropdown_closed()

    def dropdown_closed(self):
        if not self.dropdown_busy:return
        if self.dropdown_job is not None:self.after_cancel(self.dropdown_job);self.dropdown_job=None
        self.dropdown_busy=False;self.dropdown_widget=None;self.last_tick=time.monotonic()
        # Let the popup release its native mouse/focus grab before redrawing.
        if self.dropdown_finish_job is None:self.dropdown_finish_job=self.after_idle(self.finish_dropdown)

    def finish_dropdown(self):
        self.dropdown_finish_job=None
        if self.dropdown_busy or not self.winfo_exists():return
        self.update_frame()
        if self.playing and self.active and self.play_job is None:
            self.last_tick=time.monotonic();self.play_job=self.after(67,self.tick)

    def tick(self):
        self.play_job=None
        if not self.playing or not self.active or self.dropdown_busy:return
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
        if event.inaxes is self.map and event.button==1:
            if event.dblclick:
                closest=None;distance=10.
                for data in self.data:
                    if data['category'] in ('missile','bullet','sam') or track_is_active(data,self.cursor):continue
                    segments=visible_trail_edges(data['line'])
                    if not len(segments):continue
                    points=self.map.transData.transform(segments.reshape(-1,2)).reshape(-1,2,2)
                    starts=points[:,0];vectors=points[:,1]-starts;mouse=np.array((event.x,event.y))
                    fraction=np.clip(np.sum((mouse-starts)*vectors,axis=1)/np.maximum(np.sum(vectors*vectors,axis=1),1e-9),0,1)
                    gap=float(np.min(np.linalg.norm(mouse-starts-fraction[:,None]*vectors,axis=1)))
                    if gap<distance:closest=data;distance=gap
                if closest is not None:
                    self.drag=None;self.jump_to_track_start(closest);return
            self.drag=(event.x,event.y,self.center.copy())

    def motion(self,event):
        if self.drag is None or event.x is None or event.y is None:return
        x,y,center=self.drag
        if np.hypot(event.x-x,event.y-y)<4:return
        self.set_follow(False)
        self.center=center-np.array([(event.x-x)*np.diff(self.map.get_xlim())[0]/max(self.map.bbox.width,1),
                                     (event.y-y)*2*self.radius/max(self.map.bbox.height,1)])
        self.sync_limits();self.canvas.draw_idle()

    def highlight_selection(self,data,x,y):
        if data.get('inspect_key')!=self.inspector.selected:return
        self.selection_horizontal.set_ydata([y,y]);self.selection_horizontal.set_visible(True)
        self.selection_vertical.set_xdata([x,x]);self.selection_vertical.set_visible(True)
        if self.follow:self.center=np.array([x,y]);self.sync_limits()

    def layout_timestamp(self):
        width=max(self.timestamp_bar.winfo_width(),1);half=self.current_timestamp.winfo_reqwidth()/2
        fraction=np.clip((self.cursor-self.start)/max(self.end-self.start,1e-9),0,1)
        x=np.clip(10+fraction*max(width-20,0),min(half,width/2),max(width-half,width/2))
        self.current_timestamp.place(x=x,y=1,anchor='n')

    def release(self,event):
        drag=self.drag;self.drag=None
        if drag is None or event.inaxes is not self.map or event.x is None or event.y is None:return
        if np.hypot(event.x-drag[0],event.y-drag[1])>5:return
        closest=None;distance=13
        for data in self.data:
            if data['category'] in ('missile','bullet','sam') or not data['marker'].get_visible():continue
            x,y=data['marker'].get_data()
            if not len(x):continue
            px,py=self.map.transData.transform((x[0],y[0]));gap=np.hypot(event.x-px,event.y-py)
            if gap<distance:closest=data;distance=gap
        for data,x,y in (*self.missile_inspect_points,*self.sam_inspect_points):
            px,py=self.map.transData.transform((x,y));gap=np.hypot(event.x-px,event.y-py)
            if gap<distance:closest=data;distance=gap
        if closest is not None:
            if closest['inspect_key']==self.inspector.selected:self.set_follow(True)
            self.select_aircraft(closest['inspect_key'])

    def scroll(self,event):
        if event.inaxes is self.map and event.xdata is not None and event.ydata is not None:
            self.zoom(1/1.2 if event.button=='up' else 1.2,np.array([event.xdata,event.ydata]))

    def destroyed(self,event):
        if event.widget is not self:return
        if self.dropdown_trace is not None:
            self.tk.call('trace','remove','execution','ttk::combobox::Post','leave',self.dropdown_trace)
            self.dropdown_trace=None
        for job in (self.play_job,self.poll_job,self.glide_blink_job,self.dropdown_job,self.dropdown_finish_job):
            if job is not None:self.after_cancel(job)
        self.generation+=1
