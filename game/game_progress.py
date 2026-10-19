"""Sequential configurable objectives and persistent achievement records."""
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import sys
import time
from tkinter import ttk, messagebox
from .game_config import STATS_PATH
from .game_settings import STATS
from .game_combat import Aircraft, Factory, ICBM, Missile, Bomb

ACHIEVEMENTS=[
 ('pilot',"I'm a pilot.",'Deploy an aircraft.'),('fox3','FOX 3!','Get a unit kill with an AIM-120.'),
 ('fox1','FOX 1!','Get a unit kill with an AIM-9.'),('pickle','Pickle!','Get a unit kill with a bomb.'),
 ('magnum','Magnum!','Get a unit kill with an AGM-88.'),('brrr','BRRR','Get a unit kill with CIWS.'),
 ('big_bomb','Thats a big ass bomb.','Get a unit kill with a 2000 lb bomb.'),
 ('generator','UNLIMITED POWER!','Upgrade your Generator to Level 5.'),
 ('factory','Monopoly','Upgrade your Factory to Level 5.'),('hangars','10 Fighter Garage','Upgrade your Hangars to Level 5.'),
 ('crew','Sausage party','Upgrade your Ground Crew to Level 5.'),('logistics','Rotor Head','Upgrade your Logistics to Level 5.'),
 ('choppa','Get to the choppa!','Have five helicopters deployed at once.'),
 ('kansas','Not in Kansas anymore','Travel 1000 NM from the airbase.'),
 ('leader','Follow the leader','Form up on another aircraft.'),
 ('telephone','Is that a telephone pole?!','Spot an enemy ICBM.'),
 ('oppenheimer','Oppenheimer Style','Deploy a nuke.'),
 ('paycheck','Paycheck to Paycheck','Have less than $500 in your bank account.'),
 ('pattern','Pattern Full','Have all 10 aircraft airborne at the same time.'),
 ('force','Use the force Luke',"Kill a target you haven't spotted yet with a silo missile, AGM-88 or Sidearm."),
 ('embarrassing','Thats Embarrassing','Lose an aircraft to an enemy bomber.')]

HIDDEN_ACHIEVEMENTS={'force','embarrassing'}
PROGRESS_BLUE='#438cff'


def achievement_path(settings_path=None):
    settings=Path(settings_path) if settings_path is not None else Path.home()/'.wire_judge'/'settings.json'
    return settings.parent/'game_achievements.json'


class AchievementStore:
    def __init__(self,path=None,settings_path=None):
        self.path=Path(path) if path is not None else achievement_path(settings_path)
        self.unlocked=set();self.load_error=None
        source=self.path
        if path is None and not source.exists():
            # Import the previous install-local records once; the user copy wins
            # thereafter, including an intentionally empty Reset Achievements file.
            legacy_root=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(STATS_PATH).parent
            legacy_paths=(legacy_root/'game_achievements.json',)
            if not getattr(sys,'frozen',False):
                legacy_paths+=(legacy_root.parent/'game_achievements.json',)
            for legacy in legacy_paths:
                if legacy!=self.path and legacy.is_file():
                    source=legacy
                    break
        if source.exists():
            try:
                data=json.loads(source.read_text(encoding='utf-8'));values=data['unlocked']
                if not isinstance(values,list) or any(not isinstance(v,str) for v in values):raise ValueError('Invalid achievement records')
                self.unlocked=set(values)
            except (OSError,ValueError,KeyError,TypeError) as exc:self.load_error=f'Cannot read achievements: {exc}'
            if source!=self.path and self.load_error is None:
                try:self.save()
                except (OSError,ValueError) as exc:self.load_error=f'Cannot migrate achievements: {exc}'
    def save(self):
        if self.load_error:raise ValueError(self.load_error+'; use Reset Achievements to start fresh.')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_name(self.path.name+'.tmp')
        try:
            temporary.write_text(json.dumps({'version':1,'unlocked':sorted(self.unlocked)},indent=2)+'\n',encoding='utf-8')
            os.replace(temporary,self.path)
        finally:
            if temporary.exists():temporary.unlink()
    def unlock(self,key):
        if key in self.unlocked:return False
        old=set(self.unlocked);self.unlocked.add(key)
        try:self.save()
        except (OSError,ValueError):self.unlocked=old;raise
        return True
    def reset(self):
        old=set(self.unlocked);error=self.load_error;self.unlocked=set();self.load_error=None
        try:self.save()
        except (OSError,ValueError):self.unlocked=old;self.load_error=error;raise


def target_name(unit):
    if hasattr(unit,'band_number') and hasattr(unit,'wave_counts'):return 'Airfield'
    if isinstance(unit,Aircraft):return unit.kind
    return getattr(unit,'stats_key',getattr(unit,'name',''))


def matches_weapon(required,actual):
    return required=='Any' or required==actual or (required=='Bombs' and actual.endswith(' lb Bomb'))


def campaign_objective(campaign):
    """Use the same outer radius as campaign band generation, including the core."""
    settings=campaign.settings;total=len(settings['tiers'])
    radius=settings['safe_radius_nm']+settings['band_width_nm']*total
    bands=[band for band in campaign.bands if 1<=band.number<=total]
    remaining=sum(runway.alive for band in bands for runway in band.runways)
    complete=len(bands)==total and all(not runway.alive for band in bands for runway in band.runways)
    return {'id':'campaign_final','title':'Destroy the remaining Airfields.',
            'description':f'Locate and destroy all remaining airfields within {radius:g} NM',
            'reward':0,'complete':complete,'remaining':remaining,'bands_opened':len(bands),'total_bands':total}


class RunProgress:
    def __init__(self,objectives,store):
        self.objectives=deepcopy(objectives);self.store=store;self.index=0;self.count=0
        self.levels={};self.located={};self.notifications=[];self.errors=[];self.reported_errors=set()
        self.debug_enabled=False;self.revision=0;self.final_completed=False
    def unlock(self,key):
        if self.debug_enabled:return
        try:
            if self.store.unlock(key):self.notifications.append(('achievement',key));self.revision+=1
        except (OSError,ValueError) as exc:
            if str(exc) not in self.reported_errors:self.errors.append(str(exc));self.reported_errors.add(str(exc))
    def complete_ready(self):
        while self.index<len(self.objectives):
            o=self.objectives[self.index]
            progress=self.levels.get(o['target'],0) if o['type']=='upgrade' else len(self.located.get(o['target'],set())) if o['type']=='locate' else self.count
            if progress<o['amount']:break
            self.notifications.append(('objective',deepcopy(o)));self.index+=1;self.count=0;self.revision+=1
    def action(self,kind,target,weapon='Any'):
        if self.index<len(self.objectives):
            o=self.objectives[self.index]
            if o['type']==kind and o['target']==target and (kind!='kill' or matches_weapon(o['weapon'],weapon)):
                self.count+=1;self.revision+=1
        self.complete_ready()
    def kill(self,owner,target,weapon):
        if isinstance(owner,Aircraft) and owner.enemy and owner.kind=='Bomber' and isinstance(target,Aircraft) and not target.enemy and not isinstance(target,ICBM):
            self.unlock('embarrassing')
        if getattr(owner,'enemy',False) or not getattr(target,'enemy',False) or isinstance(target,(Missile,Bomb,ICBM)):return
        self.action('kill',target_name(target),weapon)
        if not getattr(target,'kill_was_spotted',True) and weapon in ('AGM-88','Sidearm','Conventional','Cluster','Nuclear'):
            self.unlock('force')
        key={'AIM-120':'fox3','AIM-9':'fox1','AGM-88':'magnum','CIWS':'brrr'}.get(weapon)
        if key:self.unlock(key)
        if weapon.endswith(' lb Bomb'):self.unlock('pickle')
        if weapon=='2000 lb Bomb':self.unlock('big_bomb')
    def snapshot(self,levels,located):
        for target,level in levels.items():self.levels[target]=max(level,self.levels.get(target,0))
        for target,ids in located.items():self.located.setdefault(target,set()).update(ids)
        self.complete_ready()
        for target,key in (('Generator','generator'),('Factory','factory'),('Hangars','hangars'),('Ground Crew','crew'),('Logistics','logistics')):
            if self.levels.get(target,0)>=5:self.unlock(key)
    def objective_progress(self):
        if self.index>=len(self.objectives):return 0
        o=self.objectives[self.index]
        return self.levels.get(o['target'],0) if o['type']=='upgrade' else len(self.located.get(o['target'],set())) if o['type']=='locate' else self.count


class ProgressUI:
    def init_progress(self):
        self.debug_enabled=False;self.debug_shortcut_down=False
        self.progress=RunProgress(STATS['objectives'],AchievementStore(settings_path=getattr(self.app,'settings_path',None)))
        self.progress_scroll_panel,self.progress_panel,self.progress_scroll_canvas=self.create_scroll_menu()
        style=ttk.Style(self)
        style.configure('ProgressNotice.TFrame',bordercolor=PROGRESS_BLUE,lightcolor=PROGRESS_BLUE,darkcolor=PROGRESS_BLUE,borderwidth=2,relief='solid')
        style.configure('ObjectiveInstrument.TFrame',background='#0c1928',bordercolor=PROGRESS_BLUE,lightcolor=PROGRESS_BLUE,darkcolor=PROGRESS_BLUE,borderwidth=2,relief='solid')
        style.configure('ObjectiveInterior.TFrame',background='#0c1928')
        style.configure('ObjectiveInstrument.TLabel',background='#0c1928',foreground='#a4b5ca')
        style.configure('Objective.Horizontal.TProgressbar',background=PROGRESS_BLUE,troughcolor='#172c43',bordercolor='#172c43',lightcolor=PROGRESS_BLUE,darkcolor=PROGRESS_BLUE)
        style.configure('ProgressConfirm.TButton',background=PROGRESS_BLUE,foreground='white')
        style.map('ProgressConfirm.TButton',background=[('active','#69adff'),('!disabled',PROGRESS_BLUE)],foreground=[('!disabled','white')])
        self.objective_popup=ttk.Frame(self,padding=12,style='ProgressNotice.TFrame');self.objective_notices=[];self.objective_popup_id=None;self.progress_notice_job=None
        self.progress_menu_revision=None
        ttk.Button(self.debug_panel,text='Reset Achievements',command=self.reset_achievements).pack(fill='x',pady=(10,0))
    def progress_action(self,kind,target,weapon='Any'):
        if not self.run_started:return
        self.progress.action(kind,target,weapon);self.process_progress_notices()
    def process_progress_notices(self):
        notices=self.progress.notifications[:];self.progress.notifications.clear()
        for kind,value in notices:
            if kind=='objective':
                self.money+=value['reward'];self.add_log(f'Objective complete: {value["title"]}'+(f' · +${value["reward"]:,.0f}' if value['reward'] else ''),'reward')
                self.objective_notices.append(dict(value,kind='objective',ready_at=time.monotonic()+2.))
            else:
                title,description=next((title,desc) for key,title,desc in ACHIEVEMENTS if key==value)
                self.objective_notices.append({'id':'achievement:'+value,'kind':'achievement','title':title,'description':description,'ready_at':time.monotonic()+2.})
                self.add_log(f'Achievement unlocked: {title}','reward')
        for error in self.progress.errors:self.add_log(error,'status')
        self.progress.errors.clear()
        if notices:self.refresh_resources()
        self.refresh_objective_popup()
        if self.left_menu=='Objectives':self.refresh_progress_menu()
    def poll_progress(self):
        if not self.run_started:return
        for owner,target,weapon in self.combat.progress_kills:self.progress.kill(owner,target,weapon)
        self.combat.progress_kills.clear()
        if self.money<500:self.progress.unlock('paycheck')
        if getattr(self.combat,'nuclear_launches',0)>0:self.progress.unlock('oppenheimer')
        airborne_count=sum(a.alive and (a.state in ('airborne','rtb','approach') or a.state=='takeoff' and a.takeoff_airborne) for a in self.aircraft.values())
        if airborne_count>=10:self.progress.unlock('pattern')
        levels={'Airfield':self.airfield.level,'Generator':self.airfield.power_level,'Factory':self.airfield.factory_level,
                'Hangars':self.airfield.hangar_level,'Ground Crew':self.airfield.ground_crew_level,'Logistics':self.airfield.logistics_level}
        located={}
        for unit in [*self.combat.factories,*self.combat.enemy_radars,*self.combat.enemy_sams]:
            known=unit.id in self.combat.known if isinstance(unit,Factory) else id(unit) in self.combat.known_ground
            if known:located.setdefault(target_name(unit),set()).add(id(unit))
        for contact in self.combat.contacts[False].values():
            unit=contact.target
            if unit.enemy:located.setdefault(target_name(unit),set()).add(id(unit))
        self.progress.snapshot(levels,located)
        campaign=getattr(self,'campaign',None)
        if campaign is not None and self.progress.index>=len(self.progress.objectives) and not self.progress.final_completed:
            final=campaign_objective(campaign)
            if final['complete']:
                self.progress.final_completed=True;self.progress.revision+=1
                self.progress.notifications.append(('objective',final))
        for a in self.aircraft.values():
            if a.state in ('airborne','rtb','approach') or a.state=='takeoff' and a.takeoff_airborne:self.progress.unlock('pilot')
            if a.alive and math.dist((a.x,a.y),(self.airfield.x,self.airfield.y))>=1000:self.progress.unlock('kansas')
            if a.alive and a.leader is not None:self.progress.unlock('leader')
        if sum(h.state in ('outbound','returning') for h in self.logistics.helicopters)>=5:self.progress.unlock('choppa')
        if self.progress.located.get('ICBM') or any(m.enemy and getattr(m,'player_spotted',False) for m in self.combat.icbms):self.progress.unlock('telephone')
        self.process_progress_notices()
    def refresh_progress_menu(self):
        final=campaign_objective(self.campaign) if getattr(self,'campaign',None) is not None else None
        final_signature=(final['description'],final['remaining'],final['bands_opened'],final['total_bands'],final['complete']) if final else None
        signature=(self.progress.revision,self.progress.index,self.progress.objective_progress(),self.debug_enabled,self.run_result,final_signature)
        if signature==self.progress_menu_revision:return
        self.progress_menu_revision=signature
        for child in self.progress_panel.winfo_children():child.destroy()
        if self.run_result is not None:ttk.Button(self.progress_panel,text='Back to Results',command=lambda:self.show_run_screen(self.run_result)).pack(fill='x',pady=(0,10))
        objective_panel=ttk.Frame(self.progress_panel,style='ObjectiveInstrument.TFrame',padding=12)
        objective_panel.pack(fill='x',pady=(0,14))
        header=ttk.Frame(objective_panel,style='ObjectiveInterior.TFrame')
        header.pack(fill='x',pady=(0,10))
        ttk.Label(header,text='YOUR OBJECTIVE',style='ObjectiveInstrument.TLabel',font=('Helvetica',11,'bold'),foreground=PROGRESS_BLUE).pack(side='left')
        active=self.progress.index<len(self.progress.objectives) or final is not None and not final['complete']
        ttk.Label(header,text='● ACTIVE' if active else '✓ COMPLETE',style='ObjectiveInstrument.TLabel',font=('Helvetica',8,'bold'),foreground=PROGRESS_BLUE if active else '#72d693').pack(side='right')
        if self.progress.index<len(self.progress.objectives):
            o=self.progress.objectives[self.progress.index];count=min(o['amount'],self.progress.objective_progress())
            ttk.Label(objective_panel,text=f'{self.progress.index+1}. {o["title"]}',style='ObjectiveInstrument.TLabel',foreground=PROGRESS_BLUE,font=('Helvetica',13,'bold'),wraplength=230,justify='left').pack(fill='x',pady=(0,10))
            ttk.Progressbar(objective_panel,style='Objective.Horizontal.TProgressbar',maximum=o['amount'],value=count).pack(fill='x',pady=(0,5))
            status=f'{count}/{o["amount"]} '+('Factories destroyed' if o['type']=='kill' and o['target']=='Factory' else 'Located' if o['type']=='locate' else 'Progress')
            ttk.Label(objective_panel,text=status,style='ObjectiveInstrument.TLabel',font=('Courier',10),wraplength=230).pack(fill='x')
            ttk.Label(objective_panel,text=f'Reward ${o["reward"]:,.0f}',style='ObjectiveInstrument.TLabel',foreground='#72d693',wraplength=230).pack(fill='x',pady=(6,0))
        elif final is not None:
            ttk.Label(objective_panel,text=('✓ ' if final['complete'] else '')+final['title'],style='ObjectiveInstrument.TLabel',font=('Helvetica',13,'bold'),foreground='#72d693' if final['complete'] else PROGRESS_BLUE,wraplength=230).pack(fill='x',pady=(0,8))
            ttk.Label(objective_panel,text=final['description'],style='ObjectiveInstrument.TLabel',wraplength=230,justify='left').pack(fill='x',pady=(0,10))
            ttk.Progressbar(objective_panel,style='Objective.Horizontal.TProgressbar',maximum=final['total_bands'],value=sum(all(not runway.alive for runway in band.runways) for band in self.campaign.bands if 1<=band.number<=final['total_bands'])).pack(fill='x',pady=(0,5))
        else:ttk.Label(objective_panel,text='All objectives completed!',style='ObjectiveInstrument.TLabel',foreground='#72d693',wraplength=230).pack(fill='x')
        for i,o in enumerate(self.progress.objectives):
            if i<self.progress.index:ttk.Label(self.progress_panel,text='✓ '+o['title'],foreground='#72d693',wraplength=270).pack(anchor='w',pady=2)
        ttk.Separator(self.progress_panel,orient='horizontal').pack(fill='x',pady=(18,4))
        ttk.Label(self.progress_panel,text='ACHIEVEMENTS',font=('Helvetica',12,'bold'),anchor='center').pack(fill='x',pady=(16,8))
        completed=sum(key in self.progress.store.unlocked for key,_,_ in ACHIEVEMENTS)
        ttk.Progressbar(self.progress_panel,maximum=len(ACHIEVEMENTS),value=completed).pack(fill='x')
        ttk.Label(self.progress_panel,text=f'{completed/len(ACHIEVEMENTS):.0%} complete · {completed}/{len(ACHIEVEMENTS)}',anchor='center').pack(fill='x',pady=(3,8))
        if self.debug_enabled:ttk.Label(self.progress_panel,text='Debug enabled · New achievements disabled for this run.',foreground='#e6bd48',wraplength=270).pack(fill='x',pady=(0,8))
        for key,title,description in ACHIEVEMENTS:
            earned=key in self.progress.store.unlocked
            ttk.Label(self.progress_panel,text=('✓ ' if earned else '○ ')+title,foreground='#72d693' if earned else '#dfe9f5',font=('Helvetica',13,'bold'),wraplength=270).pack(anchor='w',pady=(8,0))
            if earned or key not in HIDDEN_ACHIEVEMENTS:
                ttk.Label(self.progress_panel,text=description,wraplength=270).pack(anchor='w',pady=(0,3))
            else:ttk.Label(self.progress_panel,text='Hidden achievement',foreground='#91a0b2').pack(anchor='w',pady=(0,3))
        self.bind_menu_wheel(self.progress_panel,self.progress_scroll_canvas)
    def progress_notice_ready(self):
        self.progress_notice_job=None
        self.refresh_objective_popup()
    def refresh_objective_popup(self):
        if not self.objective_notices:
            if getattr(self,'progress_notice_job',None) is not None:
                self.after_cancel(self.progress_notice_job);self.progress_notice_job=None
            self.objective_popup.place_forget();self.objective_popup_id=None;return
        o=self.objective_notices[0]
        remaining=o.get('ready_at',0)-time.monotonic()
        if remaining>0:
            self.objective_popup.place_forget();self.objective_popup_id=None
            if getattr(self,'progress_notice_job',None) is None:
                self.progress_notice_job=self.after(max(1,math.ceil(remaining*1000)),self.progress_notice_ready)
            return
        if self.objective_popup_id!=o['id']:
            for child in self.objective_popup.winfo_children():child.destroy()
            achievement=o.get('kind')=='achievement'
            ttk.Label(self.objective_popup,text='ACHIEVEMENT UNLOCKED' if achievement else 'OBJECTIVE COMPLETE',font=('Helvetica',11,'bold'),foreground=PROGRESS_BLUE).pack(anchor='w')
            ttk.Label(self.objective_popup,text=o['title'],font=('Helvetica',13,'bold'),foreground=PROGRESS_BLUE,wraplength=250,justify='left').pack(fill='x',pady=(6,3))
            ttk.Label(self.objective_popup,text=o['description'] if achievement else o.get('description',f'+${o["reward"]:,.0f}'),wraplength=250,justify='left').pack(fill='x',pady=(0,6))
            ttk.Button(self.objective_popup,text='Confirm',style='ProgressConfirm.TButton',command=self.confirm_objective).pack(fill='x')
            self.objective_popup_id=o['id']
            self.play_game_sound('achievement_unlocked' if achievement else 'objective_complete')
        self.objective_popup.place(in_=self.canvas,x=12,rely=1.,y=-12,anchor='sw');self.objective_popup.lift()
    def confirm_objective(self):
        if self.objective_notices:self.objective_notices.pop(0)
        if self.run_result is not None:self.run_screen.place_forget()
        self.show_left_menu('Objectives');self.refresh_objective_popup()
    def enable_debug_menu(self):
        if self.playing:self.tick_elapsed()
        was_playing=self.playing
        self.playing=False
        if self.job is not None:self.after_cancel(self.job);self.job=None
        self.play_button.configure(image=self.pause_icon,style='GamePause.TButton')
        if not self.debug_enabled:
            yes=messagebox.askyesno('Enable debug mode?', 'You are about to enable the debug menu. Doing so will disable achievements for the entire run. Do you want to enable debug mode?',parent=self)
            if not yes:
                self.playing=was_playing;self.last_tick=__import__('time').monotonic()
                self.play_button.configure(image=self.play_icon if was_playing else self.pause_icon,style='GamePlay.TButton' if was_playing else 'GamePause.TButton')
                self.schedule_tick();return
            self.debug_enabled=True;self.progress.debug_enabled=True;self.progress.revision+=1
        self.show_left_menu('Debug');self.schedule_tick()
    def reset_achievements(self):
        if not self.debug_enabled:return
        if not messagebox.askyesno('Reset achievements?', 'Reset all persistent achievements? Objectives will keep their current progress.',parent=self):return
        try:self.progress.store.reset()
        except (OSError,ValueError) as exc:messagebox.showerror('Cannot reset achievements',str(exc),parent=self);return
        self.progress.revision+=1;self.add_log('Achievements reset','status')
        self.refresh_progress_menu()
