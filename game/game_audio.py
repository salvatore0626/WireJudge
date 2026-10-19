"""Game sound routing, zoom attenuation and wall-clock throttling."""
import math
import time
from pathlib import Path
from .game_settings import STATS
from core.sound_effects import SoundEffects

UI_EVENTS={'buy_aircraft','place_unit','upgrade','radar_ping','objective_complete','achievement_unlocked','kill_reward'}


def zoom_gain(width,settings):
    anchors=[(settings['full_volume_zoom_nm'],1.),(settings['quiet_zoom_nm'],settings['quiet_volume']),
             (settings['barely_audible_zoom_nm'],settings['barely_audible_volume'])]
    if width<=anchors[0][0]:return 1.
    for (left,a),(right,b) in zip(anchors,anchors[1:]):
        if width<=right:
            f=(width-left)/(right-left)
            return math.exp(math.log(a)*(1-f)+math.log(b)*f) if a>0 and b>0 else a+(b-a)*f
    return anchors[-1][1]*anchors[-1][0]/max(width,anchors[-1][0])


def center_gain(frame_distance,settings):
    """0 is screen center, 1 is an edge, >1 is outside the visible rectangle."""
    if not settings['center_falloff_enabled']:return 1.
    distance=max(0.,frame_distance);edge=settings['edge_volume'];power=settings['center_falloff_exponent']
    if distance<=1:return edge+(1-edge)*(1-distance)**power
    fade=max(0.,1-(distance-1)/(settings['silence_distance_frames']-1))
    return edge*fade**power


def kill_reward_gain(reward,settings):
    """Linear payout scaling, clamped at the configured reward anchors."""
    low=settings['min_reward'];high=settings['max_reward']
    fraction=max(0.,min(1.,(reward-low)/(high-low)))
    return settings['min_volume_multiplier']+(settings['max_volume_multiplier']-settings['min_volume_multiplier'])*fraction


class GameAudio:
    def __init__(self,options=None,player=None,clock=time.monotonic):
        self.settings=STATS['audio'];self.clock=clock;self.last={};self.muted=False
        self.player=player or SoundEffects(options,polyphonic=True,max_voices=self.settings['max_voices'],
                                         directory=Path(__file__).resolve().parent/'assets'/'sounds')

    def play(self,event,width=10,frame_distance=0.,volume_multiplier=1.):
        if self.muted:return False
        if not self.settings['enabled'] or event not in self.settings['events']:return False
        spec=self.settings['events'][event];now=self.clock()
        gain=self.settings['master_volume']*spec['volume']*max(0.,volume_multiplier)
        if event not in UI_EVENTS:gain*=zoom_gain(width,self.settings)*center_gain(frame_distance,self.settings)
        if gain<=0 or now-self.last.get(event,-math.inf)<spec['cooldown_seconds']:return False
        self.last[event]=now
        self.player.play(spec['file'],gain)
        return True

    def set_muted(self,muted):
        self.muted=bool(muted)
        if self.muted:self.stop()

    def stop(self):self.player.stop()
    def close(self):self.player.close()
