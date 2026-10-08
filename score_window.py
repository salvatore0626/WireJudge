"""Sortable, player-grouped score sheet with per-cell winners."""
import tkinter as tk
import math
from tkinter import ttk,messagebox
from tkinter.font import Font
from scoring import maximum,is_best
from engine import clock,last_attempts
from plots import BG,TEXT,MUTED
from score_export import export_scores

COLUMNS=(('name','Name'),('loc','Localizer'),('glide','Glide'),('aoa','AoA'),('wire','Wire'),('total','Total'))
CASE3_COLUMNS=(COLUMNS[0],('position','Platform\nPosition'),('speed','Platform\nSpeed'))+COLUMNS[1:]

def score_sheet(attempts,scores,bests,column='total',descending=True,best_only=False,columns=COLUMNS,last_only=False):
    """Ranks always use total; sorting and visible column winners are independent."""
    standings=sorted(bests.items(),key=lambda pair:(-pair[1],pair[0]))
    ranks={};previous=None;rank=0
    for index,(player,value) in enumerate(standings,1):
        if value!=previous:rank=index
        ranks[player]=rank;previous=value
    groups={}
    for a in attempts:groups.setdefault(a.player,[]).append(a)
    def value(a):
        score=scores.get(a.edit_id)
        return round(getattr(score,column),1) if score else None
    def ordered(items,key):
        available=[item for item in items if key(item) is not None]
        unavailable=[item for item in items if key(item) is None]
        return sorted(available,key=key,reverse=descending)+unavailable
    if column=='name':players=sorted(groups,key=str.casefold,reverse=descending)
    else:
        def group_value(player):
            values=[value(a) for a in groups[player] if scores.get(a.edit_id) and scores[a.edit_id].complete]
            return max(values) if values else None
        players=ordered(sorted(groups,key=str.casefold),group_value)
    rows=[]
    last_ids={a.edit_id for a in last_attempts(attempts)} if last_only else set()
    for player in players:
        chronological=sorted(groups[player],key=lambda a:a.start)
        numbers={a.edit_id:n for n,a in enumerate(chronological,1)}
        visible=[a for a in chronological if (not best_only or is_best(a,scores.get(a.edit_id),bests)) and (not last_only or a.edit_id in last_ids)]
        rows.append({'player':player,'rank':ranks.get(player.casefold()),'attempt':None})
        if column!='name':visible=ordered(visible,value)
        for a in visible:rows.append({'player':player,'attempt':a,'number':numbers[a.edit_id]})
    winners={}
    for key,_ in columns[1:]:
        values=[round(getattr(scores[row['attempt'].edit_id],key),1) for row in rows if row['attempt'] is not None and scores.get(row['attempt'].edit_id) is not None and scores[row['attempt'].edit_id].complete]
        winners[key]=max(values) if values else None
    return rows,winners

class ScoreWindow(ttk.Frame):
    def __init__(self,app,parent=None):
        super().__init__(parent if parent is not None else app);self.app=app
        self.sort_column='total';self.descending=True;self.rows=[];self.winners={};self.cell_items={};self._drawing=False;self._draw_job=None
        ttk.Label(self,text='PLAYER SCORES',font=('Helvetica',16,'bold'),padding=16).pack(anchor='w')
        self.summary=tk.StringVar()
        controls=ttk.Frame(self,padding=(16,0,16,12));controls.pack(fill='x')
        self.best_only=tk.BooleanVar(value=False)
        self.last_only=False
        self.show_all_btn=ttk.Button(controls,text='Show All',command=lambda:self.set_best_only(False));self.show_all_btn.pack(side='left')
        self.best_only_btn=ttk.Button(controls,text='Best Only',command=lambda:self.set_best_only(True));self.best_only_btn.pack(side='left',padx=8)
        self.show_last_btn=ttk.Button(controls,text='Last Only',command=self.set_last_only);self.show_last_btn.pack(side='left')
        self.export_btn=ttk.Button(controls,text='Export',command=self.choose_export);self.export_btn.pack(side='right')
        body=ttk.Frame(self);body.pack(fill='both',expand=True,padx=16,pady=(0,16))
        body.rowconfigure(1,weight=1);body.columnconfigure(0,weight=1)
        self.header=ttk.Frame(body);self.header.grid(row=0,column=0,sticky='ew')
        self.buttons={};self.columns=()
        self.canvas=tk.Canvas(body,bg='#182436',highlightthickness=0)
        self.canvas.grid(row=1,column=0,sticky='nsew')
        scrollbar=ttk.Scrollbar(body,command=self.canvas.yview);scrollbar.grid(row=1,column=1,sticky='ns');self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.bind('<Configure>',lambda _:self.schedule_draw(120))
        self.bind('<Destroy>',self.cancel_draw,add='+')
        self.canvas.bind('<MouseWheel>',self.wheel)
        self.canvas.bind('<Button-4>',lambda _:self.canvas.yview_scroll(-3,'units'))
        self.canvas.bind('<Button-5>',lambda _:self.canvas.yview_scroll(3,'units'))
        self.refresh()

    def set_best_only(self,value):
        self.last_only=False
        self.best_only.set(value)
        self.refresh()

    def set_last_only(self):
        self.best_only.set(False);self.last_only=True;self.refresh()

    def wheel(self,event):
        delta=event.delta
        if delta:self.canvas.yview_scroll(-int(delta/120) if abs(delta)>=120 else (-1 if delta>0 else 1),'units')
        return 'break'

    def choose_export(self):
        if self.app.busy:return
        if getattr(self,'export_page',None) is not None:return
        self.app.refresh_scores()
        attempts=sorted(self.app.attempts,key=lambda a:(a.player.casefold(),a.start))
        scores=dict(self.app.scores);settings=self.app.settings;filename=self.app.filename
        bests=dict(self.app.best_scores)
        wires={a.edit_id:self.app.get_wire(a) for a in attempts}
        packed=[(widget,widget.pack_info()) for widget in self.pack_slaves()]
        for widget,_ in packed:widget.pack_forget()
        dialog=ttk.Frame(self);self.export_page=dialog;dialog.pack(fill='both',expand=True)
        def back():
            dialog.destroy();self.export_page=None
            for widget,options in packed:widget.pack(**options)
            self.refresh()
        ttk.Label(dialog,text='Select Players & Attempts',font=('Helvetica',16,'bold'),padding=16).pack(anchor='w')
        selection_controls=ttk.Frame(dialog,padding=(16,0,16,12));selection_controls.pack(fill='x')
        footer=ttk.Frame(dialog,padding=16);footer.pack(side='bottom',fill='x')
        body=ttk.Frame(dialog,padding=(16,0,16,0));body.pack(fill='both',expand=True)
        tree=ttk.Treeview(body,show='tree',selectmode='none');tree.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(body,command=tree.yview);scroll.pack(side='right',fill='y');tree.configure(yscrollcommand=scroll.set)
        tree.tag_configure('provisional',foreground='#ffce76')
        tree.tag_configure('missing_wire',foreground='#ff727c')
        selected=set();groups={};rows={};labels={};numbers={}
        for a in attempts:groups.setdefault(a.player,[]).append(a)
        for index,(player,items) in enumerate(groups.items()):
            parent=f'player:{index}';rows[parent]=items;labels[parent]=player
            tree.insert('', 'end',iid=parent,text='[ ] '+player,open=True)
            for number,a in enumerate(items,1):
                row=f'attempt:{index}:{number}';rows[row]=[a];numbers[a.edit_id]=number
                wire=wires[a.edit_id];score=scores.get(a.edit_id)
                labels[row]=f'Attempt {number} · {clock(a.start)} · '+('Bolter' if wire=='Bolter' else 'Wire '+wire if wire else 'Wire Not Set')
                tree.insert(parent,'end',iid=row,text='[ ] '+labels[row],tags=('missing_wire',) if not wire else ('provisional',) if score and not score.complete else ())
        def update_selection():
            for iid,items in rows.items():
                count=sum(a.edit_id in selected for a in items)
                mark='[x]' if count==len(items) else '[-]' if count else '[ ]'
                tree.item(iid,text=mark+' '+labels[iid])
            next_btn.configure(state='normal' if selected else 'disabled')
        def toggle(row):
            items=rows.get(row,[])
            if not items:return
            ids={a.edit_id for a in items}
            if ids<=selected:selected.difference_update(ids)
            else:selected.update(ids)
            update_selection()
        def select_all():
            selected.clear();selected.update(a.edit_id for a in attempts);update_selection()
        def select_best():
            selected.clear();selected.update(a.edit_id for a in attempts if is_best(a,scores.get(a.edit_id),bests));update_selection()
        def select_last():
            selected.clear();selected.update(a.edit_id for a in last_attempts(attempts));update_selection()
        def select_none():
            selected.clear();update_selection()
        ttk.Button(selection_controls,text='Select All',command=select_all).pack(side='left')
        ttk.Button(selection_controls,text='Select Best',command=select_best).pack(side='left',padx=8)
        ttk.Button(selection_controls,text='Select Last',command=select_last).pack(side='left')
        ttk.Button(selection_controls,text='Select None',command=select_none).pack(side='left',padx=8)
        def click(event):
            if tree.identify_element(event.x,event.y).endswith('indicator'):return
            row=tree.identify_row(event.y)
            if row:tree.focus(row);toggle(row);return 'break'
        tree.bind('<Button-1>',click)
        tree.bind('<space>',lambda event:(toggle(tree.focus()),'break')[-1])
        def finish():
            chosen=[a for a in attempts if a.edit_id in selected]
            if not chosen:return
            try:path=export_scores(chosen,scores,wires,numbers,settings,filename)
            except (OSError,ValueError) as error:
                messagebox.showerror('Could not export scores',str(error),parent=dialog);return
            back();self.app.status.set(f'Scores exported to {path}')
            messagebox.showinfo('Scores Exported',f'Saved {len(chosen)} attempts to:\n{path}',parent=self.app)
        ttk.Button(footer,text='Back',command=back).pack(side='left')
        next_btn=ttk.Button(footer,text='Next',command=finish,state='disabled');next_btn.pack(side='right')
        if not attempts:ttk.Label(dialog,text='No attempts available.',padding=16).pack()
        tree.focus_set()

    def sort_by(self,key):
        self.descending=not self.descending if key==self.sort_column else key!='name'
        self.sort_column=key;self.refresh()

    def refresh(self):
        self.app.refresh_scores()
        self.show_all_btn.configure(style='Selected.TButton' if not self.best_only.get() and not self.last_only else 'TButton')
        self.best_only_btn.configure(style='Selected.TButton' if self.best_only.get() else 'TButton')
        self.show_last_btn.configure(style='Selected.TButton' if self.last_only else 'TButton')
        columns=CASE3_COLUMNS if self.app.settings.recovery_case==3 else COLUMNS
        if columns!=self.columns:
            for button in self.buttons.values():button.destroy()
            for index in range(len(self.columns)):self.header.columnconfigure(index,weight=0,minsize=0)
            self.columns=columns;self.buttons={}
            if self.sort_column not in dict(columns):self.sort_column='total';self.descending=True
            for index,(key,label) in enumerate(columns):
                self.header.columnconfigure(index,weight=3 if index==0 else 1,minsize=220 if index==0 else 94)
                button=ttk.Button(self.header,text=label,command=lambda key=key:self.sort_by(key));button.grid(row=0,column=index,sticky='ew',padx=(0,1));self.buttons[key]=button
        self.rows,self.winners=score_sheet(self.app.attempts,self.app.scores,self.app.best_scores,self.sort_column,self.descending,self.best_only.get(),self.columns,last_only=self.last_only)
        for key,label in self.columns:self.buttons[key].configure(text=label+(' ▼' if self.descending else ' ▲') if key==self.sort_column else label)
        self.summary.set(f'Case {self.app.settings.recovery_case} · Maximum {maximum(self.app.settings):,.0f} points · place = best complete total · green ★ = best visible complete score in each column (ties included)\nProvisional scores are marked * and excluded from ranks/highlights. Best filters include tied best totals.')
        self.schedule_draw()

    def cancel_draw(self,event=None):
        if event is not None and event.widget is not self:return
        if self._draw_job is not None:self.after_cancel(self._draw_job);self._draw_job=None

    def schedule_draw(self,delay=0):
        self.cancel_draw();self._draw_job=self.after(delay,self.draw)

    def draw(self):
        self._draw_job=None
        if self._drawing or not self.winfo_viewable():return
        self._drawing=True
        try:
            self.header.update_idletasks()
            self._draw()
        finally:self._drawing=False

    def _draw(self):
        if not self.winfo_exists():return
        self.canvas.delete('all');self.cell_items={}
        edges=[button.winfo_x() for button in self.buttons.values()]+[self.canvas.winfo_width()]
        if edges[-1]<=1:return
        rowheight=38
        for index,row in enumerate(self.rows):
            y=index*rowheight;attempt=row['attempt'];group=attempt is None
            background='#24374d' if group else ('#182436' if index%2 else '#1b2b3f')
            self.canvas.create_rectangle(0,y,edges[-1],y+rowheight,fill=background,outline='#304156')
            if group:
                rank=row['rank'];name=(f'{rank}. ' if rank is not None else '')+row['player']+(' · Unranked' if rank is None else '')
            else:
                score=self.app.scores.get(attempt.edit_id);wire=self.app.get_wire(attempt)
                name=f'Attempt {row["number"]} · {clock(attempt.start)}'
                if score and not score.complete:name+=' *'
            name_color='#ffce76' if not group and score and not score.complete else TEXT
            if group:
                self.canvas.create_text(12,y+rowheight/2,text=name,fill=name_color,font=('Helvetica',11,'bold'),anchor='w',width=max(1,edges[1]-34))
            else:
                wire_text='Bolter' if wire=='Bolter' else f'Wire {wire}' if wire else 'Wire Not Set'
                prefix=name+' · ';size=11;label_font=Font(self,font=('Helvetica',size))
                while size>8 and label_font.measure(prefix+wire_text)>edges[1]-34:
                    size-=1;label_font.configure(size=size)
                self.canvas.create_text(26,y+rowheight/2,text=prefix,fill=name_color,font=('Helvetica',size),anchor='w')
                self.canvas.create_text(26+label_font.measure(prefix),y+rowheight/2,text=wire_text,fill=name_color if wire else '#ff727c',font=('Helvetica',size),anchor='w')
            for col,(key,_) in enumerate(self.columns[1:],1):
                if group:continue
                score=self.app.scores.get(attempt.edit_id)
                winning=bool(score and score.complete and round(getattr(score,key),1)==self.winners[key])
                if winning:self.canvas.create_rectangle(edges[col]+1,y+1,edges[col+1]-1,y+rowheight-1,fill='#214837',outline='')
                value=('★ ' if winning else '')+f'{getattr(score,key):,.1f}' if score else '—'
                item=self.canvas.create_text(edges[col+1]-12,y+rowheight/2,text=value.removeprefix('★ '),fill='#83edb8' if winning else '#ffce76' if score and not score.complete else TEXT,font=('Helvetica',11,'bold' if winning else 'normal'),anchor='e')
                if winning:
                    # Draw the star so it remains visible even with limited Tk fonts.
                    x=self.canvas.bbox(item)[0]-10;cy=y+rowheight/2;points=[]
                    for tip in range(10):
                        angle=math.pi*tip/5-math.pi/2;radius=6 if tip%2==0 else 2.6
                        points.extend((x+radius*math.cos(angle),cy+radius*math.sin(angle)))
                    self.canvas.create_polygon(points,fill='#83edb8',outline='')
                self.cell_items[(attempt.edit_id,key)]={'item':item,'winner':winning,'text':value}
        self.canvas.configure(scrollregion=(0,0,edges[-1],max(len(self.rows)*rowheight,1)),yscrollincrement=rowheight)
