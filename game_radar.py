"""Radar footprints and exposed union edges; no added geometry dependency."""
import math
import numpy as np


def footprint(x, y, radius, heading=0., angle=360.):
    if angle >= 360:
        angles=np.linspace(0,math.tau,97)[:-1]
        return np.column_stack((x+radius*np.cos(angles),y+radius*np.sin(angles)))
    half=math.radians(angle/2)
    # Counterclockwise winding, including the two radial sides of the cone.
    angles=np.linspace(heading+half,heading-half,25)
    arc=np.column_stack((x+radius*np.sin(angles),y+radius*np.cos(angles)))
    return np.vstack(((x,y),arc))


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
