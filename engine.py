"""Carrier-relative geometry and exploratory recovery detection."""
from dataclasses import dataclass, asdict
import json, re
from pathlib import Path
import numpy as np
from reader import quaternion_candidate

@dataclass
class Settings:
    offset_x: float = 7.0
    offset_y: float = 5.7
    offset_z: float = -50.0
    glide_deg: float = 3.5
    runway_deg: float = -10.0
    graph_range_nm: float = 1.25
    limit_outline_opacity: float = 0.50
    limit_shading_opacity: float = 0.10
    limit_center_opacity: float = 0.40
    start_end_opacity: float = 0.60
    show_graph_key: bool = True
    show_timestamp: bool = False
    random_animations: bool = True
    random_animation_frequency_sec: float = 60.0
    animation_opacity: float = 0.60
    animation_approach: bool = True
    animation_scores: bool = True
    animation_editor: bool = True
    animation_settings: bool = True
    replay_procedure_opacity: float = 0.60
    replay_trail_fade_sec: float = 30.0
    replay_trail_length_sec: float = 180.0
    graph_line_width: float = 1.0
    glide_tolerance_deg: float = 0.7
    localizer_tolerance_deg: float = 2.5
    wind_x: float = 0.0
    wind_y: float = 0.0
    wind_z: float = 0.0
    aoa_min_deg: float = 4.0
    aoa_max_deg: float = 12.0
    show_data_points: bool = False
    editor_radius_nm: float = 10.0
    editor_interpolated: bool = False
    scoring_loc_points: float = 1000.0
    scoring_glide_points: float = 1000.0
    scoring_aoa_points: float = 1000.0
    scoring_bolter_points: float = 0.0
    scoring_wire1_points: float = 250.0
    scoring_wire2_points: float = 750.0
    scoring_wire3_points: float = 1000.0
    scoring_wire4_points: float = 500.0
    scoring_changeover_nm: float = 0.08
    recovery_case: int = 1
    case3_graph_range_nm: float = 11.0
    case3_platform_alt_ft: float = 300.0
    case3_platform_speed_knots: float = 50.0
    case3_feather_nm: float = 1.0  # Legacy saved setting; no longer used.
    case3_speed_deadzone_nm: float = 1.0
    case3_speed_changeover_shift_nm: float = 0.25
    case3_leg1_speed_knots: float = 250.0
    case3_leg2_speed_knots: float = 200.0
    case3_platform_start_nm: float = 8.5
    case3_platform_end_nm: float = 3.25
    scoring_case3_position_points: float = 1000.0
    scoring_case3_speed_points: float = 1000.0
    scoring_case3_loc_points: float = 1000.0
    scoring_case3_glide_points: float = 1000.0
    scoring_case3_aoa_points: float = 1000.0
    case1_glide_start_nm: float = 0.75
    case3_glide_start_nm: float = 2.25

    def validate(self):
        if not 1<=self.random_animation_frequency_sec<=86400:raise ValueError('Random Animation Frequency must be between 1 and 86,400 seconds.')
        if not 0<=self.animation_opacity<=1:raise ValueError('Animation Opacity must be between 0% and 100%.')
        if not 0<=self.replay_procedure_opacity<=1:raise ValueError('Procedure Markings opacity must be between 0% and 100%.')
        if not 0<=self.replay_trail_fade_sec<=3600:raise ValueError('Trail Fade must be between 0 and 3,600 seconds.')
        if self.replay_trail_length_sec!=-1 and not 0<=self.replay_trail_length_sec<=7200:raise ValueError('Replay trail length must be None or between 0 and 7,200 seconds.')
        if not all(np.isfinite(v) for v in asdict(self).values()): raise ValueError('All values must be finite numbers.')
        if not 0.1 <= self.glide_deg <= 15: raise ValueError('Glide slope must be between 0.1° and 15°.')
        if not -180 <= self.runway_deg <= 180: raise ValueError('Runway offset must be between −180° and 180°.')
        if any(not 0<=getattr(self,key)<=1 for key in ('limit_outline_opacity','limit_shading_opacity','limit_center_opacity','start_end_opacity')):raise ValueError('Limit opacity must be between 0% and 100%.')
        if not .5<=self.graph_line_width<=5:raise ValueError('Line thickness must be between 0.5 and 5.')
        if not .1 <= self.graph_range_nm <= 10: raise ValueError('Graph range must be between 0.1 and 10 NM.')
        if not 0 < self.glide_tolerance_deg < 10 or not 0 < self.localizer_tolerance_deg < 30: raise ValueError('Graph envelope angles must be positive and below 10° / 30°.')
        if max(abs(self.offset_x),abs(self.offset_y),abs(self.offset_z))>10000:raise ValueError('Carrier offsets must be within ±10,000 units.')
        if max(abs(self.wind_x),abs(self.wind_y),abs(self.wind_z))>200:raise ValueError('Wind components must be within ±200 m/s.')
        if not -180 <= self.aoa_min_deg < self.aoa_max_deg <= 180:raise ValueError('AoA minimum must be below maximum, both within −180° to 180°.')
        if not .05 <= self.editor_radius_nm <= 200:raise ValueError('Editor map radius must be between 0.05 and 200 NM.')
        if not .01<=self.scoring_changeover_nm<=10:raise ValueError('Scoring change-over must be between 0.01 and 10 NM.')
        if self.recovery_case not in (1,3):raise ValueError('Recovery case must be 1 or 3.')
        if not .1<=self.case3_graph_range_nm<=20:raise ValueError('Case 3 graph range must be between 0.1 and 20 NM.')
        if not 0<=self.case1_glide_start_nm<=10:raise ValueError('Case 1 Glide Start must be between 0 and 10 NM.')
        if not 0<self.case3_glide_start_nm<=3:raise ValueError('Case 3 Glide Start must be positive and at most 3 NM.')
        start=self.case3_glide_start_nm if self.recovery_case==3 else self.case1_glide_start_nm
        if start>0 and self.scoring_changeover_nm>=start:raise ValueError('Glide End must be closer to the carrier than Glide Start.')
        if not 0<self.case3_platform_alt_ft<=60761.155:raise ValueError('Case 3 altitude limit must be positive and at most 60,761 ft.')
        if not 0<self.case3_platform_speed_knots<=1000:raise ValueError('Case 3 platform speed limit must be positive and at most 1,000 knots.')
        if not 0<self.case3_leg1_speed_knots<=1000 or not 0<self.case3_leg2_speed_knots<=1000:raise ValueError('Leg speeds must be positive and at most 1,000 knots.')
        if not 3<=self.case3_platform_end_nm<self.case3_platform_start_nm<=10:raise ValueError('Platform boundaries must have 3 ≤ Platform End < Platform Start ≤ 10 NM.')
        if self.case3_platform_end_nm<self.case3_glide_start_nm:raise ValueError('Platform End must be at or farther out than Case 3 Glide Start.')
        near,far=speed_deadzone_bounds(self)
        if self.case3_platform_start_nm<=far and self.case3_platform_end_nm>=near:raise ValueError('The speed deadzone must leave some platform distance available for speed grading.')
        if not 0<=self.case3_feather_nm<=7:raise ValueError('Case 3 limit feathering must be between 0 and 7 NM.')
        if not 0<=self.case3_speed_deadzone_nm<=6:raise ValueError('Speed Change Deadzone must be between 0 and 6 NM (total width).')
        if not 3<=near<=far<=10:raise ValueError('Speed changeover shift and deadzone must place the deadzone between 3 and 10 NM.')
        if any(not 0<=getattr(self,name)<=1e6 for name in self.__dataclass_fields__ if name.startswith('scoring_') and name.endswith('_points')):
            raise ValueError('Scoring points must be between 0 and 1,000,000.')

    @classmethod
    def load(cls,path):
        try:
            data=json.loads(Path(path).read_text())
            if 'case3_platform_alt_ft' not in data and 'case3_platform_alt_nm' in data:
                data['case3_platform_alt_ft']=float(data['case3_platform_alt_nm'])*1852*3.280839895
            s=cls(**{k:v for k,v in data.items() if k in cls.__dataclass_fields__});s.validate();return s
        except (OSError,ValueError,TypeError): return cls()

    def save(self,path):
        self.validate();p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
        tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(asdict(self),indent=2));tmp.replace(p)

def speed_deadzone_bounds(settings):
    """Center the ungraded band on 6 NM plus the shift; positive moves left."""
    center=6+settings.case3_speed_changeover_shift_nm
    half=settings.case3_speed_deadzone_nm/2
    return center-half,center+half

@dataclass
class Attempt:
    player: str
    aircraft: str
    entity_id: int
    start: float
    end: float
    closest: float
    status: str
    time: np.ndarray
    distance: np.ndarray
    height: np.ndarray
    lateral: np.ndarray
    aoa: np.ndarray
    world_altitude: np.ndarray = None
    anchor_time: float = 0.0
    edit_id: str = ''
    groundspeed_knots: np.ndarray = None

    def summary(self):
        return dict(player=self.player,aircraft=self.aircraft,entity_id=self.entity_id,start=self.start,end=self.end,closest=self.closest,status=self.status)

    def intercept(self):
        """First descending 600-ft world-altitude crossing; do not bridge replay gaps."""
        if self.world_altitude is None:return None
        altitude=np.asarray(self.world_altitude);target=600/3.280839895
        crossings=np.flatnonzero((altitude[:-1]>=target)&(altitude[1:]<target))
        for i in crossings:
            if self.time[i+1]-self.time[i]>3:continue
            fraction=(altitude[i]-target)/(altitude[i]-altitude[i+1])
            def at(values):return float(values[i]+fraction*(values[i+1]-values[i]))
            distance=at(self.distance)
            if distance<0:continue
            return dict(time=at(self.time),distance=distance,height=at(self.height),
                        lateral=at(self.lateral),aoa=at(self.aoa))
        return None


def clean_rows(rows):
    # Keep the last sample of each identical/near-identical timestamp.
    return rows[np.r_[np.diff(rows[:,0])>1e-5,True]]


def rotate(q,v):
    xyz=q[...,:3];w=q[...,3,None]
    return v+2*np.cross(xyz,np.cross(xyz,v)+w*v)


def inverse(q):
    r=q.copy();r[...,:3]*=-1;return r


def glide_origin_msl_ft(carrier,settings):
    """Freeze reference altitude at the carrier's first pose, for comparable plots."""
    offset=np.array([settings.offset_x,settings.offset_y,settings.offset_z])
    if carrier is None:return float(offset[1]*3.280839895)
    row=clean_rows(carrier['rows'])[0]
    q=quaternion_candidate(np.array([row[7]]))[0]
    origin=row[1:4]+rotate(q,offset)
    return float(origin[1]*3.280839895)


def target_intercept_nm(settings,origin_msl_ft):
    """Where the configured glide centerline meets 600 ft MSL, in horizontal NM."""
    if origin_msl_ft>600:return None
    return float((600-origin_msl_ft)/(3.280839895*1852*np.tan(np.radians(settings.glide_deg))))

def glide_start_nm(settings,origin_msl_ft):
    if settings.recovery_case==3:return settings.case3_glide_start_nm
    return settings.case1_glide_start_nm or target_intercept_nm(settings,origin_msl_ft)

def approach_reference(settings,distance,origin_msl_ft):
    """Fixed approach geometry in metres, independent of grading boundaries."""
    d=np.asarray(distance,dtype=float);origin=origin_msl_ft/3.280839895
    slope=np.tan(np.radians(settings.glide_deg))
    final=origin+slope*d
    low=origin+np.tan(np.radians(settings.glide_deg-settings.glide_tolerance_deg))*d
    high=origin+np.tan(np.radians(settings.glide_deg+settings.glide_tolerance_deg))*d
    loc=np.tan(np.radians(settings.localizer_tolerance_deg))*d
    if settings.recovery_case!=3:return dict(center=final,lower=low,upper=high,loc_width=loc)
    platform=d>3*1852;alt=1200/3.280839895
    return dict(center=np.where(platform,alt,final),
                lower=np.where(platform,alt-settings.case3_platform_alt_ft/3.280839895,low),
                upper=np.where(platform,alt+settings.case3_platform_alt_ft/3.280839895,high),
                loc_width=loc)



def interpolate_quaternions(times, q, target):
    if len(times)==1:return np.broadcast_to(q[0],(len(target),4)).copy()
    i=np.clip(np.searchsorted(times,target,side='right')-1,0,len(times)-2)
    f=np.clip((target-times[i])/(times[i+1]-times[i]),0,1)
    a=q[i];b=q[i+1].copy();dot=np.sum(a*b,axis=1);b[dot<0]*=-1;dot=np.abs(dot)
    theta=np.arccos(np.clip(dot,-1,1));den=np.sin(theta)
    near=den<1e-5;den[near]=1
    result=(np.sin((1-f)*theta)/den)[:,None]*a+(np.sin(f*theta)/den)[:,None]*b
    result[near]=(1-f[near,None])*a[near]+f[near,None]*b[near]
    return result/np.linalg.norm(result,axis=1,keepdims=True)


def velocity_from_positions(rows,max_gap=3):
    t=rows[:,0];v=np.column_stack([np.gradient(rows[:,j],t) for j in (1,2,3)])
    dt=np.diff(t);interval_speed=np.linalg.norm(np.diff(rows[:,1:4],axis=0),axis=1)/dt
    bad=(dt>max_gap)|(interval_speed>650)
    invalid=np.r_[bad,False]|np.r_[False,bad]
    v[invalid]=np.nan
    return v

def black_box_data(track,attempt):
    """Motion diagnostics; attitude uses the existing candidate rotation decoder."""
    rows=clean_rows(track['rows']);velocity=velocity_from_positions(rows)
    q=quaternion_candidate(rows[:,7])
    forward=rotate(q,np.broadcast_to([0.,0.,1.],(len(rows),3)))
    right=rotate(q,np.broadcast_to([1.,0.,0.],(len(rows),3)))
    up=rotate(q,np.broadcast_to([0.,1.,0.],(len(rows),3)))
    horizontal=np.linalg.norm(velocity[:,[0,2]],axis=1)
    angle=np.degrees(np.arctan2(velocity[:,1],horizontal));angle[horizontal<5]=np.nan
    keep=(rows[:,0]>=attempt.start)&(rows[:,0]<=attempt.end)
    return dict(distance=np.interp(rows[keep,0],attempt.time,attempt.distance)/1852,
                vertical_speed=velocity[keep,1]*3.280839895*60,
                flight_path=angle[keep],pitch=np.degrees(np.arcsin(np.clip(forward[keep,1],-1,1))),
                bank=np.degrees(np.arctan2(-right[keep,1],up[keep,1])))

def groundspeed_from_positions(rows):
    """World-horizontal speed, including ship travel; never infer airspeed."""
    velocity=velocity_from_positions(rows,max_gap=20)
    return np.linalg.norm(velocity[:,[0,2]],axis=1)*3600/1852


def player_label(name):
    # Multi-crew entries remain together rather than attributing a flight to the wrong person.
    m=re.search(r'\(([^()]*)\)\s*$',name)
    return m.group(1).strip() if m else name


def aircraft_label(name):
    return re.sub(r'\s*\([^()]*\)\s*$','',name).strip()


def inbound_groups(rows,distance,good):
    """Bridge sparse recorded keyframes, but not intervening maneuvers or teleports."""
    indices=np.flatnonzero(good)
    if not len(indices):return []
    left=indices[:-1];right=indices[1:];dt=rows[right,0]-rows[left,0]
    gap=dt>8
    # A longer gap can be a single replay keyframe interval during steady flight.
    # Only bridge adjacent raw samples with plausible inbound displacement.
    sparse=(right==left+1)&(dt<=20)
    rate=(distance[left]-distance[right])/dt
    speed=np.linalg.norm(rows[right,1:4]-rows[left,1:4],axis=1)/dt
    continuous=sparse&(rate>20)&(rate<350)&(speed<350)
    return np.split(indices,np.flatnonzero(gap&~continuous)+1)


def full_track(track,carrier,settings):
    """All recorded samples with carrier-relative geometry; no artificial aircraft points."""
    cr=clean_rows(carrier['rows']);r=clean_rows(track['rows'])
    r=r[(r[:,0]>=cr[0,0])&(r[:,0]<=cr[-1,0])]
    if len(r)<2:raise ValueError('This track has fewer than two samples overlapping the carrier log.')
    t=r[:,0];cp=np.column_stack([np.interp(t,cr[:,0],cr[:,j]) for j in (1,2,3)])
    q=interpolate_quaternions(cr[:,0],quaternion_candidate(cr[:,7]),t)
    ship_local=rotate(inverse(q),r[:,1:4]-cp)
    local=ship_local-np.array([settings.offset_x,settings.offset_y,settings.offset_z])
    angle=np.radians(settings.runway_deg)
    d=-(np.sin(angle)*local[:,0]+np.cos(angle)*local[:,2])
    lateral=np.cos(angle)*local[:,0]-np.sin(angle)*local[:,2]
    world_v=velocity_from_positions(r)-np.array([settings.wind_x,settings.wind_y,settings.wind_z])
    body_v=rotate(inverse(quaternion_candidate(r[:,7])),world_v)
    aoa=np.degrees(np.arctan2(-body_v[:,1],body_v[:,2]))
    aoa[(np.linalg.norm(world_v,axis=1)<25)|(body_v[:,2]<10)]=np.nan
    return dict(track=track,rows=r,time=t,distance=d,height=local[:,1],lateral=lateral,
                aoa=aoa,world_altitude=r[:,2],groundspeed_knots=groundspeed_from_positions(r),map_x=ship_local[:,0]/1852,map_y=ship_local[:,2]/1852)


def attempt_from_range(data,start,end,anchor_time=None,edit_id='',status='Manual attempt'):
    t=data['time']
    if not np.isfinite(start) or not np.isfinite(end) or not t[0]<=start<end<=t[-1]:
        raise ValueError('Start/stop must be ordered and within one recorded aircraft track.')
    mask=(t>=start)&(t<=end)
    if mask.sum()<2:raise ValueError('An attempt needs at least two recorded samples. Widen the interval.')
    tr=data['track'];nearest=np.argmin(np.hypot(data['distance'][mask],data['lateral'][mask]))
    if anchor_time is None:anchor_time=float(t[mask][nearest])
    return Attempt(player_label(tr['name']),aircraft_label(tr['name']),tr['id'],float(start),float(end),
                   float(np.hypot(data['distance'][mask],data['lateral'][mask])[nearest]),status,
                   t[mask],data['distance'][mask],data['height'][mask],data['lateral'][mask],
                   data['aoa'][mask],data['world_altitude'][mask],anchor_time,edit_id,data.get('groundspeed_knots',np.full(len(t),np.nan))[mask])


def analyze(tracks,carrier,settings):
    settings.validate();cr=clean_rows(carrier['rows'])
    cq=quaternion_candidate(cr[:,7]);attempts=[]
    offset=np.array([settings.offset_x,settings.offset_y,settings.offset_z]);angle=np.radians(settings.runway_deg)
    for tr in tracks:
        if tr['type']!=0 or '(' not in tr['name']:continue
        # First version focuses on conventional jet approaches, not vertical recoveries.
        if any(s in tr['name'].upper() for s in ('AV-42','AH-94','AH-99')):continue
        r=clean_rows(tr['rows']);r=r[(r[:,0]>=cr[0,0])&(r[:,0]<=cr[-1,0])]
        if len(r)<12:continue
        t=r[:,0];cp=np.column_stack([np.interp(t,cr[:,0],cr[:,j]) for j in (1,2,3)])
        q=interpolate_quaternions(cr[:,0],cq,t)
        local=rotate(inverse(q),r[:,1:4]-cp)-offset
        # Landing area forward = sin(offset)*carrier right + cos(offset)*carrier forward.
        along=np.sin(angle)*local[:,0]+np.cos(angle)*local[:,2]
        lateral=np.cos(angle)*local[:,0]-np.sin(angle)*local[:,2]
        d=-along;h=local[:,1]
        closing=-np.gradient(d,t)
        detection_range=10*1852+200 if settings.recovery_case==3 else 6000.0
        good=(d>0)&(d<detection_range)&(h>-25)&(h<650)&(np.abs(lateral)<np.maximum(350,d*.35))&(closing>20)&(closing<350)
        ii=np.flatnonzero(good)
        if not len(ii):continue
        # Brief corrections and sparse, physically consistent keyframes can stay together.
        groups=inbound_groups(r,d,good)
        world_v=velocity_from_positions(r)-np.array([settings.wind_x,settings.wind_y,settings.wind_z])
        aircraft_q=quaternion_candidate(r[:,7]);body_v=rotate(inverse(aircraft_q),world_v)
        aoa=np.degrees(np.arctan2(-body_v[:,1],body_v[:,2]))
        aoa[(np.linalg.norm(world_v,axis=1)<25)|(body_v[:,2]<10)]=np.nan
        for group in groups:
            a,b=int(group[0]),int(group[-1])
            if len(group)<12 or t[b]-t[a]<4 or np.ptp(d[group])<350:continue
            # Detection can begin below 600 ft after a lateral/control correction.
            # Include an earlier crossing only along the same continuous inbound leg.
            target=600/3.280839895
            prior=np.flatnonzero((r[:-1,2]>=target)&(r[1:,2]<target)
                                 &(t[:-1]<t[a])&(t[:-1]>=t[a]-90))
            for i in (prior[::-1] if settings.recovery_case==1 else []):
                segment=slice(i,a+1)
                if (d[i]>d[a] and 0<d[i]<=detection_range
                    and np.all(d[segment]>0) and np.max(d[segment])<=d[i]+150
                    and np.all(np.diff(t[segment])<=3)):
                    a=int(i);break
            if settings.recovery_case==3:
                # Include the outer boundary's bracketing sample, even if a
                # later final fragment triggered detection. Do not cross outages.
                while a>0 and d[a]<10*1852:
                    dt=t[a]-t[a-1];dd=d[a-1]-d[a]
                    if dt<=0 or dt>20 or dd<=0 or dd/dt>350:break
                    a-=1
            # Search near the end for a close pass, including threshold/deck crossing.
            future=np.arange(a,min(len(t),np.searchsorted(t,t[b]+18,side='right')))
            close=future[(np.abs(d[future])<600)&(np.abs(lateral[future])<220)&(h[future]>-30)&(h[future]<120)]
            if not len(close):continue
            nearest=int(close[np.argmin(np.hypot(d[close],lateral[close]))])
            end=min(len(t),np.searchsorted(t,t[nearest]+15,side='right'))
            idx=np.arange(a,end)
            if len(idx)<2:continue
            late=idx[(t[idx]>=t[nearest])&(t[idx]<t[nearest]+12)]
            # Derived relative displacement; statuses are explicitly estimates.
            rs=np.linalg.norm(np.column_stack([np.gradient(local[:,j],t) for j in range(3)]),axis=1)
            slow=late[(rs[late]<8)&(np.abs(h[late])<10)&(np.abs(lateral[late])<120)]
            status='Possible recovery' if len(slow)>=3 else ('Deck crossing / pass' if np.min(np.abs(d[close]))<80 else 'Close approach / wave-off')
            attempts.append(Attempt(player_label(tr['name']),aircraft_label(tr['name']),tr['id'],float(t[a]),float(t[end-1]),float(np.min(np.hypot(d[close],lateral[close]))),status,t[idx],d[idx],h[idx],lateral[idx],aoa[idx],r[idx,2],float(t[nearest]),groundspeed_knots=groundspeed_from_positions(r)[idx]))
    # Merge only overlapping detections of the same track (not distinct bolters).
    attempts.sort(key=lambda a:(a.player.casefold(),a.start))
    result=[]
    for a in attempts:
        if result and result[-1].entity_id==a.entity_id and a.start<=result[-1].end:
            prev=result[-1]
            if a.closest<prev.closest:result[-1]=a
        else:result.append(a)
    return result


def last_attempts(attempts):
    last={}
    for a in attempts:
        key=a.player.casefold()
        if key not in last or a.start>last[key].start:last[key]=a
    return sorted(last.values(),key=lambda a:(a.player.casefold(),a.start))


def clock(seconds):
    seconds=int(seconds);return f'{seconds//3600:02}:{seconds//60%60:02}:{seconds%60:02}'


def auto_bolter(attempt):
    """Low deck pass followed by continuous flight more than 0.35 NM away."""
    t=np.asarray(attempt.time);d=np.asarray(attempt.distance)
    h=np.asarray(attempt.height);l=np.asarray(attempt.lateral)
    armed=False
    for i in range(len(t)-1):
        dt=t[i+1]-t[i]
        values=np.array([d[i],d[i+1],h[i],h[i+1],l[i],l[i+1]])
        if dt<=0 or dt>20 or not np.isfinite(values).all():
            armed=False;continue
        speed=float(np.linalg.norm([d[i+1]-d[i],h[i+1]-h[i],l[i+1]-l[i]])/dt)
        if armed and speed<8:return False
        if speed>350 or speed<8:
            armed=False;continue
        # Use the closest point on an inbound segment, including sparse keyframes.
        if d[i]>d[i+1] and d[i]>0 and d[i+1]<185.2:
            fraction=float(np.clip(d[i]/(d[i]-d[i+1]),0,1))
            distance=d[i]+fraction*(d[i+1]-d[i])
            height=h[i]+fraction*(h[i+1]-h[i])
            lateral=l[i]+fraction*(l[i+1]-l[i])
            if abs(distance)<=185.2 and abs(lateral)<=60 and -10<=height<=15:
                armed=True
        if armed and d[i+1]<0 and np.hypot(d[i+1],l[i+1])>0.35*1852:return True
        if armed and d[i+1]>185.2:armed=False
    return False
