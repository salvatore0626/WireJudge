"""Ground-unit health, ammunition, and local aircraft scope instruments."""
import math
import tkinter as tk
from .game_aircraft_inspector import BG,FACE,TEXT,MUTED,health_color
from .game_settings import STATS

class GroundInspector(tk.Canvas):
    def __init__(self,parent):
        super().__init__(parent,width=270,height=330,background=BG,highlightthickness=0)
        self.unit=None;self.aircraft=[];self.elapsed=0.;self.mode='';self.width_seen=0
        self.weapons=[];self.scope_dots=[];self.scope_updated=-math.inf
        self.bind('<Configure>',self.resized)

    def resized(self,event):
        if event.width!=self.width_seen:
            self.width_seen=event.width
            if self.unit is not None:self.render()

    def update_unit(self,unit,mode,aircraft,elapsed,weapons=()):
        state=(getattr(unit,'enabled',True),getattr(unit,'radar_range_nm',unit.range_nm))
        if self.unit is not unit or self.mode!=mode or state!=getattr(self,'scope_state',None):self.scope_updated=-math.inf
        self.scope_state=state
        self.unit=unit;self.mode=mode;self.aircraft=list(aircraft);self.weapons=list(weapons);self.elapsed=elapsed
        self.refresh_scope_contacts();self.render()

    def scope_point(self,aircraft):
        unit=self.unit;radius=self.scope_range
        if radius<=0:return None
        if not aircraft.alive or (self.mode!='pac3' and not getattr(aircraft,'sensors_active',True)):return None
        x,y=aircraft.position(self.elapsed) if hasattr(aircraft,'position') else (aircraft.x,aircraft.y)
        dx,dy=x-unit.x,y-unit.y
        if math.hypot(dx,dy)>radius:return None
        if self.mode in ('radar','ewr','ciws','saaw') and not unit.radar_detects(x,y):return None
        if self.mode=='flak' and not unit.visual_detects(x,y):return None
        return 135+dx/radius*96,191-dy/radius*96

    @property
    def scope_range(self):return self.unit.visual_range_nm if self.mode=='flak' else getattr(self.unit,'radar_range_nm',self.unit.range_nm)

    def refresh_scope_contacts(self):
        if self.unit is None or self.mode=='sam':return False
        if self.elapsed>=self.scope_updated and self.elapsed-self.scope_updated<STATS['world']['scope_refresh_seconds']-1e-9:return False
        self.scope_updated=self.elapsed;self.scope_dots=[]
        for aircraft in self.aircraft:
            point=self.scope_point(aircraft)
            if point is not None:self.scope_dots.append((*point,'#ef6262' if getattr(aircraft,'enemy',False) else '#69adff'))
        for weapon in self.weapons:
            point=self.scope_point(weapon)
            if point is not None:self.scope_dots.append((*point,'#ef6262'))
        return True

    def draw_scope_contacts(self,factor=1.):
        self.delete('scope_dots')
        for x,y,color in self.scope_dots:
            self.create_oval((x-3)*factor,(y-3)*factor,(x+3)*factor,(y+3)*factor,fill=color,outline='',tags='scope_dots')

    def render(self):
        unit=self.unit
        if unit is None:return
        self.delete('all')
        hp=max(0.,min(1.,unit.health/unit.max_health))
        self.create_rectangle(5,39,265,64,fill=FACE,outline='#405168')
        if hp:self.create_rectangle(6,40,6+258*hp,63,fill=health_color(hp),outline='')
        self.create_rectangle(92,43,178,60,fill=FACE,outline='')
        self.create_text(135,51,text=f'HP {max(0,unit.health):g}/{unit.max_health:g}',fill=TEXT,font=('Helvetica',10,'bold'))
        if self.mode=='sam':
            self.create_text(135,86,text=f'AMMO {unit.ammo}/{unit.ammo_capacity}',fill=MUTED,font=('Helvetica',9,'bold'))
            for i in range(unit.ammo_capacity):
                x=65+i*47;color='#b18aff' if i<unit.ammo else '#405168'
                self.create_polygon(x-6,113,x,100,x+6,113,x+6,148,x-6,148,fill=color,outline='')
                self.create_polygon(x-6,132,x-12,150,x-6,146,x+6,146,x+12,150,x+6,132,fill=color,outline='')
            base_height=175
            if hasattr(unit,'gun_ammo'):
                self.create_text(135,183,text=f'GUN AMMO {unit.gun_ammo}/{unit.gun_ammo_capacity}',fill=MUTED,font=('Helvetica',9,'bold'))
                for i in range(unit.gun_ammo_capacity):
                    x=7+(i%30)*8.8;y=201+(i//30)*13
                    self.create_line(x,y,x,y+8,fill='#ffe66d' if i<unit.gun_ammo else '#303e50',width=2)
                base_height=201+math.ceil(unit.gun_ammo_capacity/30)*13+12
        elif self.mode in ('ewr','pac3'):
            offset=0
            cy=191
            self.create_rectangle(8,89+offset,262,302+offset,fill='#171226' if self.mode=='pac3' else '#071c16',outline='#786195' if self.mode=='pac3' else '#416d58',width=2)
            half=math.radians(unit.radar_angle_deg)/2
            points=[(135,cy)]+[(135+96*math.sin(unit.bearing-half+2*half*i/40),cy-96*math.cos(unit.bearing-half+2*half*i/40)) for i in range(41)]
            if self.mode=='pac3':
                inner=96*unit.stats['min_engagement_range_nm']/unit.range_nm
                points=points[1:]+[(135+inner*math.sin(unit.bearing-half+2*half*i/40),cy-inner*math.cos(unit.bearing-half+2*half*i/40)) for i in range(40,-1,-1)]
            self.create_polygon(*[v for p in points for v in p],fill='#362345' if self.mode=='pac3' else '#103528',outline='#b18aff' if self.mode=='pac3' else '#59e887')
            for radius in (32,64):
                arc=[v for i in range(41) for v in (135+radius*math.sin(unit.bearing-half+2*half*i/40),cy-radius*math.cos(unit.bearing-half+2*half*i/40))]
                self.create_line(*arc,fill='#244d3a')
            self.draw_scope_contacts()
            self.sweep=None if self.mode=='pac3' else self.create_line(135,cy,135,cy-96,fill='#59e887',width=2,tags='scope_sweep')
            self.create_oval(132,cy-3,138,cy+3,fill='#b18aff' if self.mode=='pac3' else '#59e887',outline='')
            self.create_text(135,318+offset,text=f'{unit.range_nm:g} NM · {unit.radar_angle_deg:g}° · Blue friendly / Red enemy',fill=MUTED,font=('Helvetica',8))
            self.command_line=self.create_line(135,cy,135+96*math.sin(unit.desired_bearing),cy-96*math.cos(unit.desired_bearing),fill='#e5d9ff' if self.mode=='pac3' else '#ffe66d',dash=(4,3),width=2,tags='command_bearing')
            base_height=337+offset
        else:
            self.create_oval(33,89,237,293,fill='#071c16',outline='#416d58',width=2)
            for radius in (32,64,96):self.create_oval(135-radius,191-radius,135+radius,191+radius,outline='#244d3a')
            self.create_line(39,191,231,191,fill='#244d3a');self.create_line(135,95,135,287,fill='#244d3a')
            self.draw_scope_contacts()
            self.sweep=self.create_line(135,191,135,95,fill='#59e887',width=2,tags='scope_sweep')
            self.create_oval(132,188,138,194,fill='#59e887',outline='')
            self.create_text(135,310,text=f'{self.scope_range:g} NM · Blue friendly / Red enemy',fill=MUTED,font=('Helvetica',9))
            base_height=330
            if self.mode in ('ciws','flak'):
                self.create_text(135,347,text=f'AMMO {unit.ammo}/{unit.ammo_capacity}',fill=MUTED,font=('Helvetica',9,'bold'))
                # One yellow stroke per remaining bullet; dim strokes show empty slots.
                for i in range(unit.ammo_capacity):
                    x=7+(i%30)*8.8;y=365+(i//30)*13
                    self.create_line(x,y,x,y+8,fill='#ffe66d' if i<unit.ammo else '#303e50',width=2)
                base_height=365+math.ceil(unit.ammo_capacity/30)*13+12
            if self.mode=='saaw':
                self.create_text(135,347,text=f'AMMO {unit.ammo}/{unit.ammo_capacity}',fill=MUTED,font=('Helvetica',9,'bold'))
                count=max(1,unit.ammo_capacity)
                for i in range(unit.ammo_capacity):
                    x=135+(i-(count-1)/2)*min(47,230/count);color='#b18aff' if i<unit.ammo else '#405168'
                    self.create_polygon(x-6,380,x,367,x+6,380,x+6,415,x-6,415,fill=color,outline='')
                    self.create_polygon(x-6,399,x-12,417,x-6,413,x+6,413,x+12,417,x+6,399,fill=color,outline='')
                self.create_text(135,439,text=f'GUN AMMO {unit.gun_ammo}/{unit.gun_ammo_capacity}',fill=MUTED,font=('Helvetica',9,'bold'))
                for i in range(unit.gun_ammo_capacity):
                    x=7+(i%30)*8.8;y=457+(i//30)*13
                    self.create_line(x,y,x,y+8,fill='#ffe66d' if i<unit.gun_ammo else '#303e50',width=2)
                base_height=457+math.ceil(unit.gun_ammo_capacity/30)*13+12
        if self.mode!='sam':
            title='OPTICAL' if self.mode=='flak' else 'SCOPE' if self.mode=='pac3' else 'RADAR'
            self.create_rectangle(95,68,175,83,fill=BG,outline='')
            self.create_text(135,76,text=title,fill=TEXT,font=('Helvetica',10,'bold'))
        width=self.winfo_width();factor=width/270 if width>1 else 1.
        if factor!=1:self.scale('all',0,0,factor,factor)
        height=round(base_height*factor)
        if height!=getattr(self,'render_height',None):self.render_height=height;self.configure(height=height)
        self.animate(self.elapsed)

    def animate(self,elapsed):
        self.elapsed=elapsed
        if self.unit is None or self.mode=='sam':return
        factor=self.winfo_width()/270 if self.winfo_width()>1 else 1.
        if self.refresh_scope_contacts():self.draw_scope_contacts(factor)
        angle=elapsed*math.tau/6 if getattr(self.unit,'enabled',True) else 0.
        if self.mode in ('ewr','pac3'):
            half=math.radians(self.unit.radar_angle_deg)/2
            angle=self.unit.bearing+half*math.sin(elapsed*math.tau/6) if self.unit.enabled else self.unit.bearing
        if self.mode=='pac3':angle=self.unit.bearing
        cy=191
        if self.mode in ('ewr','pac3'):
            self.coords(self.command_line,135*factor,cy*factor,(135+96*math.sin(self.unit.desired_bearing))*factor,(cy-96*math.cos(self.unit.desired_bearing))*factor)
        if self.sweep is not None:self.coords(self.sweep,135*factor,cy*factor,(135+96*math.sin(angle))*factor,(cy-96*math.cos(angle))*factor)


class AmmoInspector(tk.Canvas):
    def __init__(self,parent):
        super().__init__(parent,width=270,height=105,background=BG,highlightthickness=0)
        self.unit=None;self.width_seen=0
        self.bind('<Configure>',self.resized)

    def resized(self,event):
        if event.width!=self.width_seen:
            self.width_seen=event.width
            if self.unit is not None:self.render()

    def update_ammo(self,unit):
        self.unit=unit;self.render()

    def render(self):
        unit=self.unit
        if unit is None:return
        self.delete('all')
        fraction=unit.ammo/unit.ammo_capacity
        self.create_rectangle(8,5,262,27,fill=FACE,outline='#405168')
        if fraction:self.create_rectangle(9,6,9+252*fraction,26,fill='#b18aff',outline='')
        self.create_rectangle(91,8,179,24,fill=FACE,outline='')
        label='DRONES' if unit.stats_key=='Drone Launcher' else 'AMMO'
        self.create_text(135,16,text=f'{label} {unit.ammo}/{unit.ammo_capacity}',fill=TEXT,font=('Helvetica',10,'bold'))
        for i in range(unit.ammo_capacity):
            x=85+i*50;color='#b18aff' if i<unit.ammo else '#405168'
            if unit.stats_key=='Drone Launcher':
                self.create_polygon(x,40,x+4,60,x+19,70,x+19,76,x+4,71,x+4,87,x+10,94,x,91,x-10,94,x-4,87,x-4,71,x-19,76,x-19,70,x-4,60,fill=color,outline='')
            else:self.create_polygon(x,40,x-5,51,x-5,89,x-9,96,x+9,96,x+5,89,x+5,51,fill=color,outline='')
        width=self.winfo_width();factor=width/270 if width>1 else 1.
        if factor!=1:self.scale('all',0,0,factor,factor)
        height=round(105*factor)
        if height!=getattr(self,'render_height',None):self.render_height=height;self.configure(height=height)


class HealthInspector(tk.Canvas):
    def __init__(self,parent):
        super().__init__(parent,width=270,height=35,background=BG,highlightthickness=0)
        self.unit=None;self.width_seen=0
        self.bind('<Configure>',self.resized)

    def resized(self,event):
        if event.width!=self.width_seen:
            self.width_seen=event.width
            if self.unit is not None:self.render()

    def update_health(self,unit):
        self.unit=unit;self.render()

    def render(self):
        unit=self.unit
        if unit is None:return
        self.delete('all')
        fraction=max(0.,min(1.,unit.health/unit.max_health))
        self.create_rectangle(5,5,265,30,fill=FACE,outline='#405168')
        if fraction:self.create_rectangle(6,6,6+258*fraction,29,fill=health_color(fraction),outline='')
        self.create_rectangle(82,9,188,26,fill=FACE,outline='')
        self.create_text(135,17,text=f'HP {max(0,unit.health):g}/{unit.max_health:g}',fill=TEXT,font=('Helvetica',10,'bold'))
        width=self.winfo_width();factor=width/270 if width>1 else 1.
        if factor!=1:self.scale('all',0,0,factor,factor)
        height=round(35*factor)
        if height!=getattr(self,'render_height',None):self.render_height=height;self.configure(height=height)


class ConfidenceInspector(HealthInspector):
    def update_signal(self,signal):
        self.unit=signal;self.render()

    def render(self):
        if self.unit is None:return
        self.delete('all')
        fraction=self.unit.confidence
        self.create_rectangle(5,5,265,30,fill=FACE,outline='#405168')
        if fraction:self.create_rectangle(6,6,6+258*fraction,29,fill=health_color(fraction),outline='')
        self.create_rectangle(82,9,188,26,fill=FACE,outline='')
        self.create_text(135,17,text='Confidence',fill=TEXT,font=('Helvetica',10,'bold'))
        width=self.winfo_width();factor=width/270 if width>1 else 1.
        if factor!=1:self.scale('all',0,0,factor,factor)
        height=round(35*factor)
        if height!=getattr(self,'render_height',None):self.render_height=height;self.configure(height=height)
