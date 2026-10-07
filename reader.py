"""Independent, bounded reader for the v1 VTR motion-track section.
Rotation is retained as its raw packed 32-bit value. Custom/event sections
are not decoded. No input files are modified.
"""
import ctypes, ctypes.util, struct
from pathlib import Path
import numpy as np

class Reader:
    def __init__(self, data): self.data=data; self.offset=0
    def read(self, fmt):
        size=struct.calcsize('<'+fmt)
        if self.offset+size>len(self.data): raise ValueError('Unexpected end of replay')
        result=struct.unpack_from('<'+fmt,self.data,self.offset); self.offset+=size
        return result[0] if len(result)==1 else result
    def string(self):
        n=self.read('i')
        if not 0<=n<=65536 or self.offset+n>len(self.data): raise ValueError('Invalid string length')
        result=self.data[self.offset:self.offset+n].decode('utf-8'); self.offset+=n
        return result

def decompress(path, limit=256*1024*1024):
    compressed=Path(path).read_bytes()
    try:
        import lz4.block
        size=max(1024*1024,len(compressed)*2)
        while size<=limit:
            try: return lz4.block.decompress(compressed,uncompressed_size=size)
            except lz4.block.LZ4BlockError: size*=2
    except ImportError:
        name=ctypes.util.find_library('lz4')
        if not name: raise RuntimeError('Install the Python lz4 package')
        lib=ctypes.CDLL(name)
        lib.LZ4_decompress_safe.argtypes=[ctypes.c_char_p,ctypes.c_void_p,ctypes.c_int,ctypes.c_int]
        lib.LZ4_decompress_safe.restype=ctypes.c_int
        size=max(1024*1024,len(compressed)*2)
        while size<=limit:
            out=ctypes.create_string_buffer(size)
            n=lib.LZ4_decompress_safe(compressed,out,len(compressed),size)
            if n>=0:return out.raw[:n]
            size*=2
    raise ValueError('Invalid LZ4 block or decoded-size limit exceeded')

def read_motion(path):
    data=decompress(path);r=Reader(data)
    version=r.read('i')
    if version!=1:raise ValueError(f'Unsupported VTR version {version}')
    ntracks=r.read('i')
    if not 0<=ntracks<=100000:raise ValueError('Invalid track count')
    tracks=[]
    for _ in range(ntracks):
        entity=r.read('i');kind=r.read('i');identity=None;label=''
        hasmeta=r.read('B')
        if hasmeta:identity=r.read('i');label=r.string()
        count=r.read('i')
        if not 1<=count<=10000000:raise ValueError('Invalid sample count')
        rows=np.empty((count,8),dtype=np.float64)
        t=r.read('f');pos=np.array(r.read('3f'));vel=np.array(r.read('3f'));packed=r.read('I')
        rows[0]=[t,*pos,*vel,packed]
        for i in range(1,count):
            dt=r.read('f');flags=r.read('B')
            if dt<0 or flags>7:raise ValueError('Invalid delta keyframe')
            t+=dt
            if flags&1:pos+=r.read('3f')
            if flags&2:vel+=r.read('3f')
            if flags&4:packed=(packed+r.read('i'))&0xffffffff
            rows[i]=[t,*pos,*vel,packed]
        if not np.isfinite(rows).all():raise ValueError('Non-finite motion data')
        tracks.append(dict(id=entity,type=kind,identity=identity,name=label,rows=rows))
    end=r.offset;custom_count=r.read('i')
    return tracks,dict(version=version,decoded_bytes=len(data),motion_end=end,custom_count=custom_count)

def quaternion_candidate(packed):
    """Hypothesis: signed bytes in x,y,z,w order, normalized. Not authoritative."""
    a=np.asarray(packed,dtype=np.uint32)
    q=np.stack([((a>>shift)&255).astype(np.int16) for shift in (0,8,16,24)],axis=-1)
    q=np.where(q>=128,q-256,q).astype(float)
    norms=np.linalg.norm(q,axis=-1,keepdims=True)
    if np.any(norms==0):raise ValueError('Zero packed quaternion')
    return q/norms

def heading_candidate(packed):
    q=quaternion_candidate(packed);x,y,z,w=np.moveaxis(q,-1,0)
    return np.arctan2(2*(x*z+w*y),1-2*(x*x+y*y))

