"""Automatic ground-unit resupply, using NM and simulation seconds."""
from dataclasses import dataclass
import math

LOGISTICS_LEVELS = (1,2,3,4,5)
LOGISTICS_UPGRADE_COSTS = (1000,2500,5000,10000)

@dataclass
class LogisticsHelicopter:
    id: int
    x: float = 0.
    y: float = 0.
    heading: float = 0.
    state: str = 'parked'
    target: object = None
    speed: float = 175.
    color: str = '#56deef'

    @property
    def alive(self):return True

    @property
    def name(self):return f'Logistics Heli #{self.id}'

class LogisticsFleet:
    def __init__(self):
        self.helicopters=[]
        self.requests=[]

    def sync(self,count,airfield):
        while len(self.helicopters)<count:
            self.helicopters.append(LogisticsHelicopter(len(self.helicopters)+1,airfield.x,airfield.y))

    def requested(self,unit):
        return any(u is unit for u in self.requests) or any(h.state=='outbound' and h.target is unit for h in self.helicopters)

    def request(self,unit,airfield):
        if not airfield.alive or not unit.alive or unit.enemy or unit.ammo>=unit.ammo_capacity or self.requested(unit):return False
        self.requests.append(unit)
        return True

    def status(self,unit):
        if not unit.alive:return 'Destroyed'
        heli=next((h for h in self.helicopters if h.state=='outbound' and h.target is unit),None)
        if heli:return f'Resupply: Heli #{heli.id} inbound'
        if any(u is unit for u in self.requests):return 'Resupply queued'
        return 'Ready' if unit.ammo>0 else 'Waiting for resupply'

    def advance(self,units,airfield,seconds):
        reserved={id(h.target) for h in self.helicopters if h.state=='outbound'}
        self.requests[:]=[u for u in self.requests if u.alive and not u.enemy and u.ammo<u.ammo_capacity and id(u) not in reserved]
        requested_ids={id(u) for u in self.requests}
        waiting=[*self.requests,*[u for u in units if u.alive and not u.enemy and u.ammo<=0 and id(u) not in reserved and id(u) not in requested_ids]]
        for h in self.helicopters:
            remaining=max(0.,seconds)
            # Complete legs with leftover time, including zero-distance deliveries.
            while True:
                if h.state=='parked':
                    h.x,h.y=airfield.x,airfield.y
                    if not airfield.alive or not waiting:break
                    h.target=waiting.pop(0);h.state='outbound'
                    self.requests[:]=[u for u in self.requests if u is not h.target]
                if h.state=='outbound' and (not h.target.alive or h.target.ammo>=h.target.ammo_capacity):
                    h.target=None;h.state='returning'
                destination=(h.target.x,h.target.y) if h.state=='outbound' else (airfield.x,airfield.y)
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
                    h.target.ammo=h.target.ammo_capacity
                    if hasattr(h.target,'shot_timer'):h.target.shot_timer=0.
                    h.target=None;h.state='returning'
                else:h.state='parked'
