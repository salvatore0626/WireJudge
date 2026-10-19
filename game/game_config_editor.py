"""Standalone native editor for every game_stats.json setting (standard library only)."""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .game_config import SCHEMA, STATS_PATH, load_stats, OBJECTIVE_DEFAULTS
from .game_campaign_comparison import CampaignComparison


def label(key):
    special = {'cms': 'Countermeasures', 'icbm': 'ICBM', 'ground_units': 'Friendly ground units',
               'Power': 'Generator', 'objectives':'Objectives', 'tiers': 'Campaign zones', 'default_loadouts': 'Friendly default loadouts'}
    return special.get(str(key), str(key) if any(c.isupper() for c in str(key)) else str(key).replace('_', ' ').capitalize()).replace('band', 'zone').replace('Band', 'Zone').replace('visual', 'optical').replace('Visual', 'Optical')


def get_at(data, path):
    for part in path:
        data = data[part]
    return data


def set_at(data, path, value):
    get_at(data, path[:-1])[path[-1]] = value


def rule_at(path):
    rule = SCHEMA
    for part in path:
        rule = rule['$list'] if isinstance(part, int) else rule[part]
    return rule


def leaves(data, path=()):
    if isinstance(data, dict):
        for key, value in data.items():
            yield from leaves(value, path + (key,))
    elif isinstance(data, list):
        for i, value in enumerate(data):
            yield from leaves(value, path + (i,))
    else:
        yield path, data


def parse_value(text, rule, path):
    name = '.'.join(map(str, path))
    if rule == 'text':
        return str(text)
    if rule == 'boolean':
        return bool(text)
    try:
        value = int(text) if rule == 'integer' else float(text)
    except (ValueError, TypeError):
        raise ValueError(f'{name}: enter {"a whole number" if rule == "integer" else "a number"}') from None
    if not math.isfinite(value):
        raise ValueError(f'{name}: enter a finite number')
    if value < 0 or (rule == 'positive' and value <= 0):
        raise ValueError(f'{name}: must be {"> 0" if rule == "positive" else ">= 0"}')
    if rule == 'fraction' and value > 1:
        raise ValueError(f'{name}: must be between 0 and 1')
    return int(value) if isinstance(value,float) and value.is_integer() else value


def validate_data(data):
    # Reuse the entire game's validator, including cross-setting rules.
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'game_stats.json'
        path.write_text(json.dumps(data, allow_nan=False), encoding='utf-8')
        return load_stats(path)


class ConfigDocument:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.data = load_stats(self.path)
        self.original = deepcopy(self.data)
        self.fingerprint = self.digest(self.path)

    @staticmethod
    def digest(path):
        return hashlib.sha256(Path(path).read_bytes()).digest()

    def save(self, data, path=None):
        validate_data(data)
        target = Path(path or self.path).resolve()
        if target == self.path and self.digest(target) != self.fingerprint:
            raise ValueError('The JSON changed outside this editor. Open it again before saving to avoid overwriting those changes.')
        backup = None
        if target.exists():
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            backup = target.with_name(target.name + '.' + stamp + '.bak')
            shutil.copy2(target, backup)
        # Write atomically so a failed save cannot leave a partial JSON file.
        fd, temporary = tempfile.mkstemp(prefix=target.name + '.', suffix='.tmp', dir=target.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False, allow_nan=False)
                handle.write('\n')
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        self.path = target
        self.data = deepcopy(data)
        self.original = deepcopy(data)
        self.fingerprint = self.digest(target)
        return backup


class ConfigEditor(tk.Tk):
    def __init__(self, path=STATS_PATH):
        super().__init__()
        self.title('Wire Judge · Game Settings')
        self.geometry('1180x800')
        self.minsize(850,560)
        self.configure(bg='#101b2b')
        self.document = None
        self.variables = {}
        self.selection = None
        self.tree_paths = {}
        self.dirty = False
        self.search_job = None
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', background='#101b2b', foreground='#e4ecf6', font=('Segoe UI',10))
        style.configure('TEntry', fieldbackground='#22334b', foreground='#ffffff', insertcolor='white')
        style.configure('TCombobox', fieldbackground='#22334b', foreground='white')
        style.map('TCombobox', fieldbackground=[('readonly','#22334b')], foreground=[('readonly','white')])
        style.configure('TButton', padding=(12,7), background='#263b55')
        style.map('TButton', background=[('active','#355779')])
        style.configure('Save.TButton', background='#237350')
        style.configure('Treeview', background='#17263a', fieldbackground='#17263a', rowheight=27)
        style.map('Treeview', background=[('selected','#305d8b')])
        style.configure('Heading.TLabel',font=('Segoe UI',17,'bold'))
        style.configure('Muted.TLabel',foreground='#a6b7cb')
        toolbar = ttk.Frame(self, padding=14)
        toolbar.pack(fill='x')
        ttk.Label(toolbar, text='GAME SETTINGS', style='Heading.TLabel').pack(side='left')
        for text, command, sty in [('Save','save','Save.TButton'),('Save As…','save_as','TButton'),('Validate','validate','TButton'),('Open…','open_file','TButton')]:
            ttk.Button(toolbar,text=text,command=getattr(self,command),style=sty).pack(side='right',padx=4)
        self.filename = ttk.Label(self, style='Muted.TLabel', padding=(16,0,16,8))
        self.filename.pack(fill='x')
        pane = ttk.Panedwindow(self, orient='horizontal')
        pane.pack(fill='both',expand=True,padx=14)
        nav = ttk.Frame(pane)
        pane.add(nav,weight=1)
        self.search = tk.StringVar()
        ttk.Label(nav,text='Search settings',style='Muted.TLabel').pack(anchor='w',pady=(0,5))
        ttk.Entry(nav,textvariable=self.search).pack(fill='x',pady=(0,8))
        self.search.trace_add('write', self.schedule_search)
        navbody = ttk.Frame(nav)
        navbody.pack(fill='both',expand=True)
        self.tree = ttk.Treeview(navbody,show='tree',selectmode='browse')
        self.tree.pack(side='left',fill='both',expand=True)
        bar=ttk.Scrollbar(navbody,command=self.tree.yview)
        bar.pack(side='right',fill='y')
        self.tree.configure(yscrollcommand=bar.set)
        self.tree.bind('<<TreeviewSelect>>',self.select)
        right = ttk.Frame(pane,padding=(18,0,0,0))
        pane.add(right,weight=4)
        self.heading = ttk.Label(right,text='Select a settings group',style='Heading.TLabel')
        self.heading.pack(anchor='w')
        self.actions = ttk.Frame(right)
        self.actions.pack(fill='x',pady=8)
        ttk.Label(right,text='Distances: NM · Speeds: knots · Times: game seconds · Fractions: 0.10 = 10%',style='Muted.TLabel').pack(anchor='w',pady=(0,10))
        body=ttk.Frame(right)
        body.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(body,bg='#101b2b',highlightthickness=0)
        self.canvas.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(body,command=self.canvas.yview)
        scroll.pack(side='right',fill='y')
        self.canvas.configure(yscrollcommand=scroll.set)
        self.form=ttk.Frame(self.canvas,padding=(0,0,12,14))
        self.form_window=self.canvas.create_window(0,0,window=self.form,anchor='nw')
        self.form.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(self.form_window,width=e.width))
        self.bind_all('<MouseWheel>',self.wheel)
        self.bind_all('<Button-4>',self.wheel)
        self.bind_all('<Button-5>',self.wheel)
        footer=ttk.Frame(self,padding=14)
        footer.pack(fill='x')
        self.status=ttk.Label(footer,text='Open a game_stats.json file to begin.',style='Muted.TLabel')
        self.status.pack(side='left',fill='x',expand=True)
        ttk.Button(footer,text='Reference notes',command=self.notes).pack(side='right')
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.bind('<Control-s>',lambda e:self.save())
        self.bind('<Control-o>',lambda e:self.open_file())
        self.after_idle(lambda:self.load(path))

    def wheel(self,event):
        widget=self.winfo_containing(event.x_root,event.y_root)
        if widget and (widget==self.canvas or str(widget).startswith(str(self.form))):
            delta=-1 if getattr(event,'num',None)==4 else 1 if getattr(event,'num',None)==5 else -int(event.delta/120) if abs(event.delta)>=120 else -1 if event.delta>0 else 1
            self.canvas.yview_scroll(delta,'units')
            return 'break'

    def mark_dirty(self,*args):
        self.dirty=True
        self.title('Wire Judge · Game Settings *')
        self.status.configure(text='Unsaved changes. Save, then restart Wire Judge to apply them.')

    def collected(self):
        data=deepcopy(self.document.data)
        for path,var in self.variables.items():
            set_at(data,path,parse_value(var.get(),rule_at(path),path))
        return data

    def confirm_discard(self):
        return not self.dirty or messagebox.askyesno('Unsaved changes','Discard unsaved changes?',parent=self)

    def load(self,path):
        try:
            document=ConfigDocument(path)
        except (ValueError,OSError) as exc:
            messagebox.showerror('Cannot open settings',str(exc),parent=self)
            return
        self.document=document
        self.variables={}
        self.dirty=False
        self.selection=None
        self.title('Wire Judge · Game Settings')
        self.filename.configure(text=str(document.path))
        self.search.set('')
        self.rebuild_tree()
        self.status.configure(text='All settings loaded. Save, then restart Wire Judge to apply changes.')

    def open_file(self):
        if not self.confirm_discard(): return
        path=filedialog.askopenfilename(parent=self,title='Open game settings',initialdir=STATS_PATH.parent,filetypes=[('JSON settings','*.json')])
        if path:self.load(path)

    def schedule_search(self,*args):
        if self.search_job:self.after_cancel(self.search_job)
        self.search_job=self.after(180,self.rebuild_tree)

    def rebuild_tree(self):
        self.search_job=None
        if not self.document:return
        self.tree.delete(*self.tree.get_children())
        self.tree_paths={}
        query=self.search.get().strip().lower()
        def add(value,path,parent):
            text=(f'Objective {path[-1]+1} · {value.get("title","")}' if path[0]=='objectives' else f'Zone {path[-1]+1}') if isinstance(path[-1],int) else label(path[-1])
            matches=not query or any(query in (' '.join(map(str,p))+' '+label(p[-1])).lower() for p,_ in leaves(value,path))
            if not matches:return
            iid=self.tree.insert(parent,'end',text=text,open=bool(query) or len(path)==1)
            self.tree_paths[iid]=path
            if isinstance(value,dict):
                for key,child in value.items():
                    if isinstance(child,(dict,list)):add(child,path+(key,),iid)
            elif value and isinstance(value[0],dict):
                for i,child in enumerate(value):add(child,path+(i,),iid)
        for key,value in self.document.data.items():add(value,(key,),'')
        iid=next((i for i,p in self.tree_paths.items() if p==self.selection),None)
        if iid is None:iid=next(iter(self.tree_paths),None)
        if iid:self.tree.selection_set(iid);self.tree.see(iid);self.select()
        else:self.render(None)

    def select(self,event=None):
        selected=self.tree.selection()
        if selected:self.render(self.tree_paths[selected[0]])

    def variable(self,path,value):
        if path not in self.variables:
            var=tk.BooleanVar(value=value) if isinstance(value,bool) else tk.StringVar(value=str(value))
            var.trace_add('write',self.mark_dirty)
            self.variables[path]=var
        return self.variables[path]

    def render(self,path):
        self.selection=path
        for child in self.form.winfo_children():child.destroy()
        for child in self.actions.winfo_children():child.destroy()
        self.canvas.yview_moveto(0)
        if path is None:
            self.heading.configure(text='No matching settings')
            return
        self.heading.configure(text=' / '.join((f'Objective {p+1}' if path[0]=='objectives' else f'Zone {p+1}') if isinstance(p,int) else label(p) for p in path))
        ttk.Button(self.actions,text='Reset this group',command=self.reset_group).pack(side='left')
        if path[0]=='campaign':ttk.Button(self.actions,text='Compare Zones',command=self.compare_campaign).pack(side='left',padx=6)
        if path[:2]==('campaign','tiers'):
            ttk.Button(self.actions,text='Duplicate zone' if len(path)>2 else 'Add zone',command=self.add_band).pack(side='left',padx=6)
            if len(path)>2:ttk.Button(self.actions,text='Remove zone',command=self.remove_band).pack(side='left')
        if path[0]=='objectives':
            ttk.Button(self.actions,text='Add objective',command=lambda:self.edit_objective('add')).pack(side='left',padx=4)
            if len(path)>1:
                for title,action in (('Duplicate','duplicate'),('Remove','remove'),('Up','up'),('Down','down')):
                    ttk.Button(self.actions,text=title,command=lambda action=action:self.edit_objective(action)).pack(side='left',padx=2)
        query=self.search.get().lower().strip()
        def build(value,p,depth=0):
            if isinstance(value,(dict,list)):
                if p!=path:
                    ttk.Label(self.form,text=label(p[-1]) if not isinstance(p[-1],int) else f'Objective {p[-1]+1}' if p[0]=='objectives' else f'Zone {p[-1]+1}',font=('Segoe UI',11,'bold')).pack(anchor='w',pady=(14,5))
                if isinstance(value,list) and rule_at(p).get('$length') is None and p not in (('campaign','tiers'),('objectives',)):
                    controls=ttk.Frame(self.form);controls.pack(anchor='w',pady=4)
                    ttk.Button(controls,text='+ Add entry',command=lambda:self.resize_list(p,1)).pack(side='left')
                    if value:ttk.Button(controls,text='− Remove last',command=lambda:self.resize_list(p,-1)).pack(side='left',padx=4)
                items=value.items() if isinstance(value,dict) else enumerate(value)
                for key,child in items:build(child,p+(key,),depth+1)
                return
            if query and query not in (' '.join(map(str,p))+' '+label(p[-1])).lower():return
            row=ttk.Frame(self.form);row.pack(fill='x',pady=5)
            key=p[-1]
            if key in ('description','runway_description'):
                ttk.Label(row,text=label(key)).pack(anchor='w')
                var=self.variable(p,value)
                editor=tk.Text(row,height=4,width=40,wrap='word',background='#22334b',foreground='white',insertbackground='white',undo=True)
                editor.insert('1.0',var.get());editor.edit_modified(False);editor.pack(fill='x',expand=True,pady=(4,0))
                def changed(event,editor=editor,var=var):
                    if editor.edit_modified():
                        var.set(editor.get('1.0','end-1c'));editor.edit_modified(False)
                editor.bind('<<Modified>>',changed)
                return
            if isinstance(key,int):
                container=rule_at(p[:-1]);length=container.get('$length')
                text=('Minimum' if key==0 else 'Maximum') if length==2 else f'Level {key+2 if "prices" in p else key+1}' if length in (4,5) else f'Slot {key+1}' if p[-2] in ('hardpoints','bays') else f'Entry {key+1}'
            else:text=label(key)
            ttk.Label(row,text=text,wraplength=300).pack(side='left',fill='x',expand=True)
            var=self.variable(p,value);rule=rule_at(p)
            if rule=='boolean':ttk.Checkbutton(row,text='Enabled',variable=var).pack(side='right')
            elif rule=='text' and p[0]=='objectives' and p[-1] in ('type','target','weapon'):
                options=('build','kill','upgrade','locate') if p[-1]=='type' else (
                    ['Any','Bombs','AIM-120','AIM-9','AGM-88','Sidearm','CIWS','Flak','Conventional','Cluster','Nuclear',*[f'{w} lb Bomb' for w in self.document.data['bombs']]] if p[-1]=='weapon' else
                    sorted(set(self.document.data['friendly_aircraft'])|set(self.document.data['enemy_aircraft'])|set(self.document.data['ground_units'])|set(self.document.data['enemy_ground_units'])|{'Airfield','ICBM','Generator','Factory','Hangars','Ground Crew','Logistics'}))
                ttk.Combobox(row,textvariable=var,values=options,width=23,state='readonly').pack(side='right')
            elif rule=='text' and p[:2]==('upgrades','airfield_unlocks'):
                options=sorted({x for group in self.document.original['upgrades']['airfield_unlocks'].values() for x in group})
                ttk.Combobox(row,textvariable=var,values=options,width=23,state='readonly').pack(side='right')
            elif rule=='text' and p[-2] in ('hardpoints','bays'):
                options=['Empty']
                if p[-2]=='hardpoints':
                    spec=self.document.data['missiles']
                    options += [f'{spec[k]["hardpoint_count"]}× {"AIM-120C" if k=="AIM-120" else k}' for k in ('AIM-120','AIM-9','AGM-88','Sidearm')]
                    options += ['1× Sidearm']
                else:options += [f'{v["bay_count"]}× {int(k):,} lb Bomb' for k,v in self.document.data['bombs'].items()]
                ttk.Combobox(row,textvariable=var,values=list(dict.fromkeys([value,*options])),width=23,state='readonly').pack(side='right')
            else:ttk.Entry(row,textvariable=var,width=24 if rule=='text' else 16).pack(side='right')
            hint={'fraction':'0–1 fraction','integer':'whole number','positive':'greater than 0','number':'0 or greater','text':'text'}.get(rule,'')
            if hint:ttk.Label(row,text=hint,style='Muted.TLabel',width=17).pack(side='right',padx=10)
        build(get_at(self.document.data,path),path)

    def edit_objective(self,action):
        index=self.selection[1] if len(self.selection)>1 else 0
        def change(data):
            values=data['objectives']
            if action in ('add','duplicate'):
                objective=deepcopy(values[index]) if action=='duplicate' and values else deepcopy(OBJECTIVE_DEFAULTS[0])
                ids={o['id'] for o in values};number=1
                while f'objective_{number}' in ids:number+=1
                objective['id']=f'objective_{number}'
                if action=='add':objective['title']='New objective'
                position=index+1 if action=='duplicate' and values else len(values)
                values.insert(position,objective);self.selection=('objectives',position)
            elif action=='remove' and values:
                values.pop(index);self.selection=('objectives',min(index,len(values)-1)) if values else ('objectives',)
            elif action in ('up','down') and values:
                other=index+(-1 if action=='up' else 1)
                if 0<=other<len(values):values[index],values[other]=values[other],values[index];self.selection=('objectives',other)
        self.change_structure(change)

    def compare_campaign(self):
        if self.document is None:return
        try:self.comparison_data()
        except (ValueError,OSError) as exc:
            messagebox.showerror('Cannot compare campaign',str(exc),parent=self);return
        CampaignComparison(self,self.comparison_data,self.apply_comparison_edit)

    def comparison_data(self):
        data=self.collected()
        validate_data(data)
        return data

    def apply_comparison_edit(self,path,value):
        data=self.collected()
        set_at(data,path,value)
        validate_data(data)
        self.document.data=data;self.variables={};self.selection=path
        self.mark_dirty();self.rebuild_tree()

    def change_structure(self,action):
        try:
            data=self.collected()
            action(data)
            self.document.data=data
            self.variables={}
            self.mark_dirty()
            self.rebuild_tree()
        except (ValueError,IndexError) as exc:messagebox.showerror('Cannot change list',str(exc),parent=self)

    def resize_list(self,path,delta):
        def change(data):
            values=get_at(data,path)
            if delta>0:values.append(values[-1] if values else 'Fighter' if path[:2]==('upgrades','airfield_unlocks') else 'Empty' if path[-1] in ('hardpoints','bays') else '' if rule_at(path)['$list']=='text' else 1)
            elif values:values.pop()
        self.change_structure(change)

    def add_band(self):
        index=self.selection[2] if len(self.selection)>2 else -1
        def change(data):
            tiers=data['campaign']['tiers']
            tiers.append(deepcopy(tiers[index]))
            self.selection=('campaign','tiers',len(tiers)-1)
        self.change_structure(change)

    def remove_band(self):
        index=self.selection[2]
        def change(data):
            tiers=data['campaign']['tiers']
            if len(tiers)==1:raise ValueError('Keep at least one campaign zone.')
            tiers.pop(index)
            self.selection=('campaign','tiers',min(index,len(tiers)-1))
        self.change_structure(change)

    def reset_group(self):
        path=self.selection
        if not path:return
        try:original=deepcopy(get_at(self.document.original,path))
        except (IndexError,KeyError):
            messagebox.showinfo('New group','This group did not exist when the file was opened.',parent=self);return
        set_at(self.document.data,path,original)
        self.variables={p:v for p,v in self.variables.items() if p[:len(path)]!=path}
        self.mark_dirty();self.rebuild_tree()

    def validate(self):
        if not self.document:return
        try:validate_data(self.collected())
        except (ValueError,OSError) as exc:
            messagebox.showerror('Invalid settings',str(exc),parent=self);return
        self.status.configure(text='Validation passed. All current settings satisfy the game’s checks.')

    def save(self,path=None):
        if not self.document:return
        try:backup=self.document.save(self.collected(),path)
        except (ValueError,OSError) as exc:
            messagebox.showerror('Settings were not saved',str(exc),parent=self);return
        self.variables={};self.dirty=False
        self.title('Wire Judge · Game Settings')
        self.filename.configure(text=str(self.document.path))
        self.render(self.selection)
        self.status.configure(text='Saved. Restart Wire Judge to apply changes.' + (' Backup created next to the JSON.' if backup else ''))

    def save_as(self):
        if not self.document:return
        path=filedialog.asksaveasfilename(parent=self,title='Save settings copy',initialdir=self.document.path.parent,initialfile='game_stats.json',defaultextension='.json',filetypes=[('JSON settings','*.json')])
        if path:self.save(path)

    def notes(self):
        path=Path(__file__).with_name('GAME_STATS_README.txt')
        window=tk.Toplevel(self);window.title('Game settings reference');window.geometry('850x650')
        body=ttk.Frame(window,padding=12);body.pack(fill='both',expand=True)
        text=tk.Text(body,wrap='word',bg='#17263a',fg='#e4ecf6',font=('Segoe UI',10),padx=14,pady=14)
        text.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(body,command=text.yview);scroll.pack(side='right',fill='y');text.configure(yscrollcommand=scroll.set)
        text.insert('1.0',path.read_text(encoding='utf-8') if path.exists() else 'Reference notes file not found.');text.configure(state='disabled')

    def close(self):
        if self.confirm_discard():self.destroy()


if __name__=='__main__':
    import sys
    ConfigEditor(Path(sys.argv[1]) if len(sys.argv)>1 else STATS_PATH).mainloop()
