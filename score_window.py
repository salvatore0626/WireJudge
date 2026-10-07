"""Sortable, player-grouped score sheet with per-cell winners."""
import tkinter as tk
import math
from tkinter import ttk
from scoring import maximum,is_best
from engine import clock
from plots import BG,TEXT,MUTED

COLUMNS=(('name','Name'),('loc','Localizer'),('glide','Glide'),('aoa','AoA'),('wire','Wire'),('total','Total'))
CASE3_COLUMNS=(COLUMNS[0],('position','Platform\nPosition'),('speed','Platform\nSpeed'))+COLUMNS[1:]

def score_sheet(attempts,scores,bests,column='total',descending=True,best_only=False,columns=COLUMNS):
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
    for player in players:
        chronological=sorted(groups[player],key=lambda a:a.start)
        numbers={a.edit_id:n for n,a in enumerate(chronological,1)}
        visible=[a for a in chronological if not best_only or is_best(a,scores.get(a.edit_id),bests)]
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
        self.sort_column='total';self.descending=True;self.rows=[];self.winners={};self.cell_items={};self._drawing=False
        ttk.Label(self,text='PLAYER SCORES',font=('Helvetica',16,'bold'),padding=16).pack(anchor='w')
        self.summary=tk.StringVar()
        controls=ttk.Frame(self,padding=(16,0,16,12));controls.pack(fill='x')
        self.best_only=tk.BooleanVar(value=False)
        ttk.Checkbutton(controls,text='Show only best attempt',variable=self.best_only,command=self.refresh).pack(side='left')
        ttk.Button(controls,text='Refresh',command=self.refresh).pack(side='right')
        body=ttk.Frame(self);body.pack(fill='both',expand=True,padx=16,pady=(0,16))
        body.rowconfigure(1,weight=1);body.columnconfigure(0,weight=1)
        self.header=ttk.Frame(body);self.header.grid(row=0,column=0,sticky='ew')
        self.buttons={};self.columns=()
        self.canvas=tk.Canvas(body,bg='#182436',highlightthickness=0)
        self.canvas.grid(row=1,column=0,sticky='nsew')
        scrollbar=ttk.Scrollbar(body,command=self.canvas.yview);scrollbar.grid(row=1,column=1,sticky='ns');self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.bind('<Configure>',lambda _:self.after_idle(self.draw))
        self.canvas.bind('<MouseWheel>',self.wheel)
        self.canvas.bind('<Button-4>',lambda _:self.canvas.yview_scroll(-3,'units'))
        self.canvas.bind('<Button-5>',lambda _:self.canvas.yview_scroll(3,'units'))
        self.refresh()

    def wheel(self,event):
        delta=event.delta
        if delta:self.canvas.yview_scroll(-int(delta/120) if abs(delta)>=120 else (-1 if delta>0 else 1),'units')
        return 'break'

    def sort_by(self,key):
        self.descending=not self.descending if key==self.sort_column else key!='name'
        self.sort_column=key;self.refresh()

    def refresh(self):
        self.app.refresh_scores()
        columns=CASE3_COLUMNS if self.app.settings.recovery_case==3 else COLUMNS
        if columns!=self.columns:
            for button in self.buttons.values():button.destroy()
            for index in range(len(self.columns)):self.header.columnconfigure(index,weight=0,minsize=0)
            self.columns=columns;self.buttons={}
            if self.sort_column not in dict(columns):self.sort_column='total';self.descending=True
            for index,(key,label) in enumerate(columns):
                self.header.columnconfigure(index,weight=3 if index==0 else 1,minsize=220 if index==0 else 94)
                button=ttk.Button(self.header,text=label,command=lambda key=key:self.sort_by(key));button.grid(row=0,column=index,sticky='ew',padx=(0,1));self.buttons[key]=button
        self.rows,self.winners=score_sheet(self.app.attempts,self.app.scores,self.app.best_scores,self.sort_column,self.descending,self.best_only.get(),self.columns)
        for key,label in self.columns:self.buttons[key].configure(text=label+(' ▼' if self.descending else ' ▲') if key==self.sort_column else label)
        self.summary.set(f'Case {self.app.settings.recovery_case} · Maximum {maximum(self.app.settings):,.0f} points · place = best complete total · green ★ = best visible complete score in each column (ties included)\nProvisional scores are marked * and excluded from ranks/highlights. Best filters include tied best totals.')
        self.after_idle(self.draw)

    def draw(self):
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
                name=f'Attempt {row["number"]} · {clock(attempt.start)}'+(' · Bolter' if wire=='Bolter' else f' · Wire {wire}' if wire else ' · Wire not set')
                if score and not score.complete:name+=' *'
            self.canvas.create_text(12 if group else 26,y+rowheight/2,text=name,fill=TEXT,font=('Helvetica',11,'bold' if group else 'normal'),anchor='w',width=max(1,edges[1]-34))
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
