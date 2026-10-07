"""Distance-weighted linear approach scores; no scores until a wire is assigned."""
from dataclasses import dataclass
import numpy as np
from engine import glide_start_nm,approach_reference

WIRE_FIELDS={'Bolter':'scoring_bolter_points','1':'scoring_wire1_points',
             '2':'scoring_wire2_points','3':'scoring_wire3_points','4':'scoring_wire4_points'}

@dataclass
class Score:
    loc: float
    glide: float
    aoa: float
    wire: float
    total: float
    complete: bool
    coverage: dict
    sampled: float
    aoa_interpolated: float
    start_nm: float
    end_nm: float
    note: str = ''
    position: float = 0.0
    speed: float = 0.0

def approach_maximum(settings,case=None):
    case=settings.recovery_case if case is None else case
    if case==3:return sum(getattr(settings,'scoring_case3_'+key+'_points') for key in ('position','speed','loc','glide','aoa'))
    return settings.scoring_loc_points+settings.scoring_glide_points+settings.scoring_aoa_points

def maximum(settings):
    return approach_maximum(settings)+max(getattr(settings,field) for field in WIRE_FIELDS.values())

def score_attempt(attempt,wire,settings,origin_msl_ft):
    if settings.recovery_case==3:return score_case3(attempt,wire,settings,origin_msl_ft)
    return score_case1(attempt,wire,settings,origin_msl_ft)

def score_case1(attempt,wire,settings,origin_msl_ft):
    if wire not in WIRE_FIELDS:return None
    wire_score=getattr(settings,WIRE_FIELDS[wire]);upper=glide_start_nm(settings,origin_msl_ft);lower=settings.scoring_changeover_nm
    if upper is None or upper<=lower:
        return Score(0,0,0,wire_score,wire_score,False,dict(loc=0,glide=0,aoa=0),0,0,upper or 0,lower,
                     'Glide End must be closer to the carrier than Glide Start.')
    # Uniform distance midpoints give every part of the approach equal weight,
    # independent of replay cadence, speed, or time spent correcting/reversing.
    edges=np.linspace(upper*1852,lower*1852,4097);grid=(edges[:-1]+edges[1:])/2
    count=len(grid);fractions={key:np.zeros(count) for key in ('loc','glide','aoa')}
    covered={key:np.zeros(count,dtype=bool) for key in fractions}
    traversed=np.zeros(count,dtype=bool);sampled=np.zeros(count,dtype=bool);interpolated=np.zeros(count,dtype=bool)
    d=np.asarray(attempt.distance);t=np.asarray(attempt.time)
    altitude=(np.asarray(attempt.world_altitude)-origin_msl_ft/3.280839895) if attempt.world_altitude is not None else np.asarray(attempt.height)
    aoa=np.asarray(attempt.aoa);known=np.flatnonzero(np.isfinite(aoa))
    filled=np.interp(t,t[known],aoa[known],left=np.nan,right=np.nan) if len(known)>=2 else aoa.copy()
    slope=np.tan(np.radians(settings.glide_deg))
    up=np.tan(np.radians(settings.glide_deg+settings.glide_tolerance_deg))-slope
    down=slope-np.tan(np.radians(settings.glide_deg-settings.glide_tolerance_deg))
    loc_width=np.tan(np.radians(settings.localizer_tolerance_deg))
    for i in range(len(d)-1):
        dt=t[i+1]-t[i];dd=d[i]-d[i+1]
        if not np.isfinite(dd) or dd<=0 or dt<=0 or dt>20 or dd/dt>350:continue
        keep=(grid<=d[i])&(grid>=d[i+1])&~traversed
        if not keep.any():continue
        traversed[keep]=True;x=grid[keep];f=(d[i]-x)/dd
        def between(values):return values[i]+f*(values[i+1]-values[i])
        lateral=between(attempt.lateral);height=between(altitude);alpha=between(filled)
        error=height-slope*x;glide_width=np.where(error>=0,up*x,down*x)
        errors={'loc':abs(lateral)/(loc_width*x),'glide':abs(error)/glide_width,'aoa':abs(alpha-8)/5}
        for key,normalized in errors.items():
            valid=np.isfinite(normalized)
            indices=np.flatnonzero(keep)[valid];covered[key][indices]=True
            fractions[key][indices]=np.clip(1-normalized[valid],0,1)
        if dt<=3:sampled[keep]=True
        if dt>3 or not np.isfinite(aoa[i:i+2]).all():interpolated[keep]=covered['aoa'][keep]
    coverage={key:float(values.mean()) for key,values in covered.items()}
    loc=float(fractions['loc'].mean()*settings.scoring_loc_points)
    glide=float(fractions['glide'].mean()*settings.scoring_glide_points)
    aoa_score=float(fractions['aoa'].mean()*settings.scoring_aoa_points)
    enabled={'loc':settings.scoring_loc_points,'glide':settings.scoring_glide_points,'aoa':settings.scoring_aoa_points}
    complete=all(coverage[key]>=.999 for key,points in enabled.items() if points>0)
    return Score(loc,glide,aoa_score,wire_score,loc+glide+aoa_score+wire_score,complete,coverage,
                 float(sampled.mean()),float(interpolated.mean()),upper,lower,
                 '' if complete else 'Provisional: missing approach distance/data earns zero; excluded from ranked best scores.')

def score_case3(attempt,wire,settings,origin_msl_ft):
    if wire not in WIRE_FIELDS:return None
    lower=settings.scoring_changeover_nm;upper=settings.case3_glide_start_nm;wire_score=getattr(settings,WIRE_FIELDS[wire])
    if not 0<lower<upper<=3:raise ValueError('Case 3 must have 0 < Glide End < Glide Start ≤ 3 NM.')
    # Separate uniform grids preserve phase boundaries and full-distance
    # denominators. Platform speed legs are weighted by their judged distance.
    def grid(high,low,count):
        edges=np.linspace(high*1852,low*1852,count+1);return (edges[1:]+edges[:-1])/2
    platform_grid=grid(settings.case3_platform_start_nm,settings.case3_platform_end_nm,max(1,int(round((settings.case3_platform_start_nm-settings.case3_platform_end_nm)*512))))
    final_grid=grid(upper,lower,4096);distance=np.r_[platform_grid,final_grid]
    platform=np.arange(len(distance))<len(platform_grid);final=~platform
    speed_active=platform&(abs(distance/1852-6)>=settings.case3_speed_deadzone_nm/2)
    active_by_key={'position':platform,'speed':speed_active,'loc':final,'glide':final,'aoa':final}
    count=len(distance);keys=('position','speed','loc','glide','aoa')
    fractions={key:np.zeros(count) for key in keys};covered={key:np.zeros(count,dtype=bool) for key in keys}
    traversed=np.zeros(count,dtype=bool);sampled=np.zeros(count,dtype=bool);interpolated=np.zeros(count,dtype=bool)
    d=np.asarray(attempt.distance);t=np.asarray(attempt.time)
    altitude=np.asarray(attempt.world_altitude) if attempt.world_altitude is not None else np.asarray(attempt.height)+origin_msl_ft/3.280839895
    aoa=np.asarray(attempt.aoa);known=np.flatnonzero(np.isfinite(aoa))
    filled=np.interp(t,t[known],aoa[known],left=np.nan,right=np.nan) if len(known)>=2 else aoa.copy()
    speed=np.asarray(attempt.groundspeed_knots) if attempt.groundspeed_knots is not None else np.full(len(t),np.nan)
    for i in range(len(d)-1):
        dt=t[i+1]-t[i];dd=d[i]-d[i+1]
        if not np.isfinite(dd) or dd<=0 or dt<=0 or dt>20 or dd/dt>350:continue
        keep=(distance<=d[i])&(distance>=d[i+1])&~traversed
        if not keep.any():continue
        traversed[keep]=True;indices=np.flatnonzero(keep);x=distance[keep];f=(d[i]-x)/dd
        def between(values):return values[i]+f*(values[i+1]-values[i])
        lateral=between(attempt.lateral);height=between(altitude);alpha=between(filled);knots=between(speed)
        ref=approach_reference(settings,x,origin_msl_ft);error=height-ref['center']
        alt_width=np.where(error>=0,ref['upper']-ref['center'],ref['center']-ref['lower'])
        # Nonpositive asymmetric widths can occur with extreme edited geometry.
        # On the exact target credit is still one; any error on a closed side is zero.
        def credit(error,width):
            ratio=np.divide(abs(error),width,out=np.full_like(error,np.inf),where=width>0)
            ratio=np.where(abs(error)<1e-9,0,ratio)
            return np.clip(1-ratio,0,1)
        loc_credit=credit(lateral,ref['loc_width']);alt_credit=credit(error,alt_width)
        values={'position':(loc_credit+alt_credit)/2,'speed':np.clip(1-abs(knots-np.where(x>=6*1852,settings.case3_leg1_speed_knots,settings.case3_leg2_speed_knots))/settings.case3_platform_speed_knots,0,1),
                'loc':loc_credit,'glide':alt_credit,'aoa':np.clip(1-abs(alpha-8)/5,0,1)}
        for key,value in values.items():
            active=active_by_key[key][indices]
            valid=active&np.isfinite(value)
            covered[key][indices[valid]]=True;fractions[key][indices[valid]]=value[valid]
        if dt<=3:sampled[keep]=True
        if dt>3 or not np.isfinite(aoa[i:i+2]).all():interpolated[keep]=covered['aoa'][keep]
    coverage={key:float(covered[key][active_by_key[key]].mean()) for key in keys}
    points={key:float(fractions[key][active_by_key[key]].mean()*getattr(settings,'scoring_case3_'+key+'_points')) for key in keys}
    complete=all(coverage[key]>=.999 for key in keys if getattr(settings,'scoring_case3_'+key+'_points')>0)
    return Score(points['loc'],points['glide'],points['aoa'],wire_score,sum(points.values())+wire_score,complete,coverage,
                 float(sampled.mean()),float(interpolated[final].mean()),settings.case3_platform_start_nm,lower,
                 '' if complete else 'Provisional: missing platform/final data earns zero; excluded from ranked best scores.',points['position'],points['speed'])

def best_by_player(attempts,scores):
    best={}
    for a in attempts:
        score=scores.get(a.edit_id)
        if score is not None and score.complete:
            key=a.player.casefold();best[key]=max(best.get(key,-1),round(score.total,1))
    return best

def is_best(attempt,score,best):
    return score is not None and score.complete and round(score.total,1)==best.get(attempt.player.casefold())
