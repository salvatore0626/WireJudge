"""Player strategic missile silo, warhead planning, area damage and inspector."""
from dataclasses import dataclass
import math
import random
import time
from tkinter import ttk
from .game_settings import STATS
from .game_combat import Factory, Aircraft, ICBM
from .game_aircraft_inspector import AircraftInspector, FACE, TEXT, MUTED, GREEN, YELLOW
from .game_icbm_inspector import filled_missile, impact_clock

BLUE='#69adff'

@dataclass(eq=False)
class StrikePoint:
    x: float
    y: float
    name: str = 'Strike point'
    unit: object = None
    alive: bool = True
    enemy: bool = False
    plans: object = None
    region_center: object = None
    region_radius: float = 0.

    def update(self):
        if self.unit is not None:
            if self.unit.alive and (self.region_center is None or math.dist((self.unit.x,self.unit.y),self.region_center)<=self.region_radius):
                self.x,self.y=self.unit.x,self.unit.y
            else:self.unit=None

@dataclass
class PlayerMissileSilo(Factory):
    name: str = 'Missile Silo'
    enemy: bool = False
    warhead: object = None
    warhead_price: object = None
    target_point: object = None
    launch_due: object = None
    reload_due: float = 0.

    @property
    def stats_key(self):return 'Missile Silo'
    @property
    def price(self):return self.stats['price']
    @property
    def power(self):return self.stats['power']
    @property
    def width(self):return .5
    @property
    def length(self):return .5
    @property
    def long_range(self):return False
    def corners(self):return [(self.x+dx*self.width/2,self.y+dy*self.length/2) for dx in (-1,1) for dy in (-1,1)]
    def fueled(self,now):return self.alive and self.launch_due is None and now>=self.reload_due
    def ready(self,now):return self.fueled(now) and self.warhead is not None
    def countdown(self,now):
        if not self.ready(now) or self.target_point is None:return False
        if math.dist((self.x,self.y),(self.target_point.x,self.target_point.y))<self.min_engagement_range_nm:return False
        self.launch_due=now+self.stats['countdown_seconds'];return True

class PlayerStrike(ICBM):
    def __init__(self,owner,target,number,warhead,child=False,x=None,y=None,speed=None):
        self.warhead=warhead;self.cluster_child=child
        super().__init__(owner,target,number)
        self.enemy=False;self.color=BLUE
        if child:
            self.health=STATS['player_warheads']['Cluster']['submunition_health']
            if x is not None:self.x,self.y=x,y
            if speed is not None:self.speed=speed
        else:self.speed=self.flight_stats['launch_speed_knots']
        self.heading=math.atan2(target.x-self.x,target.y-self.y)
    @property
    def flight_stats(self):return STATS['player_strike_missile']
    @property
    def spec(self):
        s=STATS['player_strike_missile']
        return {'health':STATS['player_warheads']['Cluster']['submunition_health'] if self.cluster_child else s['health'],
                'speed':s['speed_knots'],'fuel':math.inf,'burn':0,'cms':0,'hardpoints':0,'bays':0,'price':0,
                'visual_range_nm':0,'radar_range_nm':0,'radar_angle_degrees':0,'afterburner':False,'can_refuel':False}
    @property
    def name(self):return f'{self.warhead} '+('warhead' if self.cluster_child else 'missile')+f' #{self.number}'


def damageable_units(world):
    units=[*world.ground_targets,*world.factories,*world.enemy_radars,*world.enemy_sams,
           *world.friendly_aircraft,*world.enemies,*world.icbms,*world.missiles,*world.bombs]
    # Some collections reference the same aircraft or structure.
    return list({id(u):u for u in units if hasattr(u,'health')}.values())


def cluster_targets(world,point,rng=None):
    s=STATS['player_warheads']['Cluster'];rng=rng or world.rng
    targets=[]
    for unit in damageable_units(world):
        if not unit.alive or not getattr(unit,'enemy',False):continue
        known=(world.contact(unit) is not None if isinstance(unit,Aircraft) else
               unit.id in world.known if isinstance(unit,Factory) else id(unit) in world.known_ground)
        if known and math.dist((unit.x,unit.y),point)<=s['coverage_radius_nm']:targets.append(unit)
    targets.sort(key=lambda u:(math.dist((u.x,u.y),point),getattr(u,'id',0)))
    plans=[]
    for _ in range(s['max_per_target']):
        for unit in targets:
            if len(plans)>=s['count']:break
            plans.append(StrikePoint(unit.x,unit.y,getattr(unit,'name','Target'),unit,region_center=point,region_radius=s['coverage_radius_nm']))
    while len(plans)<s['count']:
        radius=s['coverage_radius_nm']*math.sqrt(rng.random());angle=rng.uniform(0,math.tau)
        plans.append(StrikePoint(point[0]+radius*math.sin(angle),point[1]+radius*math.cos(angle),'Random impact'))
    return plans


def blast(world,missile,now):
    s=STATS['player_warheads'][missile.warhead]
    radius=s['impact_radius_nm'] if missile.cluster_child else s['blast_radius_nm']
    damage=s['damage']*world.rng.uniform(1-s['damage_spread_fraction'],1+s['damage_spread_fraction']) if missile.cluster_child else s['center_damage']
    for unit in damageable_units(world):
        if unit is missile or not unit.alive:continue
        position=unit.position(now) if not isinstance(unit,Aircraft) and hasattr(unit,'position') else (unit.x,unit.y)
        distance=math.dist(position,(missile.x,missile.y))
        if distance>radius+1e-9:continue
        amount=damage if missile.cluster_child else damage+(s['edge_damage']-damage)*min(1,distance/radius)
        amount=round(amount);unit.health=max(0,unit.health-amount)
        world.events.append((now,f'{missile.name} hit {world.unit_name(unit)} for {amount} HP',0,'status'))
        if unit.health<=0 and isinstance(unit,Aircraft):unit.destroy()
        world.record_kill(missile.owner,unit,now,missile.warhead)
    world.strike_blasts.append((now,missile.x,missile.y,radius,missile.warhead))
    world.explosions.append((now,missile.x,missile.y,BLUE))
    if missile.warhead=='Nuclear':world.nuclear_clouds.append((time.monotonic(),missile.x,missile.y,radius))
    world.emit_sound({'Conventional':'silo_conventional_impact','Cluster':'silo_cluster_impact','Nuclear':'silo_nuclear_impact'}[missile.warhead],(missile.x,missile.y));missile.destroy()


def advance_silos(world,now):
    for silo in world.player_silos:
        if not silo.alive:
            silo.launch_due=None;continue
        if silo.launch_due is None or now<silo.launch_due-1e-9:continue
        missile=PlayerStrike(silo,silo.target_point,world.next_icbm_id,silo.warhead)
        world.next_icbm_id+=1;world.icbms.append(missile);world.weapon_totals['missiles']+=1
        if missile.warhead=='Nuclear':world.nuclear_launches=getattr(world,'nuclear_launches',0)+1
        silo.warhead=None;silo.warhead_price=None;silo.target_point=None;silo.launch_due=None
        silo.reload_due=now+silo.stats['reload_seconds']
        world.events.append((now,f'{silo.name} #{silo.id} launched {missile.name}',0,'status'))
        world.emit_sound('icbm_launch',(silo.x,silo.y))


def advance_strike(world,missile,now,dt):
    missile.target.update();target=missile.target;s=missile.flight_stats
    old=missile.speed;missile.speed=min(s['speed_knots'],old+s['acceleration_knots_per_second']*dt)
    ramp=min(dt,max(0,(s['speed_knots']-old)/s['acceleration_knots_per_second']))
    travel=(old*ramp+.5*s['acceleration_knots_per_second']*ramp*ramp+s['speed_knots']*(dt-ramp))/3600
    dx,dy=target.x-missile.x,target.y-missile.y;distance=math.hypot(dx,dy)
    burst=STATS['player_warheads']['Cluster']['burst_distance_nm'] if missile.warhead=='Cluster' and not missile.cluster_child else 0
    stop=max(burst,s['hit_radius_nm'])
    missile.heading=math.atan2(dx,dy)
    step=min(travel,max(0,distance-stop))
    if distance:missile.x+=dx/distance*step;missile.y+=dy/distance*step
    if travel+stop>=distance:
        if burst:
            plans=target.plans if target.plans is not None else cluster_targets(world,(target.x,target.y))
            for plan in plans:
                child=PlayerStrike(missile.owner,plan,world.next_icbm_id,'Cluster',True,missile.x,missile.y,missile.speed)
                world.next_icbm_id+=1;world.icbms.append(child)
            world.events.append((now,f'{missile.name} split into {len(plans)} warheads',0,'status'))
            world.emit_sound('missile_explosion',(missile.x,missile.y));missile.destroy()
        else:
            missile.x,missile.y=target.x,target.y;blast(world,missile,now)
    if missile.alive:
        if not missile.history or now-missile.history[-1][0]>=.2:missile.history.append((now,missile.x,missile.y,missile.speed))
        while missile.history and now-missile.history[0][0]>60:missile.history.popleft()


def silo_fuel_display(silo,elapsed):
    if not silo.alive:return 0.,None,'DESTROYED'
    if silo.launch_due is not None:return 1.,max(0.,silo.launch_due-elapsed),'COUNTDOWN TO LAUNCH'
    remaining=max(0.,silo.reload_due-elapsed)
    return max(0.,min(1.,1-remaining/silo.stats['reload_seconds'])),remaining,'COUNTDOWN TO READY' if remaining else 'READY'


class PlayerSiloFuelInspector(AircraftInspector):
    def update_silo(self,silo,elapsed):
        self.aircraft=silo;self.elapsed=elapsed;self.render()

    def render(self):
        silo=self.aircraft
        if silo is None:return
        self.delete('all');fill,remaining,title=silo_fuel_display(silo,self.elapsed)
        self.create_rectangle(8,5,262,190,fill='#071c16',outline='#416d58',width=2)
        self.create_text(135,21,text='FUEL',fill=MUTED,font=('Helvetica',9,'bold'))
        shape=[(135,35),(145,55),(145,125),(158,151),(145,144),(145,155),
               (125,155),(125,144),(112,151),(125,125),(125,55)]
        coords=lambda points:[v for point in points for v in point]
        self.create_polygon(*coords(shape),fill='#152b26',outline='')
        filled=filled_missile(shape,fill)
        if len(filled)>=3:self.create_polygon(*coords(filled),fill=GREEN if fill>=1 else BLUE,outline='')
        self.create_polygon(*coords(shape),fill='',outline='#80a89a',width=2)
        self.create_text(135,173,text=f'{fill*100:.0f}% · '+('Fueled' if fill>=1 else 'Refueling' if silo.alive else 'Destroyed'),fill=GREEN if fill>=1 else MUTED,font=('Helvetica',11,'bold'))
        self.create_rectangle(8,201,262,278,fill='#07130e',outline='#405168',width=2)
        self.create_text(135,218,text=title,fill=MUTED,font=('Helvetica',9,'bold'))
        self.create_text(135,251,text=impact_clock(remaining),fill=YELLOW if silo.launch_due is not None else GREEN,font=('Courier New',25,'bold'))
        width=self.winfo_width();factor=width/270 if width>1 else 1.
        if factor!=1:self.scale('all',0,0,factor,factor)
        height=round(287*factor)
        if height!=getattr(self,'render_height',None):self.render_height=height;self.configure(height=height)


class PlayerSiloUI:
    def init_player_silo_controls(self,inspector,build):
        self.player_silos=self.combat.player_silos;self.placing_player_silo=False;self.silo_target_picker=None
        self.silo_target_preview=None
        self.player_silo_button=ttk.Button(build,image=self.build_button_images['Missile Silo'],command=self.toggle_player_silo)
        self.player_silo_panel=ttk.Frame(inspector)
        self.player_silo_target_button=ttk.Button(self.player_silo_panel,text='Target',command=self.select_silo_target)
        self.player_silo_target_button.pack(fill='x',pady=(5,3))
        self.player_silo_launch_button=ttk.Button(self.player_silo_panel,text='Launch',command=self.launch_player_silo)
        self.player_silo_launch_button.pack(fill='x',pady=(3,8))
        self.player_silo_fuel=PlayerSiloFuelInspector(self.player_silo_panel)
        self.player_silo_fuel.pack(fill='x',pady=(0,8))
        self.warhead_buttons={}
        for name in STATS['player_warheads']:
            button=ttk.Button(self.player_silo_panel,command=lambda name=name:self.toggle_silo_warhead(name))
            button.pack(fill='x',pady=3);self.warhead_buttons[name]=button
        self.player_silo_status=ttk.Label(self.player_silo_panel,wraplength=240,justify='left')
        self.player_silo_status.pack(fill='x',pady=6)

    def refresh_player_silo(self,silo):
        self.airfield_health.update_health(silo);self.airfield_health.pack(fill='x',before=self.inspector_label)
        self.player_silo_panel.pack(fill='x',before=self.inspector_label)
        due=silo.launch_due;point=silo.target_point;ready=silo.ready(self.elapsed)
        self.player_silo_fuel.update_silo(silo,self.elapsed)
        self.player_silo_status.configure(text=f'Minimum range: {silo.min_engagement_range_nm:g} NM'+
            (f'\nTarget: {point.x:.1f}, {point.y:.1f} NM' if point else ''))
        for name,button in self.warhead_buttons.items():
            price=STATS['player_warheads'][name]['price'];owned=silo.warhead==name
            can_refund=owned and silo.fueled(self.elapsed)
            can_buy=silo.fueled(self.elapsed) and silo.warhead is None and self.money>=price
            refund=silo.warhead_price if silo.warhead_price is not None else price
            button.configure(text=f'Refund {name} · ${refund:,.0f}' if owned else f'{name} · ${price:,.0f}',
                state='normal' if can_refund or can_buy else 'disabled',
                style='GameSell.TButton' if owned else 'GamePurchaseReady.TButton' if can_buy else 'TButton')
        self.player_silo_target_button.configure(text='Target',state='normal' if ready else 'disabled',
            style='GamePlay.TButton' if ready and point else 'GamePause.TButton' if ready else 'TButton')
        can_launch=ready and point is not None
        self.player_silo_launch_button.configure(text='Launch',state='normal' if can_launch else 'disabled',
            style='GamePlay.TButton' if can_launch else 'TButton')
        self.inspector_text.set('Blast damage affects both teams.' if silo.alive else 'Destroyed')
        if silo.alive:self.destroy_unit_button.pack(fill='x',pady=(12,4))

    def toggle_silo_warhead(self,name):
        if isinstance(self.selected,PlayerMissileSilo) and self.selected.warhead==name:
            return self.refund_silo_warhead()
        return self.buy_silo_warhead(name)

    def refund_silo_warhead(self):
        silo=self.selected
        if not isinstance(silo,PlayerMissileSilo) or not silo.fueled(self.elapsed) or silo.warhead is None:return False
        price=silo.warhead_price if silo.warhead_price is not None else STATS['player_warheads'][silo.warhead]['price']
        name=silo.warhead;self.money+=price
        silo.warhead=None;silo.warhead_price=None;silo.target_point=None
        if self.silo_target_picker is silo:
            self.silo_target_picker=None;self.pointer=None;self.canvas.configure(cursor='')
        self.add_log(f'Refund {name} warhead · +${price:,.0f}','reward')
        self.refresh_resources();self.refresh_inspector();self.request_draw();return True

    def buy_silo_warhead(self,name):
        silo=self.selected
        if not isinstance(silo,PlayerMissileSilo) or not silo.fueled(self.elapsed) or silo.warhead is not None:return False
        price=STATS['player_warheads'][name]['price']
        if self.money<price:return False
        self.spend_money(price,f'{name} warhead for Missile Silo #{silo.id}')
        silo.warhead=name;silo.warhead_price=price;self.play_game_sound('buy_aircraft');self.refresh_inspector();self.request_draw();return True

    def select_silo_target(self):
        if not isinstance(self.selected,PlayerMissileSilo) or not self.selected.ready(self.elapsed):return
        silo=self.selected;self.cancel_commands();self.silo_target_picker=silo;self.pointer=None
        self.canvas.configure(cursor='crosshair');self.inspector_text.set(f'Click an impact point at least {silo.min_engagement_range_nm:g} NM from this silo. Escape cancels.')
        self.request_draw()

    def finish_silo_target(self,event):
        silo=self.silo_target_picker
        if silo is None or not silo.ready(self.elapsed):self.silo_target_picker=None;return
        point=self.world(event.x,event.y)
        if math.dist((silo.x,silo.y),point)<silo.min_engagement_range_nm:
            self.inspector_text.set(f'Target must be at least {silo.min_engagement_range_nm:g} NM from the silo.');return
        silo.target_point=StrikePoint(*point)
        if silo.warhead=='Cluster':
            seed=f'{silo.id}:{point[0]:.3f}:{point[1]:.3f}'
            silo.target_point.plans=cluster_targets(self.combat,point,random.Random(seed))
        self.silo_target_picker=None;self.pointer=None;self.canvas.configure(cursor='')
        self.refresh_inspector();self.request_draw()

    def launch_player_silo(self):
        silo=self.selected
        if isinstance(silo,PlayerMissileSilo) and silo.countdown(self.elapsed):
            self.add_log(f'Missile Silo #{silo.id}: {silo.warhead} launch countdown','status')
            self.refresh_inspector();self.request_draw();return True
        return False

    def toggle_player_silo(self):
        if not self.unlocked('Missile Silo'):return False
        was=self.placing_player_silo;self.cancel_commands()
        self.placing_player_silo=not was;self.selected=None
        self.show_left_menu('Build',cancel=False);self.canvas.configure(cursor='crosshair' if not was else '')
        self.refresh_inspector();self.request_draw();return True

    def place_player_silo(self,x,y):
        silo=PlayerMissileSilo(self.next_build_id('player_silo',self.player_silos),x,y)
        error=self.placement_error(silo)
        if error:self.inspector_text.set(error);return None
        self.spend_money(silo.price,f'Build Missile Silo #{silo.id}');self.play_game_sound('place_unit')
        self.player_silos.append(silo);self.progress_action('build','Missile Silo');self.cancel_placement();self.selected=silo
        self.refresh_inspector();self.request_draw();return silo

    def draw_player_silo(self,silo,ghost=False):
        if not ghost and self.ground_dot_required(silo):return
        x,y=self.pixel(silo.x,silo.y);f=max(.2,self.building_factor()*.4)
        color='#586070' if not silo.alive else BLUE
        if ghost and self.placement_error(silo):color='#ef6262'
        c=self.canvas;c.create_rectangle(x-20*f,y-20*f,x+20*f,y+20*f,fill=PANEL_COLOR,outline=color,width=2,tags='game_combat')
        c.create_oval(x-14*f,y-14*f,x+14*f,y+14*f,fill=PANEL_COLOR,outline=color,width=2,tags='game_combat')
        c.create_line(x-10*f,y,x+10*f,y,fill=color,width=2,tags='game_combat')
        if self.selected is silo:c.create_rectangle(x-24*f,y-24*f,x+24*f,y+24*f,outline='white',tags='game_combat')

    def draw_silo_target_preview(self):
        silo=self.silo_target_picker or (self.selected if isinstance(self.selected,PlayerMissileSilo) else None)
        point=self.pointer if self.silo_target_picker else ((silo.target_point.x,silo.target_point.y) if silo and silo.target_point else None)
        if silo is None or point is None or silo.warhead is None:return
        x,y=self.pixel(*point);s=STATS['player_warheads'][silo.warhead]
        radius=s['coverage_radius_nm'] if silo.warhead=='Cluster' else s['blast_radius_nm'];r=radius*self.scale()
        valid=math.dist((silo.x,silo.y),point)>=silo.min_engagement_range_nm;color=BLUE if valid else '#ef6262'
        self.canvas.create_oval(x-r,y-r,x+r,y+r,outline=color,width=2,dash=(6,4),tags='game_combat')
        sx,sy=self.pixel(silo.x,silo.y);minimum=silo.min_engagement_range_nm*self.scale()
        self.canvas.create_oval(sx-minimum,sy-minimum,sx+minimum,sy+minimum,outline='#ef6262',dash=(2,5),tags='game_combat')
        if silo.warhead=='Cluster':
            seed=f'{silo.id}:{point[0]:.3f}:{point[1]:.3f}'
            plans=silo.target_point.plans if not self.silo_target_picker and silo.target_point.plans is not None else cluster_targets(self.combat,point,random.Random(seed))
            counts={}
            for plan in plans:
                plan.update()
                key=id(plan.unit) if plan.unit is not None else (plan.x,plan.y)
                count=counts.get(key,0)+1;counts[key]=count
                px,py=self.pixel(plan.x,plan.y);marker=max(7,.18*self.scale())+3*(count-1)
                self.canvas.create_oval(px-marker,py-marker,px+marker,py+marker,outline=color,width=1.5,tags='game_combat')
        self.canvas.create_text(x,y-r-12,text='Target Area',fill=color,tags='game_combat')

    def draw_radiation_marker(self,x,y,radius,color):
        c=self.canvas
        c.create_oval(x-radius-2,y-radius-2,x+radius+2,y+radius+2,fill=PANEL_COLOR,outline=color,width=1,tags='game_combat')
        for start in (30,150,270):
            points=[]
            for i in range(13):
                angle=math.radians(start+i*5);points.extend((x+radius*math.cos(angle),y+radius*math.sin(angle)))
            for i in range(12,-1,-1):
                angle=math.radians(start+i*5);points.extend((x+radius*.3*math.cos(angle),y+radius*.3*math.sin(angle)))
            c.create_polygon(*points,fill=color,outline='',tags='game_combat')
        r=radius*.18;c.create_oval(x-r,y-r,x+r,y+r,fill=color,outline='',tags='game_combat')

    def draw_player_strike(self,m,show_label=True):
        x,y=self.pixel(m.x,m.y);c=self.canvas;far=self.view_width>=75
        color=BLUE if int(time.monotonic()*2)%2==0 else '#ffffff'
        if m.cluster_child:
            if far:c.create_oval(x-3.5,y-3.5,x+3.5,y+3.5,fill=BLUE,outline='',tags='game_combat')
            else:
                ux,uy=math.sin(m.heading),-math.cos(m.heading)
                def point(fwd,side):return x+ux*fwd-uy*side,y+uy*fwd+ux*side
                coords=[v for fwd,side in ((-2.8,-.46),(2,-.46),(3.2,0),(2,.46),(-2.8,.46)) for v in point(fwd,side)]
                c.create_polygon(*coords,fill=BLUE,outline=BLUE,tags='game_combat')
                for side in (-1,1):c.create_polygon(*point(-2.6,side*.4),*point(-3,side),*point(-1.4,side*.4),fill=BLUE,tags='game_combat')
        elif m.warhead=='Nuclear':self.draw_radiation_marker(x,y,9 if far else 14,color)
        elif far:c.create_oval(x-7,y-7,x+7,y+7,fill=color,outline='',tags='game_combat')
        else:
            ux,uy=math.sin(m.heading),-math.cos(m.heading)
            def point(fwd,side):return x+ux*fwd-uy*side,y+uy*fwd+ux*side
            coords=[v for fwd,side in ((-14,-2.3),(10,-2.3),(16,0),(10,2.3),(-14,2.3)) for v in point(fwd,side)]
            c.create_polygon(*coords,fill=BLUE,outline=BLUE,tags='game_combat')
            for side in (-1,1):c.create_polygon(*point(-13,side*2),*point(-15,side*5),*point(-7,side*2),fill=BLUE,tags='game_combat')
            c.create_line(*point(-11,-.7),*point(7,-.7),fill='#ffffff',width=1,tags='game_combat')
        if self.selected is m:
            radius=7 if m.cluster_child else 19
            c.create_oval(x-radius,y-radius,x+radius,y+radius,outline='#ffffff',tags='game_combat')
        if show_label and not far and (not m.cluster_child or self.selected is m):
            c.create_text(x,y+(13 if m.cluster_child else 25),text=m.name,fill=BLUE,tags='game_combat')

    def draw_strike_blasts(self):
        c=self.canvas
        self.combat.strike_blasts[:]=[b for b in self.combat.strike_blasts if self.elapsed-b[0]<3]
        for when,bx,by,radius,warhead in self.combat.strike_blasts:
            if warhead=='Nuclear':continue
            px,py=self.pixel(bx,by);r=radius*self.scale()
            c.create_oval(px-r,py-r,px+r,py+r,outline=BLUE,width=2,tags='game_combat')
        now=time.monotonic()
        self.combat.nuclear_clouds[:]=[b for b in self.combat.nuclear_clouds if now-b[0]<20]
        for when,bx,by,radius in self.combat.nuclear_clouds:
            age=max(0,now-when);x,y=self.pixel(bx,by)
            grow=min(1,age/2);fade=min(1,max(0,(20-age)/6))
            size=max(38,min(140,radius*self.scale()*.35))*(.2+.8*grow)
            # Expanding shockwave follows the real damage radius, then fades.
            if age<3:
                r=max(size,radius*self.scale()*min(1,age/1.5))
                color=self.muted_map_color('#fff2ba',max(0,1-age/3))
                c.create_oval(x-r,y-r,x+r,y+r,outline=color,width=3,tags='game_combat')
            smoke=self.muted_map_color('#b2a895',fade*.8)
            shade=self.muted_map_color('#655e57',fade*.85)
            glow=self.muted_map_color('#ffc969',fade*max(.1,1-age/5))
            # Dust ring, rising stem and layered mushroom cap.
            c.create_oval(x-size*.9,y-size*.12,x+size*.9,y+size*.15,fill=shade,outline='',tags='game_combat')
            c.create_polygon(x-size*.14,y,x-size*.26,y-size*.65,x-size*.11,y-size*.94,
                             x+size*.11,y-size*.94,x+size*.26,y-size*.65,x+size*.14,y,
                             fill=shade,outline='',tags='game_combat')
            c.create_oval(x-size*.11,y-size*.84,x+size*.11,y-size*.12,fill=glow,outline='',tags='game_combat')
            for offset,lift,r in ((-.55,.84,.3),(.55,.84,.3),(-.3,1.03,.38),(.3,1.03,.38),(0,1.12,.43)):
                px=x+offset*size;py=y-lift*size
                c.create_oval(px-r*size,py-r*.65*size,px+r*size,py+r*.65*size,fill=smoke,outline=shade,width=1,tags='game_combat')
            if age<1.5:
                r=size*.35*(1-age/1.5);c.create_oval(x-r,y-r,x+r,y+r,fill='#fff7d0',outline='',tags='game_combat')

PANEL_COLOR='#162338'
