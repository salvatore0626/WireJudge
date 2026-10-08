"""Small decorative aircraft scenes; independent of recorded replay data."""
import math
import random
import time
import tkinter as tk
from PIL import Image
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.collections import LineCollection
from replay_trails import trail_segments,trail_colors
from replay_style import (PALETTE,ENEMY_COLOR,AIRCRAFT_SIZE,AIRCRAFT_TRAIL_WIDTH,
                          MISSILE_COLOR,MISSILE_TRAIL_WIDTH,aircraft_marker,
                          missile_color,missile_size,missile_path,update_explosions)
from animation_overlay import AnimationOverlay

class AircraftScene:
    def __init__(self,width,height,kind=None):
        self.width=width;self.height=height;self.kind=kind or random.choice(('formation','joinup','fight'))
        if self.kind=='kiss_off':
            self.build_kiss_off()
            self.ensure_offscreen();self.finish_paths();return
        formation_scene=self.kind in ('formation','joinup','breakaway','solo','enemy')
        speed=random.uniform(65,80) if formation_scene else random.uniform(36,46)
        self.duration=max(width,height)/speed+12;self.times=np.arange(0,self.duration+.1,.05)
        self.color=random.choice(PALETTE);self.actors=[];self.missiles=[]
        self.turn=random.choice((-1,1))*random.choice((15,25,45,50,60))
        angle=random.uniform(0,math.tau)
        center=np.array((width/2,height/2),dtype=float)
        lead=self.curve(angle,speed,self.turn)
        lead+=center-lead[len(lead)//2]
        if self.kind in ('formation','joinup','breakaway','solo','enemy'):
            count=1 if self.kind in ('solo','enemy') else random.randint(2,4)
            formation=random.choice(('chevron','left','right'));self.formation=formation
            derivative=np.gradient(lead,axis=0);directions=derivative/np.linalg.norm(derivative,axis=1)[:,None]
            right=np.column_stack((-directions[:,1],directions[:,0]))
            for i in range(count):
                rank=(i+1)//2
                lateral=(1 if i%2 else -1)*rank*25 if formation=='chevron' else i*25*(1 if formation=='right' else -1)
                along=-rank*30 if formation=='chevron' else -i*30
                offsets=np.tile((along,lateral),(len(self.times),1)).astype(float)
                if i and self.kind=='joinup':
                    blend=self.smooth(np.clip((self.times-random.uniform(1,2))/random.uniform(4,7),0,1))
                    initial=np.array((along-random.uniform(70,180),lateral+random.choice((-1,1))*random.uniform(100,220)))
                    offsets=initial[None,:]*(1-blend[:,None])+offsets*blend[:,None]
                path=lead+directions*offsets[:,0,None]+right*offsets[:,1,None]
                self.actors.append(dict(path=path,color=ENEMY_COLOR if self.kind=='enemy' else self.color,team='friendly',death=float('inf')))
            if count>1 and (self.kind=='breakaway' or random.random()<.35):
                for actor in self.actors[-random.randint(1,min(2,count-1)):]:
                    start=random.uniform(7,10);index=np.searchsorted(self.times,start);path=actor['path']
                    velocity=path[index]-path[index-1];heading=math.atan2(velocity[1],velocity[0])
                    elapsed=self.times[index:]-self.times[index]
                    delta=math.radians(random.choice((-1,1))*random.uniform(45,60))*self.smooth(np.clip(elapsed/5,0,1))
                    steps=np.column_stack((np.cos(heading+delta),np.sin(heading+delta)))*speed*.05
                    path[index:]=path[index]+np.vstack((np.zeros(2),np.cumsum(steps[:-1],axis=0)))
        else:
            self.layout=random.choice(('head_on','flank','chase','2v1','2v2')) if self.kind=='fight' else self.kind
            counts=(2,2) if self.layout=='2v2' else random.choice(((2,1),(1,2))) if self.layout=='2v1' else (1,1)
            self.winner=random.choice(('friendly','enemy'))
            for team,count in zip(('friendly','enemy'),counts):
                heading=angle+(math.pi if team=='enemy' and self.layout!='chase' else 0)
                if team=='enemy' and self.layout=='flank':heading=angle+random.choice((-1,1))*math.pi/2
                for i in range(count):
                    path=self.curve(heading,speed*random.uniform(.92,1.08),random.choice((-1,1))*random.uniform(35,65))
                    self.crossing_time=self.duration*.46
                    crossing=np.searchsorted(self.times,self.crossing_time)
                    offset=np.array((-math.sin(angle),math.cos(angle)))*(i*55+(100 if team=='enemy' else -100))
                    if self.layout=='chase' and team=='enemy':offset+=np.array((math.cos(angle),math.sin(angle)))*230
                    path+=center+offset-path[crossing]
                    self.actors.append(dict(path=path,color=self.color if team=='friendly' else ENEMY_COLOR,team=team,death=float('inf')))
            self.ensure_offscreen()
            battle=self.crossing_time+self.entry_delay
            for fire in np.arange(max(2,battle-7),battle+7,2.8):
                team=random.choice(('friendly','enemy'))
                shooters=[i for i,a in enumerate(self.actors) if a['team']==team and a['death']>fire]
                targets=[i for i,a in enumerate(self.actors) if a['team']!=team and a['death']>fire]
                if not shooters or not targets:continue
                candidates=[(source,target) for source in shooters for target in targets if self.launch_possible(source,target,fire)]
                if not candidates:continue
                source,target=random.choice(candidates)
                # Keep the winning flight alive, but allow losses on either side.
                survivors=[a for a in self.actors if a['team']==self.winner and a['death']>fire]
                hit=random.random()<( .55 if team==self.winner else .2) and not (team!=self.winner and len(survivors)==1)
                self.fire(source,target,float(fire),hit)
            # A final valid shot may resolve the fight, but never invent a hit or
            # launch sideways just to force the chosen side to win.
            survivors=[i for i,a in enumerate(self.actors) if a['team']==self.winner and a['death']>battle+7]
            targets=[i for i,a in enumerate(self.actors) if a['team']!=self.winner and a['death']>battle+7]
            for source in survivors:
                for target in targets:
                    if self.launch_possible(source,target,battle+7):self.fire(source,target,battle+7,True)
        if formation_scene:self.ensure_offscreen()
        self.finish_paths()

    def build_kiss_off(self):
        """Lead-first echelon-right breaks, all rolling onto one downwind."""
        self.color=random.choice(PALETTE);self.actors=[];self.missiles=[];self.formation='right'
        speed=random.uniform(58,70);self.break_interval=2.0
        lane=self.height*.26;upwind=self.height*.65
        first_break=(self.width*.30+100)/speed
        # Integrate constant-speed headings with eased roll-in/roll-out. The
        # common downwind sets each turn duration, so wider turns by the
        # outside wingmen still finish precisely on the same lane.
        u=np.linspace(0,1,2001);heading=math.pi*self.smooth(u)
        du=u[1]-u[0]
        ix=np.r_[0,np.cumsum((np.cos(heading[:-1])+np.cos(heading[1:]))*.5*du)]
        iy=np.r_[0,np.cumsum((np.sin(heading[:-1])+np.sin(heading[1:]))*.5*du)]
        turns=[(upwind+i*25-lane)/(speed*iy[-1]) for i in range(3)]
        exits=[]
        for i,turn_duration in enumerate(turns):
            break_at=first_break+i*self.break_interval
            break_x=-100-i*30+speed*break_at
            exits.append(break_at+turn_duration+(break_x+100)/speed)
        self.duration=max(exits)+.25
        self.times=np.arange(0,self.duration+.1,.05);reverse=random.choice((False,True))
        self.downwind_lane=self.height-lane if reverse else lane
        self.break_times=[];self.turn_durations=turns;self.kiss_speed=speed
        for i,duration in enumerate(turns):
            start_x=-100-i*30;start_y=upwind+i*25
            break_at=first_break+i*self.break_interval;self.break_times.append(break_at)
            break_x=start_x+speed*break_at
            elapsed=self.times-break_at;progress=np.clip(elapsed/duration,0,1)
            x=np.where(elapsed<0,start_x+speed*self.times,break_x+speed*duration*np.interp(progress,u,ix))
            y=np.where(elapsed<0,start_y,start_y-speed*duration*np.interp(progress,u,iy))
            downwind=elapsed>=duration
            x[downwind]=break_x-speed*(elapsed[downwind]-duration);y[downwind]=lane
            if reverse:x=self.width-x;y=self.height-y
            self.actors.append(dict(path=np.column_stack((x,y)),color=self.color,team='friendly',death=float('inf')))

    def ensure_offscreen(self):
        """Prepend a shared lead-in so every aircraft starts outside the viewport."""
        delay=0
        for actor in self.actors:
            point=actor['path'][0];velocity=(actor['path'][1]-point)/.05
            if -80<=point[0]<=self.width+80 and -80<=point[1]<=self.height+80:
                exits=[]
                for axis,maximum in ((0,self.width),(1,self.height)):
                    if abs(velocity[axis])>1e-6:
                        boundary=-80 if velocity[axis]>0 else maximum+80
                        exits.append((point[axis]-boundary)/velocity[axis])
                delay=max(delay,min(value for value in exits if value>=0)+.15)
        count=math.ceil(delay/.05);self.entry_delay=count*.05
        if count:
            offsets=np.arange(count,0,-1)*.05
            for actor in self.actors:
                path=actor['path'];velocity=(path[1]-path[0])/.05
                actor['path']=np.vstack((path[0]-offsets[:,None]*velocity,path))
            self.times=np.arange(len(self.actors[0]['path']))*.05;self.duration=self.times[-1]

    def finish_paths(self):
        # Survivors keep moving out of view. The scene stays alive long enough
        # for the final five seconds of aircraft and missile trails to fade.
        extension=0
        for actor in self.actors:
            if np.isfinite(actor['death']):continue
            path=actor['path'];point=path[-1];velocity=(point-path[-2])/.05
            if -80<=point[0]<=self.width+80 and -80<=point[1]<=self.height+80:
                exits=[]
                for axis,maximum in ((0,self.width),(1,self.height)):
                    if abs(velocity[axis])>1e-6:
                        boundary=maximum+80 if velocity[axis]>0 else -80
                        exits.append((boundary-point[axis])/velocity[axis])
                extension=max(extension,min(value for value in exits if value>=0)+.2)
        last_missile=max((m['terminal'] for m in self.missiles),default=0)
        count=math.ceil(max(extension,last_missile-self.times[-1],0)/.05)
        if count:
            offsets=np.arange(1,count+1)*.05
            for actor in self.actors:
                path=actor['path'];velocity=(path[-1]-path[-2])/.05
                actor['path']=np.vstack((path,path[-1]+offsets[:,None]*velocity))
            self.times=np.arange(len(self.actors[0]['path']))*.05
        self.duration=max(self.times[-1],last_missile)+5.5

    @staticmethod
    def smooth(value):return value*value*(3-2*value)

    def curve(self,angle,speed,turn):
        # A continuous coordinated turn, with gentle roll-in and roll-out.
        progress=self.smooth(np.clip(self.times/self.duration,0,1))
        heading=angle+math.radians(turn)*(progress-.5)
        steps=np.column_stack((np.cos(heading),np.sin(heading)))*speed*.05
        return np.vstack((np.zeros(2),np.cumsum(steps[:-1],axis=0)))

    def position(self,actor,t):
        path=actor['path']
        return np.array((np.interp(t,self.times,path[:,0]),np.interp(t,self.times,path[:,1])))

    def velocity(self,actor,t):
        return (self.position(actor,t+.025)-self.position(actor,t-.025))/.05

    def launch_possible(self,source,target,t):
        a=self.actors[source];b=self.actors[target]
        if a['death']<=t or b['death']<=t:return False
        velocity=self.velocity(a,t);relative=self.position(b,t)-self.position(a,t)
        distance=np.linalg.norm(relative)
        return 65<distance<800 and np.dot(velocity,relative)>math.cos(math.radians(55))*np.linalg.norm(velocity)*distance

    def fire(self,source,target,fire,hit):
        if not self.launch_possible(source,target,fire):return
        shooter=self.actors[source];victim=self.actors[target]
        position=self.position(shooter,fire);velocity=self.velocity(shooter,fire)
        launch_velocity=velocity.copy();launch_speed=np.linalg.norm(velocity)
        heading=math.atan2(velocity[1],velocity[0]);miss_side=random.choice((-1,1));random_offset=random.uniform(25,50)
        points=[position.copy()];ages=[0.];actual_hit=False;step=.02
        coast_age=None;coast_speed=0.;coast_duration=random.uniform(.65,1.1)
        closest=np.linalg.norm(self.position(victim,fire)-position)
        for i in range(1,601):
            age=(i-1)*step;now=fire+age
            # First step inherits the aircraft velocity exactly. Boost builds
            # gradually to roughly 2.7x launch speed, then the missile coasts.
            position=position+velocity*step;points.append(position.copy());ages.append(i*step)
            target_position=self.position(victim,now+step)
            if hit and victim['death']>now and np.linalg.norm(position-target_position)<6:
                actual_hit=True;break
            speed_ratio=np.interp(i*step,(0,1,3,6),(1,1.44,2.14,2.68))
            if i*step>6:speed_ratio*=math.exp(-.025*(i*step-6))
            speed=launch_speed*speed_ratio
            target_velocity=self.velocity(victim,now+step)
            relative=target_position-position
            distance=np.linalg.norm(relative)
            # Once the target is behind the missile, or a close pass starts
            # opening again, abandon guidance instead of making a U-turn.
            passed=np.dot(relative,velocity)<=0
            opening=distance>closest+8 and closest<max(55,launch_speed*1.5)
            turning_back=np.dot(velocity,launch_velocity)<math.cos(math.radians(85))*np.linalg.norm(velocity)*launch_speed
            if coast_age is None and age>.3 and (passed or opening or turning_back or victim['death']<=now):
                coast_age=age;coast_speed=np.linalg.norm(velocity)
            closest=min(closest,distance)
            if coast_age is not None:
                speed=coast_speed*math.exp(-.025*(age-coast_age))
                velocity=np.array((math.cos(heading),math.sin(heading)))*speed
                if age-coast_age>=coast_duration:break
                continue
            # Predict interception rather than directly dragging the missile
            # onto a target. A capped turn rate keeps the launch smooth.
            lookahead=min(4,np.linalg.norm(relative)/max(speed,1))
            aim=target_position+target_velocity*lookahead
            if not hit:
                normal=np.array((-target_velocity[1],target_velocity[0]))/max(np.linalg.norm(target_velocity),1)
                aim+=normal*miss_side*random_offset
            desired=math.atan2(aim[1]-position[1],aim[0]-position[0])
            error=(desired-heading+math.pi)%math.tau-math.pi
            limit=math.radians(30)*(1-math.exp(-max(age-.15,0)/1.2))*step
            if age>.15 and (hit or age<7):heading+=float(np.clip(error,-limit,limit))
            velocity=np.array((math.cos(heading),math.sin(heading)))*speed
            if not hit and age>8 and not (-100<position[0]<self.width+100 and -100<position[1]<self.height+100):break
        terminal=fire+ages[-1]
        self.missiles.append(dict(source=source,target=target,fire=fire,impact=terminal,terminal=terminal,
                                 hit=actual_hit,coast_age=coast_age,launch_velocity=launch_velocity,path=np.asarray(points),ages=np.asarray(ages)))
        if actual_hit:victim['death']=terminal

    def missile_position(self,missile,t):
        age=t-missile['fire'];path=missile['path']
        return np.array((np.interp(age,missile['ages'],path[:,0]),np.interp(age,missile['ages'],path[:,1])))

    def resize(self,width,height):
        if (width,height)==(self.width,self.height):return
        scale=np.array((width/self.width,height/self.height))
        for actor in self.actors:actor['path']*=scale
        for missile in self.missiles:
            missile['path']*=scale;missile['launch_velocity']*=scale
        self.width=width;self.height=height
        if hasattr(self,'figure'):del self.figure

    def build_renderer(self):
        self.figure=Figure(figsize=(self.width/100,self.height/100),dpi=100,facecolor=(0,0,0,0))
        self.canvas=FigureCanvasAgg(self.figure)
        ax=self.figure.add_axes((0,0,1,1),frameon=False);ax.set_axis_off()
        ax.set_xlim(0,self.width);ax.set_ylim(self.height,0)
        self.artists=[]
        for actor in self.actors:
            line=LineCollection([],linewidths=AIRCRAFT_TRAIL_WIDTH,zorder=3);ax.add_collection(line)
            marker,=ax.plot([],[],color=actor['color'],marker='^',markersize=AIRCRAFT_SIZE,ls='',zorder=11)
            self.artists.append((line,marker))
        self.missile_trails=LineCollection([],linewidths=MISSILE_TRAIL_WIDTH,linestyles='dashed',zorder=4)
        ax.add_collection(self.missile_trails)
        self.missile_markers=ax.scatter([],[],s=7,marker='D',color=MISSILE_COLOR,zorder=12)
        self.explosions=ax.scatter([],[],s=[],marker='o',facecolors='none',edgecolors=[],linewidths=2,zorder=13)

    def trail(self,position,t,start=0):
        oldest=max(start,t-5)
        times=np.linspace(oldest,t,max(2,math.ceil((t-oldest)/.08)+1))
        points=np.asarray([position(sample) for sample in times])
        data=dict(time=times,trail_time=times,x=points[:,0],y=points[:,1],breaks=[])
        return trail_segments(data,t,5,2.5)

    def draw(self,t,opacity):
        if not hasattr(self,'figure'):self.build_renderer()
        for index,(actor,(line,marker)) in enumerate(zip(self.actors,self.artists)):
            alive=t<min(actor['death'],self.times[-1])
            line.set_visible(t<min(actor['death'],self.times[-1])+5);marker.set_visible(alive)
            position=lambda sample:self.position(actor,sample)
            if alive:segments,alpha=self.trail(position,t)
            else:
                oldest=max(0,t-5);end=min(actor['death'],self.times[-1])
                if end<=oldest:segments,alpha=[],np.empty(0)
                else:
                    times=np.linspace(oldest,end,max(2,math.ceil((end-oldest)/.08)+1))
                    points=np.asarray([position(sample) for sample in times])
                    segments,alpha=trail_segments(dict(time=times,trail_time=times,x=points[:,0],y=points[:,1],breaks=[]),t,5,2.5)
            line.set_segments(segments);line.set_colors(trail_colors(actor['color'],alpha,.7*opacity))
            x,y=position(t);px,py=position(t-.05)
            marker.set_data([x],[y]);marker.set_marker(aircraft_marker(x-px,py-y));marker.set_alpha(opacity)
        missile_points=[];missile_segments=[];missile_colors=[];bursts=[]
        for missile in self.missiles:
            terminal=missile['terminal']
            position=lambda sample:self.missile_position(missile,sample)
            if t>=terminal:
                x,y=position(terminal);bursts.append((x,y,t-terminal))
            if t<missile['fire']:continue
            # Keep the same age/fade treatment after a missile has disappeared.
            end=min(t,terminal);oldest=max(missile['fire'],t-5)
            if end>oldest:
                times=np.linspace(oldest,end,max(2,math.ceil((end-oldest)/.08)+1))
                points=np.asarray([position(sample) for sample in times])
                data=dict(time=times,trail_time=times,x=points[:,0],y=points[:,1],breaks=[])
                segments,alpha=trail_segments(data,t,5,2.5)
                missile_segments.extend(segments);missile_colors.extend(trail_colors(MISSILE_COLOR,alpha,.65*opacity))
            if t<=terminal:missile_points.append(position(t))
        self.missile_trails.set_segments(missile_segments);self.missile_trails.set_colors(missile_colors)
        self.missile_markers.set_offsets(np.asarray(missile_points).reshape(-1,2))
        self.missile_markers.set_paths([missile_path(t)]);self.missile_markers.set_sizes([missile_size(t)])
        color=missile_color(t);color[3]*=opacity;self.missile_markers.set_color(color)
        update_explosions(self.explosions,bursts,self.figure.dpi,opacity)
        self.canvas.draw()
        return Image.fromarray(np.asarray(self.canvas.buffer_rgba())).copy()

class ApplicationAnimations:
    def __init__(self,app):
        self.app=app;self.scene=None;self.host=None;self.overlay=None;self.scene_bag=[];self.splash_scenes=[]
        self.next_scene=time.monotonic()+.5;self.started=0;self.timer=app.after(50,self.tick)
        app.bind('<Destroy>',self.destroyed,add='+')

    def destroyed(self,event):
        if event.widget is self.app and self.timer is not None:
            try:self.app.after_cancel(self.timer)
            except tk.TclError:pass
            self.timer=None
            self.clear()

    def clear(self):
        if self.overlay is not None:self.overlay.close();self.overlay=None
        self.scene=None;self.splash_scenes=[]

    def next_kind(self):
        if not self.scene_bag:
            self.scene_bag=[random.choice(('formation','joinup','breakaway','kiss_off')),random.choice(('formation','joinup','breakaway','kiss_off')),'fight']
            random.shuffle(self.scene_bag)
        return self.scene_bag.pop()

    def tick(self):
        self.timer=None
        try:
            settings=self.app.settings;now=time.monotonic();splash=self.app.startup_splash
            if splash is not None and splash.winfo_exists():
                host=splash;interval=5;enabled=settings.random_animations
            else:
                host=self.app.nametowidget(self.app.pages.select());interval=settings.random_animation_frequency_sec
                options={self.app.approach_page:settings.animation_approach,self.app.score_window:settings.animation_scores,
                         self.app.editor_page:settings.animation_editor,self.app.settings_page:settings.animation_settings}
                enabled=settings.random_animations and options.get(host,False)
            if host is not self.host:
                self.clear();self.host=host;self.next_scene=now+.5;self.configuration=None
            enabled=enabled and settings.animation_opacity>0 and host.winfo_ismapped() and self.app.state()!='iconic'
            configuration=(enabled,interval)
            if configuration!=getattr(self,'configuration',None):
                self.next_scene=self.started+interval if self.scene is not None else now+.5
                self.configuration=configuration
            if not enabled:
                if self.scene is not None or self.overlay is not None:self.clear()
            elif host is splash:
                surface=host.winfo_toplevel();width=max(1,surface.winfo_width());height=max(1,surface.winfo_height())
                self.splash_scenes=[(scene,start) for scene,start in self.splash_scenes if now-start<=scene.duration]
                if now>=self.next_scene:
                    self.scene=AircraftScene(width,height,self.next_kind());self.started=now
                    self.splash_scenes.append((self.scene,now));self.next_scene=now+interval
                    if self.overlay is None:self.overlay=AnimationOverlay(self.app,surface)
                if self.splash_scenes:
                    image=Image.new('RGBA',(width,height))
                    for scene,start in self.splash_scenes:
                        scene.resize(width,height)
                        image=Image.alpha_composite(image,scene.draw(now-start,settings.animation_opacity))
                    self.overlay.draw(image,surface.winfo_rootx(),surface.winfo_rooty())
            else:
                if self.scene is not None and now-self.started>self.scene.duration:self.clear()
                if self.scene is None and now>=self.next_scene:
                    surface=host.winfo_toplevel()
                    self.scene=AircraftScene(max(1,surface.winfo_width()),max(1,surface.winfo_height()),self.next_kind())
                    self.overlay=AnimationOverlay(self.app,host.winfo_toplevel())
                    self.started=now;self.next_scene=now+interval
                if self.scene is not None:
                    surface=host.winfo_toplevel()
                    self.scene.resize(max(1,surface.winfo_width()),max(1,surface.winfo_height()))
                    image=self.scene.draw(now-self.started,settings.animation_opacity)
                    self.overlay.draw(image,surface.winfo_rootx(),surface.winfo_rooty())
        except tk.TclError:
            if not self.app.winfo_exists():return
        self.timer=self.app.after(50,self.tick)
