"""Game-only detection, weapon flight, countermeasures, and damage."""
from dataclasses import dataclass, field
import math
import random
from game_aircraft import Aircraft

BOMB_DAMAGE={1000:400,500:100,250:20}
TARGET_TYPES=('Fighters','Drones','Bombers','Ground','Vehicles')
ENGAGEMENT_RANGES=(10,25,50,75,100)
MISSILE_RANGE={'AIM-120':25.,'AIM-9':8.,'SAM':30.,'HARM':140.}
MISSILE_BOOST={'AIM-120':2.,'AIM-9':3.5,'SAM':2.,'HARM':9.}
BOMB_DRAG=.025
BOMB_DISTANCE=3.
HARM_LAUNCH_RANGE=75.
HIT_RADIUS=.035


def angle_error(target,current):return (target-current+math.pi)%math.tau-math.pi

def velocity(target):
    if isinstance(target,Flare):return target.vx,target.vy
    if isinstance(target,Missile):return math.sin(target.heading)*target.speed,math.cos(target.heading)*target.speed
    if not isinstance(target,Aircraft):return 0.,0.
    return math.sin(target.heading)*target.speed,math.cos(target.heading)*target.speed

def airborne(target):
    return isinstance(target,Aircraft) and target.alive and target.sensors_active

@dataclass
class Contact:
    target: Aircraft
    seen: float
    kind: str
    x: float
    y: float
    heading: float
    history: list = field(default_factory=list)

    def __iter__(self):return iter((self.target,self.seen))

@dataclass(eq=False)
class Factory:
    id: int
    x: float
    y: float
    health: float = 50.
    category: str = 'Ground'
    name: str = 'Factory'
    enemy: bool = True

    @property
    def alive(self):return self.health>0

@dataclass(eq=False)
class Bunker(Factory):
    health: float = 500.
    name: str = 'Bunker'

@dataclass
class Bomb:
    owner: object
    target: Factory
    weight: int
    launched: float
    start: tuple
    launch_speed: float
    heading: float
    health: float = None

    def __post_init__(self):
        if self.health is None:self.health={250:20.,500:30.,1000:60.}[self.weight]

    @property
    def alive(self):return self.health>0

    @property
    def name(self):return f"{self.weight} lb Bomb"

    @property
    def duration(self):
        fraction=BOMB_DRAG*3600*BOMB_DISTANCE/max(1.,self.launch_speed)
        return -math.log(1-fraction)/BOMB_DRAG if fraction<1 else math.inf

    def speed_at(self,now):return self.launch_speed*math.exp(-BOMB_DRAG*max(0,now-self.launched))

    def distance_at(self,now):
        return min(BOMB_DISTANCE,self.launch_speed/3600/BOMB_DRAG*(1-math.exp(-BOMB_DRAG*max(0,now-self.launched))))

    def position(self,now):
        distance=self.distance_at(now)
        return self.start[0]+math.sin(self.heading)*distance,self.start[1]+math.cos(self.heading)*distance

@dataclass(eq=False)
class Flare:
    owner: Aircraft
    x: float
    y: float
    vx: float
    vy: float
    spawned: float
    alive: bool = True
    side: int = 0

@dataclass(eq=False)
class Missile:
    owner: object
    target: Aircraft
    kind: str
    launched: float
    x: float
    y: float
    heading: float
    speed: float
    launch_speed: float
    cm_lead: float
    travelled: float = 0.
    decoy: object = None
    cm_checked: bool = False
    lost_lock: float = 0.
    terminal: bool = False
    terminal_age: float = 0.
    history: list = field(default_factory=list)
    max_range: float = 0.
    coast_start_distance: object = None
    health: float = None

    def __post_init__(self):
        if self.health is None:self.health=12. if self.kind=="HARM" else 5.

    @property
    def alive(self):return self.health>0

    @property
    def name(self):return self.kind

    @property
    def range_nm(self):return self.max_range or MISSILE_RANGE[self.kind]

    @property
    def boost_duration(self):return MISSILE_BOOST[self.kind]

    @property
    def color(self):return '#ff8b45' if self.owner.enemy else '#ffe66d'

    def position(self,now=None):return self.x,self.y

@dataclass(eq=False)
class Bullet:
    owner: object
    x: float
    y: float
    heading: float
    spawned: float
    travelled: float = 0.

class CombatWorld:
    def __init__(self,seed=None):
        self.factories=[];self.enemies=[]
        self.events=[];self.kill_ids=set();self.unit_states={};self.visible_ground_contacts=set()
        self.bombs=[];self.missiles=[];self.flares=[];self.explosions=[]
        self.known=set();self.known_wrecks=set();self.contacts={False:{},True:{}}
        self.radars=[];self.sams=[];self.ciws=[];self.bullets=[];self.rng=random.Random(seed);self.last_advance=0.
        self.pending_flares=[]
        self.cm_bursts={}
        self.attacker_reveals={False:{},True:{}}
        self.ground_targets=[]
        self.enemy_radars=[];self.enemy_sams=[];self.known_ground=set()

    def unit_name(self,unit):
        if isinstance(unit,Aircraft):
            index=next((i+1 for i,a in enumerate(self.enemies) if a is unit),unit.parking_slot+1)
            return f'{"Enemy " if unit.enemy else ""}{unit.kind} #{index}'
        return f'{getattr(unit,"name",type(unit).__name__)} #{getattr(unit,"id","")}'.strip()

    def record_kill(self,owner,target,now):
        if target.alive or getattr(target,'kill_recorded',False):return
        target.kill_recorded=True
        self.kill_ids.add(id(target))
        reward=0
        if not getattr(owner,'enemy',False) and getattr(target,'enemy',False):
            if isinstance(target,Bunker):reward=1000
            elif isinstance(target,Factory):reward=100
            elif isinstance(target,Aircraft):reward={'Fighter':200,'Interceptor':200,'Drone':75,'RQ-9B':75}.get(target.kind,0)
            elif hasattr(target,'radar_emitting') or hasattr(target,'accepts_target'):reward=150
        self.events.append((now,f'{self.unit_name(owner)} killed {self.unit_name(target)}',reward,'kill'))

    def track_unit_states(self,aircraft,now):
        units=[*aircraft,*self.sams,*self.enemy_sams,*self.ciws]
        for unit in units:
            if not unit.alive or getattr(unit,'enemy',False):continue
            mode=getattr(unit,'mode',None)
            armed=(isinstance(unit,Aircraft) and unit.kind in ('Fighter','Interceptor','Bomber')) or hasattr(unit,'ammo')
            empty=armed and (unit.missiles_available+unit.bombs_available==0 if isinstance(unit,Aircraft) else unit.ammo==0)
            old=self.unit_states.get(id(unit),(None,False))
            if mode=='rtb' and old[0]!='rtb':self.events.append((now,f'{self.unit_name(unit)} is RTB',0,'status'))
            if empty and not old[1]:self.events.append((now,f'{self.unit_name(unit)} is Winchester (out of ammo)',0,'status'))
            self.unit_states[id(unit)]=(mode,empty)

    def spawn_bunker(self,x,y):
        target=Bunker(len(self.factories)+1,x,y)
        self.factories.append(target);return target

    def spawn_factory(self,x,y):
        target=Factory(len(self.factories)+1,x,y)
        self.factories.append(target);return target

    def spawn_fighter(self,x,y):
        a=Aircraft('Fighter',['1× AIM-120C','1× AIM-120C','2× AIM-9','Empty'],[],
                   enemy=True,health=50.,color='#ef6262')
        a.x=x;a.y=y;a.heading=math.atan2(-x,-y);a.speed=600.
        a.state='airborne';a.fenced_in=True;a.orbit_center=(0.,0.)
        a.target_types={'Fighters','Drones','Bombers'}
        self.enemies.append(a);return a

    def contact(self,target,team=False):return self.contacts[team].get(id(target))

    def spawn_drone(self,x,y):
        a=Aircraft('Drone',[],[],enemy=True,health=35.,color='#ffe66d')
        a.x=x;a.y=y;a.heading=math.atan2(-x,-y);a.speed=250.
        a.state='airborne';a.fenced_in=True;a.orbit_center=(0.,0.)
        a.target_types={'Ground'}
        self.enemies.append(a);return a

    def has_datalink(self,target,team=False):
        contact=self.contact(target,team)
        return airborne(target) and contact is not None and contact.kind=='datalink'

    def discover(self,aircraft,now):
        # Incoming weapons reveal their shooter without granting a radar track.
        # Refresh the timeout while any missile from that shooter is still airborne.
        for missile in self.missiles:
            if missile.owner.enemy and not isinstance(missile.owner,Aircraft) and isinstance(missile.target,Aircraft) and not missile.target.enemy:
                self.known_ground.add(id(missile.owner))
            if isinstance(missile.owner,Aircraft) and missile.owner.alive and missile.target.alive:
                self.attacker_reveals[missile.target.enemy][id(missile.owner)]=(missile.owner,now+30.)
        alive=[a for a in aircraft if a.alive]
        friendly=[a for a in alive if not a.enemy];hostile=[a for a in alive if a.enemy]
        self.visible_ground_contacts=set()
        for target in self.factories:
            if target.alive and any(a.visual_detects(target.x,target.y) for a in friendly):
                self.known.add(target.id);self.visible_ground_contacts.add(id(target))
        for target in [*self.enemy_radars,*self.enemy_sams]:
            if target.alive and any(a.visual_detects(target.x,target.y) or
                (a.sensors_active and a.missile_inventory.get('HARM',0) and getattr(target,'radar_emitting',False)
                 and math.hypot(target.x-a.x,target.y-a.y)<=HARM_LAUNCH_RANGE) for a in friendly):
                self.known_ground.add(id(target));self.visible_ground_contacts.add(id(target))
        for team,observers,targets in ((False,friendly,hostile),(True,hostile,friendly)):
            contacts=self.contacts[team]
            reveals=self.attacker_reveals[team]
            expired={key for key,(owner,until) in reveals.items() if now>=until or not owner.alive}
            for key in expired:reveals.pop(key)
            for target in targets:
                datalink=airborne(target) and (
                    any(r.radar_emitting and math.hypot(target.x-r.x,target.y-r.y)<=r.range_nm for r in (self.enemy_radars if team else self.radars))
                    or any(a.kind!='AWACS' and a.radar_detects(target.x,target.y) for a in observers))
                visual=(any(c.alive and math.hypot(target.x-c.x,target.y-c.y)<=8. for c in self.ciws) if not team else False) or id(target) in reveals or any(a.visual_detects(target.x,target.y) or
                           (a.kind=='AWACS' and airborne(target) and a.radar_detects(target.x,target.y)) for a in observers)
                old=contacts.get(id(target))
                if datalink or visual:
                    contact=old or Contact(target,now,'visual',target.x,target.y,target.heading)
                    contact.seen=now;contact.kind='datalink' if datalink else 'visual'
                    contact.x=target.x;contact.y=target.y;contact.heading=target.heading
                    if not contact.history or now-contact.history[-1][0]>=.2-1e-9:
                        contact.history.append((now,target.x,target.y,target.speed))
                    contact.history[:]=[p for p in contact.history if now-p[0]<=30]
                    contacts[id(target)]=contact
                elif id(target) in expired:contacts.pop(id(target),None)
                elif old is not None:old.kind='visual'
            self.contacts[team]={key:contact for key,contact in contacts.items() if contact.target.alive and now-contact.seen<=10.}

    def launch_sams(self,now):
        busy={(m.owner.enemy,id(m.target)) for m in self.missiles}
        for sam in [*self.sams,*self.enemy_sams]:
            if not sam.alive or sam.ammo<=0:continue
            if any(m.owner is sam for m in self.missiles):continue
            targets=[c.target for c in self.contacts[sam.enemy].values()
                     if self.has_datalink(c.target,sam.enemy) and (sam.enemy,id(c.target)) not in busy
                     and sam.accepts_target(c.target.category,c.target.x,c.target.y,on_datalink=True)]
            if not targets:continue
            target=min(targets,key=lambda a:math.hypot(a.x-sam.x,a.y-sam.y))
            heading=math.atan2(target.x-sam.x,target.y-sam.y)
            missile=Missile(sam,target,'SAM',now,sam.x,sam.y,heading,0.,0.,self.rng.uniform(2,4),max_range=sam.range_nm)
            sam.ammo-=1
            self.missiles.append(missile);busy.add((sam.enemy,id(target)))

    def weapon_choice(self,a,target):
        distance=math.hypot(target.x-a.x,target.y-a.y)
        error=abs(angle_error(math.atan2(target.x-a.x,target.y-a.y),a.heading))
        if distance<=8 and a.missile_inventory.get('AIM-9',0) and error<=math.radians(a.radar_angle_deg/2*1.2)+1e-12:return 'AIM-9'
        if distance<=25 and a.missile_inventory.get('AIM-120',0) and self.has_datalink(target,a.enemy) and a.radar_detects(target.x,target.y):return 'AIM-120'
        return None

    def prepare(self,aircraft,now):
        self.friendly_aircraft=[a for a in aircraft if not a.enemy]
        self.discover(aircraft,now)
        self.launch_sams(now)
        busy_ground={id(b.target) for b in self.bombs}|{id(m.target) for m in self.missiles if m.kind=='HARM'}
        busy_air={(m.owner.enemy,id(m.target)) for m in self.missiles}
        for a in aircraft:
            a.engage_target=None;a.combat_heading=None
            a.auto_attack_target=None
            if a.attack_target is not None and not a.attack_target.alive:
                a.attack_target=None;a.attack_point=None
            if a.attack_target is not None:
                contact=self.contact(a.attack_target,a.enemy)
                if contact is not None:a.attack_point=(contact.x,contact.y)
            a.combat_home=any(b.owner is a for b in self.bombs)
            if not a.alive or a.state!='airborne' or a.mode=='rtb':continue
            support=[m for m in self.missiles if m.owner is a and m.kind=='AIM-120'
                     and not m.terminal and m.decoy is None and m.target.alive
                     and (a.attack_target is None or m.target is a.attack_target)]
            if (not a.enemy and a.combat_used_weapons and not a.bombs_available and not a.missiles_available
                and not support and not any(m.owner is a and m.kind=='HARM' and m.target.alive for m in self.missiles)):
                a.combat_home=False;a.bomb_run_target=None;a.bomb_run_heading=None
                a.rtb();continue
            active=[weapon.target for weapon in (*self.missiles,*self.bombs)
                    if weapon.owner is a and weapon.target.alive]
            if active:a.auto_attack_target=active[0]
            run=a.bomb_run_target
            if run is not None and (not run.alive or not a.fenced_in or not a.bombs_available):
                a.bomb_run_target=None;a.bomb_run_phase='attack'
                if not a.combat_home:a.bomb_run_heading=None
            elif run is not None and a.bomb_run_phase=='reposition':
                # Finish a homeward racetrack leg so a fast aircraft has room
                # to line up a fresh, unguided bomb run instead of orbiting it.
                if not a.combat_home and math.hypot(run.x-a.x,run.y-a.y)>=12:
                    a.bomb_run_phase='attack';a.bomb_run_heading=None
                else:a.combat_home=True
            if a.combat_home:continue
            if not a.fenced_in:continue
            harms=[m for m in self.missiles if m.owner is a and m.kind=='HARM' and m.target.alive]
            if harms:
                target=harms[0].target;a.auto_attack_target=target
                a.combat_heading=math.atan2(a.x-target.x,a.y-target.y)
                continue
            if support:
                target=support[0].target;bearing=math.atan2(target.x-a.x,target.y-a.y)
                a.auto_attack_target=target
                offset=max(0,math.radians(a.radar_angle_deg/2-10))
                a.combat_heading=bearing+a.crank_side*offset
                continue
            targets=[t for t,timestamp in self.contacts[a.enemy].values()
                     if (t is a.attack_target or (a.attack_target is None and t.category in a.target_types)) and (a.enemy,id(t)) not in busy_air
                     and (t is a.attack_target or math.hypot(t.x-a.x,t.y-a.y)<=a.engagement_range) and a.air_missiles_available]
            emitters=self.radars if a.enemy else self.enemy_radars
            harm_targets=[t for t in emitters if t.alive and t.radar_emitting and a.missile_inventory.get('HARM',0)
                          and id(t) not in busy_ground
                          and (t is a.attack_target or a.attack_target is None and 'Ground' in a.target_types)
                          and not any(m.kind=='HARM' and m.target is t and m.owner.enemy==a.enemy for m in self.missiles)
                          and math.hypot(t.x-a.x,t.y-a.y)<=min(HARM_LAUNCH_RANGE,a.engagement_range if t is not a.attack_target else HARM_LAUNCH_RANGE)]
            ground=[t for t in (self.ground_targets if a.enemy and a.kind=='Drone' else [*self.factories,*self.enemy_radars,*self.enemy_sams] if not a.enemy else [])
                    if t.alive and (a.visual_detects(t.x,t.y) if a.enemy else t.id in self.known if isinstance(t,Factory) else id(t) in self.known_ground and a.visual_detects(t.x,t.y))
                    and id(t) not in busy_ground and (t is a.attack_target or (a.attack_target is None and t.category in a.target_types))
                    and (a.kind=='Drone' or a.bombs_available)
                    and (t is a.attack_target or t is a.bomb_run_target or math.hypot(t.x-a.x,t.y-a.y)<=a.engagement_range)]
            targets+=ground
            targets+=harm_targets
            if not targets:continue
            target=min(targets,key=lambda t:math.hypot(t.x-a.x,t.y-a.y));a.engage_target=target
            a.auto_attack_target=target
            dx,dy=target.x-a.x,target.y-a.y;distance=math.hypot(dx,dy)
            bearing=math.atan2(dx,dy);error=abs(angle_error(bearing,a.heading))
            if a.kind=='Drone':continue
            if not isinstance(target,Aircraft):
                if target in harm_targets:
                    if error<=math.radians(a.radar_angle_deg/2 or 30):
                        a.missile_inventory['HARM']-=1
                        self.missiles.append(Missile(a,target,'HARM',now,a.x,a.y,a.heading,a.speed,a.speed,0))
                        busy_ground.add(id(target))
                        a.combat_used_weapons=True;a.engage_target=None
                        a.combat_heading=bearing+math.pi
                    continue
                # Aim the unguided, 3-NM bomb flight before the homeward leg.
                if 2.94<=distance<=3.02 and error<=math.radians(3) and a.speed>BOMB_DRAG*3600*BOMB_DISTANCE:
                    remaining_health=target.health
                    for _ in range(a.ground_weapons_per_target):
                        weight=a.take_bomb(remaining_health)
                        if weight is None:break
                        self.bombs.append(Bomb(a,target,weight,now,(a.x,a.y),a.speed,a.heading))
                        remaining_health-=round(BOMB_DAMAGE[weight]*1.15)
                        if remaining_health<=0:break
                    a.combat_used_weapons=True
                    busy_ground.add(id(target));a.engage_target=None;a.combat_home=True
                    a.bomb_run_target=target;a.bomb_run_phase='reposition'
                    a.bomb_run_heading=a.heading+math.pi if a.enemy else math.atan2(-a.x,-a.y)
            else:
                launched=[]
                for _ in range(a.air_weapons_per_target):
                    kind=self.weapon_choice(a,target)
                    if kind is None:break
                    a.missile_inventory[kind]-=1
                    missile=Missile(a,target,kind,now,a.x,a.y,a.heading,a.speed,a.speed,self.rng.uniform(2,4))
                    self.missiles.append(missile);launched.append(missile)
                if launched:
                    a.combat_used_weapons=True
                    busy_air.add((a.enemy,id(target)));a.engage_target=None
                    if any(m.kind=='AIM-120' for m in launched):
                        a.crank_side=-1 if angle_error(bearing,a.heading)>=0 else 1
                        a.combat_heading=bearing+a.crank_side*max(0,math.radians(a.radar_angle_deg/2-10))

    def emit_flare(self,a,due,side,now,burst):
        if not a.alive:return
        vx,vy=velocity(a);lag=max(0,now-due)
        kick=side*180.
        flare=Flare(a,a.x-vx/3600*lag,a.y-vy/3600*lag,
                    vx+math.cos(a.heading)*kick,vy-math.sin(a.heading)*kick,due,side=side)
        self.flares.append(flare);burst.append(flare)

    def deploy_countermeasures(self,a,now):
        recent=self.cm_bursts.get(id(a))
        if recent is not None and now-recent[0]<6:return [f for f in recent[1] if f.alive]
        if a.cms<=0:return []
        a.cms-=1;burst=[]
        self.emit_flare(a,now,-1,now,burst)
        for i in range(1,8):self.pending_flares.append((now+1.2*i/7,a,-1 if i%2==0 else 1,burst))
        self.cm_bursts[id(a)]=(now,burst)
        return burst

    def countermeasure_check(self,m,now):
        if m.cm_checked or m.decoy is not None or not m.target.alive:return
        dx,dy=m.target.x-m.x,m.target.y-m.y;distance=math.hypot(dx,dy)
        if distance<HIT_RADIUS:return
        tvx,tvy=velocity(m.target)
        closing=((math.sin(m.heading)*m.speed-tvx)*dx+(math.cos(m.heading)*m.speed-tvy)*dy)/distance
        eta=distance*3600/closing if closing>1 else math.inf
        if eta<=m.cm_lead:
            burst=self.deploy_countermeasures(m.target,now)
            if burst:
                m.cm_checked=True
                if self.rng.random()<.8:m.decoy=self.rng.choice(burst)

    def intercept_heading(self,m,target):
        dx,dy=target.x-m.x,target.y-m.y;vx,vy=velocity(target)
        vx/=3600;vy/=3600;speed=max(1,m.speed)/3600
        aa=vx*vx+vy*vy-speed*speed;bb=2*(dx*vx+dy*vy);cc=dx*dx+dy*dy
        lead=0.;disc=bb*bb-4*aa*cc
        if abs(aa)>1e-12 and disc>=0:
            roots=((-bb-math.sqrt(disc))/(2*aa),(-bb+math.sqrt(disc))/(2*aa))
            future=[t for t in roots if t>0]
            if future:lead=min(60,min(future))
        return math.atan2(dx+vx*lead,dy+vy*lead)

    def explode_missile(self,m,now):
        m.health=0.
        self.explosions.append((now,m.x,m.y,m.color))

    def step_missile(self,m,now,dt):
        age=max(0,now-m.launched)
        target=m.decoy if m.decoy is not None else m.target
        if not m.terminal:
            if not target.alive:m.terminal=True
            elif m.kind in ('AIM-120','SAM') and m.decoy is None:
                supported=self.has_datalink(target,m.owner.enemy)
                if m.kind=='AIM-120':supported=supported and m.owner.alive and m.owner.radar_detects(target.x,target.y)
                if not supported:m.lost_lock+=dt
                else:m.lost_lock=0.
                if m.lost_lock>1.5:m.terminal=True
        if m.terminal:
            m.terminal_age+=dt
            if m.terminal_age>=1.:
                self.explode_missile(m,now);return False
        elif isinstance(m.target,Aircraft):self.countermeasure_check(m,now)
        target=m.decoy if m.decoy is not None else m.target
        change=0.
        harm_tracking=m.kind!='HARM' or getattr(m.target,'radar_emitting',False)
        if not m.terminal and harm_tracking:
            desired=self.intercept_heading(m,target)
            rate=min(math.radians(70),9.81*30/max(50,m.speed*.514444))
            if m.kind=='AIM-9' and math.hypot(target.x-m.x,target.y-m.y)<=3:rate*=1.3
            change=max(-rate*dt,min(rate*dt,angle_error(desired,m.heading)))
            m.heading=(m.heading+change)%math.tau
        if age<=m.boost_duration+1e-9:
            m.speed=min(2500.,m.launch_speed+(2500-m.launch_speed)*age/m.boost_duration)
        else:
            drag=8.
            if m.kind=='HARM':
                if m.coast_start_distance is None:m.coast_start_distance=m.travelled
                drag=2500.**2/(2*3600*max(1.,m.range_nm-m.coast_start_distance))
            m.speed=max(0,m.speed-drag*dt)
        m.speed=max(0,m.speed-abs(math.degrees(change))*1.2)
        step=m.speed/3600*dt
        if m.travelled+step>m.range_nm:step=max(0,m.range_nm-m.travelled)
        old=(m.x,m.y);m.x+=math.sin(m.heading)*step;m.y+=math.cos(m.heading)*step;m.travelled+=step
        if not m.history or now-m.history[-1][0]>=.2-1e-9:m.history.append((now,m.x,m.y))
        while m.history and now-m.history[0][0]>12:m.history.pop(0)
        if not m.terminal and target.alive and harm_tracking:
            dx,dy=m.x-old[0],m.y-old[1];length2=dx*dx+dy*dy
            t=max(0,min(1,((target.x-old[0])*dx+(target.y-old[1])*dy)/max(1e-20,length2)))
            distance=math.hypot(target.x-old[0]-t*dx,target.y-old[1]-t*dy)
            if distance<=HIT_RADIUS:
                if m.decoy is None:
                    damage=self.rng.randint(60,80) if m.kind=='HARM' else self.rng.randint(45,65)
                    target.health=max(0.,target.health-damage)
                    if target.health<=0 and isinstance(target,Aircraft):target.destroy()
                    self.record_kill(m.owner,target,now)
                else:target.alive=False
                self.explode_missile(m,now);return False
        if m.travelled>=m.range_nm-1e-9 or (m.speed<100 and age>m.boost_duration):
            self.explode_missile(m,now);return False
        return True

    def advance_ciws(self,now,dt):
        candidates=[*self.enemies,*self.missiles,*self.bombs]
        for gun in self.ciws:
            if not gun.alive:continue
            if gun.ammo<=0:
                gun.attack_target=None;gun.shot_timer=0.;continue
            targets=[t for t in candidates if t.alive and (t.enemy if isinstance(t,Aircraft) else t.owner.enemy)
                     and (airborne(t) if isinstance(t,Aircraft) else True)
                     and (t.category if isinstance(t,Aircraft) else 'Missiles' if isinstance(t,Missile) else 'Bombs') in gun.preferred_targets
                     and math.dist((gun.x,gun.y),(t.position(now) if not isinstance(t,Aircraft) else (t.x,t.y)))<=gun.range_nm]
            gun.attack_target=min(targets,key=lambda t:math.dist((gun.x,gun.y),t.position(now) if not isinstance(t,Aircraft) else (t.x,t.y)),default=None)
            if gun.attack_target is None:
                gun.shot_timer=0.;continue
            # 10 rounds per second, independent of simulation tick size.
            gun.shot_timer+=dt
            while gun.ammo>0 and gun.shot_timer>=.1-1e-9:
                gun.shot_timer-=.1
                gun.ammo-=1
                t=gun.attack_target;tx,ty=t.position(now) if not isinstance(t,Aircraft) else (t.x,t.y)
                vx,vy=velocity(t) if not isinstance(t,Bomb) else (math.sin(t.heading)*t.speed_at(now),math.cos(t.heading)*t.speed_at(now))
                travel=math.hypot(tx-gun.x,ty-gun.y)/(.833333)
                heading=math.atan2(tx+vx/3600*travel-gun.x,ty+vy/3600*travel-gun.y)+self.rng.uniform(-math.radians(5),math.radians(5))
                self.bullets.append(Bullet(gun,gun.x,gun.y,heading,now))
        remaining=[]
        for bullet in self.bullets:
            distance=min(3000/3600*dt,3.5-bullet.travelled);old=(bullet.x,bullet.y)
            bullet.x+=math.sin(bullet.heading)*distance;bullet.y+=math.cos(bullet.heading)*distance;bullet.travelled+=distance
            hit=None
            for t in candidates:
                if not t.alive or not (t.enemy if isinstance(t,Aircraft) else t.owner.enemy):continue
                if isinstance(t,Aircraft) and not airborne(t):continue
                tx,ty=t.position(now) if not isinstance(t,Aircraft) else (t.x,t.y)
                dx,dy=bullet.x-old[0],bullet.y-old[1];d2=dx*dx+dy*dy
                along=max(0,min(1,((tx-old[0])*dx+(ty-old[1])*dy)/max(d2,1e-20)))
                if math.hypot(tx-old[0]-along*dx,ty-old[1]-along*dy)<=.015:hit=t;break
            if hit is not None:
                hit.health=max(0.,hit.health-self.rng.randint(2,3))
                if not hit.alive:
                    pos=hit.position(now) if not isinstance(hit,Aircraft) else (hit.x,hit.y)
                    self.explosions.append((now,*pos,'#ffe9a0'))
                    if isinstance(hit,Aircraft):hit.destroy()
                    self.record_kill(bullet.owner,hit,now)
            elif bullet.travelled<3.5:remaining.append(bullet)
        self.bullets=remaining

    def advance(self,now):
        dt=max(0,now-self.last_advance);self.last_advance=now
        self.advance_ciws(now,dt)
        for drone in self.enemies:
            target=drone.engage_target
            if (drone.kind=='Drone' and drone.alive and drone.state=='airborne'
                and target is not None and not isinstance(target,Aircraft) and target.alive
                and math.hypot(drone.x-target.x,drone.y-target.y)<=HIT_RADIUS):
                target.health=max(0,target.health-self.rng.randint(30,60))
                self.record_kill(drone,target,now)
                self.explosions.append((now,drone.x,drone.y,'#ffe66d'))
                drone.destroy()
        remaining=[]
        for bomb in self.bombs:
            if not bomb.alive:continue
            if now-bomb.launched>=bomb.duration-1e-9:
                x,y=bomb.position(now)
                if bomb.target.alive and math.hypot(x-bomb.target.x,y-bomb.target.y)<=.18:
                    damage=round(BOMB_DAMAGE[bomb.weight]*self.rng.uniform(.85,1.15))
                    bomb.target.health=max(0,bomb.target.health-damage)
                    self.record_kill(bomb.owner,bomb.target,now)
                bomb.health=0.
                self.explosions.append((now,x,y,'#87caff'))
            else:remaining.append(bomb)
        self.bombs=remaining
        pending=[]
        for due,a,side,burst in self.pending_flares:
            if due<=now+1e-9:self.emit_flare(a,due,side,now,burst)
            else:pending.append((due,a,side,burst))
        self.pending_flares=pending
        for flare in self.flares:
            flare_dt=min(dt,max(0,now-flare.spawned))
            drag=math.exp(-.45*flare_dt)
            flare.x+=flare.vx/3600*(1-drag)/.45;flare.y+=flare.vy/3600*(1-drag)/.45
            flare.vx*=drag;flare.vy*=drag
            if now-flare.spawned>=8:flare.alive=False
        airborne_missiles=[]
        for missile in self.missiles:
            if not missile.alive:continue
            if self.step_missile(missile,now,dt):airborne_missiles.append(missile)
            elif isinstance(missile.owner,Aircraft) and missile.owner.alive and isinstance(missile.target,Aircraft):
                self.attacker_reveals[missile.target.enemy][id(missile.owner)]=(missile.owner,now+30.)
        self.known_wrecks.update(id(a) for a in self.enemies if not a.alive and self.contact(a) is not None)
        self.missiles=airborne_missiles
        self.flares=[f for f in self.flares if f.alive]
        self.explosions=[e for e in self.explosions if now-e[0]<1.]
        self.track_unit_states([*getattr(self,"friendly_aircraft",()),*self.enemies],now)
