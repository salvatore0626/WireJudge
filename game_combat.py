"""Game-only detection, weapon flight, countermeasures, and damage."""
from dataclasses import dataclass, field
import math
import random
from game_aircraft import Aircraft, intercept_point

from game_settings import STATS, ground_stats

BOMB_DAMAGE={int(w):s['damage'] for w,s in STATS['bombs'].items()}
TARGET_TYPES=('Fighters','Suicide Drones','Bombers','ICBMs','Radars','Ground')
ENGAGEMENT_RANGES=tuple(STATS['aircraft_behavior']['engagement_range_options_nm'])
MISSILE_RANGE={k:s['max_range_nm'] for k,s in STATS['missiles'].items()}
MISSILE_LAUNCH_RANGE={k:s['launch_range_nm'] for k,s in STATS['missiles'].items()}
MISSILE_DAMAGE={k:(s['damage'],s['damage_spread_fraction']) for k,s in STATS['missiles'].items()}
ANTI_RADAR_WEAPONS=('AGM-88','Sidearm')
MISSILE_BOOST={k:s['boost_seconds'] for k,s in STATS['missiles'].items()}
BOMB_DRAG=STATS['bomb_behavior']['drag_per_second']
BOMB_DISTANCE=STATS['bomb_behavior']['drop_range_nm']
AGM88_LAUNCH_RANGE=MISSILE_LAUNCH_RANGE['AGM-88']
HIT_RADIUS=STATS['missile_behavior']['hit_radius_nm']
SALVO_INTERVAL=STATS['missile_behavior']['salvo_interval_seconds']


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
    def __post_init__(self):
        if self.health is None:self.health=self.max_health

    @property
    def stats_key(self):return 'Factory'

    @property
    def stats(self):return ground_stats(self.stats_key,self.enemy)

    @property
    def min_engagement_range_nm(self):return self.stats.get('min_engagement_range_nm',0)

    id: int
    x: float
    y: float
    health: float = None
    category: str = 'Ground'
    name: str = 'Factory'
    enemy: bool = True

    @property
    def alive(self):return self.health>0

    @property
    def max_health(self):return self.stats['health']

@dataclass(eq=False)
class Bunker(Factory):
    health: float = None
    name: str = 'Bunker'

    @property
    def max_health(self):return self.stats['health']

    @property
    def stats_key(self):return 'Bunker'

@dataclass(eq=False)
class ICBMSilo(Factory):
    def __post_init__(self):
        super().__post_init__()
        if self.enabled is None:self.enabled=self.stats['launch_enabled']

    health: float = None
    name: str = 'ICBM Silo'
    enabled: bool = None
    ammo: int = 1
    ammo_capacity: int = 1

    @property
    def max_health(self):return self.stats['health']

    @property
    def stats_key(self):return 'ICBM Silo'


@dataclass(eq=False)
class DroneLauncher(Factory):
    name: str = 'Drone Launcher'
    ammo: int = None
    enabled: bool = None
    next_launch: float = 0.

    def __post_init__(self):
        super().__post_init__()
        if not self.enemy:raise ValueError('Drone Launcher is an enemy-only unit')
        if self.ammo is None:self.ammo=self.ammo_capacity
        if self.enabled is None:self.enabled=self.stats['launch_enabled']

    @property
    def stats_key(self):return 'Drone Launcher'

    @property
    def ammo_capacity(self):return self.stats['ammo']


class ICBM(Aircraft):
    """Air-contact interface for an uncrewed missile; movement is ballistic."""
    def __init__(self,owner,target,number,x=0.,y=0.):
        self.owner=owner if owner is not None else self;self.target=target;self.number=number
        super().__init__('ICBM',enemy=True,state='airborne',mode='icbm',color='#ff4f64')
        self.x,self.y=(owner.x,owner.y) if owner is not None else (x,y)
        self.speed=STATS['icbm']['launch_speed_knots']
        self.heading=math.atan2(target.x-self.x,target.y-self.y)

    @property
    def spec(self):
        return {'health':STATS['icbm']['health'],'speed':STATS['icbm']['speed_knots'],
                'fuel':math.inf,'burn':0,'cms':0,'hardpoints':0,'bays':0,'price':0,
                'visual_range_nm':0,'radar_range_nm':0,'radar_angle_degrees':0,
                'afterburner':False,'can_refuel':False}

    @property
    def category(self):return 'ICBMs'

    @property
    def name(self):return f'ICBM #{self.number}'

    def position(self,now):return self.x,self.y

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
    drop_distance: float = BOMB_DISTANCE

    def __post_init__(self):
        if self.health is None:self.health=STATS['bombs'][str(self.weight)]['health']

    @property
    def alive(self):return self.health>0

    @property
    def name(self):return f"{self.weight} lb Bomb"

    @property
    def duration(self):
        fraction=BOMB_DRAG*3600*self.drop_distance/max(1.,self.launch_speed)
        return -math.log(1-fraction)/BOMB_DRAG if fraction<1 else math.inf

    def speed_at(self,now):return self.launch_speed*math.exp(-BOMB_DRAG*max(0,now-self.launched))

    def distance_at(self,now):
        return min(self.drop_distance,self.launch_speed/3600/BOMB_DRAG*(1-math.exp(-BOMB_DRAG*max(0,now-self.launched))))

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
class RadarMemoryPoint:
    x: float
    y: float
    alive: bool = True


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
    cm_burst: object = None
    cm_burst_count: int = 0
    lost_lock: float = 0.
    terminal: bool = False
    terminal_age: float = 0.
    history: list = field(default_factory=list)
    max_range: float = 0.
    coast_start_distance: object = None
    radar_memory_point: object = None
    health: float = None
    pitbull: bool = False

    @property
    def stats(self):
        return STATS['missiles'][self.kind]

    def __post_init__(self):
        if self.kind in ('SAM','LR SAM'):self.kind='MIM-104' if self.kind=='LR SAM' or getattr(self.owner,'long_range',False) else 'MIM-23'
        if self.health is None:self.health=self.stats['health']

    @property
    def alive(self):return self.health>0

    @property
    def name(self):return self.kind

    @property
    def range_nm(self):return self.max_range or self.stats['max_range_nm']

    @property
    def boost_duration(self):return self.stats['boost_seconds']

    @property
    def color(self):return '#ff8b45' if self.owner.enemy else '#ffe66d'

    def position(self,now=None):return self.x,self.y

    @property
    def guidance_target(self):return self.decoy if self.decoy is not None else self.radar_memory_point or self.target

@dataclass(eq=False)
class Bullet:
    owner: object
    x: float
    y: float
    heading: float
    spawned: float
    travelled: float = 0.

@dataclass(eq=False)
class FlakShell:
    owner: object
    start: tuple
    end: tuple
    launched: float
    duration: float

    def position(self,now):
        fraction=max(0.,min(1.,(now-self.launched)/max(1e-9,self.duration)))
        return tuple(a+(b-a)*fraction for a,b in zip(self.start,self.end))

@dataclass(eq=False)
class Shrapnel:
    owner: object
    x: float
    y: float
    heading: float
    travelled: float = 0.


class CombatWorld:
    def __init__(self,seed=None):
        self.factories=[];self.enemies=[];self.friendly_aircraft=[];self.icbms=[];self.next_icbm_id=1
        self.events=[];self.kill_ids=set();self.unit_states={};self.visible_ground_contacts=set()
        self.bombs=[];self.missiles=[];self.flares=[];self.explosions=[];self.flak_shells=[];self.shrapnel=[]
        self.known=set();self.known_wrecks=set();self.contacts={False:{},True:{}}
        self.radars=[];self.sams=[];self.ciws=[];self.bullets=[];self.rng=random.Random(seed);self.last_advance=0.
        self.pending_flares=[];self.attack_salvos=[];self.last_target_shot={};self.current_aircraft=[]
        self.cm_bursts={}
        self.campaign=None
        self.contact_numbers={'F':0,'B':0,'D':0}
        self.airfield_health_snapshots={}
        self._target_limit_cache=None
        self._committed_cache=None
        self.sound_callback=None
        self.weapon_totals={k:0 for k in ('bullets','missiles','flak shells','bombs')}
        self.attacker_reveals={False:{},True:{}}
        self.ground_targets=[]
        self.enemy_radars=[];self.enemy_sams=[];self.known_ground=set();self.identified_ground=set()

    def aircraft_label(self,unit):
        if isinstance(unit,ICBM):return unit.name
        if not unit.enemy:return str(unit.parking_slot+1)
        if not hasattr(unit,'contact_label'):
            prefix='B' if unit.kind=='Bomber' else 'D' if unit.kind=='Suicide Drone' else 'F'
            self.contact_numbers[prefix]+=1;unit.contact_label=f'{prefix}{self.contact_numbers[prefix]}'
        return unit.contact_label

    def register_enemy(self,unit):
        self.aircraft_label(unit);self.enemies.append(unit)

    def log_airfield_damage(self,now):
        units=[u for u in self.ground_targets if type(u).__name__=='Airfield']+[u for u in self.factories if hasattr(u,'band_number')]
        for unit in units:
            old=self.airfield_health_snapshots.get(id(unit),unit.health)
            if unit.health<old:
                self.events.append((now,f'{self.unit_name(unit)} took {old-unit.health:g} HP damage · {max(0,unit.health):g}/{unit.max_health:g} HP',0,'damage'))
            self.airfield_health_snapshots[id(unit)]=unit.health

    def unit_name(self,unit):
        if isinstance(unit,ICBM):return unit.name
        if isinstance(unit,Aircraft):
            return f'{self.aircraft_label(unit)} · {unit.kind}' if unit.enemy else f'{unit.kind} #{unit.parking_slot+1}'
        if hasattr(unit,'band_number'):return unit.name
        name=getattr(unit,'name',type(unit).__name__);number=getattr(unit,'id',None)
        return f'{name} #{number}' if number is not None else name

    def record_kill(self,owner,target,now):
        if target.alive or getattr(target,'kill_recorded',False):return
        target.kill_recorded=True
        if isinstance(target,(Missile,ICBM)):self.emit_sound('missile_explosion',(target.x,target.y))
        elif isinstance(target,Bomb):self.emit_sound(f'bomb_{target.weight}',target.position(now))
        if isinstance(target,ICBM) and not getattr(owner,'enemy',False):target.intercepted=True
        self.kill_ids.add(id(target))
        reward=0
        if not getattr(owner,'enemy',False) and getattr(target,'enemy',False):
            if isinstance(target,ICBMSilo):reward=STATS['economy']['kill_rewards']['ICBM Silo']
            elif isinstance(target,Bunker):reward=STATS['economy']['kill_rewards']['Bunker']
            elif isinstance(target,Factory):reward=STATS['economy']['kill_rewards']['Factory']
            elif isinstance(target,Aircraft):reward=STATS['economy']['kill_rewards'].get(target.kind,0)
            elif hasattr(target,'stats_key'):reward=STATS['economy']['kill_rewards'].get(target.stats_key,0)
        kind='enemy_kill' if getattr(owner,'enemy',False) else 'kill'
        self.events.append((now,f'{self.unit_name(owner)} killed {self.unit_name(target)}',reward,kind))

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
        s=STATS['enemy_default_loadouts']['Fighter']
        a=Aircraft('Fighter',list(s['hardpoints']),list(s['bays']),
                   enemy=True,color='#ef6262')
        a.x=x;a.y=y;a.heading=math.atan2(-x,-y);a.speed=a.cruise_speed
        a.state='airborne';a.fenced_in=True;a.orbit_center=(0.,0.)
        a.target_types={'Fighters','Suicide Drones','Bombers'}
        airfield=next((u for u in self.ground_targets if type(u).__name__=='Airfield'),None)
        a.direct_to((airfield.x,airfield.y) if airfield is not None else (0.,0.))
        self.register_enemy(a);return a

    def spawn_interceptor(self,x,y):
        # Match the existing wave loadout; use the Interceptor's independent enemy stats.
        from game_settings import loadout_label
        a=Aircraft('Interceptor',enemy=True,color='#ef6262')
        a.hardpoints=[loadout_label('1× AIM-120')]*a.spec['hardpoints'];a.refill()
        a.x=x;a.y=y;a.heading=math.atan2(-x,-y);a.speed=a.cruise_speed
        a.state='airborne';a.target_types={'Fighters','Suicide Drones','Bombers'}
        airfield=next((u for u in self.ground_targets if type(u).__name__=='Airfield'),None)
        a.direct_to((airfield.x,airfield.y) if airfield is not None else (0.,0.))
        self.register_enemy(a);return a

    def spawn_bomber(self,x,y):
        s=STATS['enemy_default_loadouts']['Bomber']
        a=Aircraft('Bomber',list(s['hardpoints']),list(s['bays']),enemy=True,color='#ef6262')
        a.x=x;a.y=y;a.heading=math.atan2(-x,-y);a.speed=a.cruise_speed
        a.state='airborne';a.orbit_center=(0.,0.);a.target_types={'Ground','Fighters','Bombers','Suicide Drones'}
        airfield=next((u for u in self.ground_targets if type(u).__name__=='Airfield'),None)
        a.direct_to((airfield.x,airfield.y) if airfield is not None else (0.,0.))
        self.register_enemy(a);return a

    def contact(self,target,team=False):return self.contacts[team].get(id(target))

    def spawn_drone(self,x,y):
        a=Aircraft('Suicide Drone',[],[],enemy=True,color='#ffe66d')
        a.x=x;a.y=y;a.heading=math.atan2(-x,-y);a.speed=a.cruise_speed
        a.state='airborne';a.fenced_in=True;a.orbit_center=(0.,0.)
        a.target_types={'Ground'}
        airfield=next((u for u in self.ground_targets if type(u).__name__=='Airfield'),None)
        a.direct_to((airfield.x,airfield.y) if airfield is not None else (0.,0.))
        self.register_enemy(a);return a

    def emit_sound(self,event,position=None):
        if self.sound_callback is not None:self.sound_callback(event,position)

    def has_datalink(self,target,team=False):
        contact=self.contact(target,team)
        return airborne(target) and contact is not None and contact.kind=='datalink'

    def discover(self,aircraft,now):
        # Firing a weapon does not reveal its shooter; sensors must spot it.
        alive=[a for a in [*aircraft,*self.icbms] if a.alive]
        friendly=[a for a in alive if not a.enemy];hostile=[a for a in alive if a.enemy]
        ground_observers=[u for u in self.ground_targets if not getattr(u,'enemy',False) and hasattr(u,'visual_detects')]
        self.visible_ground_contacts=set()
        for target in self.factories:
            if target.alive and any(a.visual_detects(target.x,target.y) for a in [*friendly,*ground_observers]):
                self.known.add(target.id);self.visible_ground_contacts.add(id(target))
        for target in [*self.enemy_radars,*self.enemy_sams]:
            if target.alive and any(a.visual_detects(target.x,target.y) for a in [*friendly,*ground_observers]):
                self.known_ground.add(id(target));self.identified_ground.add(id(target));self.visible_ground_contacts.add(id(target))
        for target in [*self.radars,*[u for u in self.ciws if getattr(u,'shot_kind',None)=='flak']]:
            if target.alive and any(a.visual_detects(target.x,target.y) for a in hostile):self.identified_ground.add(id(target))
        for team,observers,targets in ((False,friendly,hostile),(True,hostile,friendly)):
            contacts=self.contacts[team]
            reveals=self.attacker_reveals[team]
            expired={key for key,(owner,until) in reveals.items() if now>=until or not owner.alive}
            for key in expired:reveals.pop(key)
            for target in targets:
                datalink=airborne(target) and (
                    any(r.radar_detects(target.x,target.y) for r in [*(self.enemy_radars if team else self.radars),*[u for u in (self.enemy_sams if team else self.ciws) if hasattr(u,'radar_detects')]])
                    or any(a.kind!='AWACS' and a.radar_detects(target.x,target.y) for a in observers))
                early_visual=False
                visual=(not team and any(u.visual_detects(target.x,target.y) for u in ground_observers)) or early_visual or any(c.alive and math.hypot(target.x-c.x,target.y-c.y)<=getattr(c,'visual_range_nm',8.) for c in (self.ciws if not team else [u for u in self.enemy_sams if u.stats_key=='CIWS'])) or id(target) in reveals or any(a.visual_detects(target.x,target.y) or
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
            if not sam.alive or not getattr(sam,'enabled',True) or sam.ammo<=0 or 'max_inflight_missiles' not in sam.stats:continue
            if sum(m.owner is sam for m in self.missiles)>=sam.stats['max_inflight_missiles']:continue
            if now-getattr(sam,'last_missile_shot',-math.inf)<sam.stats['shot_interval_seconds']-1e-9:continue
            missile_kind=getattr(sam,'missile_kind','MIM-23')
            if missile_kind=='MIM-23' and sam.long_range:missile_kind='MIM-104'
            if missile_kind=='SM1':
                targets=[a for a in self.friendly_aircraft if airborne(a) and a.enemy!=sam.enemy
                         and a.category in sam.preferred_targets and (sam.enemy,id(a)) not in busy
                         and sam.radar_detects(a.x,a.y)
                         and sam.min_engagement_range_nm<=math.hypot(a.x-sam.x,a.y-sam.y)<=min(sam.range_nm,MISSILE_LAUNCH_RANGE[missile_kind])]
            else:
                targets=[c.target for c in self.contacts[sam.enemy].values()
                         if self.has_datalink(c.target,sam.enemy) and (sam.enemy,id(c.target)) not in busy
                         and sam.accepts_target(c.target.category,c.target.x,c.target.y,on_datalink=True)
                         and math.hypot(c.target.x-sam.x,c.target.y-sam.y)<=MISSILE_LAUNCH_RANGE[missile_kind]]
            if not targets:continue
            target=min(targets,key=lambda a:math.hypot(a.x-sam.x,a.y-sam.y))
            heading=sam.bearing if missile_kind=='PAC-3 MSE' else math.atan2(target.x-sam.x,target.y-sam.y)
            launch_speed=STATS['missiles'][missile_kind].get('launch_speed_knots',0.)
            missile=Missile(sam,target,missile_kind,now,sam.x,sam.y,heading,launch_speed,launch_speed,self.rng.uniform(STATS['countermeasures']['lead_seconds_min'],STATS['countermeasures']['lead_seconds_max']),max_range=MISSILE_RANGE[missile_kind])
            sam.ammo-=1;sam.last_missile_shot=now
            self.missiles.append(missile);busy.add((sam.enemy,id(target)))
            if not sam.enemy:self.weapon_totals['missiles']+=1

    def radar_site_support(self,target,team=False):
        sites=self.enemy_radars if team else self.radars
        return any(r.radar_detects(target.x,target.y) for r in sites)

    def weapon_choice(self,a,target):
        distance=math.hypot(target.x-a.x,target.y-a.y)
        error=abs(angle_error(math.atan2(target.x-a.x,target.y-a.y),a.heading))
        if distance<=MISSILE_LAUNCH_RANGE['AIM-9'] and a.weapon_enabled('AIM-9') and a.missile_inventory.get('AIM-9',0) and error<=math.radians((a.radar_angle_deg/2 or 30)*1.2)+1e-12:return 'AIM-9'
        if distance<=MISSILE_LAUNCH_RANGE['AIM-120'] and a.weapon_enabled('AIM-120') and a.missile_inventory.get('AIM-120',0) and self.has_datalink(target,a.enemy) and a.radar_detects(target.x,target.y):return 'AIM-120'
        return None

    def prefers_anti_radar(self,a,target):
        return target.category=='Radars' and any(a.weapon_enabled(kind) and a.missile_inventory.get(kind,0)>0 for kind in ANTI_RADAR_WEAPONS)

    def anti_radar_weapon(self,a,target):
        distance=math.hypot(target.x-a.x,target.y-a.y)
        identified=id(target) in self.identified_ground
        standard=not getattr(target,'long_range',False) and not getattr(target,'early_warning',False)
        sidearm=(identified or getattr(target,'missile_kind',None)=='SM1') and a.weapon_enabled('Sidearm') and a.missile_inventory.get('Sidearm',0)>0 and distance<=MISSILE_LAUNCH_RANGE['Sidearm']
        harm=a.weapon_enabled('AGM-88') and a.missile_inventory.get('AGM-88',0)>0 and distance<=AGM88_LAUNCH_RANGE
        if standard and sidearm:return 'Sidearm'
        if harm:return 'AGM-88'
        if sidearm:return 'Sidearm'
        return None

    def committed_shots(self,target,team):
        if self._committed_cache is not None:return self._committed_cache.get((id(target),team),0)
        active=sum(weapon.target is target and weapon.owner.enemy==team and weapon.target.alive for weapon in (*self.missiles,*self.bombs))
        reserved=sum(plan['remaining'] for plan in self.attack_salvos if plan['target'] is target and plan['owner'].enemy==team)
        return active+reserved

    def target_limit(self,target,team):
        cache=self._target_limit_cache
        if cache is None:return self.compute_target_limit(target,team)
        key=(id(target),team)
        if key not in cache:cache[key]=self.compute_target_limit(target,team)
        return cache[key]

    def compute_target_limit(self,target,team):
        air=isinstance(target,Aircraft);limits=[1]
        active_owners=None
        for a in self.current_aircraft:
            limit=a.air_weapons_per_target if air else a.ground_weapons_per_target
            if limit<=max(limits):continue
            if a.enemy!=team or not a.alive or a.state!='airborne' or a.mode=='rtb' or not a.fenced_in:continue
            if a.attack_target is not None and a.attack_target is not target:continue
            if active_owners is None:active_owners={id(weapon.owner) for weapon in (*self.missiles,*self.bombs) if weapon.target is target and weapon.owner.enemy==team and isinstance(weapon.owner,Aircraft)}
            if id(a) not in active_owners:
                if air:
                    if target is not a.attack_target and math.hypot(target.x-a.x,target.y-a.y)>a.engagement_range:continue
                    if not (target is a.attack_target or target.category in a.target_types) or self.weapon_choice(a,target) is None:continue
                else:
                    anti=(target is a.attack_target or 'Radars' in a.target_types) and getattr(target,'radar_emitting',False) and self.anti_radar_weapon(a,target) is not None
                    known=(a.visual_detects(target.x,target.y) if a.enemy else target.id in self.known if isinstance(target,Factory) else id(target) in self.known_ground)
                    bomb=a.usable_bombs and not self.prefers_anti_radar(a,target) and known and (target is a.attack_target or target.category in a.target_types) and math.hypot(target.x-a.x,target.y-a.y)<=a.engagement_range
                    if not anti and not bomb:continue
            limits.append(a.air_weapons_per_target if air else a.ground_weapons_per_target)
        return max(limits)

    def target_has_room(self,target,a):return self.committed_shots(target,a.enemy)<self.target_limit(target,a.enemy)

    def remaining_rounds(self,a,family):
        if family=='air':return a.usable_air_missiles
        if family=='bomb':return a.usable_bombs
        return sum(a.missile_inventory.get(kind,0) for kind in ANTI_RADAR_WEAPONS if a.weapon_enabled(kind))

    def fire_one(self,a,target,family,now,followup=False):
        if not a.alive or a.state!='airborne' or a.mode=='rtb' or not a.fenced_in or not target.alive:return False
        dx,dy=target.x-a.x,target.y-a.y;distance=math.hypot(dx,dy);bearing=math.atan2(dx,dy)
        error=abs(angle_error(bearing,a.heading))
        if family=='bomb':
            if distance<=.1 or distance>BOMB_DISTANCE+.02 or error>math.radians(STATS['bomb_behavior']['alignment_degrees']) or a.speed<=BOMB_DRAG*3600*distance:return False
            weight=a.take_bomb(target.health)
            if weight is None:return False
            self.bombs.append(Bomb(a,target,weight,now,(a.x,a.y),a.speed,a.heading,drop_distance=min(BOMB_DISTANCE,distance)))
            if not a.enemy:self.weapon_totals['bombs']+=1
            a.bomb_run_target=target;a.bomb_run_phase='reposition';a.combat_home=True
            a.bomb_run_heading=a.heading+math.pi if a.enemy else math.atan2(-a.x,-a.y)
        else:
            kind=self.weapon_choice(a,target) if family=='air' else self.anti_radar_weapon(a,target)
            if kind is None or (family=='anti' and (not getattr(target,'radar_emitting',False) or (not followup and error>math.radians(a.radar_angle_deg/2 or 30)))):return False
            a.missile_inventory[kind]-=1
            self.missiles.append(Missile(a,target,kind,now,a.x,a.y,a.heading,a.speed,a.speed,self.rng.uniform(STATS['countermeasures']['lead_seconds_min'],STATS['countermeasures']['lead_seconds_max']) if family=='air' else 0))
            self.emit_sound('aircraft_missile',(a.x,a.y))
            if not a.enemy:self.weapon_totals['missiles']+=1
            if family=='anti':a.combat_heading=bearing+math.pi
            elif kind=='AIM-120':
                a.crank_side=-1 if angle_error(bearing,a.heading)>=0 else 1
                a.combat_heading=bearing+a.crank_side*max(0,math.radians(a.radar_angle_deg/2-10))
        if self._committed_cache is not None:
            key=(id(target),a.enemy);self._committed_cache[key]=self._committed_cache.get(key,0)+1
        a.combat_used_weapons=True;a.engage_target=None
        self.last_target_shot[(a.enemy,id(target))]=now
        return True

    def start_salvo(self,a,target,family,now):
        if not self.target_has_room(target,a) or now-self.last_target_shot.get((a.enemy,id(target)),-math.inf)<SALVO_INTERVAL-1e-9:return False
        if not self.fire_one(a,target,family,now):return False
        own_limit=a.air_weapons_per_target if family=='air' else a.ground_weapons_per_target
        remaining=min(own_limit-1,self.remaining_rounds(a,family),self.target_limit(target,a.enemy)-self.committed_shots(target,a.enemy))
        if remaining>0:
            self.attack_salvos.append({'owner':a,'target':target,'family':family,'remaining':remaining,'fired':1,'due':now+SALVO_INTERVAL})
            if self._committed_cache is not None:
                key=(id(target),a.enemy);self._committed_cache[key]=self._committed_cache.get(key,0)+remaining
            if family=='bomb':a.combat_home=False;a.bomb_run_phase='attack';a.bomb_run_heading=None
            elif family=='air':a.combat_heading=None;a.engage_target=target
        return True

    def process_salvos(self,now):
        pending=[]
        for plan in self.attack_salvos:
            a,target=plan['owner'],plan['target']
            if not a.alive or not target.alive or a.state!='airborne' or a.mode=='rtb' or not a.fenced_in or not self.remaining_rounds(a,plan['family']):continue
            own_limit=a.air_weapons_per_target if plan['family']=='air' else a.ground_weapons_per_target
            active=sum(weapon.target is target and weapon.owner.enemy==a.enemy for weapon in (*self.missiles,*self.bombs))
            if plan['fired']>=own_limit or active>=self.target_limit(target,a.enemy):continue
            if now>=plan['due']-1e-9:
                if now-self.last_target_shot.get((a.enemy,id(target)),-math.inf)<SALVO_INTERVAL-1e-9:
                    pending.append(plan);continue
                if not self.fire_one(a,target,plan['family'],now,followup=True):continue
                plan['remaining']-=1;plan['fired']+=1;plan['due']=now+SALVO_INTERVAL
            if plan['remaining']>0:pending.append(plan)
        self.attack_salvos=pending

    def prepare(self,aircraft,now):
        # Eligibility is a snapshot of this simulation step; committed shots stay live.
        self._target_limit_cache={}
        try:self.prepare_step(aircraft,now)
        finally:self._target_limit_cache=None;self._committed_cache=None

    def prepare_step(self,aircraft,now):
        self.current_aircraft=list(aircraft)
        self.friendly_aircraft=[a for a in aircraft if not a.enemy]
        if self.campaign is not None:
            self.campaign.advance(now)
            aircraft.extend(a for a in self.enemies if not any(a is old for old in aircraft))
        self.reload_enemies(now)
        self.launch_icbms(now)
        aircraft.extend(self.launch_drones(now))
        self.current_aircraft=list(aircraft)
        self.log_airfield_damage(now)
        self.discover(aircraft,now)
        self.launch_sams(now)
        self.process_salvos(now)
        self._committed_cache={}
        for weapon in (*self.missiles,*self.bombs):
            if weapon.target.alive:
                key=(id(weapon.target),weapon.owner.enemy)
                self._committed_cache[key]=self._committed_cache.get(key,0)+1
        for plan in self.attack_salvos:
            key=(id(plan['target']),plan['owner'].enemy)
            self._committed_cache[key]=self._committed_cache.get(key,0)+plan['remaining']
        for a in aircraft:
            a.engage_target=None;a.combat_heading=None
            a.auto_attack_target=None
            if a.attack_target is not None and not a.attack_target.alive:
                a.attack_target=None;a.attack_point=None
            if a.attack_target is not None:
                contact=self.contact(a.attack_target,a.enemy)
                if contact is not None:a.attack_point=(contact.x,contact.y)
                elif id(a.attack_target) in self.known_ground or (isinstance(a.attack_target,Factory) and a.attack_target.id in self.known):a.attack_point=(a.attack_target.x,a.attack_target.y)
            a.combat_home=any(b.owner is a for b in self.bombs)
            if not a.alive or a.state!='airborne' or a.mode=='rtb':continue
            if getattr(a,'wave_assembling',False):continue
            support=[m for m in self.missiles if m.owner is a and m.kind=='AIM-120' and not m.pitbull
                     and not m.terminal and m.decoy is None and m.target.alive
                     and not self.radar_site_support(m.target,a.enemy)
                     and (a.attack_target is None or m.target is a.attack_target)]
            if (not a.enemy and a.combat_used_weapons and not a.bombs_available and not a.missiles_available
                and not support and not any(m.owner is a and m.kind in ANTI_RADAR_WEAPONS and m.target.alive for m in self.missiles)):
                a.combat_home=False;a.bomb_run_target=None;a.bomb_run_heading=None
                a.request_auto('rtb','ammo');continue
            if a.missiles_available or a.bombs_available:
                a.ignored_auto.discard('ammo')
                if a.pending_auto and a.pending_auto['reason']=='ammo':a.pending_auto=None
            active=[weapon.target for weapon in (*self.missiles,*self.bombs)
                    if weapon.owner is a and weapon.target.alive]
            if active:a.auto_attack_target=active[0]
            harms=[m for m in self.missiles if m.owner is a and m.kind in ANTI_RADAR_WEAPONS and m.target.alive]
            if harms:
                target=harms[0].target;a.auto_attack_target=target
                a.combat_home=False
                a.combat_heading=math.atan2(a.x-target.x,a.y-target.y)
                continue
            plan=next((plan for plan in self.attack_salvos if plan['owner'] is a),None)
            if plan is not None and plan['family']!='anti':
                a.combat_home=False;a.engage_target=plan['target'];a.auto_attack_target=plan['target'];continue
            run=a.bomb_run_target
            if run is not None and (not run.alive or not a.fenced_in or not a.usable_bombs):
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
            if support:
                target=support[0].target;bearing=math.atan2(target.x-a.x,target.y-a.y)
                a.auto_attack_target=target
                offset=max(0,math.radians(a.radar_angle_deg/2-10))
                a.combat_heading=bearing+a.crank_side*offset
                # Supporting an earlier AIM-120 does not forbid another valid shot.
                available=[t for t,timestamp in self.contacts[a.enemy].values()
                           if (t is a.attack_target or (a.attack_target is None and t.category in a.target_types))
                           and (t is a.attack_target or math.hypot(t.x-a.x,t.y-a.y)<=a.engagement_range)
                           and self.target_has_room(t,a) and self.weapon_choice(a,t) is not None]
                if available:
                    follow=min(available,key=lambda t:math.hypot(t.x-a.x,t.y-a.y))
                    self.start_salvo(a,follow,'air',now)
                    a.combat_heading=bearing+a.crank_side*offset
                continue
            targets=[t for t,timestamp in self.contacts[a.enemy].values()
                     if (t is a.attack_target or (a.attack_target is None and t.category in a.target_types)) and self.target_has_room(t,a)
                     and (t is a.attack_target or math.hypot(t.x-a.x,t.y-a.y)<=a.engagement_range) and a.usable_air_missiles]
            emitters=[*self.radars,*[s for s in [*self.sams,*self.ciws] if getattr(s,'radar_emitting',False)]] if a.enemy else [*self.enemy_radars,*[s for s in self.enemy_sams if getattr(s,'radar_emitting',False)]]
            harm_targets=[t for t in emitters if t.alive and t.radar_emitting and self.anti_radar_weapon(a,t) is not None
                          and self.target_has_room(t,a)
                          and (t is a.attack_target or (a.attack_target is None and 'Radars' in a.target_types))
                          and math.hypot(t.x-a.x,t.y-a.y)<=AGM88_LAUNCH_RANGE]
            ground=[t for t in (self.ground_targets if a.enemy and a.kind in ('Suicide Drone','Bomber') else [*self.factories,*self.enemy_radars,*self.enemy_sams] if not a.enemy else [])
                    if t.alive and (a.visual_detects(t.x,t.y) if a.enemy else t.id in self.known if isinstance(t,Factory) else id(t) in self.known_ground and (t is a.attack_target or a.visual_detects(t.x,t.y)))
                    and self.target_has_room(t,a) and (t is a.attack_target or (a.attack_target is None and t.category in a.target_types))
                    and (a.kind=='Suicide Drone' or (a.usable_bombs and not self.prefers_anti_radar(a,t)))
                    and (t is a.attack_target or t is a.bomb_run_target or math.hypot(t.x-a.x,t.y-a.y)<=a.engagement_range)]
            targets+=ground
            if harm_targets:targets=harm_targets
            if not targets:continue
            target=min(targets,key=lambda t:math.hypot(t.x-a.x,t.y-a.y));a.engage_target=target
            a.auto_attack_target=target
            dx,dy=target.x-a.x,target.y-a.y;distance=math.hypot(dx,dy)
            bearing=math.atan2(dx,dy);error=abs(angle_error(bearing,a.heading))
            if a.kind=='Suicide Drone':continue
            if not isinstance(target,Aircraft):
                if target in harm_targets:
                    if error<=math.radians(a.radar_angle_deg/2 or 30):self.start_salvo(a,target,'anti',now)
                    continue
                a.bomb_run_target=target;a.bomb_run_phase='attack'
                continuing_bombs=any(b.target is target and b.owner.enemy==a.enemy for b in self.bombs)
                release_min=.1 if continuing_bombs else BOMB_DISTANCE-.06
                if distance<BOMB_DISTANCE+.05 and (distance<release_min or error>math.radians(STATS['bomb_behavior']['alignment_degrees'])):
                    a.bomb_run_phase='reposition';a.combat_home=True;a.engage_target=None
                    a.bomb_run_heading=math.atan2(a.x-target.x,a.y-target.y) if distance>1e-6 else a.heading
                    continue
                # Aim the unguided bomb flight before the homeward leg.
                if release_min<=distance<=BOMB_DISTANCE+.02 and error<=math.radians(STATS['bomb_behavior']['alignment_degrees']) and a.speed>BOMB_DRAG*3600*BOMB_DISTANCE:
                    self.start_salvo(a,target,'bomb',now)
            else:
                self.start_salvo(a,target,'air',now)

    def emit_flare(self,a,due,side,now,burst):
        if not a.alive:return
        vx,vy=velocity(a);lag=max(0,now-due)
        kick=side*180.
        flare=Flare(a,a.x-vx/3600*lag,a.y-vy/3600*lag,
                    vx+math.cos(a.heading)*kick,vy-math.sin(a.heading)*kick,due,side=side)
        self.flares.append(flare);burst.append(flare)

    def deploy_countermeasures(self,a,now):
        recent=self.cm_bursts.get(id(a))
        if recent is not None and now-recent[0]<STATS['countermeasures']['burst_cooldown_seconds']:return [f for f in recent[1] if f.alive]
        if a.cms<=0:return []
        a.cms-=1;burst=[]
        self.emit_flare(a,now,-1,now,burst)
        count=STATS['countermeasures']['burst_flare_count']
        for i in range(1,count):self.pending_flares.append((now+STATS['countermeasures']['burst_duration_seconds']*i/(count-1),a,-1 if i%2==0 else 1,burst))
        self.cm_bursts[id(a)]=(now,burst)
        return burst

    def countermeasure_check(self,m,now):
        if m.cm_checked or m.decoy is not None or not m.target.alive:return
        if m.cm_burst is not None:
            if len(m.cm_burst)<m.cm_burst_count:return
            m.cm_checked=True
            choices=[flare for flare in m.cm_burst if flare.alive]
            if choices and self.rng.random()<STATS['countermeasures']['success_probability']:
                m.decoy=self.rng.choice(choices)
                self.events.append((now,f'{self.unit_name(m.target)} successfully used CMS on {self.unit_name(m.owner)} ({m.kind})',0,'status'))
            return
        dx,dy=m.target.x-m.x,m.target.y-m.y;distance=math.hypot(dx,dy)
        if distance<HIT_RADIUS:return
        tvx,tvy=velocity(m.target)
        closing=((math.sin(m.heading)*m.speed-tvx)*dx+(math.cos(m.heading)*m.speed-tvy)*dy)/distance
        eta=distance*3600/closing if closing>1 else math.inf
        if eta<=m.cm_lead:
            burst=self.deploy_countermeasures(m.target,now)
            if burst:
                # Keep the live burst list so later scheduled decoys join it.
                m.cm_burst=self.cm_bursts[id(m.target)][1]
                m.cm_burst_count=STATS['countermeasures']['burst_flare_count']
                self.countermeasure_check(m,now)

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
        self.emit_sound('missile_explosion',(m.x,m.y))

    def step_missile(self,m,now,dt):
        age=max(0,now-m.launched)
        if m.kind in ANTI_RADAR_WEAPONS:
            if getattr(m.target,'radar_emitting',False):m.radar_memory_point=None
            elif m.radar_memory_point is None:
                distance=math.hypot(m.target.x-m.x,m.target.y-m.y)
                spread=distance*STATS['missile_behavior']['anti_radar_shutdown_scatter_nm_per_nm']
                radius=self.rng.uniform(0,spread);angle=self.rng.uniform(0,math.tau)
                m.radar_memory_point=RadarMemoryPoint(m.target.x+radius*math.sin(angle),m.target.y+radius*math.cos(angle))
        target=m.guidance_target
        # Latch active guidance: a later turn away or loss of radar cannot undo it.
        if (m.kind=='AIM-120' and not m.terminal and m.target.alive and not m.pitbull
            and math.hypot(m.target.x-m.x,m.target.y-m.y)<=m.stats['pitbull_range_nm']):
            m.pitbull=True;m.lost_lock=0.
        if not m.terminal:
            if not m.target.alive:m.terminal=True
            elif m.kind in ('AIM-120','MIM-23','MIM-104','PAC-3 MSE') and m.decoy is None and not m.pitbull:
                supported=self.has_datalink(target,m.owner.enemy)
                if m.kind=='AIM-120':
                    supported=self.radar_site_support(target,m.owner.enemy) or (supported and m.owner.alive and m.owner.radar_detects(target.x,target.y))
                if not supported:m.lost_lock+=dt
                else:m.lost_lock=0.
                if m.lost_lock>STATS['missile_behavior']['lost_lock_seconds']:m.terminal=True
        if m.terminal:
            m.terminal_age+=dt
            if m.terminal_age>=STATS['missile_behavior']['self_destruct_seconds']:
                self.explode_missile(m,now);return False
        elif isinstance(m.target,Aircraft):self.countermeasure_check(m,now)
        target=m.guidance_target
        change=0.
        if m.kind=='PAC-3 MSE' and age<=m.boost_duration+1e-9:
            m.speed=min(m.stats['speed_knots'],m.launch_speed+(m.stats['speed_knots']-m.launch_speed)*age/m.boost_duration)
        can_turn=m.speed>=m.stats.get('min_turn_speed_fraction',0)*m.stats['speed_knots']
        if not m.terminal and can_turn:
            desired=self.intercept_heading(m,target)
            rate=min(math.radians(m.stats.get('turn_limit_degrees_per_second',STATS['missile_behavior']['turn_limit_degrees_per_second'])),9.81*STATS['missile_behavior']['turn_g_limit']/max(50,m.speed*.514444))
            if m.kind=='AIM-9' and math.hypot(target.x-m.x,target.y-m.y)<=STATS['missile_behavior']['aim9_close_turn_range_nm']:rate*=STATS['missile_behavior']['aim9_close_turn_multiplier']
            change=max(-rate*dt,min(rate*dt,angle_error(desired,m.heading)))
            m.heading=(m.heading+change)%math.tau
        if age<=m.boost_duration+1e-9:
            top_speed=m.stats['speed_knots']
            m.speed=min(top_speed,m.launch_speed+(top_speed-m.launch_speed)*age/m.boost_duration)
        else:
            drag=m.stats['coast_deceleration_knots_per_second']
            if m.kind in ANTI_RADAR_WEAPONS and STATS['missile_behavior']['anti_radar_range_based_drag']:
                if m.coast_start_distance is None:m.coast_start_distance=m.travelled
                drag=m.stats['speed_knots']**2/(2*3600*max(1.,m.range_nm-m.coast_start_distance))
            m.speed=max(0,m.speed-drag*dt)
        m.speed=max(0,m.speed-abs(math.degrees(change))*STATS['missile_behavior']['turn_drag_knots_per_degree'])
        step=m.speed/3600*dt
        if m.travelled+step>m.range_nm:step=max(0,m.range_nm-m.travelled)
        old=(m.x,m.y);m.x+=math.sin(m.heading)*step;m.y+=math.cos(m.heading)*step;m.travelled+=step
        if not m.history or now-m.history[-1][0]>=.2-1e-9:m.history.append((now,m.x,m.y))
        while m.history and now-m.history[0][0]>12:m.history.pop(0)
        if not m.terminal:
            dx,dy=m.x-old[0],m.y-old[1];length2=dx*dx+dy*dy
            def passed(point):
                t=max(0,min(1,((point.x-old[0])*dx+(point.y-old[1])*dy)/max(1e-20,length2)))
                return math.hypot(point.x-old[0]-t*dx,point.y-old[1]-t*dy)<=HIT_RADIUS
            # Radar shutdown removes precision guidance, not physical collision.
            hit=m.target if m.radar_memory_point is not None else target
            if hit.alive and passed(hit):
                if m.decoy is None:
                    base,spread=MISSILE_DAMAGE[m.kind]
                    damage=round(base*self.rng.uniform(1-spread,1+spread))
                    hit.health=max(0.,hit.health-damage)
                    if hit.health<=0 and isinstance(hit,Aircraft):hit.destroy()
                    self.record_kill(m.owner,hit,now)
                else:hit.alive=False
                self.explode_missile(m,now);return False
            if m.radar_memory_point is not None and passed(m.radar_memory_point):
                m.x,m.y=m.radar_memory_point.x,m.radar_memory_point.y
                self.explode_missile(m,now);return False
        if m.travelled>=m.range_nm-1e-9 or (m.speed<STATS['missile_behavior']['min_coast_speed_knots'] and age>m.boost_duration):
            self.explode_missile(m,now);return False
        return True

    def advance_ciws(self,now,dt):
        candidates=[*getattr(self,'friendly_aircraft',()),*self.enemies,*self.icbms,*self.missiles,*self.bombs]
        guns=[*self.ciws,*[u for u in self.enemy_sams if hasattr(u,'gun_ammo') or 'rounds_per_second' in u.stats]]
        for gun in guns:
            if not gun.alive or getattr(gun,'shot_kind',None)=='flak':continue
            ammo_attribute='gun_ammo' if hasattr(gun,'gun_ammo') else 'ammo'
            gun_range=getattr(gun,'gun_range_nm',gun.range_nm)
            if getattr(gun,ammo_attribute)<=0:
                gun.attack_target=None;gun.shot_timer=0.;continue
            targets=[t for t in candidates if t.alive and (t.enemy if isinstance(t,Aircraft) else t.owner.enemy)!=gun.enemy
                     and (airborne(t) if isinstance(t,Aircraft) else True)
                     and (t.category if isinstance(t,Aircraft) else 'Missiles' if isinstance(t,Missile) else 'Bombs') in gun.preferred_targets
                     and gun.min_engagement_range_nm<=math.dist((gun.x,gun.y),(t.position(now) if not isinstance(t,Aircraft) else (t.x,t.y)))<=gun_range]
            gun.attack_target=min(targets,key=lambda t:math.dist((gun.x,gun.y),t.position(now) if not isinstance(t,Aircraft) else (t.x,t.y)),default=None)
            if gun.attack_target is None:
                gun.shot_timer=0.;continue
            # SAAW: 7.5 rounds/sec; CIWS: 10, independent of tick size.
            interval=1/gun.stats['gun_rounds_per_second' if hasattr(gun,'gun_ammo') else 'rounds_per_second']
            gun.shot_timer+=dt
            while getattr(gun,ammo_attribute)>0 and gun.shot_timer>=interval-1e-9:
                gun.shot_timer-=interval
                setattr(gun,ammo_attribute,getattr(gun,ammo_attribute)-1)
                t=gun.attack_target;tx,ty=t.position(now) if not isinstance(t,Aircraft) else (t.x,t.y)
                vx,vy=velocity(t) if not isinstance(t,Bomb) else (math.sin(t.heading)*t.speed_at(now),math.cos(t.heading)*t.speed_at(now))
                travel=math.hypot(tx-gun.x,ty-gun.y)/(STATS['guns']['bullet_speed_knots']/3600)
                heading=math.atan2(tx+vx/3600*travel-gun.x,ty+vy/3600*travel-gun.y)+self.rng.uniform(-math.radians(STATS['guns']['dispersion_degrees']),math.radians(STATS['guns']['dispersion_degrees']))
                self.bullets.append(Bullet(gun,gun.x,gun.y,heading,now))
                self.emit_sound('ciws_fire',(gun.x,gun.y))
                if not gun.enemy:self.weapon_totals['bullets']+=1
        remaining=[]
        for bullet in self.bullets:
            distance=min(STATS['guns']['bullet_speed_knots']/3600*dt,getattr(bullet.owner,'gun_range_nm',bullet.owner.range_nm)-bullet.travelled);old=(bullet.x,bullet.y)
            bullet.x+=math.sin(bullet.heading)*distance;bullet.y+=math.cos(bullet.heading)*distance;bullet.travelled+=distance
            hit=None
            for t in candidates:
                if not t.alive or (t.enemy if isinstance(t,Aircraft) else t.owner.enemy)==bullet.owner.enemy:continue
                if isinstance(t,Aircraft) and not airborne(t):continue
                tx,ty=t.position(now) if not isinstance(t,Aircraft) else (t.x,t.y)
                dx,dy=bullet.x-old[0],bullet.y-old[1];d2=dx*dx+dy*dy
                along=max(0,min(1,((tx-old[0])*dx+(ty-old[1])*dy)/max(d2,1e-20)))
                if math.hypot(tx-old[0]-along*dx,ty-old[1]-along*dy)<=STATS['guns']['hit_radius_nm']:hit=t;break
            if hit is not None:
                hit.health=max(0.,hit.health-self.rng.randint(STATS['guns']['damage_min'],STATS['guns']['damage_max']))
                if not hit.alive:
                    pos=hit.position(now) if not isinstance(hit,Aircraft) else (hit.x,hit.y)
                    self.explosions.append((now,*pos,'#ffe9a0'))
                    if isinstance(hit,Aircraft):hit.destroy()
                    self.record_kill(bullet.owner,hit,now)
            elif bullet.travelled<getattr(bullet.owner,'gun_range_nm',bullet.owner.range_nm):remaining.append(bullet)
        self.bullets=remaining

    def advance_flak(self,now,dt):
        aircraft=[*self.friendly_aircraft,*self.enemies,*self.icbms]
        guns=[u for u in [*self.ciws,*self.enemy_sams] if getattr(u,'shot_kind',None)=='flak']
        for gun in guns:
            if not gun.alive or not gun.radar_emitting or gun.ammo<=0:gun.attack_target=None;gun.shot_timer=0.;continue
            targets=[a for a in aircraft if airborne(a) and a.enemy!=gun.enemy and a.category in gun.preferred_targets
                     and gun.radar_detects(a.x,a.y)
                     and gun.min_engagement_range_nm<=math.hypot(a.x-gun.x,a.y-gun.y)<=gun.range_nm]
            gun.attack_target=min(targets,key=lambda a:math.hypot(a.x-gun.x,a.y-gun.y),default=None)
            if gun.attack_target is None:gun.shot_timer=0.;continue
            gun.shot_timer+=dt
            interval=1/gun.stats['shells_per_second']
            while gun.ammo>0 and gun.shot_timer>=interval-1e-9:
                gun.shot_timer-=interval;gun.ammo-=1;target=gun.attack_target
                point=intercept_point((gun.x,gun.y),(target.x,target.y),velocity(target),STATS['flak']['shell_speed_knots'])
                dx,dy=point[0]-gun.x,point[1]-gun.y
                distance=min(gun.range_nm,math.hypot(dx,dy))
                heading=math.atan2(dx,dy)+self.rng.uniform(-math.radians(STATS['flak']['dispersion_degrees']),math.radians(STATS['flak']['dispersion_degrees']))
                point=(gun.x+math.sin(heading)*distance,gun.y+math.cos(heading)*distance)
                duration=math.dist((gun.x,gun.y),point)/STATS['flak']['shell_speed_knots']*3600
                self.flak_shells.append(FlakShell(gun,(gun.x,gun.y),point,now,duration))
                self.emit_sound('flak_fire',(gun.x,gun.y))
                if not gun.enemy:self.weapon_totals['flak shells']+=1
        pending=[];new_fragments=[]
        for shell in self.flak_shells:
            if now-shell.launched<shell.duration:pending.append(shell);continue
            x,y=shell.end;count=self.rng.randint(STATS['flak']['fragment_count_min'],STATS['flak']['fragment_count_max']);offset=self.rng.uniform(0,math.tau)
            for i in range(count):
                angle=offset+math.tau*(i+self.rng.uniform(-.2,.2))/count
                new_fragments.append(Shrapnel(shell.owner,x,y,angle))
            self.explosions.append((now,x,y,'#ffb347'))
            self.emit_sound('flak_burst',(x,y))
        self.flak_shells=pending
        candidates=[*aircraft,*self.missiles];remaining=[]
        for piece in self.shrapnel:
            distance=min(STATS['flak']['fragment_speed_knots']/3600*dt,STATS['flak']['fragment_range_nm']-piece.travelled);old=(piece.x,piece.y)
            piece.x+=math.sin(piece.heading)*distance;piece.y+=math.cos(piece.heading)*distance;piece.travelled+=distance
            hit=None
            for target in candidates:
                if not target.alive or (target.enemy if isinstance(target,Aircraft) else target.owner.enemy)==piece.owner.enemy:continue
                if isinstance(target,Aircraft) and not airborne(target):continue
                tx,ty=(target.x,target.y) if isinstance(target,Aircraft) else target.position(now)
                dx,dy=piece.x-old[0],piece.y-old[1];length2=dx*dx+dy*dy
                along=max(0.,min(1.,((tx-old[0])*dx+(ty-old[1])*dy)/max(length2,1e-20)))
                if math.hypot(tx-old[0]-along*dx,ty-old[1]-along*dy)<=STATS['flak']['fragment_hit_radius_nm']:hit=target;break
            if hit is not None:
                hit.health=max(0.,hit.health-self.rng.randint(STATS['flak']['fragment_damage_min'],STATS['flak']['fragment_damage_max']))
                if not hit.alive:
                    if isinstance(hit,Aircraft):hit.destroy()
                    self.record_kill(piece.owner,hit,now)
            elif piece.travelled<STATS['flak']['fragment_range_nm']:remaining.append(piece)
        # New bursts are drawn at their origin before they move on the next step.
        self.shrapnel=[*remaining,*new_fragments]

    def spawn_drone_launcher(self,x,y):
        unit=DroneLauncher(max((t.id for t in self.factories),default=0)+1,x,y)
        self.factories.append(unit);return unit

    def launch_drones(self,now):
        launched=[]
        airfield=next((u for u in self.ground_targets if type(u).__name__=='Airfield'),None)
        if airfield is None or not airfield.alive:return launched
        for launcher in self.factories:
            if not isinstance(launcher,DroneLauncher) or not launcher.alive or not launcher.enabled or launcher.ammo<=0:continue
            if now<launcher.next_launch-1e-9:continue
            if math.hypot(airfield.x-launcher.x,airfield.y-launcher.y)<launcher.min_engagement_range_nm:continue
            drone=self.spawn_drone(launcher.x,launcher.y)
            drone.heading=math.atan2(airfield.x-launcher.x,airfield.y-launcher.y)
            launcher.ammo-=1;launcher.next_launch=now+launcher.stats['shot_interval_seconds']
            if launcher.ammo==0:launcher.reload_due={'ammo':now+launcher.stats['reload_seconds']}
            launched.append(drone)
            self.events.append((now,f'{self.unit_name(launcher)} launched {self.unit_name(drone)} at Airfield',0,'status'))
        return launched

    def spawn_silo(self,x,y):
        unit=ICBMSilo(max((t.id for t in self.factories),default=0)+1,x,y)
        self.factories.append(unit)
        return unit

    def spawn_icbm(self,x,y,target=None,owner=None):
        if target is None:target=next((u for u in self.ground_targets if type(u).__name__=='Airfield'),None)
        if target is None or not target.alive:return None
        missile=ICBM(owner,target,self.next_icbm_id,x,y);self.next_icbm_id+=1
        self.icbms.append(missile)
        self.emit_sound('icbm_launch',(x,y))
        return missile

    def reload_enemies(self,now):
        for unit in [*self.enemies,*self.enemy_sams,*self.factories]:
            if not unit.alive or not unit.enemy:continue
            pools=[]
            if isinstance(unit,Aircraft):
                missiles,bombs=unit.configured_weapons()
                pools=[(kind,capacity,unit.missile_inventory.get(kind,0)) for kind,capacity in missiles.items() if capacity]
                pools.extend((weight,capacity,sum(n for w,n in unit.bomb_inventory if w==weight)) for weight,capacity in bombs.items() if capacity)
                seconds=unit.spec.get('reload_seconds')
            else:
                pools=[(key,getattr(unit,key+'_capacity'),getattr(unit,key)) for key in ('ammo','gun_ammo') if hasattr(unit,key)]
                seconds=unit.stats.get('reload_seconds')
            if not pools or seconds is None:continue
            timers=getattr(unit,'reload_due',{})
            unit.reload_due=timers
            for key,capacity,remaining in pools:
                if remaining>0:timers.pop(key,None);continue
                if key not in timers:timers[key]=now+seconds
                if now<timers[key]-1e-9:continue
                if isinstance(unit,Aircraft):
                    if isinstance(key,int):
                        unit.bomb_inventory[:]=[rack for rack in unit.bomb_inventory if rack[0]!=key]
                        unit.bomb_inventory.append([key,capacity])
                    else:unit.missile_inventory[key]=capacity
                else:setattr(unit,key,capacity)
                timers.pop(key,None)
                self.events.append((now,f'{self.unit_name(unit)} reloaded',0,'status'))

    def reload_status(self,unit,now):
        timers=getattr(unit,'reload_due',{})
        return ' · '.join(f'{key}: {max(0,math.ceil(due-now))}s' for key,due in timers.items())

    def launch_icbms(self,now):
        airfield=next((u for u in self.ground_targets if type(u).__name__=='Airfield'),None)
        if airfield is None or not airfield.alive:return
        for silo in self.factories:
            if not isinstance(silo,ICBMSilo) or not silo.alive or not silo.enabled or silo.ammo<=0:continue
            if math.hypot(airfield.x-silo.x,airfield.y-silo.y)<silo.min_engagement_range_nm:continue
            missile=self.spawn_icbm(silo.x,silo.y,target=airfield,owner=silo);silo.ammo-=1
            silo.reload_due={'ammo':now+silo.stats['reload_seconds']}
            self.events.append((now,f'{self.unit_name(silo)} launched {missile.name} at Airfield',0,'status'))

    def advance_icbms(self,now,dt):
        for missile in self.icbms:
            if not missile.alive:continue
            target=missile.target
            if not target.alive:missile.destroy();continue
            stats=STATS['icbm'];old_speed=missile.speed
            missile.speed=min(stats['speed_knots'],old_speed+stats['acceleration_knots_per_second']*dt)
            ramp=min(dt,max(0,(stats['speed_knots']-old_speed)/stats['acceleration_knots_per_second']))
            travel=(old_speed*ramp+.5*stats['acceleration_knots_per_second']*ramp*ramp+stats['speed_knots']*(dt-ramp))/3600
            dx,dy=target.x-missile.x,target.y-missile.y;distance=math.hypot(dx,dy)
            missile.heading=math.atan2(dx,dy)
            if travel+stats['hit_radius_nm']>=distance:
                missile.x,missile.y=target.x,target.y
                damage=round(stats['damage']*self.rng.uniform(1-stats['damage_spread_fraction'],1+stats['damage_spread_fraction']))
                target.health=max(0,target.health-damage)
                self.events.append((now,f'{missile.name} hit Airfield for {damage} HP',0,'status'))
                self.record_kill(missile.owner,target,now);missile.destroy()
                self.explosions.append((now,missile.x,missile.y,'#ff4f64'))
                self.emit_sound('missile_explosion',(missile.x,missile.y))
            elif distance:
                missile.x+=dx/distance*travel;missile.y+=dy/distance*travel
            if not missile.history or now-missile.history[-1][0]>=.2:
                missile.history.append((now,missile.x,missile.y,missile.speed))
            while missile.history and now-missile.history[0][0]>30:missile.history.popleft()
        self.icbms[:]=[m for m in self.icbms if m.alive]

    def advance(self,now):
        dt=max(0,now-self.last_advance);self.last_advance=now
        self.advance_ciws(now,dt)
        self.advance_flak(now,dt)
        for drone in self.enemies:
            target=drone.engage_target
            if (drone.kind=='Suicide Drone' and drone.alive and drone.state=='airborne'
                and target is not None and not isinstance(target,Aircraft) and target.alive
                and math.hypot(drone.x-target.x,drone.y-target.y)<=HIT_RADIUS):
                target.health=max(0,target.health-round(STATS['drone_impact']['damage']*self.rng.uniform(1-STATS['drone_impact']['damage_spread_fraction'],1+STATS['drone_impact']['damage_spread_fraction'])))
                self.record_kill(drone,target,now)
                self.explosions.append((now,drone.x,drone.y,'#ffe66d'))
                self.emit_sound('drone_impact',(drone.x,drone.y))
                drone.destroy()
        remaining=[]
        for bomb in self.bombs:
            if not bomb.alive:continue
            if now-bomb.launched>=bomb.duration-1e-9:
                x,y=bomb.position(now)
                if bomb.target.alive and math.hypot(x-bomb.target.x,y-bomb.target.y)<=STATS['bomb_behavior']['hit_radius_nm']:
                    damage=round(BOMB_DAMAGE[bomb.weight]*self.rng.uniform(1-STATS['bombs'][str(bomb.weight)]['damage_spread_fraction'],1+STATS['bombs'][str(bomb.weight)]['damage_spread_fraction']))
                    bomb.target.health=max(0,bomb.target.health-damage)
                    self.record_kill(bomb.owner,bomb.target,now)
                bomb.health=0.
                self.explosions.append((now,x,y,'#87caff'))
                self.emit_sound(f'bomb_{bomb.weight}',(x,y))
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
        self.reload_enemies(now)
        prior_icbms=list(self.icbms)
        self.advance_icbms(now,dt)
        if self.campaign is not None:self.campaign.observe([],prior_icbms)
        self.log_airfield_damage(now)
        self.flares=[f for f in self.flares if f.alive]
        self.explosions=[e for e in self.explosions if now-e[0]<1.]
        self.track_unit_states([*getattr(self,"friendly_aircraft",()),*self.enemies],now)
