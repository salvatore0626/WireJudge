"""Animated start-screen diorama using the map's actual unit renderers."""
import math
import time
import tkinter as tk
from types import SimpleNamespace
from .game_aircraft import Aircraft, AirOperations
from .game_combat import CombatWorld, Factory
from .game_campaign import EnemyRunway
from replay.replay_style import AIRCRAFT_SIZE


class StartSceneModel:
    """Private demonstration models; independent of the player's campaign."""
    def __init__(self):
        from .game_map import CIWS, Flak
        self.world=CombatWorld(2026);self.operations=AirOperations();self.elapsed=0.;self.wall_elapsed=0.;self.next_departure=0.
        self.runway=EnemyRunway(1,-6.1,-.6,name='Airfield Alpha 1')
        self.world.factories=[self.runway,Factory(2,-7.7,-1.2),Factory(3,-7.7,.1)]
        self.world.known={unit.id for unit in self.world.factories}
        self.guns=[Flak(1,-4.5,-2.8,enemy=True,ammo=100000),CIWS(2,6.3,-1.6,enemy=True,ammo=100000)]
        self.world.enemy_sams=self.guns;self.world.known_ground={id(g) for g in self.guns}
        self.flyby=Aircraft('Fighter',enemy=False,state='airborne')
        self.flyby.health=math.inf;self.flyby.color='#438cff';self.flyby.speed=self.flyby.cruise_speed
        self.world.friendly_aircraft=[self.flyby];self.fighters=[]
        self.depart()
        self.update_flyby()

    def depart(self):
        fighter=Aircraft('Fighter',enemy=True,state='takeoff',color='#ef6262')
        fighter.x=self.runway.x;fighter.y=self.runway.y-.65;fighter.heading=0.;fighter.speed=0.;fighter.health=math.inf
        fighter.mode='path';fighter.path=[(self.runway.x,2.5),(-3.5,5.4),(3,5.8),(14,3.5)];fighter.waypoint=0
        fighter.demo_born=self.wall_elapsed;self.fighters.append(fighter)
        self.world.enemies=self.fighters
        self.next_departure=self.wall_elapsed+6.

    def update_flyby(self):
        # A looping flyby puts a visible target in both defenses' firing arcs.
        t=self.wall_elapsed*.35
        self.flyby.x=1.+6.*math.sin(t);self.flyby.y=.2+1.3*math.cos(t)
        self.flyby.heading=math.atan2(6.*math.cos(t),-1.3*math.sin(t))

    def advance(self,seconds):
        seconds=max(0.,min(.15,seconds));self.wall_elapsed+=seconds
        if self.wall_elapsed>=self.next_departure:self.depart()
        self.fighters[:]=[a for a in self.fighters if self.wall_elapsed-a.demo_born<25.]
        self.world.enemies=self.fighters;self.update_flyby()
        # Accelerated display time makes takeoffs and shell bursts readable quickly.
        remaining=seconds*6.
        while remaining>1e-9:
            dt=min(.1,remaining);remaining-=dt;self.elapsed+=dt
            for fighter in self.fighters:self.operations.step(fighter,dt)
            self.world.advance(self.elapsed)
        for gun in self.guns:
            target=gun.attack_target
            if target is not None:gun.heading=math.atan2(target.x-gun.x,target.y-gun.y)


class StartSceneRenderer:
    """Bind the existing game-map drawing methods to the private scene models."""
    def __init__(self,source,canvas,model):
        self.source=source;self.canvas=canvas;self.model=model;self.combat=model.world
        self.airfield=model.runway;self.aircraft={0:model.flyby};self.aircraft_vertices=source.aircraft_vertices
        self.selected=None;self.see_all=True;self.view_width=20.;self.elapsed=0.
        self.radars=[];self.sams=[];self.ciws=[];self.player_silos=[]
        self.placing_player_silo=False;self.silo_target_picker=None;self.pointer=None
        self.ciws_glyphs={};self.sam_glyphs={};self.radar_sweeps={}

    def __getattr__(self,name):
        method=getattr(type(self.source),name,None)
        if callable(method):return method.__get__(self,type(self))
        raise AttributeError(name)

    def scale(self):return max(1,self.canvas.winfo_width())/self.view_width
    def pixel(self,x,y):return self.canvas.winfo_width()/2+x*self.scale(),self.canvas.winfo_height()*.62-y*self.scale()
    def building_factor(self):return 2.5
    def ground_dot_required(self,unit):return False

    def draw(self):
        c=self.canvas;self.elapsed=self.model.elapsed
        c.delete('game_aircraft');c.delete('ciws_icon');self.ciws_glyphs={}
        # Live map renderers supply the runway, structures, bullets, shells and bursts.
        self.render_combat()
        for gun in self.model.guns:self.draw_ciws(gun)
        size=2.1*AIRCRAFT_SIZE*c.winfo_fpixels('1i')/72
        for aircraft in [*self.model.fighters,self.model.flyby]:
            x,y=self.pixel(aircraft.x,aircraft.y)
            self.draw_aircraft_unit(aircraft,x,y,aircraft.heading,True,size)
        if c.find_withtag('game_aircraft'):c.tag_lower('airfield_icons','game_aircraft')


class StartScene(tk.Canvas):
    def __init__(self,parent,source):
        super().__init__(parent,background='#101c2b',highlightthickness=0)
        self.model=StartSceneModel();self.renderer=StartSceneRenderer(source,self,self.model)
        self.job=None;self.running=False;self.last_time=None;self.grid_size=None
        self.bind('<Destroy>',lambda event:self.stop() if event.widget is self else None,add='+')

    def draw_grid(self):
        size=(self.winfo_width(),self.winfo_height())
        if size==self.grid_size:return
        self.grid_size=size;self.delete('intro_grid')
        for x in range(0,size[0],64):self.create_line(x,0,x,size[1],fill='#1c2d43',tags='intro_grid')
        for y in range(0,size[1],64):self.create_line(0,y,size[0],y,fill='#1c2d43',tags='intro_grid')
        self.tag_lower('intro_grid')

    def start(self):
        if self.running:return
        self.running=True;self.last_time=None;self.animate()

    def animate(self):
        self.job=None
        if not self.running:return
        if not self.winfo_ismapped():
            self.last_time=None;self.job=self.after(200,self.animate);return
        now=time.monotonic();dt=0. if self.last_time is None else now-self.last_time;self.last_time=now
        self.model.advance(dt);self.draw_grid();self.renderer.draw()
        self.job=self.after(50,self.animate)

    def stop(self):
        self.running=False;self.last_time=None
        if self.job is not None:self.after_cancel(self.job);self.job=None
