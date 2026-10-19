"""Game aircraft movement and servicing, in NM, knots, and simulated seconds."""
from collections import deque
from dataclasses import dataclass, field
import math
import random
import time

from .game_settings import STATS, aircraft_specs, crew_repair_seconds, crew_weapon_seconds, crew_count, loadout_label

AIRCRAFT_TYPES = aircraft_specs()
ENEMY_AIRCRAFT_TYPES = aircraft_specs(enemy=True)
AIRCRAFT_PRICE = AIRCRAFT_TYPES['Fighter']['price']

def ground_refuel_rate(level):
    s=STATS['ground_crew']
    return s['refuel_units_per_second_level1']*(1+s['refuel_increase_fraction_per_level'])**(level-1)


def hardpoint_weapon(value,hardpoint_counts=None):
    for kind in ('AIM-120','AIM-9','AGM-88','Sidearm'):
        if kind in value:return kind,(hardpoint_counts or {}).get(kind,STATS['missiles'][kind]['hardpoint_count'])
    return None,0


def bomb_bay_allowed(kind,value):
    if kind=='Bomber' or value=='Empty':return True
    return not any(str(weight) in value.replace(',','') for weight in (1000,2000))


@dataclass
class Aircraft:
    kind: str
    hardpoints: list = field(default_factory=list)
    bays: list = field(default_factory=list)
    color: str = '#438cff'
    enemy: bool = False
    health: float = None
    x: float = .5
    y: float = -.5
    heading: float = 0.                 # North = 0, clockwise positive.
    speed: float = 0.
    state: str = 'queued'
    takeoff_airborne: bool = False
    departure_distance: float = 0.
    mode: str = 'loiter'
    fenced_in: bool = True
    orbit_center: tuple = (0.,0.)
    orbit_radius: float = STATS['aircraft_behavior']['default_orbit_radius_nm']
    clockwise: bool = True
    path: list = field(default_factory=list)
    waypoint: int = 0
    rtb_stage: int = 0
    service_remaining: float = 0.
    service_total: float = 0.
    service_work_total: float = 0.
    service_work_remaining: float = 0.
    service_fuel_total: float = 0.
    service_refuel_rate: float = STATS['ground_crew']['refuel_units_per_second_level1']
    crew_active: bool = False
    depart_after_service: bool = False
    redeploy_after_service: bool = False
    redeploy_on_rtb: bool = False
    rtb_resume: object = field(default=None,repr=False,compare=False)
    fuel: float = -1.
    cms: int = -1
    armed_hardpoints: list = field(default_factory=list)
    armed_bays: list = field(default_factory=list)
    history: deque = field(default_factory=deque)
    last_sample: float = -1.
    leader: object = field(default=None,repr=False,compare=False)
    purchase_price: float = None
    parking_slot: int = 0
    formation_slot: int = 0
    followers: list = field(default_factory=list,repr=False,compare=False)
    speed_setting: str = 'Mil'
    target_types: set = None
    engagement_range: int = STATS['aircraft_behavior']['default_engagement_range_nm']
    air_weapons_per_target: int = STATS['aircraft_behavior']['default_air_weapons_per_target']
    ground_weapons_per_target: int = STATS['aircraft_behavior']['default_ground_weapons_per_target']
    bomb_inventory: list = field(default_factory=list)
    missile_inventory: dict = field(default_factory=dict)
    disabled_weapons: set = field(default_factory=set)
    combat_used_weapons: bool = False
    combat_home: bool = False
    bomb_run_target: object = field(default=None,repr=False,compare=False)
    bomb_run_phase: str = 'attack'
    bomb_run_heading: object = None
    combat_heading: object = None
    crank_side: int = 1
    manual_attack_pending: bool = False
    attack_target: object = field(default=None,repr=False,compare=False)
    auto_attack_target: object = field(default=None,repr=False,compare=False)
    attack_point: object = None
    combat_turn_intensity: float = 0.
    command_turn_intensity: float = 0.
    engage_target: object = field(default=None,repr=False,compare=False)
    turn_rate: float = 0.
    refueling_from: object = field(default=None,repr=False,compare=False)
    fuel_rendezvous: bool = False
    fuel_resume: object = field(default=None,repr=False,compare=False)
    pending_auto: object = field(default=None,repr=False,compare=False)
    ignored_auto: set = field(default_factory=set,repr=False,compare=False)
    defensive_missile: object = field(default=None,repr=False,compare=False)
    defensive_side: int = 0
    defensive_speed: object = None
    defensive_heading: object = None


    def __post_init__(self):
        if self.kind=='Suicide Drone' and not self.enemy:raise ValueError('Suicide Drone is an enemy-only aircraft')
        if self.target_types is None:
            self.target_types={'Fighters','Suicide Drones','Bombers','Radars','Ground'}
            if self.kind in ('Fighter','Interceptor','Bomber'):self.target_types.add('ICBMs')
        if self.health is None:self.health=self.max_health
        if self.purchase_price is None:self.purchase_price=0 if self.enemy else self.spec['price']
        self.hardpoints=([loadout_label(v,self.spec.get('hardpoint_loadout_counts')) for v in self.hardpoints]+['Empty']*self.spec['hardpoints'])[:self.spec['hardpoints']]
        self.bays=([loadout_label(v) for v in self.bays]+['Empty']*self.spec['bays'])[:self.spec['bays']]
        self.bays=[value if bomb_bay_allowed(self.kind,value) else 'Empty' for value in self.bays]
        if self.kind=='Bomber':self.hardpoints=['2× AIM-9' if 'AIM-120' in value else value for value in self.hardpoints]
        self.x,self.y=parking_position(self.parking_slot)
        self.refill()

    @property
    def alive(self):return self.health>0 and self.state!='destroyed'

    @property
    def category(self):return 'Suicide Drones' if self.kind=='Suicide Drone' else 'Bombers' if self.kind=='Bomber' else 'Fighters'

    @property
    def cms_capacity(self):return self.spec['cms']

    @property
    def missiles_available(self):return sum(self.missile_inventory.values())

    @property
    def air_missiles_available(self):return sum(self.missile_inventory.get(kind,0) for kind in ('AIM-120','AIM-9'))

    def destroy(self):
        if getattr(self,'death_wall_time',None) is None:self.death_wall_time=time.monotonic()
        self.health=0.;self.state='destroyed';self.speed=0.
        self.detach();self.engage_target=None;self.combat_heading=None;self.combat_home=False
        for follower in list(self.followers):follower.loiter((self.x,self.y))
        self.refueling_from=None

    @property
    def spec(self):
        return ENEMY_AIRCRAFT_TYPES[self.kind] if self.enemy else AIRCRAFT_TYPES[self.kind]

    @property
    def max_health(self):return self.spec['health']

    @property
    def visual_range_nm(self):return self.spec['visual_range_nm']

    @property
    def can_refuel(self):return self.spec['can_refuel']

    @property
    def ammo_full(self):
        missiles,bombs=self.configured_weapons();actual={}
        for weight,count in self.bomb_inventory:actual[weight]=actual.get(weight,0)+count
        return self.missile_inventory==missiles and actual==bombs

    @property
    def sensors_active(self):
        return self.state in ('airborne','rtb','approach')

    @property
    def radar_range_nm(self):
        return self.spec['radar_range_nm']

    @property
    def radar_angle_deg(self):
        return self.spec['radar_angle_degrees']

    def radar_detects(self,x,y):
        if not self.sensors_active or not self.radar_range_nm:return False
        dx,dy=x-self.x,y-self.y
        if math.hypot(dx,dy)>self.radar_range_nm:return False
        angle=(math.atan2(dx,dy)-self.heading+math.pi)%math.tau-math.pi
        return self.radar_angle_deg==360 or abs(angle)<=math.radians(self.radar_angle_deg/2)+1e-12

    def visual_detects(self,x,y):
        return self.sensors_active and math.hypot(x-self.x,y-self.y)<=self.visual_range_nm

    @property
    def has_afterburner(self):return self.spec['afterburner']

    @property
    def effective_speed_setting(self):
        return 'Mil' if self.speed_setting=='AB' and not self.has_afterburner else self.speed_setting

    def set_speed(self,setting):
        if setting not in ('Eco','Mil','AB') or (setting=='AB' and not self.has_afterburner):return False
        self.speed_setting=setting;return True

    @property
    def cruise_speed(self):
        return self.spec['speed']*STATS['speed_modes'][self.effective_speed_setting]['speed_multiplier']

    @property
    def max_ab_speed(self):
        return self.spec['speed']*STATS['speed_modes']['AB' if self.has_afterburner else 'Mil']['speed_multiplier']

    @property
    def fuel_burn(self):
        return self.fuel_burn_at_speed(self.cruise_speed)

    def fuel_burn_at_speed(self,speed):
        base=self.spec['burn']
        if not base:return 0.
        speed=max(0.,speed)
        mil=self.spec['speed']*STATS['speed_modes']['Mil']['speed_multiplier']
        eco=self.spec['speed']*STATS['speed_modes']['Eco']['speed_multiplier']
        eco_burn=STATS['speed_modes']['Eco']['burn_multiplier']
        mil_burn=STATS['speed_modes']['Mil']['burn_multiplier']
        if speed<=eco:return base*eco_burn*speed/max(1.,eco)
        if speed<=mil:return base*(eco_burn+(mil_burn-eco_burn)*(speed-eco)/max(1.,mil-eco))
        if self.max_ab_speed<=mil:return base*mil_burn
        fraction=min(1.,(speed-mil)/(self.max_ab_speed-mil))
        return base*(mil_burn+(STATS['speed_modes']['AB']['burn_multiplier']-mil_burn)*fraction**STATS['aircraft_behavior']['fuel_ab_ramp_exponent'])

    @property
    def actual_fuel_burn(self):
        if self.state in ('queued','parked','rollout','servicing'):return 0.
        on_tanker=(self.state=='airborne' and self.can_refuel and self.fuel_rendezvous
                   and self.mode=='formation' and self.leader is not None
                   and self.leader.kind=='KC-49' and self.leader.state=='airborne'
                   and self.leader.fuel>rtb_reserve(self.leader)
                   and math.dist((self.x,self.y),(self.leader.x,self.leader.y))<=REFUEL_RADIUS_NM)
        return 0. if on_tanker else self.fuel_burn_at_speed(self.speed)

    def weapon_enabled(self,kind):return kind not in self.disabled_weapons

    @property
    def usable_air_missiles(self):return sum(self.missile_inventory.get(kind,0) for kind in ('AIM-120','AIM-9') if self.weapon_enabled(kind))

    @property
    def usable_bombs(self):return sum(count for weight,count in self.bomb_inventory if self.weapon_enabled(weight))

    @property
    def bombs_available(self):return sum(count for weight,count in self.bomb_inventory)

    def take_bomb(self,target_health=None):
        available=[rack for rack in self.bomb_inventory if rack[1]>0 and self.weapon_enabled(rack[0])]
        if not available:return None
        capable=[rack for rack in available if target_health is not None and round(STATS['bombs'][str(rack[0])]['damage']*(1+STATS['bombs'][str(rack[0])]['damage_spread_fraction']))>=target_health]
        rack=min(capable,key=lambda r:r[0]) if capable else max(available,key=lambda r:r[0])
        rack[1]-=1
        return rack[0]

    def detach(self):
        if self.leader is not None:
            self.leader.followers[:]=[a for a in self.leader.followers if a is not self]
        self.leader=None

    def request_auto(self,action,reason,target=None):
        if self.enemy or reason in self.ignored_auto or self.mode=='rtb':return False
        if self.pending_auto and self.pending_auto['reason']=='fuel' and reason=='ammo':return False
        self.pending_auto={'action':action,'reason':reason,'target':target}
        return True

    def refill(self):
        self.pending_auto=None;self.ignored_auto.clear()
        self.fuel=self.spec['fuel']
        self.combat_used_weapons=False
        self.cms=self.cms_capacity
        self.armed_hardpoints=list(self.hardpoints)
        self.armed_bays=list(self.bays)
        self.missile_inventory,bombs=self.configured_weapons()
        self.bomb_inventory=[[weight,count] for weight,count in bombs.items()]

    def configured_weapons(self):
        missiles={'AIM-120':0,'AIM-9':0,'AGM-88':0,'Sidearm':0};bombs={}
        for value in self.hardpoints:
            kind,count=hardpoint_weapon(value,self.spec.get('hardpoint_loadout_counts'))
            if kind is not None:missiles[kind]+=count
        for value in self.bays:
            if not bomb_bay_allowed(self.kind,value):continue
            for weight,count in ((int(w),s['bay_count']) for w,s in STATS['bombs'].items()):
                if str(weight) in value.replace(',',''):
                    bombs[weight]=bombs.get(weight,0)+count;break
        return missiles,bombs

    @property
    def missing_weapons(self):
        missiles,bombs=self.configured_weapons();actual={}
        for weight,count in self.bomb_inventory:actual[weight]=actual.get(weight,0)+count
        return sum(max(0,n-self.missile_inventory.get(k,0)) for k,n in missiles.items())+sum(max(0,n-actual.get(k,0)) for k,n in bombs.items())

    @property
    def in_hangar(self):return self.alive and self.state in ('parked','servicing')

    @property
    def needs_service(self):return self.health<self.max_health or self.missing_weapons>0 or self.fuel<self.spec['fuel']-1e-9

    @property
    def service_progress(self):
        return max(0.,min(1.,1-self.service_remaining/self.service_total)) if self.service_total else 1.

    def begin_service(self,level=1):
        repair_seconds=crew_repair_seconds(level)
        weapon_seconds=crew_weapon_seconds(level)
        self.service_work_total=max(0,self.max_health-self.health)*repair_seconds+self.missing_weapons*weapon_seconds
        self.service_work_remaining=self.service_work_total
        self.service_refuel_rate=ground_refuel_rate(level)
        self.service_fuel_total=max(0,self.spec['fuel']-self.fuel)/self.service_refuel_rate
        self.service_total=max(self.service_work_total,self.service_fuel_total)
        self.service_remaining=self.service_total;self.crew_active=False
        self.depart_after_service=False
        self.state='servicing' if self.service_total>1e-9 else 'parked'
        if self.state=='parked':self.finish_service()

    def finish_service(self):
        self.health=self.max_health;self.refill();self.state='parked'
        self.service_remaining=0.;self.crew_active=False
        if self.redeploy_after_service and self.alive and not self.enemy:
            self.redeploy_after_service=False
            self.manual_attack_pending=False;self.attack_target=None;self.attack_point=None;self.auto_attack_target=None
            self.engage_target=None;self.combat_heading=None;self.combat_home=False
            self.bomb_run_target=None;self.bomb_run_heading=None
            saved=self.rtb_resume;self.rtb_resume=None
            if saved is None:
                self.set_speed('Mil')
                self.loiter((0.,0.),radius=STATS['aircraft_behavior']['default_orbit_radius_nm'])
            else:
                order,speed=saved
                self.mode,self.orbit_center,self.orbit_radius,self.clockwise,path,self.waypoint,leader,self.fenced_in=order
                self.path=list(path);self.set_speed(speed)
                if self.mode=='formation' and leader is not None and leader.alive and leader.mode!='rtb':
                    self.form_up(leader)
                else:
                    if self.mode=='formation':self.mode='loiter'
                    self.depart()
                self.fenced_in=order[-1]
        else:self.rtb_resume=None

    def retime_service(self,level):
        remaining_fraction=self.service_work_remaining/self.service_work_total if self.service_work_total else 0.
        self.service_work_total=max(0,self.max_health-self.health)*crew_repair_seconds(level)+self.missing_weapons*crew_weapon_seconds(level)
        self.service_work_remaining=self.service_work_total*remaining_fraction
        self.service_fuel_total*=self.service_refuel_rate/ground_refuel_rate(level)
        self.service_refuel_rate=ground_refuel_rate(level)
        self.service_total=max(self.service_work_total,self.service_fuel_total)
        self.service_remaining=max(self.service_work_remaining,max(0,self.spec['fuel']-self.fuel)/self.service_refuel_rate)

    def change_loadout(self,group,index,value,level=1):
        if group=='bays' and not bomb_bay_allowed(self.kind,value):return False
        stations=getattr(self,group)
        if not self.in_hangar or stations[index]==value:return False
        if self.kind=='Bomber' and group=='hardpoints' and 'AIM-120' in value:return False
        old=stations[index]
        if group=='hardpoints':
            kind,count=hardpoint_weapon(old,self.spec.get('hardpoint_loadout_counts'))
            if kind is not None:self.missile_inventory[kind]=max(0,self.missile_inventory.get(kind,0)-count)
        else:
            for weight,count in ((int(w),s['bay_count']) for w,s in STATS['bombs'].items()):
                if str(weight) in old.replace(',',''):
                    remaining=count
                    for rack in self.bomb_inventory:
                        if rack[0]==weight:
                            removed=min(rack[1],remaining);rack[1]-=removed;remaining-=removed
                    break
        stations[index]=value
        self.begin_service(level)
        return True

    def countermeasure(self,rng=None):
        """Resolve one incoming missile's decoy check; consume one CM charge."""
        if self.cms<=0:return False
        self.cms-=1
        return (rng or random).random()<STATS['countermeasures']['success_probability']

    def set_redeploy_on_rtb(self,enabled):
        self.redeploy_on_rtb=bool(enabled)
        if self.mode=='rtb' and self.state in ('rtb','approach','rollout','servicing'):
            self.redeploy_after_service=self.redeploy_on_rtb

    def rtb(self,redeploy=None):
        if redeploy is None:redeploy=self.redeploy_on_rtb
        self.manual_attack_pending=False
        if self.mode!='rtb':
            order=self.fuel_resume if self.fuel_rendezvous and self.fuel_resume is not None else (
                self.mode,tuple(self.orbit_center),self.orbit_radius,self.clockwise,list(self.path),self.waypoint,self.leader,self.fenced_in)
            self.rtb_resume=(order,self.speed_setting)
        self.redeploy_after_service=bool(redeploy)
        self.pending_auto=None
        for follower in list(self.followers):follower.loiter((0.,0.))
        self.fuel_rendezvous=False;self.fuel_resume=None
        self.mode='rtb';self.fenced_in=False;self.depart_after_service=False
        self.detach();self.refueling_from=None
        self.rtb_stage=0
        if self.state in ('queued','parked'):
            self.state='parked'
            if self.needs_service:self.begin_service()
        elif self.state=='airborne':self.state='rtb'

    def cancel_departure(self):
        if self.state!='queued':return False
        self.state='parked';self.depart_after_service=False;self.redeploy_after_service=False
        self.pending_auto=None;self.detach();return True

    def cancel_rtb(self):
        if self.mode!='rtb' or self.state not in ('airborne','rtb','approach'):return False
        self.pending_auto=None;self.fuel_rendezvous=False;self.fuel_resume=None
        self.redeploy_after_service=False;self.rtb_resume=None
        self.manual_attack_pending=False;self.attack_target=None;self.attack_point=None;self.engage_target=None
        self.auto_attack_target=None;self.combat_heading=None;self.combat_home=False
        self.bomb_run_target=None;self.bomb_run_heading=None;self.rtb_stage=0
        self.loiter((self.x,self.y),radius=7.)
        return True

    def loiter(self,center,radius=10.,clockwise=True):
        self.detach()
        self.mode='loiter';self.orbit_center=tuple(center)
        self.orbit_radius=max(.5,float(radius));self.clockwise=bool(clockwise)
        self.depart()

    @property
    def full_speed_orbit_radius(self):
        speed=self.max_ab_speed*.514444
        bank=math.radians(STATS['aircraft_behavior']['normal_bank_degrees'])
        rate=math.radians(STATS['aircraft_behavior']['normal_turn_limit_degrees_per_second'])
        # Match both steering limits and the existing orbit speed cap, with margin.
        return max(.5,speed*speed/(9.81*max(.001,math.tan(bank))*1852)/.95**2,
                   speed/max(.001,rate)/1852/.95**2,speed*speed/(9.81*1852)/.95**2)

    def direct_to(self,point):
        self.detach()
        self.manual_attack_pending=False;self.attack_target=None;self.attack_point=None;self.auto_attack_target=None
        self.engage_target=None;self.combat_heading=None;self.combat_home=False
        self.bomb_run_target=None;self.bomb_run_heading=None
        self.mode='direct';self.orbit_center=tuple(point)
        self.orbit_radius=self.full_speed_orbit_radius
        self.depart()

    def patrol(self,points):
        if not 3<=len(points)<=20:return False
        if any(math.dist(points[i],points[(i+1)%len(points)])<.05 for i in range(len(points))):return False
        self.detach()
        self.mode='patrol';self.path=[tuple(p) for p in points];self.waypoint=0
        self.depart();return True

    def form_up(self,leader):
        if leader is self or not isinstance(leader,Aircraft) or leader.enemy!=self.enemy or not leader.alive:return False
        node=leader;seen=set()
        while node is not None:
            if node is self or id(node) in seen:return False
            seen.add(id(node));node=node.leader
        if self.leader is not leader:
            self.detach()
            used={a.formation_slot for a in leader.followers}
            slot=0
            while slot in used:slot+=1
            self.formation_slot=slot;leader.followers.append(self)
        self.leader=leader;self.mode='formation';self.depart()
        return True

    def depart(self):
        if self.state=='servicing' or (self.state in ('parked','queued') and self.needs_service):return False
        if self.state in ('parked','queued','servicing'):
            self.fenced_in=True
        self.depart_after_service=True
        if self.state=='parked':self.state='queued'
        elif self.state in ('rtb','approach'):
            self.state='airborne';self.redeploy_after_service=False;self.rtb_resume=None


REFUEL_RADIUS_NM = STATS['tanker']['refuel_radius_nm']


def parking_position(slot):
    return 1.15+.35*(slot%2),-.7+.35*(slot//2)


def formation_position(leader,slot):
    rank=slot//2+1
    side=-1 if slot%2==0 else 1
    back=.12*rank;lateral=.12*rank*side
    return (leader.x-back*math.sin(leader.heading)+lateral*math.cos(leader.heading),
            leader.y-back*math.cos(leader.heading)-lateral*math.sin(leader.heading))


def rtb_reserve(a):
    return a.fuel_burn*(math.hypot(a.x,a.y)/max(STATS['aircraft_behavior']['final_speed_knots'],a.cruise_speed)*3600+STATS['aircraft_behavior']['rtb_reserve_extra_seconds'])


def rtb_alert_fuel(a):
    travel_seconds=math.hypot(a.x,a.y)/max(STATS['aircraft_behavior']['final_speed_knots'],a.cruise_speed)*3600
    return a.fuel_burn*(travel_seconds*STATS['aircraft_behavior']['rtb_alert_fuel_multiplier']+STATS['aircraft_behavior']['rtb_alert_extra_seconds'])


def angle_error(target,current):
    return (target-current+math.pi)%math.tau-math.pi

def intercept_point(origin,target,target_velocity,speed,max_lead=300.):
    """Constant-velocity intercept in NM and knots; bound unreachable predictions."""
    dx,dy=target[0]-origin[0],target[1]-origin[1]
    vx,vy=target_velocity[0]/3600,target_velocity[1]/3600
    pursuer=max(1.,speed)/3600
    aa=vx*vx+vy*vy-pursuer*pursuer
    bb=2*(dx*vx+dy*vy);cc=dx*dx+dy*dy
    if cc<1e-12:return target
    roots=[]
    if abs(aa)<1e-12:
        if abs(bb)>1e-12:roots=[-cc/bb]
    else:
        disc=bb*bb-4*aa*cc
        if disc>=0:
            roots=[(-bb-math.sqrt(disc))/(2*aa),(-bb+math.sqrt(disc))/(2*aa)]
    future=[t for t in roots if t>=0 and math.isfinite(t)]
    # No attainable intercept: use a short lead and keep updating rather than
    # steering toward a distant or negative-time solution.
    lead=min(max_lead,min(future)) if future else min(30.,math.sqrt(cc)/pursuer)
    return target[0]+vx*lead,target[1]+vy*lead

class AirOperations:
    def __init__(self):
        self.time=0.
        self.combat=None
        self.ground_crew_level=1

    def advance(self,aircraft,seconds):
        aircraft=list(aircraft)
        if self.combat is not None:
            aircraft.extend(a for a in self.combat.enemies if not any(a is owned for owned in aircraft))
        self.current_aircraft=aircraft
        # Small integration steps keep turns and runway transitions stable at every playback speed.
        remaining=max(0,float(seconds))
        while remaining>1e-9:
            campaign=self.combat.campaign if self.combat is not None else None
            if campaign is not None and (campaign.finished or campaign.awaiting_victory or not campaign.airfield.alive):break
            dt=min(.1,remaining);remaining-=dt;self.time+=dt
            if self.combat is not None:
                self.combat.prepare(aircraft,self.time)
                if campaign is not None and campaign.awaiting_victory:break
            runway_busy=any(not a.enemy and a.state in ('takeoff','approach','rollout') for a in aircraft)
            enemy_busy={id(a.home_runway) for a in aircraft if getattr(a,'home_runway',None) is not None and a.alive and a.state=='takeoff'}
            for a in aircraft:
                a.refueling_from=None
                home=getattr(a,'home_runway',None)
                available=not runway_busy if home is None else home.alive and id(home) not in enemy_busy
                if a.state=='queued' and available:
                    a.x=home.x if home is not None else 0.;a.y=(home.y if home is not None else 0.)-.65;a.heading=0.;a.speed=0.
                    if a.needs_service:
                        a.begin_service(self.ground_crew_level)
                    else:
                        a.state='takeoff';a.takeoff_airborne=False;a.departure_distance=0.
                        if home is None:runway_busy=True
                        else:enemy_busy.add(id(home))
                self.step(a,dt,not runway_busy or a.state=='approach')
                if home is None and a.state in ('takeoff','approach','rollout'):runway_busy=True
                if self.time-a.last_sample>=.2-1e-9:
                    if a.speed>=1:a.history.append((self.time,a.x,a.y,a.speed))
                    a.last_sample=self.time
                while a.history and a.history[0][0]<self.time-60.2:a.history.popleft()
            self.service_aircraft(aircraft,dt)
            self.refuel_aircraft(aircraft,dt)
            if self.combat is not None:
                self.combat.advance(self.time)
                campaign=self.combat.campaign
                if campaign is not None:
                    campaign.observe([*self.combat.ground_targets,*[a for a in aircraft if not a.enemy]])
                    if not campaign.airfield.alive or campaign.awaiting_victory:break

    def service_aircraft(self,aircraft,dt):
        waiting=[a for a in aircraft if a.alive and not a.enemy and a.state=='servicing']
        # Preserve active assignments; waiting aircraft only take free crews.
        active=[a for a in waiting if a.crew_active]
        active.extend(a for a in waiting if not a.crew_active)
        working=active[:crew_count(self.ground_crew_level)]
        for a in waiting:
            a.crew_active=any(a is w for w in working)
            if not a.crew_active:continue
            a.service_refuel_rate=ground_refuel_rate(self.ground_crew_level)
            a.fuel=min(a.spec['fuel'],a.fuel+a.service_refuel_rate*dt)
            a.service_work_remaining=max(0.,a.service_work_remaining-dt)
            a.service_remaining=max(a.service_work_remaining,max(0.,a.spec['fuel']-a.fuel)/a.service_refuel_rate)
            if a.service_remaining<=1e-9:
                a.finish_service()

    def refuel_aircraft(self,aircraft,dt):
        tankers=[a for a in aircraft if a.kind=='KC-49' and a.alive and a.state=='airborne' and a.mode!='rtb']
        for a in aircraft:
            if not a.alive or not a.can_refuel or a.state!='airborne':continue
            eligible=[t for t in tankers if t.enemy==a.enemy and t.alive and t.fuel>rtb_reserve(t) and math.dist((a.x,a.y),(t.x,t.y))<=REFUEL_RADIUS_NM]
            if not eligible:continue
            tanker=min(eligible,key=lambda t:math.dist((a.x,a.y),(t.x,t.y)))
            reserve=rtb_reserve(tanker)
            amount=min(STATS['tanker']['transfer_units_per_second']*dt,a.spec['fuel']-a.fuel,max(0,tanker.fuel-reserve))
            if amount>1e-8:
                a.fuel+=amount;tanker.fuel-=amount;a.refueling_from=tanker
            if a.fuel_rendezvous and a.fuel>=a.spec['fuel']-1e-8:
                saved=a.fuel_resume;a.detach();a.fuel_rendezvous=False;a.fuel_resume=None
                if saved is not None:
                    a.mode,a.orbit_center,a.orbit_radius,a.clockwise,a.path,a.waypoint,leader,a.fenced_in=saved
                    if a.mode=='formation' and leader is not None and leader.alive:a.form_up(leader)
                    elif a.mode=='formation':a.mode='loiter'

    def refuel_candidate(self,a):
        base_distance=math.hypot(a.x,a.y)
        candidates=[]
        if a.can_refuel:
            for t in getattr(self,'current_aircraft',()):
                distance=math.hypot(t.x-a.x,t.y-a.y)
                tanker_speed=min(t.speed,a.cruise_speed*.7)
                rendezvous_speed=a.cruise_speed
                rendezvous_burn=a.fuel_burn
                if (t.kind=='KC-49' and not t.enemy and t.alive and t.state=='airborne' and t.mode!='rtb'
                    and distance<base_distance
                    and t.fuel>rtb_reserve(t)+(a.spec['fuel']-a.fuel)
                    and a.fuel>distance/max(1.,rendezvous_speed-tanker_speed)*3600*rendezvous_burn):
                    candidates.append((distance,t))
        return min(candidates,key=lambda item:item[0])[1] if candidates else None

    def propose_fuel(self,a):
        tanker=self.refuel_candidate(a)
        a.request_auto('fuel' if tanker is not None else 'rtb','fuel',tanker)

    def seek_fuel(self,a):
        if a.fuel_rendezvous:
            leader=a.leader
            if leader is not None and leader.alive and leader.state=='airborne' and leader.mode!='rtb' and leader.fuel>rtb_reserve(leader):return
            a.fuel_rendezvous=False
            a.request_auto('rtb','fuel');return
        tanker=self.refuel_candidate(a)
        if tanker is None:a.request_auto('rtb','fuel');return
        a.fuel_resume=(a.mode,a.orbit_center,a.orbit_radius,a.clockwise,list(a.path),a.waypoint,a.leader,a.fenced_in)
        a.manual_attack_pending=False;a.attack_target=None;a.attack_point=None;a.engage_target=None;a.auto_attack_target=None;a.combat_heading=None
        a.fenced_in=False;a.form_up(tanker);a.fuel_rendezvous=True

    def formation_guidance(self,a,dt):
        leader=a.leader
        if leader is None:return a.cruise_speed
        if leader.mode=='rtb' or leader.state in ('rtb','approach','rollout','servicing','parked'):
            a.loiter((0.,0.));return a.cruise_speed
        if leader.state not in ('airborne','rtb'):
            return None
        tx,ty=formation_position(leader,a.formation_slot)
        dx,dy=tx-a.x,ty-a.y;distance=math.hypot(dx,dy)
        rank=a.formation_slot//2+1;side=-1 if a.formation_slot%2==0 else 1
        back=.12*rank;lateral=.12*rank*side
        # The slot itself has a slightly different velocity during leader turns.
        vx=leader.speed*math.sin(leader.heading)+leader.turn_rate*3600*(-back*math.cos(leader.heading)-lateral*math.sin(leader.heading))
        vy=leader.speed*math.cos(leader.heading)+leader.turn_rate*3600*(back*math.sin(leader.heading)-lateral*math.cos(leader.heading))
        slot_speed=max(80.,math.hypot(vx,vy))
        along=dx*math.sin(leader.heading)+dy*math.cos(leader.heading)
        lateral_error=dx*math.cos(leader.heading)-dy*math.sin(leader.heading)
        catch_up=min(a.cruise_speed,max(80.,leader.speed*1.1))
        # Capture from behind, with room for the aircraft's actual turn radius.
        # A direct intercept of the slot can arrive broadside at full catch-up speed.
        turn_radius=(max(80.,a.speed)*.514444)**2/(9.81*1852)
        capture=max(2.,turn_radius*2)
        blend=max(0.,min(1.,(distance-capture)/(capture*2)))
        blend=blend*blend*(3-2*blend)
        aim=intercept_point((a.x,a.y),
                            (tx-math.sin(leader.heading)*capture,
                             ty-math.cos(leader.heading)*capture),
                            (leader.speed*math.sin(leader.heading),leader.speed*math.cos(leader.heading)),
                            max(a.speed,catch_up))
        far_heading=math.atan2(aim[0]-a.x,aim[1]-a.y)
        # Near the leader, follow the moving slot's velocity rather than its
        # position. Small, bounded closure commands let the speed settle early.
        slot_heading=math.atan2(vx,vy)
        correction=max(-math.radians(25),min(math.radians(25),
                       math.atan2(lateral_error*80,slot_speed)))
        near_heading=slot_heading+correction
        heading=near_heading+angle_error(far_heading,near_heading)*blend
        matched=max(slot_speed*.65,min(catch_up,slot_speed+along*60))
        desired_speed=matched*(1-blend)+catch_up*blend
        alignment=abs(angle_error(heading,a.heading))
        if alignment>math.radians(30):desired_speed=min(desired_speed,slot_speed)
        desired_speed=min(a.cruise_speed,desired_speed)
        self.steer(a,math.sin(heading),math.cos(heading),dt)
        return desired_speed

    def steer(self,a,dx,dy,dt,combat=False):
        desired=math.atan2(dx,dy)
        # Limit heading rate using a 45-degree bank approximation, rather than
        # allowing instant turns. Slow-flight rate is capped at 12 degrees/sec.
        rate=min(math.radians(STATS['aircraft_behavior']['normal_turn_limit_degrees_per_second']),9.81*math.tan(math.radians(STATS['aircraft_behavior']['normal_bank_degrees']))/max(35,a.speed*.514444))
        error=angle_error(desired,a.heading)
        if combat and a.kind in ('Fighter','Interceptor'):
            rate=min(math.radians(STATS['aircraft_behavior']['combat_turn_limit_degrees_per_second']),9.81*math.tan(math.radians(STATS['aircraft_behavior']['combat_bank_degrees']))/max(35,a.speed*.514444))
            a.combat_turn_intensity=min(1.,max(0.,(abs(error)-math.radians(5))/math.radians(85)))
        if a.speed>=a.spec['speed_knots']*STATS['speed_modes']['Mil']['speed_multiplier']:rate*=STATS['aircraft_behavior']['fast_turn_multiplier']
        if not combat and a.state=='airborne' and a.mode in ('direct','patrol','loiter','formation','rtb'):
            if abs(error)>math.radians(STATS['aircraft_behavior']['command_turn_angle_degrees']):
                a.command_turn_intensity=max(a.command_turn_intensity,min(1.,abs(error)/math.radians(90)))
        change=max(-rate*dt,min(rate*dt,error))
        a.turn_rate=change/dt
        a.heading=(a.heading+change)%math.tau

    def toward(self,a,point,dt,combat=False):
        self.steer(a,point[0]-a.x,point[1]-a.y,dt,combat=combat)

    def patrol_guidance(self,a,dt):
        # Fly past waypoints with room to bank into the next leg.
        # Acceptance grows with speed/turn radius and stays bounded by leg length.
        count=len(a.path);a.waypoint%=count
        for _ in range(count):
            previous=a.path[(a.waypoint-1)%count];point=a.path[a.waypoint]
            following=a.path[(a.waypoint+1)%count]
            ix,iy=point[0]-previous[0],point[1]-previous[1]
            ox,oy=following[0]-point[0],following[1]-point[1]
            incoming=max(.001,math.hypot(ix,iy));outgoing=max(.001,math.hypot(ox,oy))
            angle=abs(angle_error(math.atan2(ox,oy),math.atan2(ix,iy)))
            rate=min(math.radians(STATS['aircraft_behavior']['normal_turn_limit_degrees_per_second']),
                     9.81*math.tan(math.radians(STATS['aircraft_behavior']['normal_bank_degrees']))/max(35,a.speed*.514444))
            if a.speed>=a.spec['speed_knots']*STATS['speed_modes']['Mil']['speed_multiplier']:
                rate*=STATS['aircraft_behavior']['fast_turn_multiplier']
            radius=a.speed/3600/max(.001,rate)
            lead=radius*math.tan(min(angle,math.radians(135))/2)+a.speed/3600*4
            acceptance=max(.05,min(min(incoming,outgoing)*.45,max(.35,lead)))
            dx,dy=a.x-point[0],a.y-point[1]
            passed=(dx*ix+dy*iy)/incoming>=0 and abs(dx*iy-dy*ix)/incoming<=acceptance*2
            if math.hypot(dx,dy)>acceptance and not passed:break
            a.waypoint=(a.waypoint+1)%count
        self.toward(a,a.path[a.waypoint],dt)

    def defensive_guidance(self,a):
        threats=[] if a.kind=='Suicide Drone' or self.combat is None or a.state not in ('airborne','rtb','approach') else [
            m for m in self.combat.missiles if m.alive and m.target is a
            and m.owner.enemy!=a.enemy and not m.terminal and m.decoy is None
            and math.hypot(m.x-a.x,m.y-a.y)<=STATS['aircraft_behavior']['defensive_range_nm']]
        if not threats:
            a.defensive_missile=None;a.defensive_side=0;a.defensive_speed=None;a.defensive_heading=None;return False
        if not any(m is a.defensive_missile for m in threats):
            a.defensive_missile=min(threats,key=lambda m:math.hypot(m.x-a.x,m.y-a.y))
            a.defensive_side=self.combat.rng.choice((-1,1))
            a.defensive_heading=(a.heading+a.defensive_side*math.radians(STATS['aircraft_behavior']['defensive_turn_angle_degrees']))%math.tau
            a.defensive_speed=(a.max_ab_speed*self.combat.rng.uniform(
                STATS['aircraft_behavior']['defensive_speed_min_fraction'],
                STATS['aircraft_behavior']['defensive_speed_max_fraction'])
                if a.kind in ('Fighter','Interceptor','Bomber') else None)
        return True

    def check_fuel_exhaustion(self,a):
        if (a.enemy or not a.alive or a.fuel>0
                or a.state not in ('takeoff','airborne','rtb','approach')):
            return False
        a.fuel=0.
        a.destroy()
        if self.combat is not None:
            self.combat.events.append((self.time,f'{self.combat.unit_name(a)} lost: out of fuel',0,'damage'))
        return True

    def step(self,a,dt,allow_landing=True):
        if not a.alive or a.state in ('queued','parked'):return
        if self.check_fuel_exhaustion(a):return
        if a.state=='servicing':
            if a.enemy:
                a.service_remaining=max(0.,a.service_remaining-dt)
                if a.service_remaining<=1e-9:a.refill();a.state='parked'
            return
        a.turn_rate=0.;a.combat_turn_intensity=0.;a.command_turn_intensity=0.
        defensive=self.defensive_guidance(a)
        target_speed=a.cruise_speed;acceleration=STATS['aircraft_behavior']['acceleration_knots_per_second'];deceleration=STATS['aircraft_behavior']['deceleration_knots_per_second']
        receivers=[f for f in a.followers if f.alive and f.fuel_rendezvous]
        if a.kind=='KC-49' and receivers and a.state=='airborne' and a.mode!='rtb':
            target_speed=min(target_speed,min(f.cruise_speed*.7 for f in receivers))
        if a.state=='takeoff':
            a.heading=0.
            if a.speed>=STATS['aircraft_behavior']['liftoff_speed_knots']:a.takeoff_airborne=True
            if not a.takeoff_airborne:
                target_speed=STATS['aircraft_behavior']['takeoff_target_speed_knots'];acceleration=STATS['aircraft_behavior']['takeoff_acceleration_knots_per_second']
        elif a.state=='rollout':
            target_speed=0.;deceleration=STATS['aircraft_behavior']['rollout_deceleration_knots_per_second'];a.heading=0.
            if a.speed<.5:
                a.speed=0.;a.x,a.y=parking_position(a.parking_slot)
                a.begin_service(self.ground_crew_level);return
        elif defensive:
            desired=a.defensive_heading
            self.steer(a,math.sin(desired),math.cos(desired),dt,combat=True)
        elif a.state in ('rtb','approach'):
            a.fenced_in=False
            distance=math.hypot(a.x,a.y)
            if distance<=STATS['aircraft_behavior']['rtb_eco_distance_nm']:a.set_speed('Eco')
            target_speed=min(a.cruise_speed,STATS['aircraft_behavior']['rtb_pattern_speed_knots']) if math.dist((a.x,a.y),(0.,-5.))<10 else a.cruise_speed
            if a.rtb_stage==0:
                self.toward(a,(0.,-5.),dt)
                if allow_landing and math.dist((a.x,a.y),(0.,-5.))<.6:
                    a.rtb_stage=1; a.state='approach'
            elif a.rtb_stage==1:
                target_speed=STATS['aircraft_behavior']['approach_speed_knots']
                # Intercept the extended runway centerline before final.
                self.steer(a,max(-1.,min(1.,-a.x*2)),1.,dt)
                if a.y<-.8 and abs(a.x)<.06 and abs(angle_error(0,a.heading))<math.radians(8):
                    a.rtb_stage=2
                elif a.y>-.8:
                    a.rtb_stage=0;a.state='rtb'
            else:
                target_speed=STATS['aircraft_behavior']['final_speed_knots']
                self.toward(a,(0.,.75),dt)
                if a.y>=-.65:
                    if abs(a.x)<.08 and abs(angle_error(0,a.heading))<math.radians(8) and a.speed<STATS['aircraft_behavior']['touchdown_max_speed_knots']:
                        a.state='rollout';a.heading=0.;a.x=0.
                    else:a.rtb_stage=0;a.state='rtb'
        else:
            if a.combat_home:
                if a.bomb_run_heading is None:self.toward(a,(0.,0.),dt)
                else:self.steer(a,math.sin(a.bomb_run_heading),math.cos(a.bomb_run_heading),dt)
            elif a.combat_heading is not None and a.fenced_in:
                self.steer(a,math.sin(a.combat_heading),math.cos(a.combat_heading),dt)
            elif a.engage_target is not None and a.fenced_in:
                target=a.engage_target
                point=(target.x,target.y)
                if isinstance(target,Aircraft):
                    point=intercept_point((a.x,a.y),point,
                                          (target.speed*math.sin(target.heading),target.speed*math.cos(target.heading)),
                                          a.speed)
                    if any(a.weapon_enabled(kind) and a.missile_inventory.get(kind,0)>0
                           and math.hypot(target.x-a.x,target.y-a.y)<=STATS['missiles'][kind]['launch_range_nm']
                           for kind in ('AIM-9','AIM-120')):
                        bearing=math.atan2(target.x-a.x,target.y-a.y)
                        lead_heading=math.atan2(point[0]-a.x,point[1]-a.y)
                        limit=math.radians(max(0,a.radar_angle_deg/2-5))
                        heading=bearing+max(-limit,min(limit,angle_error(lead_heading,bearing)))
                        point=(a.x+math.sin(heading),a.y+math.cos(heading))
                if target is a.bomb_run_target and a.bombs_available:
                    distance=math.hypot(target.x-a.x,target.y-a.y)
                    error=abs(angle_error(math.atan2(target.x-a.x,target.y-a.y),a.heading))
                    if distance<STATS['aircraft_behavior']['bomb_turn_slow_distance_nm'] and error>math.radians(STATS['aircraft_behavior']['bomb_turn_slow_angle_degrees']):
                        turn_radius=max(.6,min(2.,distance*.25))
                        turn_speed=math.sqrt(9.81*1852*turn_radius)/.514444
                        target_speed=min(target_speed,max(STATS['aircraft_behavior']['bomb_turn_speed_knots'],turn_speed));deceleration=STATS['aircraft_behavior']['bomb_turn_deceleration_knots_per_second']
                self.toward(a,point,dt,combat=True)
            elif a.attack_target is not None and a.attack_target.alive and a.attack_point is not None and a.fenced_in:
                self.toward(a,a.attack_point,dt,combat=True)
            elif a.mode=='formation' and a.leader is not None:
                formation_speed=self.formation_guidance(a,dt)
                if formation_speed is not None:target_speed=formation_speed
                else:
                    self.toward(a,(a.leader.x+10,a.leader.y),dt)
                    target_speed=min(240.,target_speed)
            elif a.mode=='direct':
                point=a.orbit_center
                if math.dist((a.x,a.y),point)<=max(.2,a.speed/3600*dt*1.5):
                    a.mode='loiter';a.orbit_radius=a.full_speed_orbit_radius
                self.toward(a,point,dt)
            elif a.mode=='patrol' and a.path:
                self.patrol_guidance(a,dt)
            else:
                target_speed=min(target_speed,.95*math.sqrt(9.81*a.orbit_radius*1852)/.514444)
                cx,cy=a.orbit_center;dx=a.x-cx;dy=a.y-cy
                distance=math.hypot(dx,dy)
                if distance<1e-6:dx,dy,distance=0.,1.,1.
                rx,ry=dx/distance,dy/distance
                sign=-1 if a.clockwise else 1
                radial=max(-2.,min(2.,(a.orbit_radius-distance)/max(1.,a.orbit_radius*.35)))
                self.steer(a,-sign*ry+radial*rx,sign*rx+radial*ry,dt)
            # Reserve enough fuel for the trip home, plus approach and service.
            reserve=rtb_alert_fuel(a)
            if a.fuel>reserve:
                a.ignored_auto.discard('fuel')
                if a.pending_auto and a.pending_auto['reason']=='fuel':a.pending_auto=None
            if not a.enemy:
                if a.fuel_rendezvous:self.seek_fuel(a)
                elif a.fuel<=reserve:self.propose_fuel(a)
        if a.combat_turn_intensity>0:
            target_speed=min(target_speed,max(a.cruise_speed*.5,a.cruise_speed*(1-.5*a.combat_turn_intensity)))
            deceleration=max(deceleration,20.)
        if getattr(a,'command_turn_intensity',0.)>0:
            minimum=max(.8,STATS['aircraft_behavior']['command_turn_speed_fraction']) if a.mode=='patrol' else STATS['aircraft_behavior']['command_turn_speed_fraction']
            fraction=1-(1-minimum)*a.command_turn_intensity
            target_speed=min(target_speed,a.cruise_speed*fraction)
            deceleration=max(deceleration,STATS['aircraft_behavior']['command_turn_deceleration_knots_per_second'])
        if defensive and a.defensive_speed is not None:target_speed=a.defensive_speed
        delta=target_speed-a.speed
        a.speed=max(0,a.speed+max(-deceleration*dt,min(acceleration*dt,delta)))
        distance=a.speed/3600*dt
        a.x+=math.sin(a.heading)*distance;a.y+=math.cos(a.heading)*distance
        if a.state=='takeoff' and a.takeoff_airborne:
            a.departure_distance+=distance
            if a.departure_distance>=STATS['aircraft_behavior']['takeoff_straight_distance_nm']:
                a.state='rtb' if a.mode=='rtb' else 'airborne'
        a.fuel=max(0,a.fuel-dt*a.actual_fuel_burn)
        self.check_fuel_exhaustion(a)
