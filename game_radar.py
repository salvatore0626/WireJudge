"""Radar footprints and exposed union edges; no added geometry dependency."""
import math
import numpy as np


def footprint(x, y, radius, heading=0., angle=360., inner_radius=0.):
    if angle >= 360:
        angles=np.linspace(0,math.tau,97)[:-1]
        return np.column_stack((x+radius*np.cos(angles),y+radius*np.sin(angles)))
    half=math.radians(angle/2)
    # Counterclockwise winding, including the two radial sides of the cone.
    angles=np.linspace(heading+half,heading-half,25)
    arc=np.column_stack((x+radius*np.sin(angles),y+radius*np.cos(angles)))
    if inner_radius:
        inner=np.column_stack((x+inner_radius*np.sin(angles[::-1]),y+inner_radius*np.cos(angles[::-1])))
        return np.vstack((arc,inner))
    return np.vstack(((x,y),arc))


def engagement_footprints(x,y,radius,heading,angle,inner_radius=0.):
    """Split a cone with a minimum range into convex bands for coverage merging."""
    if not inner_radius:return [footprint(x,y,radius,heading,angle)]
    half=math.radians(angle/2)
    angles=np.linspace(heading+half,heading-half,max(2,math.ceil(angle/6)+1))
    def point(r,a):return x+r*math.sin(a),y+r*math.cos(a)
    return [np.asarray((point(inner_radius,a),point(radius,a),point(radius,b),point(inner_radius,b)))
            for a,b in zip(angles,angles[1:])]


def union_outline(polygons):
    """Clip each convex footprint's edges against all other footprints.

    Half-plane clipping is batched with NumPy. Only uncovered intervals survive,
    so circles and cones share a continuous outer boundary without inner seams.
    """
    unique={}
    for polygon in polygons:
        p=np.asarray(polygon,dtype=float)
        unique.setdefault((p.shape,p.tobytes()),p)
    polygons=list(unique.values())
    bounds=[(p.min(axis=0),p.max(axis=0)) for p in polygons]
    circles=[]
    for p in polygons:
        center=p.mean(axis=0);radii=np.linalg.norm(p-center,axis=1)
        circles.append((center,radii[0],radii[0]*math.cos(math.pi/len(p)))
                       if len(p)>50 and np.ptp(radii)<1e-8 else None)
    paths=[]
    for i,p in enumerate(polygons):
        starts=p;ends=np.roll(p,-1,axis=0);delta=ends-starts
        covered=[[] for _ in starts]
        for j,q in enumerate(polygons):
            if i==j:continue
            if np.any(bounds[i][1]<bounds[j][0]) or np.any(bounds[j][1]<bounds[i][0]):continue
            indices=np.arange(len(starts))
            if circles[j] is not None:
                center,outer,inner=circles[j]
                full=(np.linalg.norm(starts-center,axis=1)<inner-1e-9)&(np.linalg.norm(ends-center,axis=1)<inner-1e-9)
                for k in np.flatnonzero(full):covered[k].append((0.,1.))
                length2=np.sum(delta*delta,axis=1)
                fraction=np.clip(np.sum((center-starts)*delta,axis=1)/np.maximum(length2,1e-20),0,1)
                close=np.linalg.norm(starts+fraction[:,None]*delta-center,axis=1)<=outer+1e-9
                indices=np.flatnonzero(close & ~full)
                if not len(indices):continue
            edge=np.roll(q,-1,axis=0)-q
            offset=starts[indices,None,:]-q[None,:,:]
            base=edge[None,:,0]*offset[:,:,1]-edge[None,:,1]*offset[:,:,0]
            slope=edge[None,:,0]*delta[indices,None,1]-edge[None,:,1]*delta[indices,None,0]
            parallel=np.abs(slope)<1e-12
            valid=~np.any(parallel & (base<-1e-9),axis=1)
            cut=np.divide(-base,slope,out=np.zeros_like(base),where=~parallel)
            enter=np.maximum(0,np.max(np.where(slope>1e-12,cut,-np.inf),axis=1))
            leave=np.minimum(1,np.min(np.where(slope<-1e-12,cut,np.inf),axis=1))
            valid &= leave-enter>1e-10
            for k in np.flatnonzero(valid):covered[indices[k]].append((enter[k],leave[k]))
        exposed=[]
        for k,intervals in enumerate(covered):
            cursor=0.
            for lo,hi in sorted(intervals):
                if lo>cursor+1e-9:exposed.append((starts[k]+cursor*delta[k],starts[k]+lo*delta[k]))
                cursor=max(cursor,hi)
            if cursor<1-1e-9:exposed.append((starts[k]+cursor*delta[k],ends[k]))
        current=[]
        for a,b in exposed:
            if current and np.max(np.abs(current[-1]-a))<1e-7:current.append(b)
            else:
                if current:paths.append(np.asarray(current))
                current=[a,b]
        if current:paths.append(np.asarray(current))
    return paths


def range_paths(x,y,radius,heading=0.,angle=360.,inner_radius=0.):
    """Closed display boundaries; a full annulus has two disconnected loops."""
    if radius<=0 or inner_radius>=radius:return []
    if angle>=360:
        loops=[footprint(x,y,radius)]
        if inner_radius>0:loops.append(footprint(x,y,inner_radius)[::-1])
    else:loops=[footprint(x,y,radius,heading,angle,inner_radius)]
    return [np.vstack((loop,loop[0])) for loop in loops]


def _clip_intervals(starts,delta,polygon,keep_matching_edges=False):
    """Batch segment/convex-polygon intersections as intervals along each edge."""
    edge=np.roll(polygon,-1,axis=0)-polygon
    offset=starts[:,None,:]-polygon[None,:,:]
    base=edge[None,:,0]*offset[:,:,1]-edge[None,:,1]*offset[:,:,0]
    slope=edge[None,:,0]*delta[:,None,1]-edge[None,:,1]*delta[:,None,0]
    parallel=np.abs(slope)<1e-12
    valid=~np.any(parallel & (base<-1e-9),axis=1)
    if keep_matching_edges:
        touching=parallel & (np.abs(base)<1e-9)
        if np.any(touching):
            aligned=edge[None,:,0]*delta[:,None,0]+edge[None,:,1]*delta[:,None,1]
            valid &= ~np.any(touching & (aligned>0),axis=1)
    cut=np.divide(-base,slope,out=np.zeros_like(base),where=~parallel)
    enter=np.maximum(0,np.max(np.where(slope>1e-12,cut,-np.inf),axis=1))
    leave=np.minimum(1,np.min(np.where(slope<-1e-12,cut,np.inf),axis=1))
    return enter,leave,valid & (leave-enter>1e-10)


def coverage_outline(specs):
    """Union of range regions, clipping directly against outer shapes and holes.

    Keep minimum-range circles as holes instead of dozens of touching wedges.
    This removes artificial radial seams and makes cost scale with sites.
    """
    canonical=[]
    for spec in specs:
        x,y,radius,heading,angle=spec[:5];inner=spec[5] if len(spec)>5 else 0.
        canonical.append((x,y,radius,0. if angle>=360 else heading,min(360.,angle),inner))
    specs=list(dict.fromkeys(canonical))
    specs=[spec for spec in specs if spec[2]>0 and (len(spec)<6 or spec[5]<spec[2])]
    if not specs:return []
    if not any(len(spec)>5 and spec[5]>0 for spec in specs):
        return union_outline([footprint(*spec) for spec in specs])
    regions=[]
    for spec in specs:
        x,y,radius,heading,angle=spec[:5];inner=spec[5] if len(spec)>5 else 0.
        # Sectors wider than a half circle need two convex clipping components.
        components=[(heading,angle)] if angle<=180 or angle>=360 else [(heading-math.radians(angle/4),angle/2),(heading+math.radians(angle/4),angle/2)]
        polygons=[(footprint(x,y,radius,h,a),footprint(x,y,inner,h,a) if inner>0 else None) for h,a in components]
        regions.append((range_paths(*spec),polygons,np.asarray((x-radius,y-radius)),np.asarray((x+radius,y+radius))))
    paths=[]
    for i,(loops,_,low,high) in enumerate(regions):
        for loop in loops:
            starts=loop[:-1];ends=loop[1:];delta=ends-starts;covered=[[] for _ in starts]
            for j,(_,polygons,other_low,other_high) in enumerate(regions):
                if i==j or np.any(high<other_low) or np.any(other_high<low):continue
                for outer,inner in polygons:
                    lo,hi,valid=_clip_intervals(starts,delta,outer,keep_matching_edges=i<j)
                    if inner is None:
                        for k in np.flatnonzero(valid):covered[k].append((lo[k],hi[k]))
                        continue
                    hole_lo,hole_hi,in_hole=_clip_intervals(starts,delta,inner,keep_matching_edges=True)
                    first_hi=np.where(in_hole,np.minimum(hi,hole_lo),hi)
                    for k in np.flatnonzero(valid & (first_hi-lo>1e-10)):covered[k].append((lo[k],first_hi[k]))
                    second_lo=np.maximum(lo,hole_hi)
                    for k in np.flatnonzero(valid & in_hole & (hi-second_lo>1e-10)):covered[k].append((second_lo[k],hi[k]))
            current=[]
            for k,intervals in enumerate(covered):
                cursor=0.
                exposed=[]
                for lo,hi in sorted(intervals):
                    if lo>cursor+1e-9:exposed.append((cursor,lo))
                    cursor=max(cursor,hi)
                if cursor<1-1e-9:exposed.append((cursor,1.))
                for lo,hi in exposed:
                    a=starts[k]+lo*delta[k];b=starts[k]+hi*delta[k]
                    if current and np.max(np.abs(current[-1]-a))<1e-7:current.append(b)
                    else:
                        if current:paths.append(np.asarray(current))
                        current=[a,b]
            if current:paths.append(np.asarray(current))
    return paths
