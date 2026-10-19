"""ICBM health, impact clock, airspeed and target display."""
import math
from .game_aircraft_inspector import AircraftInspector, BG, FACE, TEXT, MUTED, GREEN, YELLOW, RED, health_color
from .game_settings import STATS
from .game_combat import Bomb, ANTI_RADAR_WEAPONS, velocity
from .game_logistics import helipad_position


def helicopter_eta_seconds(helicopter,airfield):
    if helicopter.state=='parked':return 0.
    target=helicopter.target
    destination=((target.x,target.y) if helicopter.state=='outbound' and target is not None and target.alive
                 else helipad_position(airfield))
    return math.dist((helicopter.x,helicopter.y),destination)*3600/helicopter.speed if helicopter.speed>0 else None


class HelicopterInspector(AircraftInspector):
    def update_helicopter(self,helicopter,airfield):
        self.aircraft=helicopter;self.airfield=airfield;self.render()

    def render(self):
        h=self.aircraft
        if h is None:return
        self.delete('all')
        outbound=h.state=='outbound' and h.target is not None and h.target.alive
        self.create_rectangle(8,5,262,91,fill='#07130e',outline='#405168',width=2)
        self.create_text(135,23,text='ETA TO RESUPPLY' if outbound else 'ETA TO HELIPAD',fill=MUTED,font=('Helvetica',9,'bold'))
        self.create_text(135,57,text=impact_clock(helicopter_eta_seconds(h,self.airfield)),fill=GREEN,font=('Courier New',25,'bold'))
        if h.state=='parked':self.create_text(135,81,text='Parked',fill=MUTED,font=('Helvetica',8))
        width=self.winfo_width();factor=width/270 if width>1 else 1.
        if factor!=1:self.scale('all',0,0,factor,factor)
        height=round(101*factor)
        if height!=getattr(self,'render_height',None):self.render_height=height;self.configure(height=height)


def projectile_impact_seconds(weapon,elapsed):
    """Exact bomb flight time; missile estimate with boost, coast and target motion."""
    if not weapon.alive:return None
    if isinstance(weapon,Bomb):
        remaining=weapon.launched+weapon.duration-elapsed
        return max(0.,remaining) if math.isfinite(remaining) else None
    target=weapon.guidance_target
    if weapon.terminal or not target.alive:return None
    dx,dy=target.x-weapon.x,target.y-weapon.y
    radius=math.hypot(dx,dy)
    distance=max(0.,radius-STATS['missile_behavior']['hit_radius_nm'])*3600
    if distance==0:return 0.
    vx,vy=velocity(target)
    radial=(vx*dx+vy*dy)/radius
    speed=max(0.,weapon.speed)
    remaining_boost=max(0.,weapon.boost_duration-max(0.,elapsed-weapon.launched))
    acceleration=max(0.,weapon.stats['speed_knots']-speed)/remaining_boost if remaining_boost else 0.
    time=0.;travel=0.
    if remaining_boost:
        closure=speed-radial
        if acceleration:
            t=(-closure+math.sqrt(closure*closure+2*acceleration*distance))/acceleration
        else:t=distance/closure if closure>0 else math.inf
        if t<=remaining_boost:
            travel=(speed*t+.5*acceleration*t*t)/3600
            return t if travel<=weapon.range_nm-weapon.travelled+1e-9 else None
        distance-=closure*remaining_boost+.5*acceleration*remaining_boost**2
        travel=(speed*remaining_boost+.5*acceleration*remaining_boost**2)/3600
        speed+=acceleration*remaining_boost;time=remaining_boost
    drag=weapon.stats['coast_deceleration_knots_per_second']
    if weapon.kind in ANTI_RADAR_WEAPONS and STATS['missile_behavior']['anti_radar_range_based_drag']:
        start=weapon.coast_start_distance
        if start is None:start=weapon.travelled+travel
        drag=weapon.stats['speed_knots']**2/(2*3600*max(1.,weapon.range_nm-start))
    closure=speed-radial
    if closure<=0:return None
    if drag:
        discriminant=closure*closure-2*drag*distance
        if discriminant<0:return None
        coast_time=2*distance/(closure+math.sqrt(discriminant))
        if speed-drag*coast_time<STATS['missile_behavior']['min_coast_speed_knots']:return None
    else:coast_time=distance/closure
    travel+=(speed*coast_time-.5*drag*coast_time**2)/3600
    return time+coast_time if travel<=weapon.range_nm-weapon.travelled+1e-9 else None


class ProjectileInspector(AircraftInspector):
    def update_weapon(self,weapon,elapsed):
        self.aircraft=weapon;self.elapsed=elapsed;self.render()

    def render(self):
        weapon=self.aircraft
        if weapon is None:return
        self.delete('all')
        bomb=isinstance(weapon,Bomb)
        maximum=STATS['bombs'][str(weapon.weight)]['health'] if bomb else weapon.stats['health']
        hp=max(0.,min(1.,weapon.health/maximum))
        self.create_rectangle(5,5,265,30,fill=FACE,outline='#405168')
        if hp:self.create_rectangle(6,6,6+258*hp,29,fill=health_color(hp),outline='')
        self.create_rectangle(86,9,184,26,fill=FACE,outline='')
        self.create_text(135,17,text=f'HP {max(0,weapon.health):g}/{maximum:g}',fill=TEXT,font=('Helvetica',10,'bold'))
        seconds=projectile_impact_seconds(weapon,self.elapsed)
        self.create_rectangle(8,48,262,125,fill='#07130e',outline='#405168',width=2)
        self.create_text(135,65,text='TIME TO IMPACT' if bomb else 'EST. TIME TO IMPACT',fill=MUTED,font=('Helvetica',9,'bold'))
        self.create_text(135,96,text=impact_clock(seconds),fill=RED if seconds is not None and seconds<=10 else GREEN,font=('Courier New',25,'bold'))
        speed=weapon.speed_at(self.elapsed) if bomb else weapon.speed
        self.create_text(135,150,text=f'{speed:,.0f} knots',fill=TEXT,font=('Helvetica',11,'bold'))
        self.create_text(135,174,text=f'Target: {weapon.target.name if hasattr(weapon.target,"name") else getattr(weapon.target,"kind","Unknown")}',fill=MUTED,font=('Helvetica',9))
        if seconds is None:self.create_text(135,198,text='No impact predicted',fill=MUTED,font=('Helvetica',9))
        width=self.winfo_width();factor=width/270 if width>1 else 1.
        if factor!=1:self.scale('all',0,0,factor,factor)
        height=round(215*factor)
        if height!=getattr(self,'render_height',None):self.render_height=height;self.configure(height=height)


def impact_seconds(missile):
    """Predict arrival using the same acceleration, speed cap and hit radius as flight."""
    if not missile.alive or not missile.target.alive:return None
    stats=getattr(missile,'flight_stats',STATS['icbm'])
    stop=STATS['player_warheads']['Cluster']['burst_distance_nm'] if getattr(missile,'warhead',None)=='Cluster' and not missile.cluster_child else stats['hit_radius_nm']
    distance=max(0.,math.dist((missile.x,missile.y),(missile.target.x,missile.target.y))-stop)*3600
    if not distance:return 0.
    speed=min(stats['speed_knots'],max(0.,missile.speed))
    acceleration=stats['acceleration_knots_per_second']
    ramp_seconds=(stats['speed_knots']-speed)/acceleration
    ramp_distance=speed*ramp_seconds+.5*acceleration*ramp_seconds**2
    if distance<=ramp_distance:
        return 2*distance/(speed+math.sqrt(speed**2+2*acceleration*distance))
    return ramp_seconds+(distance-ramp_distance)/stats['speed_knots']


def impact_clock(seconds):
    if seconds is None:return '--:--:--'
    total=max(0,math.ceil(seconds-1e-9))
    return f'{total//3600:02d}:{total//60%60:02d}:{total%60:02d}'


def silo_reload_display(silo,elapsed):
    if not silo.alive:return 0.,None,False
    total=silo.stats['reload_seconds']
    due=getattr(silo,'reload_due',{}).get('ammo',elapsed+total if silo.ammo<=0 else elapsed)
    remaining=max(0.,due-elapsed)
    progress=max(0.,min(1.,1-remaining/total))
    return min(1.,progress/.9),remaining,progress>=.9-1e-9


def filled_missile(polygon,fraction):
    """Clip the silhouette at a horizontal fill level, from its bottom upward."""
    if fraction<=0:return []
    if fraction>=1:return list(polygon)
    top=min(y for x,y in polygon);bottom=max(y for x,y in polygon)
    cutoff=bottom-(bottom-top)*fraction
    result=[];previous=polygon[-1]
    for current in polygon:
        old_inside=previous[1]>=cutoff;inside=current[1]>=cutoff
        if old_inside!=inside:
            f=(cutoff-previous[1])/(current[1]-previous[1])
            result.append((previous[0]+(current[0]-previous[0])*f,cutoff))
        if inside:result.append(current)
        previous=current
    return result


class ICBMSiloInspector(AircraftInspector):
    def update_silo(self,silo,elapsed):
        self.aircraft=silo;self.elapsed=elapsed;self.render()

    def render(self):
        silo=self.aircraft
        if silo is None:return
        self.delete('all')
        hp=max(0.,min(1.,silo.health/silo.max_health))
        self.create_rectangle(5,5,265,30,fill=FACE,outline='#405168')
        if hp:self.create_rectangle(6,6,6+258*hp,29,fill=health_color(hp),outline='')
        self.create_rectangle(86,9,184,26,fill=FACE,outline='')
        self.create_text(135,17,text=f'HP {max(0,silo.health):g}/{silo.max_health:g}',fill=TEXT,font=('Helvetica',10,'bold'))
        self.create_text(135,71,text='Target: Airfield · Unlimited range',fill=MUTED,font=('Helvetica',9))

        fill,remaining,ready=silo_reload_display(silo,self.elapsed)
        self.create_rectangle(8,87,262,320,fill='#071c16',outline='#416d58',width=2)
        for y in range(100,287,20):self.create_line(20,y,250,y,fill='#133629')
        shape=[(135,108),(145,131),(145,249),(158,275),(145,268),(145,279),
               (125,279),(125,268),(112,275),(125,249),(125,131)]
        coords=lambda points:[v for point in points for v in point]
        self.create_polygon(*coords(shape),fill='#152b26',outline='')
        filled=filled_missile(shape,fill)
        if len(filled)>=3:self.create_polygon(*coords(filled),fill=GREEN if ready else '#58bfa0',outline='')
        self.create_polygon(*coords(shape),fill='',outline='#80a89a',width=2)
        state='Destroyed' if not silo.alive else 'Ready' if ready else 'Refueling'
        self.create_text(135,303,text=state,fill=GREEN if ready else MUTED,font=('Helvetica',12,'bold'))

        self.create_rectangle(8,337,262,432,fill='#07130e',outline='#405168',width=2)
        self.create_text(135,355,text='COUNTDOWN TO LAUNCH',fill=MUTED,font=('Helvetica',9,'bold'))
        color=RED if silo.enabled and remaining is not None and remaining<=30 else GREEN
        self.create_text(135,387,text=impact_clock(remaining),fill=color,font=('Courier New',25,'bold'))
        status='Destroyed' if not silo.alive else 'Engagement disabled · Launch held' if not silo.enabled else 'Launch pending' if remaining==0 else 'Engagement enabled'
        self.create_text(135,418,text=status,fill=YELLOW if silo.alive and not silo.enabled else MUTED,font=('Helvetica',8))
        width=self.winfo_width();factor=width/270 if width>1 else 1.
        if factor!=1:self.scale('all',0,0,factor,factor)
        height=round(444*factor)
        if height!=getattr(self,'render_height',None):self.render_height=height;self.configure(height=height)


class ICBMInspector(AircraftInspector):
    def update_missile(self,missile):
        self.aircraft=missile;self.render()

    def render(self):
        m=self.aircraft
        if m is None:return
        self.delete('all')
        hp=max(0.,min(1.,m.health/m.max_health))
        self.create_rectangle(5,5,265,30,fill=FACE,outline='#405168')
        if hp:self.create_rectangle(6,6,6+258*hp,29,fill=health_color(hp),outline='')
        self.create_rectangle(91,9,179,26,fill=FACE,outline='')
        self.create_text(135,17,text=f'HP {max(0,m.health):g}/{m.max_health:g}',fill=TEXT,font=('Helvetica',10,'bold'))
        status='Intercepted' if not m.alive else 'Target destroyed' if not m.target.alive else 'Inbound' if m.enemy else 'Outbound'
        self.create_text(135,71,text=status,fill=MUTED,font=('Helvetica',9))

        seconds=impact_seconds(m)
        self.create_rectangle(8,86,262,157,fill='#07130e',outline='#405168',width=2)
        self.create_text(135,101,text='TIME TO BURST' if getattr(m,'warhead',None)=='Cluster' and not m.cluster_child else 'TIME TO IMPACT',fill=MUTED,font=('Helvetica',9,'bold'))
        self.create_text(135,130,text=impact_clock(seconds),fill=RED if seconds is not None and seconds<=60 else GREEN,font=('Courier New',25,'bold'))

        maximum=getattr(m,'flight_stats',STATS['icbm'])['speed_knots']
        scale=math.ceil(max(maximum,m.speed)*1.15/100)*100
        self.dial(135,239,65,m.speed/scale,'AIRSPEED','0',f'{scale:g}',YELLOW)
        for i in range(1,6):
            x,y=self.point(135,239,46,i/6)
            self.create_text(x,y,text=f'{scale*i/6:.0f}',fill=MUTED,font=('Helvetica',7))
        self.create_line(*self.point(135,239,64,maximum/scale),*self.point(135,239,51,maximum/scale),fill=RED,width=3)
        self.create_rectangle(105,258,165,280,fill=BG,outline='#61758e')
        self.create_text(135,269,text=f'{m.speed:.0f}',fill=TEXT,font=('Helvetica',12,'bold'))
        self.create_text(135,293,text='KNOTS',fill=MUTED,font=('Helvetica',7))

        player_strike=getattr(m,'warhead',None) is not None
        if not player_strike:
            self.create_rectangle(8,338,262,365,fill=FACE,outline='#416d58')
            self.create_text(135,352,text='TARGET',fill=TEXT,font=('Helvetica',9,'bold'))
            self.create_rectangle(8,365,262,515,fill='#071c16',outline='#416d58',width=2)
            # Airfield silhouette, framed by a targeting reticle.
            target=m.target;color='#69adff' if target.alive else '#586070'
            self.create_rectangle(130,387,140,461,fill='#20384b',outline=color,width=2)
            for y in range(391,456,12):self.create_line(135,y,135,y+6,fill=color)
            self.create_line(130,422,105,422,105,449,fill=color,width=2)
            for y in (398,423,448):self.create_rectangle(87,y-7,104,y+5,outline=color)
            self.create_oval(97,389,173,465,outline=GREEN,width=1)
            for x1,y1,x2,y2 in ((76,427,112,427),(158,427,194,427),(135,374,135,404),(135,450,135,480)):
                self.create_line(x1,y1,x2,y2,fill=GREEN,width=1)
            self.create_text(135,485,text=target.name,fill=TEXT,font=('Helvetica',10,'bold'))
            distance=math.dist((m.x,m.y),(target.x,target.y))
            self.create_text(135,503,text=f'{distance:,.1f} NM',fill=MUTED,font=('Helvetica',9))

        width=self.winfo_width();factor=width/270 if width>1 else 1.
        if factor!=1:self.scale('all',0,0,factor,factor)
        height=round((312 if player_strike else 524)*factor)
        if height!=getattr(self,'render_height',None):self.render_height=height;self.configure(height=height)
