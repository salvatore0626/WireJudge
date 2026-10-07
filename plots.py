import numpy as np
from matplotlib.figure import Figure
from engine import glide_start_nm,approach_reference

BG='#111a28';PANEL='#182436';TEXT='#dce6f3';MUTED='#91a4bd';GREEN='#6cd9af';BLUE='#69b7ff'
FEET_PER_METRE=3.280839895
AOA_TARGET_DEG=8.0

def make_figure():
    return Figure(figsize=(10,8),dpi=100,facecolor=BG,layout='constrained')

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

def draw(fig,attempt,settings,origin_msl_ft=None):
    if origin_msl_ft is None:origin_msl_ft=settings.offset_y*FEET_PER_METRE
    case3=settings.recovery_case==3;intercept=glide_start_nm(settings,origin_msl_ft)
    graph_range=settings.case3_graph_range_nm if case3 else settings.graph_range_nm
    fig.clear();axes=fig.subplots(3,1,sharex=True)
    aoa_ax=axes[2].twinx()
    aoa_ax.set_zorder(axes[2].get_zorder()+1)
    aoa_ax.patch.set_visible(False)
    for ax in list(axes)+[aoa_ax]:
        ax.set_facecolor(PANEL);ax.tick_params(colors=MUTED,labelsize=9)
        ax.xaxis.label.set_color(MUTED);ax.yaxis.label.set_color(MUTED)
        for spine in ax.spines.values():spine.set_color('#344258')
        ax.spines['top'].set_visible(False)
        if ax is not aoa_ax:ax.spines['right'].set_visible(False)
        if ax in axes:ax.grid(color='#334357',alpha=.45,lw=.6)
    x=np.unique(np.r_[np.linspace(0,graph_range,400),[v for v in (3,3+1e-8,6,10) if v<=graph_range]]) if case3 else np.linspace(0,graph_range,150)
    reference=approach_reference(settings,x*1852,origin_msl_ft)
    center=reference['center']*FEET_PER_METRE;upper=reference['upper']*FEET_PER_METRE;lower=reference['lower']*FEET_PER_METRE
    ax=axes[0];ax.fill_between(x,lower,upper,color=GREEN,alpha=.10)
    ax.plot(x,upper,color=GREEN,alpha=.65,lw=1);ax.plot(x,lower,color=GREEN,alpha=.65,lw=1)
    ax.plot(x,center,color=GREEN,lw=1.3,label='Platform / glide target' if case3 else 'Glide centerline')
    ax.set_title('Case 3 Platform / Glide Path' if case3 else f'Glide Path ±{settings.glide_tolerance_deg:g}° envelope',color=TEXT,loc='left',fontsize=11)
    ax.set_ylabel('Altitude MSL (ft)')
    low=min(0,float(lower.min()),origin_msl_ft);high=max(600,float(upper.max()),origin_msl_ft+20)
    ax.set_ylim(low,high+max(20,(high-low)*.08))
    width=reference['loc_width']*FEET_PER_METRE
    ax=axes[1];ax.fill_between(x,-width,width,color=GREEN,alpha=.10)
    ax.plot(x,width,color=GREEN,alpha=.65,lw=1);ax.plot(x,-width,color=GREEN,alpha=.65,lw=1);ax.axhline(0,color=GREEN,lw=1.3)
    ax.set_title(f'Case 3 Localizer ±{settings.localizer_tolerance_deg:g}° envelope' if case3 else f'Localizer ±{settings.localizer_tolerance_deg:g}° envelope',color=TEXT,loc='left',fontsize=11)
    ax.set_ylabel('Right (−) / left (+), ft');bound=max(float(width.max()),30);ax.set_ylim(-bound*1.12,bound*1.12)
    aoa_ax.set_ylabel('AoA (degrees)');aoa_ax.set_ylim(settings.aoa_min_deg,settings.aoa_max_deg)
    if case3:
        ax=axes[2];limit=settings.case3_platform_speed_knots
        for start,end,target in ((10,6,settings.case3_leg1_speed_knots),(6,3,settings.case3_leg2_speed_knots)):
            if start<=end:continue
            ax.fill_between([end,start],target-limit,target+limit,color=GREEN,alpha=.10)
            ax.plot([end,start],[target,target],color=GREEN,lw=1.3)
        ax.set_title(f'Groundspeed / AoA - {settings.case3_leg1_speed_knots:g} / {settings.case3_leg2_speed_knots:g} knots · 8° Targets',color=TEXT,loc='left',fontsize=11)
        ax.set_ylabel('Groundspeed (knots)',color=BLUE);ax.set_ylim(max(0,min(settings.case3_leg1_speed_knots,settings.case3_leg2_speed_knots)-limit-20),max(settings.case3_leg1_speed_knots,settings.case3_leg2_speed_knots)+limit+20)
        if settings.case3_speed_deadzone_nm>0:
            half=settings.case3_speed_deadzone_nm/2
            ax.axvspan(6-half,6+half,color=MUTED,alpha=.14,zorder=1)
        ax.tick_params(axis='y',colors=BLUE);aoa_ax.tick_params(axis='y',colors='#ffce76');aoa_ax.yaxis.label.set_color('#ffce76')
        aoa_ax.plot([intercept,0],[8,8],color=GREEN,lw=1.3,label='8° target')
        for axis in axes:
            axis.axvline(6,color=MUTED,ls=':',lw=.7)
    else:
        axes[2].set_ylabel('Groundspeed (knots)',color=BLUE);axes[2].set_ylim(0,350)
        axes[2].tick_params(axis='y',colors=BLUE);aoa_ax.tick_params(axis='y',colors='#ffce76');aoa_ax.yaxis.label.set_color('#ffce76')
        aoa_ax.axhline(8,color=GREEN,lw=1.3,label='8° target')
        axes[2].set_title('Groundspeed / AoA - 8° Target',color=TEXT,loc='left',fontsize=11)
    if attempt is not None:
        d=np.asarray(attempt.distance);nm=d/1852;mask=(d>=0)&(nm<=graph_range)
        altitude=attempt.world_altitude*FEET_PER_METRE if attempt.world_altitude is not None else np.full_like(d,np.nan)
        axes[0].plot(nm[mask],altitude[mask],color=BLUE,lw=1.5,label='Aircraft path')
        axes[1].plot(nm[mask],-attempt.lateral[mask]*FEET_PER_METRE,color=BLUE,lw=1.5)
        alpha_x,alpha_y=phase_values(nm,attempt.aoa,intercept,False) if intercept is not None else (nm,attempt.aoa)
        line,=aoa_ax.plot(alpha_x,alpha_y,color='#ffce76',lw=1.5,zorder=5);line.set_gid('aoa-track')
        if intercept is not None:
            before_x,before_y=phase_values(nm,attempt.aoa,intercept,True)
            # Use the AoA coordinates but draw on the lower axis, below speed.
            line,=axes[2].plot(before_x,before_y,transform=aoa_ax.transData,color='#ffce76',lw=1.5,ls='--',alpha=.5,zorder=1.5)
            line.set_gid('aoa-before-glide')
        if case3 and attempt.groundspeed_knots is not None:
            speed_x,speed_y=phase_values(nm,attempt.groundspeed_knots,intercept,True)
            line,=axes[2].plot(speed_x,speed_y,color=BLUE,lw=1.5);line.set_gid('groundspeed-track')
            after_x,after_y=phase_values(nm,attempt.groundspeed_knots,intercept,False)
            line,=axes[2].plot(after_x,after_y,color=BLUE,lw=1.5,ls='--',alpha=.5,zorder=2)
            line.set_gid('groundspeed-after-glide')
            if settings.show_data_points:
                keep=mask&(nm>=intercept)&np.isfinite(attempt.groundspeed_knots)
                axes[2].scatter(nm[keep],attempt.groundspeed_knots[keep],s=13,color=BLUE,edgecolors=BG,linewidths=.4,zorder=8,label='Groundspeed samples')
        elif not case3 and attempt.groundspeed_knots is not None:
            line,=axes[2].plot(nm,attempt.groundspeed_knots,color=BLUE,lw=1.5,ls='--',alpha=.5,zorder=2)
            line.set_gid('groundspeed-track')
        finite=np.flatnonzero(np.isfinite(attempt.aoa))
        for left,right in zip(finite[:-1],finite[1:]):
            if right>left+1 or attempt.time[right]-attempt.time[left]>3:
                if intercept is not None:
                    before_x,before_y=phase_values(nm[[left,right]],attempt.aoa[[left,right]],intercept,True)
                    bridge,=axes[2].plot(before_x,before_y,transform=aoa_ax.transData,color='#ffce76',lw=1.5,ls='--',alpha=.5,zorder=1.5)
                    bridge.set_gid('aoa-gap-before-glide')
                bx,by=phase_values(nm[[left,right]],attempt.aoa[[left,right]],intercept,False) if intercept is not None else (nm[[left,right]],attempt.aoa[[left,right]])
                if not np.isfinite(by).any():continue
                bridge,=aoa_ax.plot(bx,by,color='#ffce76',lw=1.5,ls='-',label='_nolegend_',zorder=5);bridge.set_gid('aoa-gap')
        if settings.show_data_points:
            for ax,values,color in ((axes[0],altitude,BLUE),(axes[1],-attempt.lateral*FEET_PER_METRE,BLUE),(aoa_ax,attempt.aoa,'#ffce76')):
                keep=mask&np.isfinite(values)
                if ax is aoa_ax and intercept is not None:
                    early=keep&(nm>intercept)
                    axes[2].scatter(nm[early],values[early],transform=aoa_ax.transData,s=13,color=color,alpha=.5,zorder=1.5,label='AoA samples before glide')
                    keep&=nm<=intercept
                ax.scatter(nm[keep],values[keep],s=13,color=color,edgecolors=BG,linewidths=.4,zorder=8,label='Recorded samples')
        if not mask.any():
            for ax in axes:ax.text(.5,.6,'No samples within this graph range',transform=ax.transAxes,ha='center',color=MUTED)
        elif not np.isfinite(attempt.aoa[mask]).any():
            aoa_ax.text(.5,.6,'No reliable velocity samples for AoA',transform=aoa_ax.transAxes,ha='center',color=MUTED)
        fig.suptitle(attempt.player+' — '+attempt.aircraft+f' · Case {settings.recovery_case}',color=TEXT,fontsize=13,fontweight='bold')
    else:
        for ax in axes:ax.text(.5,.5,'Select a landing attempt',transform=ax.transAxes,ha='center',va='center',color=MUTED)
    if intercept is not None and 0<=intercept<=graph_range:
        for ax in axes:
            ax.axvline(intercept,color='#c4a1ff',ls='--',lw=1.4,zorder=9)
            ax.annotate('Glide Start',xy=(intercept,.14),xycoords=('data','axes fraction'),xytext=(6,0),textcoords='offset points',ha='left',va='bottom',color='#c4a1ff',fontsize=8,bbox=dict(facecolor=PANEL,edgecolor='none',alpha=.85,pad=2),zorder=11)
    if 0<=settings.scoring_changeover_nm<=graph_range:
        for ax in axes:
            ax.axvline(settings.scoring_changeover_nm,color='#c4a1ff',ls='--',lw=1.4,zorder=9)
            ax.annotate('Glide End',xy=(settings.scoring_changeover_nm,.03),xycoords=('data','axes fraction'),xytext=(-6,0),textcoords='offset points',ha='right',va='bottom',color='#c4a1ff',fontsize=8,bbox=dict(facecolor=PANEL,edgecolor='none',alpha=.85,pad=2),zorder=11)
    if case3:
        for ax in axes:
            for nm,label,gid in ((settings.case3_platform_start_nm,'Platform Start','platform-start'),(settings.case3_platform_end_nm,'Platform End','platform-end')):
                if nm>graph_range:continue
                line=ax.axvline(nm,color='#c4a1ff',ls='--',lw=1.4,zorder=9);line.set_gid(gid)
                ax.annotate(label,xy=(nm,.14 if gid=='platform-end' else .03),xycoords=('data','axes fraction'),xytext=(-6 if gid=='platform-end' else 6,0),textcoords='offset points',ha='right' if gid=='platform-end' else 'left',va='bottom',color='#c4a1ff',fontsize=8,bbox=dict(facecolor=PANEL,edgecolor='none',alpha=.85,pad=2),zorder=11)
    axes[0].legend(loc='upper right',facecolor=PANEL,edgecolor='#344258',labelcolor=TEXT,fontsize=8)
    axes[-1].set_xlabel('Distance NM');axes[-1].set_xlim(graph_range,0)
    return axes
