"""Game aircraft movement and servicing, in NM, knots, and simulated seconds."""
from collections import deque
from dataclasses import dataclass, field
import math
import random

AIRCRAFT_TYPES = {
    'RQ-9B': {'speed':240,'fuel':1080,'hardpoints':0,'bays':0,'cms':0,'health':35},
    'Drone': {'speed':250,'fuel':7200,'hardpoints':0,'bays':0,'cms':0},
    'Fighter': {'speed':600,'fuel':5400,'hardpoints':4,'bays':1,'cms':6},
    'Bomber': {'speed':400,'fuel':3600,'hardpoints':2,'bays':4,'cms':2},
    'Interceptor': {'speed':800,'fuel':2400,'hardpoints':4,'bays':0,'cms':4},
    'AWACS': {'speed':300,'fuel':10800,'hardpoints':0,'bays':0,'cms':6},
    'KC-49': {'speed':400,'fuel':36000,'hardpoints':0,'bays':0,'cms':6},
}

@dataclass
class Aircraft:
    kind: str
    hardpoints: list = field(default_factory=list)
    bays: list = field(default_factory=list)
    color: str = '#438cff'
    enemy: bool = False
    health: float = 100.
    x: float = .5
    y: float = -.5
    heading: float = 0.                 # North = 0, clockwise positive.
    speed: float = 0.
    state: str = 'queued'
    mode: str = 'loiter'
    fenced_in: bool = True
    orbit_center: tuple = (0.,0.)
    orbit_radius: float = 10.
    clockwise: bool = True
    path: list = field(default_factory=list)
    waypoint: int = 0
    rtb_stage: int = 0
    service_remaining: float = 0.
    service_total: float = 0.
    crew_active: bool = False
    depart_after_service: bool = False
    fuel: float = -1.
    cms: int = -1
    armed_hardpoints: list = field(default_factory=list)
    armed_bays: list = field(default_factory=list)
    history: deque = field(default_factory=deque)
    last_sample: float = -1.
    leader: object = field(default=None,repr=False,compare=False)
    parking_slot: int = 0
    formation_slot: int = 0
    followers: list = field(default_factory=list,repr=False,compare=False)
    afterburner: bool = False
    auto_afterburner: bool = False
    target_types: set = field(default_factory=lambda: {'Fighters','Drones','Bombers','Buildings','Vehicles'})
    engagement_range: int = 75
    air_weapons_per_target: int = 1
    ground_weapons_per_target: int = 1
    bomb_inventory: list = field(default_factory=list)
    missile_inventory: dict = field(default_factory=dict)
    combat_used_weapons: bool = False
    combat_home: bool = False
    bomb_run_target: object = field(default=None,repr=False,compare=False)
    bomb_run_phase: str = 'attack'
    bomb_run_heading: object = None
    combat_heading: object = None
    crank_side: int = 1
    attack_target: object = field(default=None,repr=False,compare=False)
    auto_attack_target: object = field(default=None,repr=False,compare=False)
    attack_point: object = None
    combat_turn_intensity: float = 0.
    engage_target: object = field(default=None,repr=False,compare=False)
    turn_rate: float = 0.
    refueling_from: object = field(default=None,repr=False,compare=False)
    fuel_rendezvous: bool = False
    fuel_resume: object = field(default=None,repr=False,compare=False)


    def __post_init__(self):
        if self.kind=='RQ-9B' and self.health==100:self.health=35.
        self.x,self.y=parking_position(self.parking_slot)
        self.refill()

    @property
    def alive(self):return self.health>0 and self.state!='destroyed'

    @property
    def category(self):return 'Drones' if self.kind=='Drone' else 'Bombers' if self.kind=='Bomber' else 'Fighters'

    @property
    def cms_capacity(self):return 0 if self.kind=='Drone' else 2 if self.enemy else self.spec['cms']

    @property
    def missiles_available(self):return sum(self.missile_inventory.values())

    @property
    def air_missiles_available(self):return sum(self.missile_inventory.get(kind,0) for kind in ('AIM-120','AIM-9'))

    def destroy(self):
        self.health=0.;self.state='destroyed';self.speed=0.
        self.detach();self.engage_target=None;self.combat_heading=None;self.combat_home=False
        for follower in list(self.followers):follower.loiter((self.x,self.y))
        self.refueling_from=None

    @property
    def spec(self):
        return AIRCRAFT_TYPES[self.kind]

    @property
    def max_health(self):return 35 if self.kind in ('Drone','RQ-9B') else 50 if self.enemy else 100

    @property
    def visual_range_nm(self):return 250. if self.kind=='AWACS' else 100. if self.kind=='RQ-9B' else 15.

    @property
    def can_refuel(self):return self.kind in ('Fighter','Bomber','Interceptor','RQ-9B')

    @property
    def ammo_full(self):
        missiles={'AIM-120':0,'AIM-9':0,'HARM':0}
        for value in self.armed_hardpoints:
            if 'AIM-120' in value:missiles['AIM-120']+=1
            elif 'AIM-9' in value:missiles['AIM-9']+=2 if value.startswith('2') else 1
            elif 'HARM' in value:missiles['HARM']+=1
        bombs={}
        for value in self.armed_bays:
            for weight,count in ((250,4),(500,2),(1000,1)):
                if str(weight) in value.replace(',',''):
                    bombs[weight]=bombs.get(weight,0)+count;break
        actual={}
        for weight,count in self.bomb_inventory:actual[weight]=actual.get(weight,0)+count
        return self.missile_inventory==missiles and actual==bombs

    @property
    def sensors_active(self):
        return self.state in ('airborne','rtb','approach')

    @property
    def radar_range_nm(self):
        return {'Fighter':35.,'Interceptor':45.,'AWACS':250.}.get(self.kind,0.)

    @property
    def radar_angle_deg(self):
        return {'Fighter':60.,'Interceptor':50.,'AWACS':360.}.get(self.kind,0.)

    def radar_detects(self,x,y):
        if not self.sensors_active or not self.radar_range_nm:return False
        dx,dy=x-self.x,y-self.y
        if math.hypot(dx,dy)>self.radar_range_nm:return False
        angle=(math.atan2(dx,dy)-self.heading+math.pi)%math.tau-math.pi
        return self.radar_angle_deg==360 or abs(angle)<=math.radians(self.radar_angle_deg/2)+1e-12

    def visual_detects(self,x,y):
        return self.sensors_active and math.hypot(x-self.x,y-self.y)<=self.visual_range_nm

    @property
    def cruise_speed(self):
        return self.spec['speed']*(1.2 if self.afterburner else 1. if self.fenced_in else .75)

    @property
    def max_ab_speed(self):
        return self.spec['speed']*1.2

    @property
    def fuel_burn(self):
        if self.kind=='RQ-9B':return .1
        return 2. if self.afterburner or self.auto_afterburner else 1. if self.fenced_in else .5

    @property
    def actual_fuel_burn(self):
        if self.state in ('queued','parked','rollout','servicing'):return 0.
        on_tanker=(self.state=='airborne' and self.can_refuel
                   and self.mode=='formation' and self.leader is not None
                   and self.leader.kind=='KC-49' and self.leader.state=='airborne'
                   and self.leader.fuel>rtb_reserve(self.leader)
                   and math.dist((self.x,self.y),(self.leader.x,self.leader.y))<=REFUEL_RADIUS_NM)
        return 0. if on_tanker else self.fuel_burn

    @property
    def bombs_available(self):return sum(count for weight,count in self.bomb_inventory)

    def take_bomb(self,target_health=None):
        available=[rack for rack in self.bomb_inventory if rack[1]>0]
        if not available:return None
        damage={250:20,500:100,1000:400}
        capable=[rack for rack in available if target_health is not None and round(damage[rack[0]]*1.15)>=target_health]
        rack=min(capable,key=lambda r:r[0]) if capable else max(available,key=lambda r:r[0])
        rack[1]-=1
        return rack[0]

    def detach(self):
        if self.leader is not None:
            self.leader.followers[:]=[a for a in self.leader.followers if a is not self]
        self.leader=None;self.auto_afterburner=False

    def refill(self):
        self.fuel=self.spec['fuel']
        self.combat_used_weapons=False
        self.cms=self.cms_capacity
        self.armed_hardpoints=list(self.hardpoints)
        self.armed_bays=list(self.bays)
        self.missile_inventory={'AIM-120':0,'AIM-9':0,'HARM':0}
        for value in self.hardpoints:
            if 'AIM-120' in value:self.missile_inventory['AIM-120']+=1
            elif 'AIM-9' in value:self.missile_inventory['AIM-9']+=2 if value.startswith('2') else 1
            elif 'HARM' in value:self.missile_inventory['HARM']+=1
        self.bomb_inventory=[]
        for value in self.bays:
            for weight,count in ((250,4),(500,2),(1000,1)):
                if str(weight) in value.replace(',',''):
                    self.bomb_inventory.append([weight,count]);break

    def configured_weapons(self):
        missiles={'AIM-120':0,'AIM-9':0,'HARM':0};bombs={}
        for value in self.hardpoints:
            if 'AIM-120' in value:missiles['AIM-120']+=1
            elif 'AIM-9' in value:missiles['AIM-9']+=2 if value.startswith('2') else 1
            elif 'HARM' in value:missiles['HARM']+=1
        for value in self.bays:
            for weight,count in ((250,4),(500,2),(1000,1)):
                if str(weight) in value.replace(',',''):
                    bombs[weight]=bombs.get(weight,0)+count;break
        return missiles,bombs

    @property
    def missing_weapons(self):
        missiles,bombs=self.configured_weapons();actual={}
        for weight,count in self.bomb_inventory:actual[weight]=actual.get(weight,0)+count
        return sum(max(0,n-self.missile_inventory.get(k,0)) for k,n in missiles.items())+sum(max(0,n-actual.get(k,0)) for k,n in bombs.items())

    @property
    def needs_service(self):return self.health<self.max_health or self.missing_weapons>0

    @property
    def service_progress(self):
        return max(0.,min(1.,1-self.service_remaining/self.service_total)) if self.service_total else 1.

    def begin_service(self,level=1):
        repair_seconds=6-level
        weapon_seconds=10-(level-1)*1.25
        self.service_total=max(0,self.max_health-self.health)*repair_seconds+self.missing_weapons*weapon_seconds
        self.service_remaining=self.service_total;self.crew_active=False
        self.depart_after_service=False
        self.fuel=self.spec['fuel']
        self.state='servicing' if self.service_total>1e-9 else 'parked'
        if self.state=='parked':self.refill()

    def change_loadout(self,group,index,value,level=1):
        stations=getattr(self,group)
        if self.state not in ('parked','queued','servicing') or stations[index]==value:return False
        old=stations[index]
        if group=='hardpoints':
            for kind in ('AIM-120','AIM-9','HARM'):
                if kind in old:
                    count=2 if kind=='AIM-9' and old.startswith('2') else 1
                    self.missile_inventory[kind]=max(0,self.missile_inventory.get(kind,0)-count)
                    break
        else:
            for weight,count in ((250,4),(500,2),(1000,1)):
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
        return (rng or random).random()<.8

    def rtb(self):
        for follower in list(self.followers):follower.loiter((0.,0.))
        self.fuel_rendezvous=False;self.fuel_resume=None
        self.mode='rtb';self.fenced_in=False;self.depart_after_service=False
        self.detach();self.refueling_from=None;self.afterburner=False
        self.rtb_stage=0
        if self.state in ('queued','parked'):
            self.state='parked'
            if self.needs_service:self.begin_service()
        elif self.state=='airborne':self.state='rtb'

    def loiter(self,center,radius=10.,clockwise=True):
        self.detach()
        self.mode='loiter';self.orbit_center=tuple(center)
        self.orbit_radius=max(.5,float(radius));self.clockwise=bool(clockwise)
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
        elif self.state in ('rtb','approach'):self.state='airborne'


REFUEL_RADIUS_NM = 1.


def parking_position(slot):
    return 1.15+.35*(slot%2),-.7+.35*(slot//2)


def formation_position(leader,slot):
    rank=slot//2+1
    side=-1 if slot%2==0 else 1
    back=.12*rank;lateral=.12*rank*side
    return (leader.x-back*math.sin(leader.heading)+lateral*math.cos(leader.heading),
            leader.y-back*math.cos(leader.heading)-lateral*math.sin(leader.heading))


def rtb_reserve(a):
    burn=.1 if a.kind=='RQ-9B' else .5
    return burn*(math.hypot(a.x,a.y)/max(140.,a.spec['speed']*.75)*3600+240)


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
            dt=min(.1,remaining);remaining-=dt;self.time+=dt
            if self.combat is not None:self.combat.prepare(aircraft,self.time)
            runway_busy=any(a.state in ('takeoff','approach','rollout') for a in aircraft)
            for a in aircraft:
                a.refueling_from=None
                if a.state=='queued' and not runway_busy:
                    a.x=0.;a.y=-.65;a.heading=0.;a.speed=0.
                    if a.needs_service:
                        a.begin_service(self.ground_crew_level)
                    else:
                        a.state='takeoff';runway_busy=True
                self.step(a,dt,not runway_busy or a.state=='approach')
                if a.state in ('takeoff','approach','rollout'):runway_busy=True
                if self.time-a.last_sample>=.2-1e-9:
                    if a.speed>=1:a.history.append((self.time,a.x,a.y,a.speed))
                    a.last_sample=self.time
                while a.history and a.history[0][0]<self.time-30.2:a.history.popleft()
            self.service_aircraft(aircraft,dt)
            self.refuel_aircraft(aircraft,dt)
            if self.combat is not None:self.combat.advance(self.time)

    def service_aircraft(self,aircraft,dt):
        waiting=[a for a in aircraft if a.alive and not a.enemy and a.state=='servicing']
        # Preserve active assignments; waiting aircraft only take free crews.
        active=[a for a in waiting if a.crew_active]
        active.extend(a for a in waiting if not a.crew_active)
        working=active[:self.ground_crew_level]
        for a in waiting:
            a.crew_active=any(a is w for w in working)
            if not a.crew_active:continue
            a.service_remaining=max(0.,a.service_remaining-dt)
            if a.service_remaining<=1e-9:
                a.health=a.max_health;a.refill();a.state='parked'
                a.service_remaining=0.;a.crew_active=False

    def refuel_aircraft(self,aircraft,dt):
        tankers=[a for a in aircraft if a.kind=='KC-49' and a.state=='airborne']
        for a in aircraft:
            if not a.can_refuel or a.state!='airborne':continue
            eligible=[t for t in tankers if t.enemy==a.enemy and t.alive and t.fuel>rtb_reserve(t) and math.dist((a.x,a.y),(t.x,t.y))<=REFUEL_RADIUS_NM]
            if not eligible:continue
            tanker=min(eligible,key=lambda t:math.dist((a.x,a.y),(t.x,t.y)))
            reserve=rtb_reserve(tanker)
            amount=min(180*dt,a.spec['fuel']-a.fuel,max(0,tanker.fuel-reserve))
            if amount>1e-8:
                a.fuel+=amount;tanker.fuel-=amount;a.refueling_from=tanker
            if a.fuel_rendezvous and a.fuel>=a.spec['fuel']-1e-8:
                saved=a.fuel_resume;a.detach();a.fuel_rendezvous=False;a.fuel_resume=None
                if saved is not None:
                    a.mode,a.orbit_center,a.orbit_radius,a.clockwise,a.path,a.waypoint,leader,a.fenced_in,a.afterburner=saved
                    if a.mode=='formation' and leader is not None and leader.alive:a.form_up(leader)
                    elif a.mode=='formation':a.mode='loiter'

    def seek_fuel(self,a):
        base_distance=math.hypot(a.x,a.y)
        if a.fuel_rendezvous:
            leader=a.leader
            if leader is not None and leader.alive and leader.state=='airborne' and leader.mode!='rtb' and leader.fuel>rtb_reserve(leader):return
            a.rtb();return
        candidates=[]
        if a.can_refuel and a.ammo_full:
            for t in getattr(self,'current_aircraft',()):
                distance=math.hypot(t.x-a.x,t.y-a.y)
                rendezvous_speed=min(a.max_ab_speed,max(80.,t.speed*1.1))
                rendezvous_burn=.1 if a.kind=='RQ-9B' else 2. if rendezvous_speed>a.spec['speed']*.75 else .5
                if (t.kind=='KC-49' and not t.enemy and t.alive and t.state=='airborne' and t.mode!='rtb'
                    and t.speed<a.max_ab_speed and distance<base_distance
                    and t.fuel>rtb_reserve(t)+(a.spec['fuel']-a.fuel)
                    and a.fuel>distance/max(1.,rendezvous_speed-t.speed)*3600*rendezvous_burn):
                    candidates.append((distance,t))
        if not candidates:a.rtb();return
        tanker=min(candidates,key=lambda item:item[0])[1]
        a.fuel_resume=(a.mode,a.orbit_center,a.orbit_radius,a.clockwise,list(a.path),a.waypoint,a.leader,a.fenced_in,a.afterburner)
        a.attack_target=None;a.attack_point=None;a.engage_target=None;a.auto_attack_target=None;a.combat_heading=None
        a.fenced_in=False;a.afterburner=False;a.form_up(tanker);a.fuel_rendezvous=True

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
        catch_up=min(a.max_ab_speed,max(80.,leader.speed*1.1))
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
        desired_speed=min(a.max_ab_speed,desired_speed)
        self.steer(a,math.sin(heading),math.cos(heading),dt)
        a.auto_afterburner=desired_speed>a.cruise_speed+.5
        return desired_speed

    def steer(self,a,dx,dy,dt,combat=False):
        desired=math.atan2(dx,dy)
        # Limit heading rate using a 45-degree bank approximation, rather than
        # allowing instant turns. Slow-flight rate is capped at 12 degrees/sec.
        rate=min(math.radians(12),9.81*math.tan(math.radians(45))/max(35,a.speed*.514444))
        error=angle_error(desired,a.heading)
        if combat and a.kind in ('Fighter','Interceptor'):
            rate=min(math.radians(24),9.81*math.tan(math.radians(70))/max(35,a.speed*.514444))
            a.combat_turn_intensity=min(1.,max(0.,(abs(error)-math.radians(5))/math.radians(85)))
        change=max(-rate*dt,min(rate*dt,error))
        a.turn_rate=change/dt
        a.heading=(a.heading+change)%math.tau

    def toward(self,a,point,dt,combat=False):
        self.steer(a,point[0]-a.x,point[1]-a.y,dt,combat=combat)

    def step(self,a,dt,allow_landing=True):
        if not a.alive or a.state in ('queued','parked'):return
        if a.state=='servicing':
            if a.enemy:
                a.service_remaining=max(0.,a.service_remaining-dt)
                if a.service_remaining<=1e-9:a.refill();a.state='parked'
            return
        a.turn_rate=0.;a.auto_afterburner=False;a.combat_turn_intensity=0.
        target_speed=a.cruise_speed;acceleration=8.;deceleration=8.
        if a.state=='takeoff':
            target_speed=180.;acceleration=5.;a.heading=0.
            if a.speed>=140:
                a.state='rtb' if a.mode=='rtb' else 'airborne'
        elif a.state=='rollout':
            target_speed=0.;deceleration=4.;a.heading=0.
            if a.speed<.5:
                a.speed=0.;a.x,a.y=parking_position(a.parking_slot)
                a.begin_service(self.ground_crew_level);return
        elif a.state in ('rtb','approach'):
            a.fenced_in=False
            distance=math.hypot(a.x,a.y)
            target_speed=min(a.cruise_speed,240.) if math.dist((a.x,a.y),(0.,-5.))<10 else a.cruise_speed
            if a.rtb_stage==0:
                self.toward(a,(0.,-5.),dt)
                if allow_landing and math.dist((a.x,a.y),(0.,-5.))<.6:
                    a.rtb_stage=1; a.state='approach'
            elif a.rtb_stage==1:
                target_speed=180.
                # Intercept the extended runway centerline before final.
                self.steer(a,max(-1.,min(1.,-a.x*2)),1.,dt)
                if a.y<-.8 and abs(a.x)<.06 and abs(angle_error(0,a.heading))<math.radians(8):
                    a.rtb_stage=2
                elif a.y>-.8:
                    a.rtb_stage=0;a.state='rtb'
            else:
                target_speed=140.
                self.toward(a,(0.,.75),dt)
                if a.y>=-.65:
                    if abs(a.x)<.08 and abs(angle_error(0,a.heading))<math.radians(8) and a.speed<190:
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
                    if a.missile_inventory.get('AIM-120',0) and math.hypot(target.x-a.x,target.y-a.y)<=25:
                        bearing=math.atan2(target.x-a.x,target.y-a.y)
                        lead_heading=math.atan2(point[0]-a.x,point[1]-a.y)
                        limit=math.radians(max(0,a.radar_angle_deg/2-5))
                        heading=bearing+max(-limit,min(limit,angle_error(lead_heading,bearing)))
                        point=(a.x+math.sin(heading),a.y+math.cos(heading))
                self.toward(a,point,dt,combat=True)
            elif a.mode=='formation' and a.leader is not None:
                formation_speed=self.formation_guidance(a,dt)
                if formation_speed is not None:target_speed=formation_speed
                else:
                    self.toward(a,(a.leader.x+10,a.leader.y),dt)
                    target_speed=min(240.,target_speed)
            elif a.mode=='patrol' and a.path:
                point=a.path[a.waypoint]
                if math.dist((a.x,a.y),point)<max(.2,a.speed/3600*6):
                    a.waypoint=(a.waypoint+1)%len(a.path);point=a.path[a.waypoint]
                target_speed=min(target_speed,max(120.,math.dist((a.x,a.y),point)*100))
                self.toward(a,point,dt)
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
            reserve=rtb_reserve(a)
            nearby_tanker=a.can_refuel and any(t.kind=='KC-49' and not t.enemy and t.alive and t.state=='airborne' and t.fuel>rtb_reserve(t) and math.dist((a.x,a.y),(t.x,t.y))<=REFUEL_RADIUS_NM for t in getattr(self,'current_aircraft',()))
            if not a.enemy and (a.fuel_rendezvous or a.fuel<=reserve and not nearby_tanker):self.seek_fuel(a)
        if a.combat_turn_intensity>0:
            target_speed=max(a.cruise_speed*.5,a.cruise_speed*(1-.5*a.combat_turn_intensity))
            deceleration=20.
        delta=target_speed-a.speed
        a.speed=max(0,a.speed+max(-deceleration*dt,min(acceleration*dt,delta)))
        distance=a.speed/3600*dt
        a.x+=math.sin(a.heading)*distance;a.y+=math.cos(a.heading)*distance
        a.fuel=max(0,a.fuel-dt*a.actual_fuel_burn)
