"""Shared age-based trail segments and opacity for replay views."""
import numpy as np
from matplotlib.colors import to_rgba

def trail_colors(color,alpha,opacity):
    colors=np.tile(to_rgba(color),(len(alpha),1));colors[:,3]*=opacity*alpha
    return colors

def trail_segments(data,cursor,length,fade):
    """Fade the oldest part of the trail within its total selected duration."""
    if length<0:return np.empty((0,2,2)),np.empty(0)
    aircraft=data.get('category') in ('friendly','enemy')
    if aircraft:
        current=min(max(int(np.searchsorted(data['time'],cursor,side='right'))-1,0),len(data['speed'])-1)
        if data['speed'][current]<1:return np.empty((0,2,2)),np.empty(0)
    fade=min(fade,length) if length>0 else 0
    start=data['time'][0] if length==0 else max(data['time'][0],cursor-length)
    end=min(cursor,data['time'][-1])
    if end<=start:return np.empty((0,2,2)),np.empty(0)
    left=np.searchsorted(data['trail_time'],start,side='right');right=np.searchsorted(data['trail_time'],end,side='left')
    times=np.r_[start,data['trail_time'][left:right],end]
    if length>0 and fade>0:
        fade_end=min(end,cursor-length+fade)
        if fade_end>start:times=np.unique(np.r_[times,np.linspace(start,fade_end,12)])
    points=np.column_stack((np.interp(times,data['time'],data['x']),np.interp(times,data['time'],data['y'])))
    segments=np.stack((points[:-1],points[1:]),axis=1)
    valid=np.isfinite(segments).all(axis=(1,2))
    # Interpolated boundaries must not reconnect a teleport.
    for index in data['breaks']:
        valid&=~((times[:-1]<data['time'][index])&(times[1:]>data['time'][index-1]))
    if aircraft:
        # Never paint parked portions into a departing aircraft's trail.
        interval=np.clip(np.searchsorted(data['time'],(times[:-1]+times[1:])/2,side='right')-1,0,len(data['speed'])-1)
        valid&=data['speed'][interval]>=1
    age=cursor-(times[:-1]+times[1:])/2
    alpha=np.ones(len(age)) if fade==0 else np.clip((length-age)/fade,0,1)
    # A LineCollection creates a Matplotlib Path for each entry. Group opaque
    # runs and small fade bands into polylines rather than one Path per edge.
    indices=np.flatnonzero(valid)
    if not len(indices):return [],np.empty(0)
    bands=np.floor(alpha*16).astype(int)
    split=(np.diff(indices)>1)|(bands[indices[1:]]!=bands[indices[:-1]])
    boundaries=np.r_[0,np.flatnonzero(split)+1,len(indices)]
    paths=[];opacity=[]
    for left,right in zip(boundaries[:-1],boundaries[1:]):
        run=indices[left:right];paths.append(points[run[0]:run[-1]+2]);opacity.append(float(np.mean(alpha[run])))
    return paths,np.asarray(opacity)

