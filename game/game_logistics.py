"""Automatic ground-unit resupply, using NM and simulation seconds."""
from dataclasses import dataclass
import math
from .game_settings import STATS

LOGISTICS_LEVELS = tuple(STATS['logistics']['helicopters_by_level'])
LOGISTICS_UPGRADE_COSTS = tuple(STATS['upgrades']['prices']['Logistics'])

def logistics_reload_multiplier(level):
    return STATS['logistics']['reload_speed_multipliers_by_level'][max(0,min(4,level-1))]


def helipad_position(airfield):
    return airfield.x+.5,airfield.y-.6

@dataclass
class LogisticsHelicopter:
    id: int
    x: float = 0.
    y: float = 0.
    heading: float = 0.
    state: str = 'parked'
    target: object = None
    speed: float = STATS['logistics']['speed_knots']
    color: str = '#56deef'

    @property
    def alive(self):return True

    @property
    def name(self):return f'Logistics Heli #{self.id}'

class LogisticsFleet:
    def __init__(self):
        self.helicopters=[]
        self.requests=[]
        self.reloads={};self.multiplier=1.

    def sync(self,count,airfield):
        self.multiplier=logistics_reload_multiplier(getattr(airfield,'logistics_level',1))
        for unit in self.reloads.values():
            unit.logistics_reload_remaining=unit.logistics_reload_work_remaining/self.multiplier
        while len(self.helicopters)<count:
            self.helicopters.append(LogisticsHelicopter(len(self.helicopters)+1,*helipad_position(airfield)))

    def requested(self,unit):
        return id(unit) in self.reloads or any(u is unit for u in self.requests) or any(h.state=='outbound' and h.target is unit for h in self.helicopters)

    def request(self,unit,airfield):
        if not airfield.alive or not unit.alive or unit.enemy or unit.ammo>=unit.ammo_capacity or self.requested(unit):return False
        self.requests.append(unit)
        return True

    def status(self,unit):
        if not unit.alive:return 'Destroyed'
        if id(unit) in self.reloads:return f'Reloading: {max(0,math.ceil(unit.logistics_reload_remaining))}s'
        heli=next((h for h in self.helicopters if h.state=='outbound' and h.target is unit),None)
        if heli:return f'Resupply: Heli #{heli.id} inbound'
        if any(u is unit for u in self.requests):return 'Resupply queued'
        return 'Ready' if unit.ammo>0 else 'Waiting for resupply'

    def advance_reload(self,unit,seconds):
        if not unit.alive:
            self.reloads.pop(id(unit),None)
            unit.logistics_reload_work_remaining=0.;unit.logistics_reload_remaining=0.;return
        work=max(0.,unit.logistics_reload_work_remaining-max(0.,seconds)*self.multiplier)
        unit.logistics_reload_work_remaining=work
        unit.logistics_reload_remaining=work/self.multiplier
        if work>1e-9:return
        unit.ammo=unit.ammo_capacity
        if hasattr(unit,'shot_timer'):unit.shot_timer=0.
        unit.logistics_reload_remaining=0.;unit.logistics_reload_work_remaining=0.
        self.reloads.pop(id(unit),None)

    def advance(self,units,airfield,seconds):
        seconds=max(0.,seconds)
        self.multiplier=logistics_reload_multiplier(getattr(airfield,'logistics_level',1))
        for unit in list(self.reloads.values()):self.advance_reload(unit,seconds)
        reserved={id(h.target) for h in self.helicopters if h.state=='outbound'}
        self.requests[:]=[u for u in self.requests if u.alive and not u.enemy and u.ammo<u.ammo_capacity and id(u) not in reserved and id(u) not in self.reloads]
        requested_ids={id(u) for u in self.requests}
        waiting=[*self.requests,*[u for u in units if u.alive and not u.enemy and u.ammo<=0 and id(u) not in reserved and id(u) not in requested_ids and id(u) not in self.reloads]]
        for h in self.helicopters:
            remaining=seconds
            # Complete legs with leftover time, including zero-distance deliveries.
            while True:
                if h.state=='parked':
                    h.x,h.y=helipad_position(airfield)
                    if not airfield.alive or not waiting:break
                    h.target=waiting.pop(0);h.state='outbound'
                    self.requests[:]=[u for u in self.requests if u is not h.target]
                if h.state=='outbound' and (not h.target.alive or h.target.ammo>=h.target.ammo_capacity or id(h.target) in self.reloads):
                    h.target=None;h.state='returning'
                destination=(h.target.x,h.target.y) if h.state=='outbound' else helipad_position(airfield)
                dx,dy=destination[0]-h.x,destination[1]-h.y
                distance=math.hypot(dx,dy)
                if distance>1e-9:h.heading=math.atan2(dx,dy)
                travel=distance/(h.speed/3600.)
                if travel>remaining+1e-9:
                    fraction=remaining/travel
                    h.x+=dx*fraction;h.y+=dy*fraction
                    break
                h.x,h.y=destination;remaining=max(0.,remaining-travel)
                if h.state=='outbound':
                    unit=h.target
                    unit.health=min(unit.max_health,unit.health+STATS['logistics']['heal_per_delivery'])
                    unit.logistics_reload_work_remaining=unit.stats['reload_seconds']
                    unit.logistics_reload_remaining=unit.logistics_reload_work_remaining/self.multiplier
                    self.reloads[id(unit)]=unit
                    if hasattr(unit,'shot_timer'):unit.shot_timer=0.
                    # Only the portion of this tick AFTER arrival counts toward reload.
                    self.advance_reload(unit,remaining)
                    h.target=None;h.state='returning'
                else:h.state='parked'
