"""Side-by-side campaign counts and derived totals, with editable count cells."""
from copy import deepcopy
from decimal import Decimal
import math
import tkinter as tk
from tkinter import ttk, messagebox


def rounded_growth(value,growth):
    return math.ceil(Decimal(str(value))*(1+Decimal(str(growth))))


def scaled_tier(tier,growth):
    if isinstance(tier,dict):return {k:scaled_tier(v,growth) for k,v in tier.items()}
    return [rounded_growth(v,growth) for v in tier]


def sum_pairs(pairs):
    return [sum(p[0] for p in pairs),sum(p[1] for p in pairs)]


def product(a,b):return [a[0]*b[0],a[1]*b[1]]


def display(value):
    if isinstance(value,(list,tuple)):
        return f'{value[0]:g}' if value[0]==value[1] else f'{value[0]:g} – {value[1]:g}'
    return f'{value:g}' if isinstance(value,(int,float)) else str(value)


def campaign_comparison(data):
    """Return columns, row metadata and raw values; no game imports or arbitrary score."""
    settings=data['campaign'];tiers=settings['tiers']
    columns=[f'Zone {i+1}' for i in range(len(tiers))]+[f'Continue · {len(tiers)+1}']
    expanded=[*tiers,scaled_tier(tiers[-1],settings['infinite_growth_fraction'])]
    rows=[]
    def section(title):rows.append({'label':title,'values':['']*len(expanded),'section':True,'path':None})
    def row(title,values,path=None):rows.append({'label':title,'values':values,'section':False,'path':path})
    section('ZONE OVERVIEW')
    row('Distance from player base', [f'{settings["safe_radius_nm"]+i*settings["band_width_nm"]:g}–{settings["safe_radius_nm"]+(i+1)*settings["band_width_nm"]:g} NM' for i in range(len(expanded))])
    health=[settings['runway_health']+i*settings['runway_health_per_band'] for i in range(len(tiers))]
    health.append(rounded_growth(health[-1],settings['infinite_growth_fraction']))
    row('HP per runway',health)
    row('Airfields',[t['airfields'] for t in expanded],('airfields',))
    row('Outposts',[t['outposts'] for t in expanded],('outposts',))
    factories=[];count=settings['random_factories_start_count']
    for _ in expanded:
        count=rounded_growth(count,settings['random_factories_growth_fraction']);factories.append(count)
    row('Extra standalone factories',factories)
    waves=[sum_pairs(t['wave_aircraft'].values()) for t in expanded]
    row('Aircraft / wave / airfield',waves)
    row('Aircraft / wave across all airfields',[product(t['airfields'],wave) for t,wave in zip(expanded,waves)])
    row('Combined runway HP',[product(t['airfields'],[hp,hp]) for t,hp in zip(expanded,health)])
    totals=[];ground_hp=[]
    for t,extra in zip(expanded,factories):
        total=sum_pairs([product(t['airfields'],sum_pairs(t['airfield_ground'].values())),product(t['outposts'],sum_pairs(t['outpost_ground'].values()))])
        totals.append([v+extra for v in total])
        hp=[extra*data['enemy_ground_units']['Factory']['health']]*2
        for group,base in (('airfield_ground','airfields'),('outpost_ground','outposts')):
            for kind,pair in t[group].items():
                amount=product(t[base],pair);unit_hp=data['enemy_ground_units'][kind]['health']
                hp=[h+n*unit_hp for h,n in zip(hp,amount)]
        ground_hp.append(hp)
    row('Ground units / zone (includes factories)',totals)
    row('Ground unit HP (excludes runways)',ground_hp)
    for group,title in (('airfield_ground','DEFENDERS PER AIRFIELD'),('outpost_ground','DEFENDERS PER OUTPOST'),('wave_aircraft','AIRCRAFT PER WAVE / AIRFIELD')):
        section(title)
        for kind in tiers[0][group]:row(kind,[t[group][kind] for t in expanded],(group,kind))
    section('TOTAL GROUND UNITS PER ZONE')
    for kind in tiers[0]['airfield_ground']:
        values=[]
        for t,extra in zip(expanded,factories):
            a=product(t['airfields'],t['airfield_ground'][kind]);b=product(t['outposts'],t['outpost_ground'][kind])
            values.append([x+y+(extra if kind=='Factory' else 0) for x,y in zip(a,b)])
        row(kind,values)
    return columns,rows


class CampaignComparison(tk.Toplevel):
    def __init__(self,parent,read_data,apply_edit):
        super().__init__(parent)
        self.read_data=read_data;self.apply_edit=apply_edit;self.rows=[];self.cell_editor=None;self.validating=False
        self.title('Campaign · Compare Zones')
        width=min(1160,max(850,self.winfo_screenwidth()-100));height=min(800,max(500,self.winfo_screenheight()-140))
        self.geometry(f'{width}x{height}');self.minsize(850,500)
        self.configure(bg='#101b2b')
        header=ttk.Frame(self,padding=14);header.pack(fill='x')
        ttk.Label(header,text='CAMPAIGN DIFFICULTY SCALE',font=('Segoe UI',16,'bold')).pack(side='left')
        ttk.Button(header,text='Refresh',command=self.refresh).pack(side='right')
        self.summary=ttk.Label(self,style='Muted.TLabel',padding=(14,0,14,10),wraplength=1100)
        self.summary.pack(fill='x')
        frame=ttk.Frame(self,padding=(14,0,14,0));frame.pack(fill='both',expand=True)
        ttk.Style(self).configure('CampaignCompare.Treeview',rowheight=28)
        self.table=ttk.Treeview(frame,show='tree headings',selectmode='browse',style='CampaignCompare.Treeview')
        self.table.grid(row=0,column=0,sticky='nsew')
        vertical=ttk.Scrollbar(frame,orient='vertical',command=lambda *args:self.scroll('y',*args));vertical.grid(row=0,column=1,sticky='ns')
        horizontal=ttk.Scrollbar(frame,orient='horizontal',command=lambda *args:self.scroll('x',*args));horizontal.grid(row=1,column=0,sticky='ew')
        self.table.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
        frame.rowconfigure(0,weight=1);frame.columnconfigure(0,weight=1)
        self.table.tag_configure('section',background='#294a6b',foreground='#ffffff',font=('Segoe UI',10,'bold'))
        self.table.tag_configure('overview',foreground='#86d7b0')
        self.footer=ttk.Label(self,text='Values are minimum–maximum for new spawns; prior survivors are excluded. Click a configured count to edit min / max. Enter applies; Tab moves across zones; Escape cancels. Totals and Continue preview are calculated. Save in the main editor to write changes.',style='Muted.TLabel',padding=14,wraplength=1100)
        self.footer.pack(fill='x')
        self.bind('<Configure>',self.resized)
        self.table.bind('<Button-1>',self.edit_cell)
        self.table.bind('<MouseWheel>',self.before_scroll)
        self.table.bind('<Button-4>',self.before_scroll)
        self.table.bind('<Button-5>',self.before_scroll)
        self.table.bind('<Configure>',lambda event:self.position_editor())
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.refresh()

    def resized(self,event):
        if event.widget is self:
            self.summary.configure(wraplength=max(600,event.width-28))
            self.footer.configure(wraplength=max(600,event.width-28))

    def refresh(self):
        if not self.commit_cell(recalculate=False):return
        try:
            data=self.read_data();columns,self.rows=campaign_comparison(data)
        except (ValueError,KeyError,TypeError) as exc:
            messagebox.showerror('Cannot compare campaign',str(exc),parent=self);return
        self.band_count=len(data['campaign']['tiers'])
        self.table.delete(*self.table.get_children())
        ids=[f'band{i}' for i in range(len(columns))];self.table.configure(columns=ids)
        self.table.heading('#0',text='Setting / unit');self.table.column('#0',width=330,minwidth=260,stretch=False)
        for col,title in zip(ids,columns):self.table.heading(col,text=title);self.table.column(col,width=135,minwidth=120,anchor='center',stretch=False)
        for i,row in enumerate(self.rows):
            self.table.insert('','end',iid=str(i),text=row['label'],values=[display(v) for v in row['values']],tags=('section',) if row['section'] else ('overview',) if i<12 else ())
        s=data['campaign']
        self.summary.configure(text=f'{self.band_count} zones · {s["safe_radius_nm"]:g} NM safe core · Core factories: {s["random_factories_start_count"]} · First wave: {s["first_wave_delay_seconds"]/60:g} min · Initial interval: {s["wave_interval_seconds"]/60:g} min (+{s["wave_interval_growth_fraction"]*100:g}% / wave) · Continue growth: {s["infinite_growth_fraction"]*100:g}%')

    def edit_cell(self,event):
        item=self.table.identify_row(event.y);column=self.table.identify_column(event.x)
        if self.cell_editor and (item,column)==self.cell_editor['cell']:return 'break'
        if not self.commit_cell():return 'break'
        if not item or not column or column=='#0':return
        band=int(column[1:])-1;row=self.rows[int(item)]
        if band>=self.band_count or row['path'] is None:return
        self.open_cell(item,band)
        return 'break'

    def open_cell(self,item,band,focus=0):
        row=self.rows[int(item)];path=('campaign','tiers',band,*row['path'])
        try:
            value=self.read_data()['campaign']['tiers'][band]
            for key in row['path']:value=value[key]
        except (ValueError,KeyError,TypeError) as exc:
            messagebox.showerror('Cannot edit count',str(exc),parent=self);return
        self.table.selection_set(item);self.table.see(item)
        column=f'#{band+1}'
        # Reveal horizontally hidden cells before placing the editor.
        left=sum(self.table.column(c,'width') for c in ['#0',*self.table['columns'][:band]])
        width=self.table.column(column,'width')
        total=sum(self.table.column(c,'width') for c in ['#0',*self.table['columns']])
        viewport=self.table.winfo_width();offset=self.table.xview()[0]*total
        if left<offset:self.table.xview_moveto(left/total)
        elif left+width>offset+viewport:self.table.xview_moveto(max(0,left+width-viewport)/total)
        box=ttk.Frame(self.table)
        variables=[tk.StringVar(master=self,value=str(v)) for v in value]
        entries=[]
        for i,var in enumerate(variables):
            entry=ttk.Entry(box,textvariable=var,width=4,justify='center')
            entry.grid(row=0,column=i*2,sticky='nsew');box.columnconfigure(i*2,weight=1)
            entry.bind('<Return>',lambda event:self.finish_enter())
            entry.bind('<Escape>',lambda event:self.cancel_cell())
            entry.bind('<FocusOut>',lambda event:self.after_idle(self.focus_left_cell))
            entries.append(entry)
        ttk.Label(box,text='–').grid(row=0,column=1)
        entries[1].bind('<Tab>',lambda event:self.next_cell(1))
        entries[0].bind('<Shift-Tab>',lambda event:self.next_cell(-1))
        entries[0].bind('<ISO_Left_Tab>',lambda event:self.next_cell(-1))
        self.cell_editor={'cell':(item,column),'path':path,'original':list(value),
                          'box':box,'variables':variables,'entries':entries}
        self.position_editor()
        entries[focus].focus_set();entries[focus].selection_range(0,'end')

    def position_editor(self):
        if self.cell_editor:
            bbox=self.table.bbox(*self.cell_editor['cell'])
            if bbox:
                x,y,width,height=bbox
                self.cell_editor['box'].place(x=x,y=y,width=width,height=height)
            else:self.cell_editor['box'].place_forget()

    def commit_cell(self,recalculate=True):
        editor=self.cell_editor
        if editor is None:return True
        try:
            values=[int(var.get()) for var in editor['variables']]
            if min(values)<0 or values[0]>values[1]:
                raise ValueError('Use nonnegative whole numbers with minimum no greater than maximum.')
            changed=values!=editor['original']
            if changed:self.apply_edit(editor['path'],values)
        except (ValueError,OSError) as exc:
            self.validating=True
            messagebox.showerror('Invalid counts',str(exc),parent=self)
            editor['entries'][0].focus_set()
            self.after_idle(lambda:setattr(self,'validating',False))
            return False
        item=editor['cell'][0]
        self.cancel_cell()
        if changed and recalculate:self.refresh()
        self.table.selection_set(item)
        return True

    def cancel_cell(self):
        if self.cell_editor:
            box=self.cell_editor['box'];self.cell_editor=None;box.destroy()
        self.table.focus_set()
        return 'break'

    def finish_enter(self):
        self.commit_cell()
        return 'break'

    def focus_left_cell(self):
        if not self.cell_editor or self.validating:return
        focus=self.focus_get()
        if focus not in self.cell_editor['entries']:self.commit_cell()

    def next_cell(self,direction):
        editor=self.cell_editor
        if editor is None:return 'break'
        item,column=editor['cell'];band=int(column[1:])-1
        cells=[(str(i),b) for i,row in enumerate(self.rows) if row['path'] is not None
               for b in range(self.band_count)]
        index=cells.index((item,band))+direction
        if self.commit_cell() and 0<=index<len(cells):
            item,band=cells[index];self.open_cell(item,band,focus=0 if direction>0 else 1)
        return 'break'

    def scroll(self,axis,*args):
        if self.commit_cell():getattr(self.table,axis+'view')(*args)

    def before_scroll(self,event):
        if not self.commit_cell():return 'break'

    def close(self):
        if self.commit_cell():self.destroy()
