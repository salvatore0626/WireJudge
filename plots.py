import numpy as np
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.legend_handler import HandlerBase
from matplotlib.ticker import Locator,MaxNLocator,FuncFormatter
from engine import glide_start_nm,approach_reference,speed_deadzone_bounds,clock

BG='#111a28';PANEL='#182436';TEXT='#dce6f3';MUTED='#91a4bd';GREEN='#6cd9af';BLUE='#69b7ff'
FEET_PER_METRE=3.280839895
AOA_TARGET_DEG=8.0
ATTEMPT_COLORS=(('#69b7ff','#8dd8ff'),('#ff727c','#ffb2b8'),('#9f80ff','#f7a9e8'),('#ff9850','#ffe879'))
MAX_COMPARE_ATTEMPTS=len(ATTEMPT_COLORS)
START_END_COLOR='#c4a1ff'

class PairedLineKey(HandlerBase):
    """Stack speed and AoA swatches under one attempt label."""
    def create_artists(self,legend,handle,xdescent,ydescent,width,height,fontsize,transform):
        return [Line2D([-xdescent,width-xdescent],[height*fraction-ydescent]*2,
                       color=line.get_color(),linestyle=line.get_linestyle(),lw=line.get_linewidth(),transform=transform)
                for line,fraction in zip(handle,(.2,.8))]


def make_figure():
    return Figure(figsize=(10,8),dpi=100,facecolor=BG,layout='constrained')

class TimestampLocator(Locator):
    """Keep distance/time labels readable as the plot is resized or panned."""
    def __call__(self):
        low,high=sorted(self.axis.get_view_interval())
        count=max(2,min(10,int(self.axis.axes.bbox.width/100)))
        ticks=MaxNLocator(nbins=count-1).tick_values(low,high)
        ticks=ticks[(ticks>=low)&(ticks<=high)]
        if len(ticks)>count:ticks=ticks[np.linspace(0,len(ticks)-1,count,dtype=int)]
        return ticks

def latest_sample_time(attempts,distance_nm):
    """Use a recorded sample from the newest crossing of this distance."""
    newest=None
    for attempt in attempts:
        distance=np.asarray(attempt.distance)/1852
        time=np.asarray(attempt.time)
        valid=np.isfinite(distance)&np.isfinite(time)
        exact=np.flatnonzero(valid&np.isclose(distance,distance_nm,rtol=0,atol=1e-9))
        crossings=np.flatnonzero(valid[:-1]&valid[1:]&
                                ((distance[:-1]-distance_nm)*(distance[1:]-distance_nm)<0))
        candidates=list(exact)
        for index in crossings:
            candidates.append(index if abs(distance[index]-distance_nm)<abs(distance[index+1]-distance_nm) else index+1)
        if candidates:
            latest=float(np.max(time[candidates]))
            newest=latest if newest is None else max(newest,latest)
    return newest

def phase_values(nm,values,boundary,before):
    """Clip lines at the exact phase boundary without changing recorded samples."""
    x=np.asarray(nm);y=np.asarray(values);keep=x>=boundary if before else x<=boundary
    result=np.where(keep,y,np.nan)
    # Duplicate coordinates at boundaries avoid connections across reversals.
    xx=[];yy=[]
    for i in range(len(x)):
        xx.append(x[i]);yy.append(result[i])
        if i+1<len(x) and (x[i]-boundary)*(x[i+1]-boundary)<0:
            if np.isfinite(y[i:i+2]).all():
                fraction=(boundary-x[i])/(x[i+1]-x[i])
                value=y[i]+fraction*(y[i+1]-y[i])
                if keep[i]:xx.extend((boundary,boundary));yy.extend((value,np.nan))
                else:xx.extend((boundary,boundary));yy.extend((np.nan,value))
    return np.asarray(xx),np.asarray(yy)

def draw(fig,attempt,settings,origin_msl_ft=None,labels=None,visible_graphs=None,black_box=None):
    attempts=list(attempt) if isinstance(attempt,(list,tuple)) else [attempt] if attempt is not None else []
    attempts=attempts[:MAX_COMPARE_ATTEMPTS];labels=labels or []
    comparing=len(attempts)>1
    speed_axis_color=MUTED if comparing else ATTEMPT_COLORS[0][0]
    aoa_axis_color=MUTED if comparing else ATTEMPT_COLORS[0][1]
    if origin_msl_ft is None:origin_msl_ft=settings.offset_y*FEET_PER_METRE
    case3=settings.recovery_case==3;intercept=glide_start_nm(settings,origin_msl_ft)
    graph_range=settings.case3_graph_range_nm if case3 else settings.graph_range_nm
    visible_graphs=tuple(visible_graphs) if visible_graphs is not None else (True,True,True)
    if len(visible_graphs)==3:visible_graphs=visible_graphs+(False,)
    if comparing:visible_graphs=visible_graphs[:3]+(False,)
    fig.clear()
    if not any(visible_graphs):
        fig.text(.5,.5,'Select a graph to display',color=MUTED,ha='center',va='center')
        return []
    axes=fig.subplots(4 if visible_graphs[3] else 3,1,sharex=True)
    attitude_ax=axes[3].twinx() if visible_graphs[3] else None
    aoa_ax=axes[2].twinx()
    aoa_ax.set_zorder(axes[2].get_zorder()+1)
    aoa_ax.patch.set_visible(False)
    for ax in list(axes)+[aoa_ax]+([attitude_ax] if attitude_ax is not None else []):
        ax.set_facecolor(PANEL);ax.tick_params(colors=MUTED,labelsize=9)
        ax.xaxis.label.set_color(MUTED);ax.yaxis.label.set_color(MUTED)
        for spine in ax.spines.values():spine.set_color('#344258')
        ax.spines['top'].set_visible(False)
        if ax is not aoa_ax:ax.spines['right'].set_visible(False)
        if ax in axes:ax.grid(color='#334357',alpha=.45,lw=.6)
    x=np.unique(np.r_[np.linspace(0,graph_range,400),[v for v in (3,3+1e-8,6,10) if v<=graph_range]]) if case3 else np.linspace(0,graph_range,150)
    if case3:
        # Join each visual boundary at its own platform/glide intersection.
        crossings=[]
        for altitude,angle in ((1200,settings.glide_deg),
                               (1200-settings.case3_platform_alt_ft,settings.glide_deg-settings.glide_tolerance_deg),
                               (1200+settings.case3_platform_alt_ft,settings.glide_deg+settings.glide_tolerance_deg)):
            slope=np.tan(np.radians(angle))*1852*FEET_PER_METRE
            if slope>0:
                crossing=(altitude-origin_msl_ft)/slope
                if 0<=crossing<=min(graph_range,10):crossings.append(crossing)
        x=np.unique(np.r_[x,crossings])
    reference=approach_reference(settings,x*1852,origin_msl_ft)
    center=reference['center']*FEET_PER_METRE;upper=reference['upper']*FEET_PER_METRE;lower=reference['lower']*FEET_PER_METRE
    if case3:
        center=np.minimum(1200,origin_msl_ft+np.tan(np.radians(settings.glide_deg))*x*1852*FEET_PER_METRE)
        lower=np.minimum(1200-settings.case3_platform_alt_ft,origin_msl_ft+np.tan(np.radians(settings.glide_deg-settings.glide_tolerance_deg))*x*1852*FEET_PER_METRE)
        upper=np.minimum(1200+settings.case3_platform_alt_ft,origin_msl_ft+np.tan(np.radians(settings.glide_deg+settings.glide_tolerance_deg))*x*1852*FEET_PER_METRE)
    glide_mask=x<=10 if case3 else np.ones(len(x),dtype=bool)
    ax=axes[0];ax.fill_between(x[glide_mask],lower[glide_mask],upper[glide_mask],color=GREEN,alpha=settings.limit_shading_opacity)
    ax.plot(x[glide_mask],upper[glide_mask],color=GREEN,alpha=settings.limit_outline_opacity,lw=1);ax.plot(x[glide_mask],lower[glide_mask],color=GREEN,alpha=settings.limit_outline_opacity,lw=1)
    ax.plot(x[glide_mask],center[glide_mask],color=GREEN,alpha=settings.limit_center_opacity,lw=1.3,label='Platform / glide target' if case3 else 'Glide centerline')
    ax.set_title('Case 3 Platform / Glide Path' if case3 else f'Glide Path ±{settings.glide_tolerance_deg:g}° envelope',color=TEXT,loc='left',fontsize=11)
    ax.set_ylabel('Altitude MSL (ft)')
    low=min(0,float(lower.min()),origin_msl_ft);high=max(600,float(upper.max()),origin_msl_ft+20)
    ax.set_ylim(low,high+max(20,(high-low)*.08))
    width=reference['loc_width']*FEET_PER_METRE
    ax=axes[1];loc_fill=ax.fill_between(x,-width,width,color=GREEN,alpha=settings.limit_shading_opacity)
    loc_upper,=ax.plot(x,width,color=GREEN,alpha=settings.limit_outline_opacity,lw=1)
    loc_lower,=ax.plot(x,-width,color=GREEN,alpha=settings.limit_outline_opacity,lw=1)
    ax.axhline(0,color=GREEN,alpha=settings.limit_center_opacity,lw=1.3)
    def extend_localizer(axis):
        left,right=sorted(axis.get_xlim());end=max(0,right);start=max(0,left)
        xx=np.array([start,end]);ww=np.tan(np.radians(settings.localizer_tolerance_deg))*xx*1852*FEET_PER_METRE
        loc_upper.set_data(xx,ww);loc_lower.set_data(xx,-ww)
        loc_fill.set_verts([[(start,-ww[0]),(end,-ww[1]),(end,ww[1]),(start,ww[0])]])
    if case3:axes[1].callbacks.connect('xlim_changed',extend_localizer)
    ax.set_title(f'Case 3 Localizer ±{settings.localizer_tolerance_deg:g}° envelope' if case3 else f'Localizer ±{settings.localizer_tolerance_deg:g}° envelope',color=TEXT,loc='left',fontsize=11)
    ax.set_ylabel('Right (−) / left (+), ft');bound=max(float(width.max()),30);ax.set_ylim(-bound*1.12,bound*1.12)
    aoa_ax.set_ylabel('AoA (degrees)');aoa_ax.set_ylim(settings.aoa_min_deg,settings.aoa_max_deg)
    if case3:
        ax=axes[2];limit=settings.case3_platform_speed_knots
        near,far=speed_deadzone_bounds(settings)
        for start,end,target in ((10,6,settings.case3_leg1_speed_knots),(6,3,settings.case3_leg2_speed_knots)):
            if start<=end:continue
            ax.fill_between([end,start],target-limit,target+limit,color=GREEN,alpha=settings.limit_shading_opacity)
            ax.plot([end,start],[target,target],color=GREEN,alpha=settings.limit_center_opacity,lw=1.3)
        ax.set_title(f'Groundspeed / AoA - {settings.case3_leg1_speed_knots:g} / {settings.case3_leg2_speed_knots:g} knots · 8° Targets',color=TEXT,loc='left',fontsize=11)
        ax.set_ylabel('Groundspeed (knots)',color=speed_axis_color);ax.set_ylim(max(0,min(settings.case3_leg1_speed_knots,settings.case3_leg2_speed_knots)-limit-20),max(settings.case3_leg1_speed_knots,settings.case3_leg2_speed_knots)+limit+20)
        if settings.case3_speed_deadzone_nm>0:
            ax.axvspan(near,far,color=MUTED,alpha=.14,zorder=1)
        ax.tick_params(axis='y',colors=speed_axis_color);aoa_ax.tick_params(axis='y',colors=aoa_axis_color);aoa_ax.yaxis.label.set_color(aoa_axis_color)
        aoa_ax.plot([intercept,0],[8,8],color=GREEN,alpha=settings.limit_center_opacity,lw=1.3,label='8° target')
        for axis in axes:
            axis.axvline(6,color=MUTED,ls=':',lw=.7)
    else:
        axes[2].set_ylabel('Groundspeed (knots)',color=speed_axis_color);axes[2].set_ylim(0,350)
        axes[2].tick_params(axis='y',colors=speed_axis_color);aoa_ax.tick_params(axis='y',colors=aoa_axis_color);aoa_ax.yaxis.label.set_color(aoa_axis_color)
        aoa_ax.axhline(8,color=GREEN,alpha=settings.limit_center_opacity,lw=1.3,label='8° target')
        axes[2].set_title('Groundspeed / AoA - 8° Target',color=TEXT,loc='left',fontsize=11)
    key_labels=[];path_keys=[];paired_keys=[]
    for index,attempt in enumerate(attempts):
        path_color,aoa_color=ATTEMPT_COLORS[index]
        label=labels[index] if index<len(labels) else f'{attempt.player} #{index+1}'
        key_labels.append(label)
        path_keys.append(Line2D([],[],color=path_color,lw=settings.graph_line_width))
        paired_keys.append((Line2D([],[],color=path_color,ls='--',lw=settings.graph_line_width),Line2D([],[],color=aoa_color,ls='-',lw=settings.graph_line_width)))
        d=np.asarray(attempt.distance);nm=d/1852;mask=(nm>=-.15)&(nm<=graph_range)
        altitude=attempt.world_altitude*FEET_PER_METRE if attempt.world_altitude is not None else np.full_like(d,np.nan)
        axes[0].plot(nm,altitude,color=path_color,lw=settings.graph_line_width,label=label)
        axes[1].plot(nm,-attempt.lateral*FEET_PER_METRE,color=path_color,lw=settings.graph_line_width,label=label if comparing else '_nolegend_')
        # Include the recorded post-carrier excursion in the vertical display.
        post=mask&(nm<0)
        for axis,values,padding in ((aoa_ax,attempt.aoa,1.),(axes[2],attempt.groundspeed_knots,20.)):
            if values is None:continue
            samples=np.asarray(values)[post];samples=samples[np.isfinite(samples)]
            if len(samples):
                low,high=axis.get_ylim();axis.set_ylim(min(low,float(samples.min())-padding),max(high,float(samples.max())+padding))
        alpha_x,alpha_y=phase_values(nm,attempt.aoa,intercept,False) if intercept is not None else (nm,attempt.aoa)
        line,=aoa_ax.plot(alpha_x,alpha_y,color=aoa_color,lw=settings.graph_line_width,zorder=5,label=label+' · AoA' if comparing else '_nolegend_');line.set_gid('aoa-track')
        if intercept is not None:
            before_x,before_y=phase_values(nm,attempt.aoa,intercept,True)
            # Use the AoA coordinates but draw on the lower axis, below speed.
            line,=axes[2].plot(before_x,before_y,transform=aoa_ax.transData,color=aoa_color,lw=settings.graph_line_width,ls='--',alpha=.5,zorder=1.5)
            line.set_gid('aoa-before-glide')
        if case3 and attempt.groundspeed_knots is not None:
            speed_x,speed_y=phase_values(nm,attempt.groundspeed_knots,intercept,True)
            line,=axes[2].plot(speed_x,speed_y,color=path_color,lw=settings.graph_line_width);line.set_gid('groundspeed-track')
            if comparing and not any(visible_graphs[:2]):line.set_label(label+' · Groundspeed')
            after_x,after_y=phase_values(nm,attempt.groundspeed_knots,intercept,False)
            line,=axes[2].plot(after_x,after_y,color=path_color,lw=settings.graph_line_width,ls='--',alpha=.5,zorder=2)
            line.set_gid('groundspeed-after-glide')
            if settings.show_data_points:
                keep=mask&(nm>=intercept)&np.isfinite(attempt.groundspeed_knots)
                axes[2].scatter(nm[keep],attempt.groundspeed_knots[keep],s=13,color=path_color,edgecolors=BG,linewidths=.4,zorder=8,label='Groundspeed samples')
        elif not case3 and attempt.groundspeed_knots is not None:
            line,=axes[2].plot(nm,attempt.groundspeed_knots,color=path_color,lw=settings.graph_line_width,ls='--',alpha=.5,zorder=2)
            line.set_gid('groundspeed-track')
            if comparing and not any(visible_graphs[:2]):line.set_label(label+' · Groundspeed')
        finite=np.flatnonzero(np.isfinite(attempt.aoa))
        for left,right in zip(finite[:-1],finite[1:]):
            if right>left+1 or attempt.time[right]-attempt.time[left]>3:
                if intercept is not None:
                    before_x,before_y=phase_values(nm[[left,right]],attempt.aoa[[left,right]],intercept,True)
                    bridge,=axes[2].plot(before_x,before_y,transform=aoa_ax.transData,color=aoa_color,lw=settings.graph_line_width,ls='--',alpha=.5,zorder=1.5)
                    bridge.set_gid('aoa-gap-before-glide')
                bx,by=phase_values(nm[[left,right]],attempt.aoa[[left,right]],intercept,False) if intercept is not None else (nm[[left,right]],attempt.aoa[[left,right]])
                if not np.isfinite(by).any():continue
                bridge,=aoa_ax.plot(bx,by,color=aoa_color,lw=settings.graph_line_width,ls='-',label='_nolegend_',zorder=5);bridge.set_gid('aoa-gap')
        if settings.show_data_points:
            for ax,values,color in ((axes[0],altitude,path_color),(axes[1],-attempt.lateral*FEET_PER_METRE,path_color),(aoa_ax,attempt.aoa,aoa_color)):
                keep=mask&np.isfinite(values)
                if ax is aoa_ax and intercept is not None:
                    early=keep&(nm>intercept)
                    axes[2].scatter(nm[early],values[early],transform=aoa_ax.transData,s=13,color=color,alpha=.5,zorder=1.5,label='AoA samples before glide')
                    keep&=nm<=intercept
                ax.scatter(nm[keep],values[keep],s=13,color=color,edgecolors=BG,linewidths=.4,zorder=8,label='_nolegend_' if comparing else 'Recorded samples')
        if not mask.any() and not comparing:
            for ax in axes:ax.text(.5,.6,'No samples within this graph range',transform=ax.transAxes,ha='center',color=MUTED)
        elif not comparing and not np.isfinite(attempt.aoa[mask]).any():
            aoa_ax.text(.5,.6,'No reliable velocity samples for AoA',transform=aoa_ax.transAxes,ha='center',color=MUTED)
    if attempts:
        if comparing:
            fig.suptitle(f'Comparing {len(attempts)} attempts · Case {settings.recovery_case}',color=TEXT,fontsize=13,fontweight='bold')
        else:
            attempt=attempts[0]
            fig.suptitle(attempt.player+' — '+attempt.aircraft+f' · Case {settings.recovery_case}',color=TEXT,fontsize=13,fontweight='bold')
    else:
        for ax in axes:ax.text(.5,.5,'Select a landing attempt',transform=ax.transAxes,ha='center',va='center',color=MUTED)
    if attitude_ax is not None:
        ax=axes[3];ax.set_title('Black Box',color=TEXT,loc='left',fontsize=11)
        ax.set_ylabel('Vertical speed (ft/min)',color='#438cff');ax.tick_params(axis='y',colors='#438cff')
        attitude_ax.set_ylabel('Pitch / bank (°)');attitude_ax.spines['right'].set_visible(True)
        ax.axhline(0,color=MUTED,alpha=.4,lw=.7)
        if black_box is not None:
            x=black_box['distance'];handles=[]
            for axis,key,label,color,style in ((ax,'vertical_speed','Vertical speed','#438cff','-'),
                    (attitude_ax,'pitch','Pitch','#ffe879','--'),
                    (attitude_ax,'bank','Bank','#ff727c','--')):
                line,=axis.plot(x,black_box[key],color=color,ls=style,lw=settings.graph_line_width,label=label);handles.append(line)
                if settings.show_data_points:axis.scatter(x,black_box[key],s=9,color=color)
            if settings.show_graph_key:attitude_ax.legend(handles,[line.get_label() for line in handles],loc='lower left',facecolor=PANEL,edgecolor='#344258',labelcolor=TEXT,fontsize=8,ncol=2)
    if intercept is not None and 0<=intercept<=graph_range:
        for ax in axes:
            ax.axvline(intercept,color=START_END_COLOR,alpha=settings.start_end_opacity,ls='--',lw=1.4,zorder=9)
            ax.annotate('Glide Start',xy=(intercept,.14),xycoords=('data','axes fraction'),xytext=(6,0),textcoords='offset points',ha='left',va='bottom',color=START_END_COLOR,alpha=settings.start_end_opacity,fontsize=8,bbox=dict(facecolor=PANEL,edgecolor='none',alpha=.85,pad=2),zorder=11)
    if 0<=settings.scoring_changeover_nm<=graph_range:
        for ax in axes:
            ax.axvline(settings.scoring_changeover_nm,color=START_END_COLOR,alpha=settings.start_end_opacity,ls='--',lw=1.4,zorder=9)
            ax.annotate('Glide End',xy=(settings.scoring_changeover_nm,.03),xycoords=('data','axes fraction'),xytext=(-6,0),textcoords='offset points',ha='right',va='bottom',color=START_END_COLOR,alpha=settings.start_end_opacity,fontsize=8,bbox=dict(facecolor=PANEL,edgecolor='none',alpha=.85,pad=2),zorder=11)
    if case3:
        for ax in axes:
            for nm,label,gid in ((settings.case3_platform_start_nm,'Platform Start','platform-start'),(settings.case3_platform_end_nm,'Platform End','platform-end')):
                if nm>graph_range:continue
                line=ax.axvline(nm,color=START_END_COLOR,alpha=settings.start_end_opacity,ls='--',lw=1.4,zorder=9);line.set_gid(gid)
                ax.annotate(label,xy=(nm,.14 if gid=='platform-end' else .03),xycoords=('data','axes fraction'),xytext=(-6 if gid=='platform-end' else 6,0),textcoords='offset points',ha='right' if gid=='platform-end' else 'left',va='bottom',color=START_END_COLOR,alpha=settings.start_end_opacity,fontsize=8,bbox=dict(facecolor=PANEL,edgecolor='none',alpha=.85,pad=2),zorder=11)
    # Offscreen boundary labels must not reserve space in constrained layout.
    for axis in axes:
        for text in axis.texts:
            text.set_in_layout(False);text.set_clip_on(True);text.set_clip_path(axis.patch)
    axes[-1].set_xlabel('Distance NM');axes[-1].set_xlim(graph_range,-.15)
    visible_axes=[ax for index,ax in enumerate(axes) if visible_graphs[index]]
    layout=fig.add_gridspec(len(visible_axes),1)
    for row,ax in enumerate(visible_axes):
        ax.set_subplotspec(layout[row])
        ax.set_xlabel('Distance NM' if row==len(visible_axes)-1 else '')
        ax.tick_params(axis='x',labelbottom=row==len(visible_axes)-1)
        if ax is axes[2]:aoa_ax.set_subplotspec(layout[row])
        if attitude_ax is not None and ax is axes[3]:attitude_ax.set_subplotspec(layout[row])
    for index,ax in enumerate(axes):
        if not visible_graphs[index]:fig.delaxes(ax)
    if not visible_graphs[2]:fig.delaxes(aoa_ax)
    if settings.show_timestamp and attempts and not comparing:
        bottom=visible_axes[-1]
        def timestamp_label(distance,position):
            time=latest_sample_time(attempts,distance)
            return f'{distance:g}\n'+(clock(time) if time is not None else '')
        bottom.xaxis.set_major_locator(TimestampLocator())
        bottom.xaxis.set_major_formatter(FuncFormatter(timestamp_label))
        bottom.tick_params(axis='x',labelsize=8)
    if settings.show_graph_key and attempts:
        options=dict(loc='lower left',facecolor=PANEL,edgecolor='#344258',labelcolor=TEXT,fontsize=8)
        for index in (0,1):
            if visible_graphs[index]:axes[index].legend(path_keys,key_labels,**options)
        if visible_graphs[2]:aoa_ax.legend(paired_keys,key_labels,handler_map={tuple:PairedLineKey()},**options)
    return visible_axes
