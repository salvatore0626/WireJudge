"""Shared replay and decorative aircraft rendering style."""
import numpy as np
from matplotlib.colors import to_rgba
from matplotlib.markers import MarkerStyle
from matplotlib.transforms import Affine2D

PALETTE=('#489fff','#ff9f32','#bcf34a','#bb8fff','#32e6ff','#ffe65c',
         '#38c9ac','#f3f6ff','#7480ff','#d7b899')
ENEMY_COLOR='#ff5575';MISSILE_COLOR='#ffd454';BULLET_COLOR='#fff4ce'
AIRCRAFT_SIZE=7;AIRCRAFT_TRAIL_WIDTH=1.1;MISSILE_TRAIL_WIDTH=.8
EXPLOSION_DURATION=.45

def aircraft_marker(dx,dy):
    return (3,0,-np.degrees(np.arctan2(dx,dy)))

def missile_color(t):
    phase=(1-np.cos(2*np.pi*t/1.2))/2
    return (1-phase)*np.asarray(to_rgba(MISSILE_COLOR))+phase*np.asarray(to_rgba('#ff6938'))

def sam_missile_color(t):
    phase=(1-np.cos(2*np.pi*t/1.2))/2
    return (1-phase)*np.asarray(to_rgba('#ff5555'))+phase*np.asarray(to_rgba(MISSILE_COLOR))

def missile_size(t):
    return 7*(1+.12*np.sin(2*np.pi*t/1.5))**2

def missile_path(t):
    diamond=MarkerStyle('D')
    return diamond.get_path().transformed(diamond.get_transform()).transformed(Affine2D().rotate_deg(t*60))

def explosion_frame(age,dpi=100,opacity=1):
    """Expanding orange ring, measured in display pixels in both views."""
    if not 0<=age<EXPLOSION_DURATION:return None
    radius=5+25*age
    color=np.asarray(to_rgba('#ff9d45'));color[3]=opacity*(1-age/EXPLOSION_DURATION)
    return (2*radius*72/dpi)**2,color

def update_explosions(artist,bursts,dpi=100,opacity=1):
    points=[];sizes=[];colors=[]
    for x,y,age in bursts:
        frame=explosion_frame(age,dpi,opacity)
        if frame is None:continue
        points.append((x,y));sizes.append(frame[0]);colors.append(frame[1])
    artist.set_offsets(np.asarray(points).reshape(-1,2));artist.set_sizes(sizes)
    artist.set_edgecolors(np.asarray(colors).reshape(-1,4))


BOMB_COLOR='#489fff'

def bomb_color(t):
    phase=(1-np.cos(2*np.pi*t/1.2))/2
    return (1-phase)*np.asarray(to_rgba(BOMB_COLOR))+phase*np.asarray(to_rgba('#ffffff'))

def update_bomb_pulses(artist,bursts,dpi=100):
    """Subtle in-flight pulses and full-size blue impact rings."""
    points=[];sizes=[];colors=[]
    for burst in bursts:
        x,y,phase=burst[:3];impact=len(burst)>3 and burst[3]
        if not 0<=phase<1:continue
        radius=5+25*phase*EXPLOSION_DURATION if impact else 2+4*phase
        color=np.asarray(to_rgba(BOMB_COLOR));color[3]=(1 if impact else .35)*(1-phase)
        points.append((x,y));sizes.append((2*radius*72/dpi)**2);colors.append(color)
    artist.set_offsets(np.asarray(points).reshape(-1,2));artist.set_sizes(sizes)
    artist.set_edgecolors(np.asarray(colors).reshape(-1,4))
