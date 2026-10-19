"""Canvas instruments for the aircraft inspector; no image assets required."""
import math
import tkinter as tk
from .game_settings import STATS

BG='#17202d'
FACE='#101721'
TEXT='#dfe9f5'
MUTED='#93a3b8'
GREEN='#72d693'
YELLOW='#ffe66d'
RED='#ef6262'
WEAPON_COLORS={'AIM-120':'#ffe66d','AIM-9':'#ff9a48','AGM-88':'#ef6262','Sidearm':'#d58cff',250:'#69adff',500:'#69adff',1000:'#69adff',2000:'#69adff'}


def health_color(fraction):
    fraction=max(0.,min(1.,fraction))
    low,high=(RED,YELLOW) if fraction<.5 else (YELLOW,GREEN)
    blend=fraction*2 if fraction<.5 else (fraction-.5)*2
    rgb=lambda color:tuple(int(color[i:i+2],16) for i in (1,3,5))
    return '#'+''.join(f'{round(a+(b-a)*blend):02x}' for a,b in zip(rgb(low),rgb(high)))


def fuel_estimate(a):
    # Ground/refueling states have zero actual burn; show flight endurance instead.
    if a.enemy:return math.inf,math.inf
    burn=a.actual_fuel_burn or a.fuel_burn
    seconds=max(0.,a.fuel)/burn
    speed=a.speed if a.sensors_active and a.speed>0 else a.cruise_speed
    return seconds,max(0.,speed)*seconds/3600


def weapon_rows(a):
    configured_missiles,configured_bombs=a.configured_weapons()
    bombs={}
    for weight,count in a.bomb_inventory:bombs[weight]=bombs.get(weight,0)+count
    rows=[]
    for kind in ('AIM-120','AIM-9','AGM-88','Sidearm'):
        count=a.missile_inventory.get(kind,0)
        if count or configured_missiles.get(kind,0):rows.append((kind,kind,count))
    for weight in sorted(set(configured_bombs)|set(bombs)):
        count=bombs.get(weight,0)
        if count or configured_bombs.get(weight,0):rows.append((weight,f'{weight:,} lb bomb',count))
    return rows


def suicide_drone_eta(a):
    target=a.engage_target or a.auto_attack_target or a.attack_target
    if target is not None and getattr(target,'alive',False):
        point=(target.x,target.y);label='TIME TO TARGET'
        distance=max(0.,math.dist((a.x,a.y),point)-STATS['missile_behavior']['hit_radius_nm'])
    elif a.mode=='direct':
        label='ETA TO WAYPOINT';distance=math.dist((a.x,a.y),a.orbit_center)
    else:return 'TIME TO TARGET',None
    if not a.alive or a.speed<=0:return label,None
    return label,distance*3600/a.speed


class AircraftInspector(tk.Canvas):
    def __init__(self,parent,on_toggle=None):
        super().__init__(parent,width=270,height=400,background=BG,highlightthickness=0)
        self.aircraft=None;self.number='';self.on_toggle=on_toggle
        self.bind('<Button-1>',self.click_weapon)
        self.width_seen=0
        self.bind('<Configure>',self.resized)

    def resized(self,event):
        if event.width!=self.width_seen:
            self.width_seen=event.width
            if self.aircraft is not None:self.render()

    def update_aircraft(self,aircraft,number):
        self.aircraft=aircraft;self.number=number;self.render()

    def click_weapon(self,event):
        if self.aircraft is None or self.aircraft.enemy or self.on_toggle is None:return
        factor=self.winfo_width()/270 if self.winfo_width()>1 else 1.
        x,y=event.x/factor,event.y/factor
        for i,(kind,label,count) in enumerate(weapon_rows(self.aircraft)):
            if abs(x-251)<=12 and abs(y-(431+i*32))<=12:
                self.on_toggle(self.aircraft,kind);return 'break'

    @staticmethod
    def point(cx,cy,r,fraction):
        angle=math.radians(135+270*fraction)
        return cx+r*math.cos(angle),cy+r*math.sin(angle)

    def dial(self,cx,cy,r,fraction,title,left,right,color=TEXT):
        self.create_oval(cx-r,cy-r,cx+r,cy+r,fill=FACE,outline='#405168',width=2)
        points=[v for i in range(55) for v in self.point(cx,cy,r-6,i/54)]
        self.create_line(*points,fill='#61758e',width=2)
        for i in range(9):
            self.create_line(*self.point(cx,cy,r-7,i/8),*self.point(cx,cy,r-12,i/8),fill=MUTED,width=1)
        self.create_text(cx,cy-16,text=title,fill=MUTED,font=('Helvetica',9,'bold'))
        self.create_line(cx,cy,*self.point(cx,cy,r-15,max(0.,min(1.,fraction))),fill=color,width=2)
        self.create_oval(cx-3,cy-3,cx+3,cy+3,fill=color,outline='')
        self.create_text(cx-r*.55,cy+r*.57,text=left,fill=MUTED,font=('Helvetica',8))
        self.create_text(cx+r*.55,cy+r*.57,text=right,fill=MUTED,font=('Helvetica',8))

    def weapon_icon(self,kind,x,y,color):
        if isinstance(kind,str):
            length,width={'AIM-120':(35,4),'AIM-9':(28,4),'AGM-88':(43,5),'Sidearm':(30,5)}[kind]
            self.create_polygon(x-length/2,y-width,x+length/2-6,y-width,x+length/2,y,x+length/2-6,y+width,x-length/2,y+width,fill=color,outline='')
            self.create_polygon(x-length/2+3,y,x-length/2-1,y-9,x-length/2+9,y-4,x-length/2+9,y+4,x-length/2-1,y+9,fill=color,outline='')
            if kind in ('AGM-88','Sidearm'):self.create_line(x+4,y-8,x+4,y+8,fill=color,width=3)
            elif kind=='AIM-120':self.create_line(x+7,y-7,x+7,y+7,fill=color,width=2)
        else:
            length,width={250:(24,3),500:(32,6),1000:(43,7),2000:(48,9)}[kind]
            self.create_oval(x-length/2,y-width,x+length/2,y+width,fill=color,outline='')
            self.create_polygon(x-length/2+6,y,x-length/2-2,y-7,x-length/2+3,y-4,x-length/2+3,y+4,x-length/2-2,y+7,fill=color,outline='')

    def render(self):
        a=self.aircraft
        if a is None:return
        self.delete('all')
        hp=max(0.,min(1.,a.health/a.max_health))
        self.create_rectangle(5,5,265,30,fill=FACE,outline='#405168')
        if hp:self.create_rectangle(6,6,6+258*hp,29,fill=health_color(hp),outline='')
        self.create_rectangle(94,9,176,26,fill=FACE,outline='')
        self.create_text(135,17,text=f'HP  {max(0,a.health):g}/{a.max_health:g}',fill='#ffffff',font=('Helvetica',10,'bold'))
        state=a.state.upper() if a.state=='rtb' else a.state.title()
        mode=a.mode.upper() if a.mode=='rtb' else a.mode.title()
        if not a.enemy:self.create_text(135,72,text=f'{state} · {mode} · {"Fence In" if a.fenced_in else "Fence Out"}',fill=MUTED,font=('Helvetica',9))
        maximum=a.max_ab_speed
        scale=math.ceil(max(maximum,a.speed)*1.15/100)*100
        self.dial(135,153,63,a.speed/scale,'AIRSPEED','0',f'{scale:g}',YELLOW)
        for i in range(1,6):
            x,y=self.point(135,153,44,i/6)
            self.create_text(x,y,text=f'{scale*i/6:.0f}',fill=MUTED,font=('Helvetica',7))
        self.create_line(*self.point(135,153,62,maximum/scale),*self.point(135,153,49,maximum/scale),fill=RED,width=3)
        self.create_rectangle(109,172,161,192,fill=BG,outline='#61758e')
        self.create_text(135,182,text=f'{a.speed:.0f}',fill=TEXT,font=('Helvetica',11,'bold'))
        self.create_text(135,203,text='KNOTS',fill=MUTED,font=('Helvetica',7))
        if not a.enemy:
            self.create_text(135,230,text=f'{a.effective_speed_setting} · MAX {maximum:g} kt'+(' (AB)' if a.has_afterburner else ''),fill=RED,font=('Helvetica',9))
            fuel=max(0.,min(1.,a.fuel/a.spec['fuel']))
            self.dial(67,289,45,fuel,'FUEL','E','F',health_color(fuel))
            self.create_text(67,309,text=f'{fuel:.0%}',fill=TEXT,font=('Helvetica',9,'bold'))
            seconds,distance=fuel_estimate(a)
            minutes=int(seconds//60)
            self.create_text(135,348,text=f'Fuel {a.fuel:,.0f}/{a.spec["fuel"]:,} units',fill=TEXT,font=('Helvetica',9))
            self.create_text(135,367,text=f'Est. {minutes//60}h {minutes%60:02d}m remaining · {distance:,.0f} NM',fill=MUTED,font=('Helvetica',9))
        cx=135 if a.enemy else 203;cy=250 if a.enemy else 289
        self.create_rectangle(cx-43,cy-29,cx+43,cy+29,fill=FACE,outline='#405168',width=2)
        self.create_text(cx,cy-14,text='CMS',fill=MUTED,font=('Helvetica',9,'bold'))
        self.create_text(cx,cy+11,text=f'{a.cms}/{a.cms_capacity}',fill=TEXT,font=('Helvetica',15,'bold'))
        weapons_top=290 if a.enemy else 383
        self.create_line(5,weapons_top,265,weapons_top,fill='#405168')
        self.create_text(8,weapons_top+18,text='WEAPONS',anchor='w',fill=MUTED,font=('Helvetica',9,'bold'))
        rows=weapon_rows(a)
        for i,(kind,label,count) in enumerate(rows):
            y=weapons_top+48+i*32
            armed=a.weapon_enabled(kind)
            self.weapon_icon(kind,32,y,WEAPON_COLORS[kind] if count and armed else '#586070')
            self.create_text(65,y,text=label,anchor='w',fill=TEXT if count and armed else MUTED,font=('Helvetica',10))
            self.create_text(228,y,text=f'× {count}',anchor='e',fill=TEXT if count and armed else MUTED,font=('Helvetica',10,'bold'))
            self.create_oval(244,y-7,258,y+7,fill=GREEN if armed else RED,outline='#405168',tags='weapon_toggle')
        if not rows:self.create_text(8,weapons_top+48,text='Unarmed',anchor='w',fill=MUTED,font=('Helvetica',10))
        base_height=weapons_top+67+max(0,len(rows)-1)*32
        if a.kind=='Suicide Drone':
            label,seconds=suicide_drone_eta(a)
            if seconds is None:clock='--:--'
            else:
                total=max(0,math.ceil(seconds));hours,remainder=divmod(total,3600);minutes,secs=divmod(remainder,60)
                clock=f'{hours:02d}:{minutes:02d}:{secs:02d}' if hours else f'{minutes:02d}:{secs:02d}'
            top=base_height+5
            self.create_rectangle(8,top,262,top+88,fill='#07130e',outline='#405168',width=2)
            self.create_text(135,top+19,text=label,fill=MUTED,font=('Helvetica',9,'bold'))
            self.create_text(135,top+54,text=clock,fill=GREEN,font=('Courier New',25,'bold'))
            base_height=top+98
        width=self.winfo_width();factor=width/270 if width>1 else 1.
        if factor!=1:self.scale('all',0,0,factor,factor)
        height=round(base_height*factor)
        if height!=getattr(self,'render_height',None):self.render_height=height;self.configure(height=height)
