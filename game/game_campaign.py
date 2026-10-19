"""Incremental radial campaign generation and enemy runway wave assembly."""
from dataclasses import dataclass,field
import copy
import math
import random
from decimal import Decimal
from .game_settings import STATS
from .game_combat import Factory, ICBM
from .game_aircraft import Aircraft

GROUND_TYPES=('Factory','Bunker','Radar','LR Radar','SAM','LR SAM','Flak','SAAW','CIWS','Drone Launcher','ICBM Silo')
PHONETIC=('Alpha','Bravo','Charlie','Delta','Echo','Foxtrot','Golf','Hotel','India','Juliett','Kilo','Lima','Mike','November','Oscar','Papa','Quebec','Romeo','Sierra','Tango','Uniform','Victor','Whiskey','X-ray','Yankee','Zulu')
WAVE_TYPES=('Fighter','Interceptor','Bomber','Suicide Drone')

def ceil_scaled(value,growth):
    return math.ceil(Decimal(str(value))*(Decimal(1)+Decimal(str(growth))))

def airfield_health_for_band(number,settings):
    last=len(settings['tiers'])
    health=settings['runway_health']+max(0,min(number,last)-1)*settings['runway_health_per_band']
    for _ in range(max(0,number-last)):health=ceil_scaled(health,settings['infinite_growth_fraction'])
    return health

@dataclass(eq=False)
class EnemyRunway(Factory):
    name: str = 'Enemy Runway'
    wave_counts: dict = field(default_factory=dict)
    next_wave: float = 0.
    interval: float = 0.
    wave_number: int = 0
    band_number: int = 1
    runway_health_capacity: float = None
    def __post_init__(self):
        if self.runway_health_capacity is None:self.runway_health_capacity=airfield_health_for_band(self.band_number,STATS['campaign'])
        super().__post_init__()
    @property
    def runway_length(self):return STATS['campaign']['runway_length_nm']
    @property
    def runway_width(self):return STATS['campaign']['runway_width_nm']
    @property
    def stats(self):return {'health':self.runway_health_capacity,'min_engagement_range_nm':0}

@dataclass
class Band:
    number: int
    inner: float
    outer: float
    composition: dict
    runways: list = field(default_factory=list)
    outposts: list = field(default_factory=list)
    random_factories: list = field(default_factory=list)
    completed: bool = False

class Campaign:
    def __init__(self,combat,airfield,ground_factory,seed=None):
        self.settings=STATS['campaign'];self.combat=combat;self.airfield=airfield
        self.ground_factory=ground_factory;self.rng=random.Random(seed if seed is not None else self.settings['random_seed'] or None)
        self.bands=[];self.core_factories=[];self.occupied=[];self.assemblies=[];self.started=False
        self.awaiting_victory=False;self.finished=False;self.infinite=False
        self.observed_dead=set();self.destroyed=0;self.lost=0;self.destroyed_types={};self.icbms_intercepted=0

    def player_aircraft(self):return [a for a in self.combat.friendly_aircraft if a.alive]

    def composition(self,number):
        tiers=self.settings['tiers']
        if number<=len(tiers):return copy.deepcopy(tiers[number-1])
        previous=copy.deepcopy(self.bands[-1].composition)
        def grow(value):
            if isinstance(value,dict):return {k:grow(v) for k,v in value.items()}
            if isinstance(value,list):return [ceil_scaled(n,self.settings['infinite_growth_fraction']) for n in value]
            return value
        return grow(previous)

    def clear(self,point,aircraft=True,separation=None):
        distance=self.settings['unit_separation_nm'] if separation is None else separation
        if any(math.dist(point,p)<distance for p in self.occupied):return False
        return not aircraft or all(math.dist(point,(a.x,a.y))>=self.settings['aircraft_clearance_nm'] for a in self.player_aircraft())

    def random_point(self,band):
        radius=math.sqrt(self.rng.uniform(band.inner**2,band.outer**2));angle=self.rng.uniform(0,math.tau)
        return self.airfield.x+radius*math.sin(angle),self.airfield.y+radius*math.cos(angle)

    def base_point(self,band):
        candidates=[self.random_point(band) for _ in range(self.settings['placement_attempts'])]
        separated=[p for p in candidates if self.clear(p,False,self.settings['base_separation_nm'])]
        for p in separated:
            if self.clear(p,True,self.settings['base_separation_nm']):return p
        # Mandatory bases relax aircraft clearance only; unit overlap is never relaxed.
        if separated:
            return max(separated,key=lambda p:min((math.dist(p,(a.x,a.y)) for a in self.player_aircraft()),default=math.inf))
        # Deterministic search prevents random sampling failure from omitting runways.
        for shell in range(1,101):
            radius=band.inner+(band.outer-band.inner)*shell/101
            for n in range(720):
                angle=n*math.tau/720;p=(self.airfield.x+radius*math.sin(angle),self.airfield.y+radius*math.cos(angle))
                if self.clear(p,False,self.settings['base_separation_nm']):return p
        raise RuntimeError('Campaign zone has no room for bases; reduce base separation or composition counts.')

    def unit_point(self,center,band):
        for attempt in range(self.settings['placement_attempts']*20):
            angle=self.rng.uniform(0,math.tau);radius=self.rng.uniform(self.settings['unit_separation_nm'],self.settings['garrison_radius_nm'])
            point=(center[0]+radius*math.sin(angle),center[1]+radius*math.cos(angle))
            d=math.dist(point,(self.airfield.x,self.airfield.y))
            if band.inner<=d<=band.outer and self.clear(point,attempt<self.settings['placement_attempts']):return point
        # Expand placement within the band when the local garrison is crowded.
        for _ in range(self.settings['placement_attempts']*100):
            point=self.random_point(band)
            if self.clear(point,False):return point
        raise RuntimeError('Campaign zone has no room for units; reduce unit separation or composition counts.')

    def counts(self,pair):return self.rng.randint(*pair)

    def add_garrison(self,center,band,pool):
        for kind,pair in pool.items():
            for _ in range(self.counts(pair)):
                point=self.unit_point(center,band)
                self.ground_factory(kind,*point);self.occupied.append(point)

    def random_factory_count(self,number):
        count=self.settings['random_factories_start_count']
        for _ in range(number):count=ceil_scaled(count,self.settings['random_factories_growth_fraction'])
        return count

    def generate(self,now):
        number=len(self.bands)+1;inner=self.settings['safe_radius_nm']+(number-1)*self.settings['band_width_nm']
        band=Band(number,inner,inner+self.settings['band_width_nm'],self.composition(number));self.bands.append(band)
        for airfield_index in range(self.counts(band.composition['airfields'])):
            point=self.base_point(band);self.occupied.append(point)
            runway=EnemyRunway(max((u.id for u in self.combat.factories),default=0)+1,*point,
                 wave_counts=copy.deepcopy(band.composition['wave_aircraft']),next_wave=now+self.settings['first_wave_delay_seconds'],
                 interval=self.settings['wave_interval_seconds'],band_number=number,runway_health_capacity=airfield_health_for_band(number,self.settings))
            cycle,letter=divmod(number-1,len(PHONETIC))
            code=PHONETIC[letter]+(f' {cycle+1}' if cycle else '')
            runway.name=f'Airfield {code} {airfield_index+1}'
            self.combat.factories.append(runway);band.runways.append(runway)
            self.add_garrison(point,band,band.composition['airfield_ground'])
        for _ in range(self.counts(band.composition['outposts'])):
            point=self.base_point(band);self.occupied.append(point);band.outposts.append(point)
            self.add_garrison(point,band,band.composition['outpost_ground'])
        for _ in range(self.random_factory_count(number)):
            point=self.base_point(band);self.occupied.append(point)
            band.random_factories.append(self.ground_factory('Factory',*point))
        self.combat.events.append((now,f'Zone {number} opened: {inner:g}–{band.outer:g} NM · {len(band.runways)} runways',0,'status'))
        return band

    def start(self,now=0.):
        self.started=True
        self.occupied.append((self.airfield.x,self.airfield.y))
        core=Band(0,self.settings['core_factory_min_radius_nm'],self.settings['safe_radius_nm'],{})
        for _ in range(self.random_factory_count(0)):
            point=self.base_point(core);self.occupied.append(point)
            self.core_factories.append(self.ground_factory('Factory',*point))
        self.generate(now)

    def spawn_wave(self,runway,now):
        members=[]
        for kind,pair in runway.wave_counts.items():
            for _ in range(self.counts(pair)):
                spawn={'Fighter':self.combat.spawn_fighter,'Interceptor':self.combat.spawn_interceptor,'Bomber':self.combat.spawn_bomber,'Suicide Drone':self.combat.spawn_drone}[kind]
                a=spawn(runway.x,runway.y)
                a.x=runway.x;a.y=runway.y;a.speed=0.;a.heading=0.;a.state='queued'
                a.home_runway=runway;a.wave_assembling=True
                a.attack_target=None;a.attack_point=None;a.engage_target=None;a.auto_attack_target=None
                a.mode='loiter';a.orbit_center=(runway.x,runway.y);a.orbit_radius=a.full_speed_orbit_radius
                members.append(a)
        self.assemblies.append((runway,members))
        runway.wave_number+=1
        runway.next_wave=now+runway.interval
        runway.interval*=1+self.settings['wave_interval_growth_fraction']
        self.combat.events.append((now,f'{self.combat.unit_name(runway)} assembling wave {runway.wave_number} · {len(members)} aircraft',0,'enemy_wave'))
        return members

    def advance(self,now):
        if not self.started or self.finished or self.awaiting_victory:return
        for band in self.bands:
            for runway in band.runways:
                if runway.alive and now>=runway.next_wave-1e-9:self.spawn_wave(runway,now)
        pending=[]
        for runway,members in self.assemblies:
            alive=[a for a in members if a.alive]
            if not runway.alive:
                for a in alive:
                    if a.state in ('queued','parked') or (a.state=='takeoff' and not a.takeoff_airborne):
                        a.destroy() # Aircraft still dependent on the destroyed runway cannot depart.
                alive=[a for a in alive if a.alive]
                for a in alive:
                    if a.state=='takeoff' and a.takeoff_airborne:a.state='airborne'
            if alive and all(a.state=='airborne' for a in alive):
                for a in alive:
                    a.wave_assembling=False;a.direct_to((self.airfield.x,self.airfield.y))
            elif alive:pending.append((runway,members))
        self.assemblies=pending
        band=self.bands[-1]
        if all(not r.alive for r in band.runways):
            band.completed=True
            if band.number==len(self.settings['tiers']) and not self.infinite:self.awaiting_victory=True
            else:self.generate(now)

    def continue_run(self,now):
        self.infinite=True;self.awaiting_victory=False;self.generate(now)

    def observe(self,friendly,extra_enemy=()):
        enemy=[u for u in [*extra_enemy,*self.combat.enemies,*self.combat.factories,*self.combat.enemy_radars,*self.combat.enemy_sams,*self.combat.icbms] if getattr(u,'enemy',False)]
        for units,team in ((enemy,True),(friendly,False)):
            for unit in units:
                if not unit.alive and not getattr(unit,'campaign_counted_death',False) and not getattr(unit,'sold',False):
                    unit.campaign_counted_death=True
                    self.observed_dead.add(id(unit))
                    if team:
                        self.destroyed+=1
                        if isinstance(unit,ICBM):
                            if getattr(unit,'intercepted',False):self.icbms_intercepted+=1
                        else:
                            kind=('Fighter' if unit.kind=='Interceptor' else unit.kind) if isinstance(unit,Aircraft) else 'Airfield' if isinstance(unit,EnemyRunway) else unit.stats_key
                            self.destroyed_types[kind]=self.destroyed_types.get(kind,0)+1
                    else:self.lost+=1

    def results(self,now):
        seconds=int(now);hours,remaining=divmod(seconds,3600);minutes,seconds=divmod(remaining,60)
        counts=self.destroyed_types;aircraft=sum(counts.get(k,0) for k in ('Fighter','Bomber','Suicide Drone'))
        lines=[f'Time: {hours:02d}:{minutes:02d}:{seconds:02d}',f'Aircraft destroyed: {aircraft}',
               f'Fighters: {counts.get("Fighter",0)}',f'Bombers: {counts.get("Bomber",0)}',f'Suicide Drones: {counts.get("Suicide Drone",0)}',
               f'ICBMs intercepted: {self.icbms_intercepted}']
        for key,label in (('Factory','Factories destroyed'),('Bunker','Bunkers'),('Flak','Flak'),('Radar','Radars'),('LR Radar','LR Radars'),('SAM','SAM sites'),('LR SAM','LR SAM sites'),('SAAW','SAAW'),('CIWS','CIWS'),('Drone Launcher','Drone launchers'),('ICBM Silo','ICBM silos'),('Airfield','Airfields')):
            lines.append(f'{label}: {counts.get(key,0)}')
        lines.append(f'Friendly units lost: {self.lost}')
        lines.extend(f'{k.title()}: {v:,}' for k,v in self.combat.weapon_totals.items())
        return '\n'.join(lines)
