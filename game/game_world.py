"""Scattered enemy world and gameplay RWR estimates (not a radar track)."""
from dataclasses import dataclass
import math
import random
from .game_settings import STATS

WORLD_RADIUS_NM=STATS['world']['radius_nm']
RWR_RANGE_NM=STATS['world']['rwr_range_nm']

@dataclass
class RWRSignal:
    emitter: object
    x: float
    y: float
    quality: float
    enemy: bool = True
    name: str = 'RWR Signal'

    @property
    def alive(self):return self.emitter.radar_emitting

    @property
    def confidence(self):
        # Quality divides both bearing and range uncertainty. Show how much
        # triangulation has reduced uncertainty relative to one receiver.
        return max(0.,min(1.,1-1/max(1.,self.quality)))


class RWR:
    def __init__(self,seed=None):
        self.rng=random.Random(seed);self.updated=-STATS['world']['rwr_update_seconds'];self.estimates={}

    def update(self,aircraft,radars,now):
        if now-self.updated<STATS['world']['rwr_update_seconds']-1e-9:return False
        self.updated=now;self.estimates={}
        observers=[a for a in aircraft if a.alive and a.sensors_active and not a.enemy]
        for radar in radars:
            if not radar.radar_emitting:continue
            seen=[a for a in observers if math.dist((a.x,a.y),(radar.x,radar.y))<=RWR_RANGE_NM]
            if not seen:continue
            spread=0.
            for i,a in enumerate(seen):
                for b in seen[i+1:]:
                    baseline=min(1.,math.dist((a.x,a.y),(b.x,b.y))/STATS['world']['rwr_baseline_nm'])
                    ba=math.atan2(radar.x-a.x,radar.y-a.y);bb=math.atan2(radar.x-b.x,radar.y-b.y)
                    spread=max(spread,baseline*abs(math.sin(ba-bb)))
            quality=1+(len(seen)-1)*spread
            # A single receiver has ±25% range and ±10° direction uncertainty.
            a=seen[0];dx,dy=radar.x-a.x,radar.y-a.y;distance=math.hypot(dx,dy)
            bearing=math.atan2(dx,dy)+self.rng.uniform(-math.radians(STATS['world']['rwr_bearing_error_degrees']),math.radians(STATS['world']['rwr_bearing_error_degrees']))/quality
            distance*=1+self.rng.uniform(-STATS['world']['rwr_range_error_fraction'],STATS['world']['rwr_range_error_fraction'])/quality
            self.estimates[id(radar)]=(radar,a.x+math.sin(bearing)*distance,a.y+math.cos(bearing)*distance,quality)
        return True

def scatter_world(combat,radar_type,sam_type,seed=None):
    rng=random.Random(seed)
    def point(minimum=125.,maximum=10000.):
        radius=rng.uniform(minimum,maximum);angle=rng.uniform(0,math.tau)
        return radius*math.sin(angle),radius*math.cos(angle)
    # Independent samples, with random counts and positions: no rings or bands.
    for _ in range(rng.randint(185,210)):
        x,y=point()
        (combat.spawn_bunker if rng.random()<.3 else combat.spawn_factory)(x,y)
    for _ in range(rng.randint(22,28)):
        x,y=point(125.,9980.)
        combat.enemy_radars.append(radar_type(len(combat.enemy_radars)+1,x,y,enemy=True))
        angle=rng.uniform(0,math.tau);offset=rng.uniform(3,12)
        sx,sy=x+offset*math.sin(angle),y+offset*math.cos(angle)
        if math.hypot(sx,sy)<125.:sx,sy=x,y
        combat.enemy_sams.append(sam_type(len(combat.enemy_sams)+1,sx,sy,enemy=True))
    for _ in range(rng.randint(60,72)):
        x,y=point(150.,9980.);angle=rng.uniform(0,math.tau)
        a=combat.spawn_fighter(x+20*math.sin(angle),y+20*math.cos(angle))
        a.orbit_center=(x,y);a.orbit_radius=20.;a.heading=angle+math.pi/2
        # Enemy aircraft have unlimited fuel.
