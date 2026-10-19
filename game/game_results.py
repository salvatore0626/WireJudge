"""Animated campaign results cards; animation runs on wall-clock time."""
import math
import time
import random
from types import SimpleNamespace
from .game_aircraft import Aircraft, AirOperations
from .game_combat import Factory, Bunker, DroneLauncher, ICBMSilo, ICBM
from .game_campaign import EnemyRunway
from replay.replay_style import AIRCRAFT_SIZE
import tkinter as tk
from tkinter import ttk
from .game_aircraft_inspector import BG,FACE,TEXT,MUTED

UNIT_CARDS=(('Fighter','Fighters'),('Bomber','Bombers'),('Suicide Drone','Suicide Drones'),('ICBM','ICBMs intercepted'),('Airfield','Airfields'),('Factory','Factories'),('Bunker','Bunkers'),('Flak','Flak'),('SAM','SAM'),('LR SAM','LR SAM'),('Radar','Radar'),('LR Radar','LR Radar'),('SAAW','SAAW'),('CIWS','CIWS'),('Drone Launcher','Drone launchers'),('ICBM Silo','ICBM silos'))


def results_header(campaign,elapsed):
    hours,remainder=divmod(int(elapsed),3600);minutes,seconds=divmod(remainder,60)
    counts=campaign.destroyed_types
    aircraft=sum(counts.get(k,0) for k in ('Fighter','Bomber','Suicide Drone'))
    totals=campaign.combat.weapon_totals
    return (f'{hours:02d}:{minutes:02d}:{seconds:02d} elapsed   ·   Aircraft destroyed: {aircraft}   ·   Friendly losses: {campaign.lost}\n'
            f'Bullets: {totals["bullets"]:,}   ·   Missiles: {totals["missiles"]:,}   ·   Flak shells: {totals["flak shells"]:,}   ·   Bombs: {totals["bombs"]:,}')


class ResultUnitRenderer:
    """Isolated display models using the live map's drawing and animation methods."""
    def __init__(self,source,canvas,kind):
        # Import after game_map has finished loading; no circular module initialization.
        from .game_map import Radar, SAMLauncher, SAAW, CIWS, Flak, Airfield
        self.source=source;self.canvas=canvas;self.kind=kind;self.selected=None;self.see_all=True
        self.aircraft_vertices=source.aircraft_vertices;self.elapsed=0.;self.last_time=None
        self.random=random.Random(kind);self.view_width=25
        self.radars=[];self.sams=[];self.ciws=[]
        self.radar_sweeps={};self.sam_glyphs={};self.ciws_glyphs={}
        self.combat=SimpleNamespace(enemy_radars=[],enemy_sams=[],missiles=[],identified_ground=set())
        self.operations=AirOperations()
        if kind in ('Fighter','Bomber','Suicide Drone'):
            unit=Aircraft(kind,enemy=True,state='airborne',color='#ffe66d' if kind=='Suicide Drone' else '#ef6262')
            unit.mode='loiter';unit.orbit_center=(0.,0.);unit.orbit_radius=unit.full_speed_orbit_radius
            unit.x=unit.orbit_radius;unit.y=0.;unit.heading=math.pi;unit.speed=unit.cruise_speed
        elif kind=='ICBM':unit=ICBM(None,Airfield(),1)
        elif kind=='Airfield':unit=EnemyRunway(1,0,0)
        elif kind in ('Factory','Bunker','Drone Launcher','ICBM Silo'):
            unit={'Factory':Factory,'Bunker':Bunker,'Drone Launcher':DroneLauncher,'ICBM Silo':ICBMSilo}[kind](1,0,0)
        elif kind in ('Radar','LR Radar'):
            unit=Radar(1,0,0,enemy=True,long_range=kind=='LR Radar');self.combat.enemy_radars=[unit]
        else:
            cls={'SAM':SAMLauncher,'LR SAM':SAMLauncher,'SAAW':SAAW,'CIWS':CIWS,'Flak':Flak}[kind]
            kwargs={'enemy':True}
            if kind in ('SAM','LR SAM'):kwargs['long_range']=kind=='LR SAM'
            unit=cls(1,0,0,**kwargs);self.combat.enemy_sams=[unit]
        self.unit=unit

    def __getattr__(self,name):
        method=getattr(type(self.source),name,None)
        if callable(method):return method.__get__(self,type(self))
        raise AttributeError(name)

    def pixel(self,x,y):return max(140,self.canvas.winfo_width())/2,65
    def scale(self):return 24.
    def building_factor(self):return 2.
    def ground_dot_required(self,unit):return False

    def draw(self,now):
        dt=0. if self.last_time is None else max(0.,min(.5,now-self.last_time))
        self.last_time=now;self.elapsed+=dt
        # Preserve card labels/counts; remove only the tags used by the map renderers.
        for tag in ('game_aircraft','game_combat','radar_icon','radar_sweep','sam_icon','sam_glyph','ciws_icon'):
            self.canvas.delete(tag)
        self.radar_sweeps={};self.sam_glyphs={};self.ciws_glyphs={}
        self.rotate_radars();self.rotate_sams();self.rotate_ciws()
        if self.kind in ('Fighter','Bomber','Suicide Drone'):
            if dt>0:self.operations.step(self.unit,dt)
            x,y=self.pixel(self.unit.x,self.unit.y)
            size=4*AIRCRAFT_SIZE*self.canvas.winfo_fpixels('1i')/72
            self.draw_aircraft_unit(self.unit,x,y,self.unit.heading,True,size)
        elif self.kind=='ICBM':self.draw_icbm_unit(self.unit,show_label=False)
        elif self.kind in ('Factory','Bunker','Airfield','Drone Launcher','ICBM Silo'):
            self.draw_enemy_structure(self.unit,show_label=False)
        elif self.kind in ('Radar','LR Radar'):self.draw_radar(self.unit)
        else:self.draw_sam(self.unit)


class ResultBoard(ttk.Frame):
    def __init__(self,parent,campaign,source):
        super().__init__(parent)
        self.cards=[];self.renderers=[];self.job=None;self.running=True;self.columns=None
        self.canvas=tk.Canvas(self,width=780,height=380,background=BG,highlightthickness=0)
        bar=ttk.Scrollbar(self,orient='vertical',command=self.canvas.yview)
        bar.pack(side='right',fill='y');self.canvas.pack(side='left',fill='both',expand=True)
        self.canvas.configure(yscrollcommand=bar.set)
        self.content=ttk.Frame(self.canvas);self.window=self.canvas.create_window(0,0,window=self.content,anchor='nw')
        for kind,label in UNIT_CARDS:
            count=campaign.icbms_intercepted if kind=='ICBM' else campaign.destroyed_types.get(kind,0)
            card=tk.Canvas(self.content,width=140,height=146,background=FACE,highlightthickness=1,highlightbackground='#405168')
            card.create_text(70,14,text=label,fill=MUTED,font=('Helvetica',9,'bold'),tags='card_title')
            card.create_text(70,123,text=f'{count:,}',fill='#ffffff' if count else '#65758a',font=('Helvetica',23,'bold'),tags='card_count')
            card.bind('<Configure>',lambda e:(e.widget.coords('card_title',e.width/2,14),e.widget.coords('card_count',e.width/2,123)))
            self.cards.append((kind,card))
            self.renderers.append(ResultUnitRenderer(source,card,kind))
            for event in ('<MouseWheel>','<Button-4>','<Button-5>'):card.bind(event,self.scroll)
        self.canvas.bind('<Configure>',self.resize)
        self.content.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<MouseWheel>',self.scroll)
        self.bind('<Destroy>',lambda e:self.stop() if e.widget is self else None)
        self.animate()

    def resize(self,event):
        self.canvas.itemconfigure(self.window,width=event.width)
        columns=max(1,min(4,event.width//154))
        if columns==self.columns:return
        self.columns=columns
        for col in range(4):self.content.columnconfigure(col,weight=1 if col<columns else 0)
        for i,(kind,card) in enumerate(self.cards):card.grid(row=i//columns,column=i%columns,padx=5,pady=5,sticky='ew')
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def scroll(self,event):
        self.canvas.yview_scroll(-1 if getattr(event,'num',None)==4 or getattr(event,'delta',0)>0 else 1,'units')
        return 'break'

    def animate(self):
        self.job=None
        if not self.running:return
        now=time.monotonic()
        for renderer in self.renderers:renderer.draw(now)
        self.job=self.after(100,self.animate)

    def stop(self):
        self.running=False
        if self.job is not None:self.after_cancel(self.job);self.job=None
