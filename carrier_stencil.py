"""Carrier-native vector deck stencil with a runway aligned to live ILS settings."""
import json
from functools import lru_cache
from pathlib import Path
import numpy as np
from matplotlib.patches import Polygon, Circle
from matplotlib.colors import to_rgba

@lru_cache(maxsize=1)
def stencil_geometry():
    return json.loads((Path(__file__).resolve().parent/'assets'/'carrier_stencil.json').read_text())

def draw_carrier_stencil(ax,settings):
    geometry=stencil_geometry()
    def deck_coordinates(key):
        vertices=np.asarray(geometry[key],dtype=float).copy()
        vertices[:,0]=vertices[:,0]*geometry['deck_width_m']/95+geometry['lateral_center_m']
        vertices[:,1]=(vertices[:,1]+90)*geometry['deck_length_m']/380-geometry['stern_aft_m']
        return vertices/1852
    deck=None
    for key,color,alpha,gid in (
        ('deck_vertices_xz','#24374d',.25,'carrier-deck'),
        ('island_vertices_xz','#24374d',.25,'carrier-island')):
        patch=Polygon(deck_coordinates(key),closed=True,
                      facecolor=color,edgecolor='#858585',lw=1.2,zorder=.6)
        patch.set_facecolor(to_rgba(color,alpha))
        patch.set_gid(gid);ax.add_patch(patch)
        if key=='deck_vertices_xz':deck=patch
    if 'island_circle_xz' in geometry:
        center=np.asarray(geometry['island_circle_xz'],dtype=float)
        center[0]=center[0]*geometry['deck_width_m']/95+geometry['lateral_center_m']
        center[1]=(center[1]+90)*geometry['deck_length_m']/380-geometry['stern_aft_m']
        circle=Circle(center/1852,geometry['island_circle_radius_m']/1852,
                      fill=False,edgecolor='#858585',lw=1.2,zorder=.7)
        circle.set_gid('carrier-island-circle');ax.add_patch(circle)
    angle=np.radians(settings.runway_deg)
    forward=np.array([np.sin(angle),np.cos(angle)])
    right=np.array([np.cos(angle),-np.sin(angle)])
    origin=np.array([settings.offset_x,settings.offset_z])
    origin=origin+geometry.get('runway_visual_lateral_offset_m',0)*right
    aft=geometry['runway_aft_m'];front=geometry['runway_forward_m'];half=geometry['runway_width_m']/2
    corners=np.array([origin+along*forward+across*right for along,across in
                      ((-aft,-half),(front,-half),(front,half),(-aft,half))])/1852
    for side,indices in (('left',[0,1]),('right',[3,2])):
        line,=ax.plot(corners[indices,0],corners[indices,1],color='#ffffff',lw=1,zorder=1)
        line.set_clip_path(deck);line.set_clip_box(ax.bbox);line.set_in_layout(False)
        line.set_gid('carrier-runway-'+side)
    center=np.array([origin-aft*forward,origin+front*forward])/1852
    line,=ax.plot(center[:,0],center[:,1],color='#ffff00',lw=1,zorder=1)
    line.set_clip_path(deck)
    line.set_clip_box(ax.bbox);line.set_in_layout(False)
    line.set_gid('carrier-runway-centerline')
    markings=geometry.get('deck_markings',{})
    def runway_line(across,start,end,color,width,gid,dashes=None):
        points=np.array([origin+along*forward+across*right for along in (start,end)])/1852
        line,=ax.plot(points[:,0],points[:,1],color=color,lw=width,zorder=1)
        if dashes:line.set_linestyle(dashes)
        line.set_clip_path(deck);line.set_clip_box(ax.bbox);line.set_in_layout(False);line.set_gid(gid)
    border=markings.get('runway_border_width_m',2.5)
    pitch=markings.get('runway_block_spacing_m',18)
    block_length=markings.get('runway_block_length_m',4)
    for side in (-1,1):
        runway_line(side*(half+border),-aft,front,'#ffffff',.7,'carrier-runway-outer-edge')
        runway_line(side*(half+border+5),-aft,front,'#9aa3ad',.5,
                     'carrier-runway-guide',(0,(5,7)))
        for start in np.arange(-aft,front,pitch):
            points=np.array([origin+along*forward+across*right for along,across in
                             ((start,side*half),(min(start+block_length,front),side*half),
                              (min(start+block_length,front),side*(half+border)),
                              (start,side*(half+border)))])/1852
            patch=Polygon(points,closed=True,facecolor='#ffffff',edgecolor='none',zorder=1)
            patch.set_clip_path(deck);patch.set_clip_box(ax.bbox);patch.set_in_layout(False)
            patch.set_gid('carrier-runway-edge-block');ax.add_patch(patch)
