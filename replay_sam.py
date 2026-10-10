"""Observed SAM launchers and exposed boundaries of their threat circles."""
import re
import numpy as np

SAM_RANGES={'FIM92':2500/1852,'9M311':4.3,'BSM66':12.,'ASMRM':20.,
            'BSM66LR':27.,'FLKM100':24.,'FLKM100LR':27.,'MAD4':33.,'MAD4LR':32.,
            'SLIR1':1.7,'RIM118':1.2,'ASM66':26.,'ASM66LR':32.}
SAM_COLOR='#ff5575'

def sam_missile_key(name):
    name=re.sub(r'[^A-Z0-9]','',name.upper())
    if name.startswith('ASMRM'):return 'ASMRM'
    return name if name in SAM_RANGES else None

def sam_range(name):
    return SAM_RANGES.get(sam_missile_key(name))

def compatible_launcher(missile,launcher):
    if launcher['type'] not in (2,3):return False
    key=sam_missile_key(missile);name=re.sub(r'[^A-Z0-9]','',launcher['name'].upper())
    if key=='FIM92':return 'MANPADS' in name
    if key=='9M311':return name=='SAAW'
    if key=='SLIR1':return name=='IRAPC'
    if key=='RIM118':return name=='IRMDLAUNCHER'
    if key=='ASMRM':return name=='SLMRMLAUNCHER'
    if key and key.startswith('MAD4'):return name=='MAD4LAUNCHER'
    if key:return name in ('SAMBATTERY','SAMLAUNCHERP')
    return False

def sam_sources(tracks):
    result={};launchers=[t for t in tracks if t['type'] in (2,3)]
    for missile in tracks:
        if missile['type']!=6 or sam_range(missile['name']) is None:continue
        row=missile['rows'][0];time=row[0];position=row[1:4];candidates=[]
        for launcher in launchers:
            if not compatible_launcher(missile['name'],launcher):continue
            rows=launcher['rows']
            if not rows[0,0]<=time<=rows[-1,0]:continue
            location=np.array([np.interp(time,rows[:,0],rows[:,axis]) for axis in (1,2,3)])
            distance=float(np.linalg.norm(location-position))
            candidates.append((distance,launcher['id']))
        candidates.sort()
        if candidates and candidates[0][0]<=25 and (len(candidates)==1 or candidates[1][0]-candidates[0][0]>=5):
            result[missile['id']]=candidates[0][1]
    return result

def threat_circle_segments(centers,radii):
    """Return only circle arcs outside every other threat disc, in world NM."""
    centers=np.asarray(centers,dtype=float).reshape(-1,3);radii=np.asarray(radii,dtype=float)
    segments=[];tau=2*np.pi
    for i,(center,radius) in enumerate(zip(centers,radii)):
        hidden=[];covered=False
        for j,(other,r) in enumerate(zip(centers,radii)):
            if i==j:continue
            delta=other[[0,2]]-center[[0,2]];distance=np.linalg.norm(delta)
            if distance<1e-10 and abs(radius-r)<1e-10:
                if j<i:covered=True;break
                continue
            if distance+radius<=r+1e-10:covered=True;break
            if distance>=radius+r or distance+r<=radius:continue
            angle=np.arctan2(delta[1],delta[0])%tau
            half=np.arccos(np.clip((distance**2+radius**2-r**2)/(2*distance*radius),-1,1))
            start=(angle-half)%tau;stop=(angle+half)%tau
            hidden.extend([(start,stop)] if start<=stop else [(0,stop),(start,tau)])
        if covered:continue
        cursor=0.;visible=[]
        for start,stop in sorted(hidden):
            if start>cursor:visible.append((cursor,start))
            cursor=max(cursor,stop)
        if cursor<tau:visible.append((cursor,tau))
        for start,stop in visible:
            angles=np.linspace(start,stop,max(2,int(np.ceil((stop-start)/np.radians(2)))+1))
            points=np.tile(center,(len(angles),1))
            points[:,0]+=radius*np.cos(angles);points[:,2]+=radius*np.sin(angles)
            segments.extend(np.stack((points[:-1],points[1:]),axis=1))
    return np.asarray(segments,dtype=float).reshape(-1,2,3)
