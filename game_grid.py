"""Fixed world-space tactical grid rendered as a single cached canvas image."""
import math
from PIL import Image, ImageDraw

MAJOR_NM=250.
MINOR_NM=50.


def blend(background,foreground,opacity):
    return tuple(round(int(background[i:i+2],16)*(1-opacity)+int(foreground[i:i+2],16)*opacity) for i in (1,3,5))


def grid_image(width,height,center,view_width,opacity,background,foreground):
    width=max(1,int(width));height=max(1,int(height))
    scale=width/view_width;cx,cy=center
    opacity=max(0.,min(1.,opacity))
    image=Image.new('RGB',(width,height),background)
    labels=[]
    if opacity==0:return image,labels
    draw=ImageDraw.Draw(image)
    for spacing,strength in ((MINOR_NM,.30),(MAJOR_NM,.75)):
        color=blend(background,foreground,opacity*strength)
        for axis,span in ((0,width),(1,height)):
            origin=cx if axis==0 else cy
            lo=origin-span/(2*scale);hi=origin+span/(2*scale)
            for index in range(math.ceil(lo/spacing),math.floor(hi/spacing)+1):
                value=index*spacing
                pixel=round(span/2+(value-origin)*scale*(1 if axis==0 else -1))
                if not 0<=pixel<span:continue
                if axis==0:draw.line((pixel,0,pixel,height-1),fill=color)
                else:draw.line((0,pixel,width-1,pixel),fill=color)
                # Labels may thin out at extreme zoom; grid spacing never changes.
                if spacing==MAJOR_NM and spacing*scale>=55:
                    labels.append((pixel+3,height-10,value) if axis==0 else (7,pixel-5,value))
    return image,labels
