"""Wire Judge v0.12.27 — local native-VTR approach viewer."""
from pathlib import Path
from collections import defaultdict
from dataclasses import asdict
import os, queue, threading, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from toolbar import GraphToolbar
from reader import read_motion
from engine import Settings,analyze,last_attempts,player_label,clock,glide_origin_msl_ft,glide_start_nm,target_intercept_nm
from plots import make_figure,draw,BG,TEXT,MUTED
from annotations import Annotations,WIRE_OPTIONS,replay_digest
from attempt_edits import AttemptEdits
from editor import AttemptEditorPage
from scoring import score_attempt,best_by_player,is_best,maximum,approach_maximum
from score_window import ScoreWindow

SETTINGS_PATH=Path.home()/'.wire_judge'/'settings.json'
ANNOTATIONS_DIR=Path.home()/'.wire_judge'/'annotations'
ASSETS_DIR=Path(__file__).resolve().parent/'assets'

class WireJudge(tk.Tk):
    def __init__(self):
        super().__init__();self.title('Wire Judge · Native VTR Viewer');self.geometry('1380x900');self.minsize(1050,760);self.configure(bg=BG)
        self.app_icon=tk.PhotoImage(file=str(ASSETS_DIR/'app_icon.png'))
        self.header_logo=tk.PhotoImage(file=str(ASSETS_DIR/'header_logo.png'))
        self.iconphoto(True,self.app_icon)
        self.settings=Settings.load(SETTINGS_PATH);self.tracks=[];self.attempts=[];self.selected=None;self.carrier=None;self.filename=None;self.busy=False;self.messages=queue.Queue()
        self.annotations=None
        self.edits=None;self.auto_attempts=[];self.settings_path=SETTINGS_PATH;self.row_players={}
        self.scores={};self.best_scores={};self.score_window=None
        style=ttk.Style(self);style.theme_use('clam')
        style.configure('.',background=BG,foreground=TEXT,font=('Helvetica',11))
        style.configure('TFrame',background=BG);style.configure('TLabel',background=BG,foreground=TEXT)
        style.configure('TNotebook',background=BG,borderwidth=0)
        style.configure('TNotebook.Tab',background='#24374d',foreground=TEXT,padding=(10,4),font=('Helvetica',10))
        style.map('TNotebook.Tab',background=[('selected','#355372'),('active','#355372')],foreground=[('selected',TEXT)],padding=[('selected',(18,10)),('!selected',(10,4))],font=[('selected',('Helvetica',12,'bold')),('!selected',('Helvetica',10))],expand=[('selected',(2,2,2,0)),('!selected',(0,0,0,0))])
        style.configure('TButton',background='#24374d',foreground=TEXT,padding=(12,8),borderwidth=0)
        style.map('TButton',background=[('active','#355372')])
        for name,base,active in (('NeedsInput','#963f48','#b44b56'),('Selected','#27694e','#328563')):
            style.configure(name+'.TButton',background=base,foreground='#ffffff')
            style.map(name+'.TButton',background=[('active',active),('disabled',base)],foreground=[('disabled','#c9c9c9')])
        style.configure('TCheckbutton',background=BG,foreground=TEXT)
        style.configure('Treeview',background='#182436',fieldbackground='#182436',foreground=TEXT,rowheight=30,borderwidth=0)
        style.map('Treeview',background=[('selected','#294b70')],foreground=[('selected','#ffffff')])
        style.configure('TEntry',fieldbackground='#24374d',foreground=TEXT,insertcolor=TEXT)
        style.configure('TCombobox',fieldbackground='#24374d',foreground=TEXT,arrowcolor=TEXT)
        style.map('TCombobox',fieldbackground=[('readonly','#24374d'),('disabled','#182436')],foreground=[('readonly',TEXT),('disabled',MUTED)])
        top=ttk.Frame(self,padding=(16,12));top.pack(fill='x')
        self.open_btn=ttk.Button(top,text='Select Replay',command=self.open_file);self.open_btn.pack(side='left',padx=10)
        self.carrier_btn=ttk.Button(top,text='Select Carrier',command=self.choose_carrier,state='disabled');self.carrier_btn.pack(side='left')
        ttk.Label(top,text='Recovery:').pack(side='left',padx=(20,8))
        self.case_value=tk.StringVar(value=f'Case {self.settings.recovery_case}')
        self.case_select=ttk.Combobox(top,textvariable=self.case_value,values=('Case 1','Case 3'),state='readonly',width=9)
        self.case_select.pack(side='left');self.case_select.bind('<<ComboboxSelected>>',self.change_case)
        self.points_value=tk.BooleanVar(value=self.settings.show_data_points)
        
        self.update_input_buttons()
        brand=ttk.Frame(top);brand.pack(side='right')
        ttk.Label(brand,image=self.header_logo).pack(side='left',padx=(0,8))
        ttk.Label(brand,text='WIRE JUDGE',font=('Helvetica',16,'bold')).pack(side='left')
        self.file_text=tk.StringVar(value='Open a native VTOL VR replay to begin');ttk.Label(self,textvariable=self.file_text,foreground=MUTED,padding=(18,0,18,8)).pack(fill='x')
        carrierbar=ttk.Frame(self,padding=(18,6,18,12));carrierbar.pack(fill='x')
        self.carrier_text=tk.StringVar(value='Select the carrier unit after loading');ttk.Label(carrierbar,textvariable=self.carrier_text).pack(side='left')
        self.content=ttk.Frame(self);self.content.pack(fill='both',expand=True,padx=16,pady=(0,8))
        self.carrier_selection=None
        self.pages=ttk.Notebook(self.content);self.pages.pack(fill='both',expand=True)
        self.approach_page=ttk.Frame(self.pages);self.settings_page=ttk.Frame(self.pages)
        self.pages.add(self.approach_page,text='Approach Viewer')
        self.score_window=ScoreWindow(self,self.pages);self.pages.add(self.score_window,text='Scores')
        self.editor_page=AttemptEditorPage(self,self.pages);self.pages.add(self.editor_page,text='Attempt Editor')
        self.pages.add(self.settings_page,text='Settings')
        view_controls=ttk.Frame(self.approach_page,padding=(0,4,0,8));view_controls.pack(fill='x')
        ttk.Checkbutton(view_controls,text='Data points',variable=self.points_value,command=self.toggle_points).pack(side='left')
        body=ttk.Panedwindow(self.approach_page,orient='horizontal');body.pack(fill='both',expand=True)
        left=ttk.Frame(body,padding=(0,4,12,4));right=ttk.Frame(body);body.add(left,weight=1);body.add(right,weight=4)
        ttk.Label(left,text='PLAYERS & APPROACHES',font=('Helvetica',11,'bold')).pack(anchor='w',pady=(0,8))
        self.attempt_filter=tk.StringVar(value='All')
        filterbar=ttk.Frame(left);filterbar.pack(fill='x',pady=(0,10))
        ttk.Label(filterbar,text='Show:').pack(side='left',padx=(0,8))
        self.attempt_filter_select=ttk.Combobox(filterbar,textvariable=self.attempt_filter,values=('All','Last attempt','Best attempt'),state='readonly',width=16)
        self.attempt_filter_select.pack(side='left');self.attempt_filter_select.bind('<<ComboboxSelected>>',lambda *_:self.populate())
        self.player_search=tk.StringVar();search=ttk.Entry(left,textvariable=self.player_search);search.pack(fill='x');self.player_search.trace_add('write',lambda *_:self.populate())
        ttk.Label(left,text='Search player or aircraft',foreground=MUTED,font=('Helvetica',9)).pack(anchor='w',pady=(3,10))
        treeframe=ttk.Frame(left);treeframe.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(treeframe,show='tree',selectmode='browse');self.tree.column('#0',width=350,minwidth=250);self.tree.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(treeframe,orient='vertical',command=self.tree.yview);scroll.pack(side='right',fill='y');self.tree.configure(yscrollcommand=scroll.set);self.tree.bind('<<TreeviewSelect>>',self.select_attempt)
        self.tree.bind('<Double-1>',self.open_player_editor)
        self.count_text=tk.StringVar(value='No replay loaded')
        wirebar=ttk.Frame(left,padding=(0,8,0,4));wirebar.pack(side='bottom',fill='x',before=treeframe)
        ttk.Label(wirebar,text='Wire caught:').pack(side='left')
        self.wire_value=tk.StringVar();self.wire_select=ttk.Combobox(wirebar,textvariable=self.wire_value,values=WIRE_OPTIONS,width=9,state='disabled');self.wire_select.pack(side='left',padx=8);self.wire_select.bind('<<ComboboxSelected>>',self.set_wire)
        self.total_text=tk.StringVar();ttk.Label(wirebar,textvariable=self.total_text,foreground='#6cd9af',font=('Helvetica',10)).pack(side='left')
        self.fig=make_figure();self.canvas=FigureCanvasTkAgg(self.fig,master=right);self.canvas.get_tk_widget().pack(fill='both',expand=True);self.canvas.get_tk_widget().bind('<Configure>',lambda _:self.after_idle(self.sync_figure_size),add='+')
        self.toolbar=GraphToolbar(self.canvas,right);self.toolbar.pack(side='bottom',fill='x',before=self.canvas.get_tk_widget())
        self.status=tk.StringVar(value='Geometry and AoA are provisional. Wire choices are manual and saved automatically.')
        self.footer=ttk.Label(self,textvariable=self.status,foreground=MUTED,padding=(18,8),wraplength=1300);self.footer.pack(side='bottom',fill='x',before=self.content)
        self.build_settings();self.pages.bind('<<NotebookTabChanged>>',self.page_changed)
        self.protocol('WM_DELETE_WINDOW',self.close_app)
        self.row_attempts={};draw(self.fig,None,self.settings);self.canvas.draw();self.after(100,self.poll)

    def close_app(self):
        if self.editor_page.confirm_context_change():self.destroy()

    def sync_figure_size(self):
        widget=self.canvas.get_tk_widget();w=widget.winfo_width();h=widget.winfo_height()
        if w>1 and h>1:
            self.fig.set_size_inches(w/self.fig.dpi,h/self.fig.dpi,forward=False);self.canvas.draw_idle()

    def set_busy(self,value,status):
        self.busy=value;self.status.set(status)
        self.open_btn.configure(state='disabled' if value else 'normal')
        self.pages.tab(self.settings_page,state='disabled' if value else 'normal')
        self.save_settings_btn.configure(state='disabled' if value else 'normal')
        self.carrier_btn.configure(state='disabled' if value or not self.tracks else 'normal')
        self.wire_select.configure(state='disabled' if value or self.selected is None else 'readonly')
        self.case_select.configure(state='disabled' if value else 'readonly')
        self.pages.tab(self.editor_page,state='disabled' if value else 'normal')
        self.editor_page.refresh()
        self.update_input_buttons()

    def update_input_buttons(self):
        self.open_btn.configure(style='Selected.TButton' if self.filename is not None else 'NeedsInput.TButton')
        self.carrier_btn.configure(style='Selected.TButton' if self.carrier is not None else 'NeedsInput.TButton')

    def work(self,kind,fn):
        def run():
            try:self.messages.put((kind,fn(),None))
            except Exception as e:self.messages.put((kind,None,str(e)))
        threading.Thread(target=run,daemon=True).start()

    def poll(self):
        try:
            kind,value,error=self.messages.get_nowait()
            if error:
                self.set_busy(False,'Could not complete '+kind+'.');messagebox.showerror('Wire Judge',error,parent=self)
            elif kind=='load':
                self.filename,(self.tracks,info),digest=value;self.annotations=Annotations(ANNOTATIONS_DIR/(digest+'.json'));self.edits=AttemptEdits(ANNOTATIONS_DIR/(digest+'_attempts.json'));self.auto_attempts=[];self.attempts=[];self.selected=None;self.carrier=None;self.editor_page.reset();self.populate();self.redraw()
                self.file_text.set(self.filename.name+f'  ·  {len(self.tracks):,} motion tracks  ·  native format v{info["version"]}')
                self.show_tabs();self.carrier_text.set('Select the carrier unit');self.set_busy(False,'Replay loaded. Select the correct carrier unit.')
                if not self.tracks:messagebox.showinfo('No motion tracks','This VTR contains no motion tracks. Aircraft approaches cannot be reconstructed from this file.',parent=self)
                else:self.choose_carrier()
            elif kind=='analyze':
                self.auto_attempts=value;self.selected=None;self.apply_edits();self.editor_page.reset();self.set_busy(False,f'{len(self.attempts)} attempts available. Double-click a player to edit their flight log. Glide End marks where approach judging ends.')
                children=self.tree.get_children()
                for parent in children:
                    child=self.tree.get_children(parent)
                    if child:self.tree.selection_set(child[-1]);self.tree.see(child[-1]);break
        except queue.Empty:pass
        self.after(100,self.poll)

    def open_file(self):
        appdata=os.environ.get('APPDATA') if os.name=='nt' else None
        initialdir=Path(appdata) if appdata else Path.home()
        if appdata:
            replays=initialdir/'Boundless Dynamics, LLC'/'VTOLVR'/'SaveData'/'Replays'
            if replays.is_dir():initialdir=replays
        if not initialdir.is_dir():initialdir=Path.home()
        path=filedialog.askopenfilename(parent=self,title='Open native VTOL VR replay',initialdir=str(initialdir),filetypes=[('VTOL VR Replay','*.vtr'),('All files','*')])
        if not path:return
        if not self.editor_page.confirm_context_change():return
        self.set_busy(True,'Decompressing and reading replay motion tracks…');self.work('load',lambda:(Path(path),read_motion(path),replay_digest(path)))

    def choose_carrier(self):
        if not self.tracks or self.busy:return
        if not self.editor_page.confirm_context_change():return
        if self.carrier_selection is not None:self.carrier_selection.destroy()
        self.pages.pack_forget()
        dialog=ttk.Frame(self.content);dialog.pack(fill='both',expand=True);self.carrier_selection=dialog
        ttk.Label(dialog,text='Search and select the actual carrier unit',font=('Helvetica',14,'bold'),padding=16).pack(anchor='w')
        searchrow=ttk.Frame(dialog,padding=(16,0));searchrow.pack(fill='x')
        ttk.Label(searchrow,text='Search:').pack(side='left',padx=(0,8))
        query=tk.StringVar();entry=ttk.Entry(searchrow,textvariable=query);entry.pack(side='left',fill='x',expand=True);entry.focus_set()
        all_units=tk.BooleanVar(value=False);ttk.Checkbutton(dialog,text='Show all unit types',variable=all_units).pack(anchor='w',padx=16,pady=8)
        # Reserve footer space before packing the expanding table.
        footer=ttk.Frame(dialog,padding=(16,8,16,16));footer.pack(side='bottom',fill='x')
        ttk.Label(footer,text='Offsets use this unit’s native origin and rotation.',foreground=MUTED).pack(anchor='w',pady=(0,8))
        frame=ttk.Frame(dialog);frame.pack(fill='both',expand=True,padx=16)
        tree=ttk.Treeview(frame,columns=('id','type','samples'),show='tree headings');tree.heading('#0',text='Unit');tree.heading('id',text='Track ID');tree.heading('type',text='Type');tree.heading('samples',text='Samples');tree.column('#0',width=370)
        for key in ('id','type','samples'):tree.column(key,width=80,stretch=False)
        tree.pack(side='left',fill='both',expand=True);sb=ttk.Scrollbar(frame,command=tree.yview);sb.pack(side='right',fill='y');tree.configure(yscrollcommand=sb.set)
        lookup={}
        def refresh(*_):
            tree.delete(*tree.get_children());lookup.clear();text=query.get().casefold()
            for tr in self.tracks:
                if not all_units.get() and tr['type']!=4:continue
                if text not in (tr['name']+' '+str(tr['id'])).casefold():continue
                iid=str(tr['id']);lookup[iid]=tr;tree.insert('', 'end',iid=iid,text=tr['name'] or '(unnamed unit)',values=(tr['id'],tr['type'],len(tr['rows'])))
        def select(*_):
            selection=tree.selection()
            if not selection or self.busy:return
            if not self.editor_page.confirm_context_change():return
            self.carrier=lookup[selection[0]];self.show_tabs();self.carrier_text.set(f'Carrier: {self.carrier["name"]}  ·  track {self.carrier["id"]}');self.reanalyze()
        query.trace_add('write',refresh);all_units.trace_add('write',refresh);tree.bind('<Double-1>',select);tree.bind('<Return>',select)
        buttons=ttk.Frame(footer);buttons.pack(fill='x')
        if self.carrier is not None:ttk.Button(buttons,text='Cancel',command=self.show_tabs).pack(side='left')
        ttk.Button(buttons,text='Use selected carrier',width=22,command=select).pack(side='right');refresh()

    def show_tabs(self):
        if self.carrier_selection is not None:
            self.carrier_selection.destroy();self.carrier_selection=None
        self.pages.pack(fill='both',expand=True)

    def reanalyze(self):
        if self.carrier is None:return
        self.update_settings_readouts()
        self.set_busy(True,'Finding carrier-relative approach attempts…')
        tracks=self.tracks;carrier=self.carrier;settings=self.settings
        self.work('analyze',lambda:analyze(tracks,carrier,settings))

    def populate(self):
        if not hasattr(self,'tree'):return
        self.refresh_scores();self.tree.tag_configure('best',foreground='#6cd9af')
        old=self.selected;self.tree.delete(*self.tree.get_children());self.row_attempts={};self.row_players={}
        mode=self.attempt_filter.get()
        visible=last_attempts(self.attempts) if mode=='Last attempt' else [a for a in self.attempts if is_best(a,self.scores.get(a.edit_id),self.best_scores)] if mode=='Best attempt' else self.attempts
        groups=defaultdict(list)
        for tr in self.tracks:
            if tr['type']==0 and '(' in tr['name'] and not any(s in tr['name'].upper() for s in ('AV-42','AH-94','AH-99')):groups[player_label(tr['name'])]
        for a in visible:groups[a.player].append(a)
        text=self.player_search.get().strip().casefold();shown=0;selected_row=None
        for n,(player,attempts) in enumerate(sorted(groups.items(),key=lambda p:p[0].casefold())):
            if text and text not in player.casefold() and not any(text in a.aircraft.casefold() for a in attempts):continue
            parent=f'p{n}';self.tree.insert('','end',iid=parent,text=f'{player}  ({len(attempts)})',open=True)
            self.row_players[parent]=player
            for i,a in enumerate(sorted(attempts,key=lambda a:a.start)):
                row=f'{parent}a{i}';self.row_attempts[row]=a;shown+=1
                wire=self.get_wire(a);suffix=('  ·  Bolter' if wire=='Bolter' else '  ·  Wire '+wire) if wire else ''
                score=self.scores.get(a.edit_id)
                if score:suffix+=f'  ·  {score.total:,.1f}'+(' provisional' if not score.complete else '')
                best=is_best(a,score,self.best_scores)
                self.tree.insert(parent,'end',iid=row,text=('★ ' if best else '')+f'{clock(a.start)}  ·  {a.aircraft}'+suffix,tags=('best',) if best else ())
                if a is old:selected_row=row
        self.count_text.set(f'{shown} shown / {len(self.attempts)} detected attempts')
        if self.score_window and self.score_window.winfo_exists():self.score_window.refresh()
        if selected_row:self.tree.selection_set(selected_row)
        elif old is not None:self.selected=None;self.redraw()

    def apply_edits(self):
        selected_id=self.selected.edit_id if self.selected else None
        self.attempts=self.edits.apply(self.auto_attempts,self.tracks,self.carrier,self.settings)
        self.selected=next((a for a in self.attempts if a.edit_id==selected_id),None)
        self.populate();self.redraw()
        if self.edits.warnings:self.status.set('Some saved intervals could not be applied: '+self.edits.warnings[0])
        if self.score_window and self.score_window.winfo_exists():self.score_window.refresh()

    def open_player_editor(self,event=None):
        if self.busy or self.carrier is None:return 'break'
        row=self.tree.identify_row(event.y) if event is not None else self.tree.focus()
        player=self.row_players.get(row)
        if player:
            self.pages.select(self.editor_page);self.editor_page.select_player(player)
        return 'break'

    def toggle_points(self):
        self.settings.show_data_points=self.points_value.get()
        try:self.settings.save(SETTINGS_PATH)
        except OSError as error:messagebox.showerror('Could not save setting',str(error),parent=self)
        self.redraw()

    def select_attempt(self,*_):
        selected=self.tree.selection()
        if not selected:return
        a=self.row_attempts.get(selected[0])
        if a is None:return
        self.selected=a;self.redraw()

    def redraw(self):
        a=self.selected
        self.wire_value.set(self.get_wire(a) if a else '')
        self.wire_select.configure(state='readonly' if a and not self.busy else 'disabled')
        score=self.scores.get(a.edit_id) if a else None
        self.total_text.set((f'{score.total:,.1f} pts'+(' *' if not score.complete else '')) if score else 'Unscored' if a else '')
        origin=glide_origin_msl_ft(self.carrier,self.settings)
        self.toolbar.new_graph();draw(self.fig,a,self.settings,origin);self.canvas.draw_idle()

    def get_wire(self,attempt):
        return self.annotations.get(self.carrier['id'],attempt) if attempt and self.carrier and self.annotations else ''

    def set_wire(self,*_):
        if not self.selected or not self.annotations or self.busy:return
        try:self.annotations.set(self.carrier['id'],self.selected,self.wire_value.get())
        except (OSError,ValueError) as error:
            self.wire_value.set(self.get_wire(self.selected));messagebox.showerror('Could not save wire',str(error),parent=self);return
        self.populate();self.redraw();self.status.set('Manual wire choice saved for this landing.')
        if self.score_window and self.score_window.winfo_exists():self.score_window.refresh()

    def refresh_scores(self):
        origin=glide_origin_msl_ft(self.carrier,self.settings)
        self.scores={a.edit_id:score_attempt(a,self.get_wire(a),self.settings,origin) for a in self.attempts}
        self.best_scores=best_by_player(self.attempts,self.scores)

    def page_changed(self,event=None):
        if self.pages.select()==str(self.score_window):self.score_window.refresh()
        elif self.pages.select()==str(self.approach_page):self.after_idle(self.sync_figure_size)
        elif self.pages.select()==str(self.editor_page):self.editor_page.refresh()

    def show_scores(self):
        self.score_window.refresh();self.pages.select(self.score_window)

    def show_settings(self):
        if not self.busy:self.pages.select(self.settings_page)

    def change_case(self,*_):
        if self.busy:return
        previous=self.settings.recovery_case;chosen=3 if self.case_value.get()=='Case 3' else 1
        if chosen==previous:return
        if not self.editor_page.confirm_context_change():self.case_value.set(f'Case {previous}');return
        try:
            values=asdict(self.settings);values['recovery_case']=chosen;settings=Settings(**values);settings.validate()
            start=glide_start_nm(settings,glide_origin_msl_ft(self.carrier,settings))
            if start is None or settings.scoring_changeover_nm>=start:raise ValueError('Glide End must be closer to the carrier than Glide Start for the selected case.')
            settings.save(SETTINGS_PATH)
        except (ValueError,OSError) as error:
            self.case_value.set(f'Case {previous}');messagebox.showerror('Could not change recovery case',str(error),parent=self);return
        self.settings=settings;self.selected=None;self.populate();self.redraw();self.update_settings_readouts();self.score_window.refresh()
        if self.carrier is not None:self.reanalyze()
        else:self.status.set(f'Case {chosen} selected.')

    def build_settings(self):
        dialog=self.settings_page
        buttons=ttk.Frame(dialog,padding=16);buttons.pack(side='bottom',fill='x')
        tabs=ttk.Notebook(dialog);tabs.pack(fill='both',expand=True,padx=12,pady=12)
        general=ttk.Frame(tabs,padding=16);scoring_page=ttk.Frame(tabs,padding=16);carrier_page=ttk.Frame(tabs,padding=16)
        tabs.add(general,text='Approach & graphs');tabs.add(scoring_page,text='Point Values');tabs.add(carrier_page,text='Carrier Config')
        self.settings_tabs=tabs;variables={};self.setting_variables=variables
        def tolerance(settings):return max(8-settings.aoa_min_deg,settings.aoa_max_deg-8)
        def displayed(settings,key):
            if key=='aoa_tolerance_deg':return tolerance(settings)
            if key=='case1_glide_start_nm':return glide_start_nm(Settings(**{**asdict(settings),'recovery_case':1}),glide_origin_msl_ft(self.carrier,settings)) or 0
            return getattr(settings,key)
        self.auto_start_display=f'{displayed(self.settings,"case1_glide_start_nm"):.12g}'
        def entry(group,key,label,row):
            ttk.Label(group,text=label).grid(row=row,column=0,sticky='w',pady=6)
            variable=tk.StringVar(value=f'{displayed(self.settings,key):.12g}');variables[key]=variable
            ttk.Entry(group,textvariable=variable,width=12).grid(row=row,column=1,sticky='e',padx=(16,0),pady=6)
        def reset_start():
            try:
                values=asdict(self.settings)
                for key in ('offset_x','offset_y','offset_z','runway_deg','glide_deg'):values[key]=float(variables[key].get())
                geometry=Settings(**values)
                if not .1<=geometry.glide_deg<=15:raise ValueError('Glide slope must be between 0.1° and 15°.')
                start=target_intercept_nm(geometry,glide_origin_msl_ft(self.carrier,geometry))
                if start is None or not 0<start<=10:raise ValueError('The configured carrier/glide geometry has no 600 ft intercept within 10 NM.')
                variables['case1_glide_start_nm'].set(f'{start:.12g}')
            except (ValueError,TypeError) as error:messagebox.showerror('Could not reset Glide Start',str(error),parent=self)
        self.reset_case1_start=reset_start
        ttk.Style(self).configure('Square.TButton',padding=(4,3))
        self.reset_start_image=tk.PhotoImage(width=18,height=18)
        for y in range(18):
            for x in range(18):
                radius=(x-8)**2+(y-9)**2
                if (35<=radius<=60 and not (x>=10 and y<=6)) or (10<=x<=15 and 2<=y<=7 and x+y>=17):self.reset_start_image.put(TEXT,(x,y))
        groups=(('Graphs',{'graph_range_nm':'Case 1 Render Distance (NM)','case3_graph_range_nm':'Case 3 Render Distance (NM)'}),
                ('Glide boundaries',{'case1_glide_start_nm':'Case 1 Glide Start (NM)','case3_glide_start_nm':'Case 3 Glide Start (NM)','scoring_changeover_nm':'Glide End (NM)'}),
                ('Glide Limits',{'glide_tolerance_deg':'Glide slope +/- (°)','localizer_tolerance_deg':'Localizer +/- (°)','aoa_tolerance_deg':'AoA +/- (°)'}),
                ('CASE 3 Limits',{'case3_platform_alt_ft':'Platform Alt +/- (ft)','case3_platform_speed_knots':'Platform Spd +/- (Knots)','case3_leg1_speed_knots':'Leg 1 Speed (Knots)','case3_speed_deadzone_nm':'Speed Change Deadzone (NM)','case3_leg2_speed_knots':'Leg 2 Speed (Knots)','case3_platform_start_nm':'Platform Start (NM)','case3_platform_end_nm':'Platform End (NM)'}))
        general.columnconfigure(0,weight=1);general.columnconfigure(1,weight=1)
        for section,(heading,mapping) in enumerate(groups):
            group=ttk.LabelFrame(general,text=heading,padding=(12,8));group.grid(row=section//2,column=section%2,sticky='new',padx=(0,12) if section%2==0 else 0,pady=(0,12));group.columnconfigure(0,weight=1)
            for i,(key,label) in enumerate(mapping.items()):
                entry(group,key,label,i)
                if key=='case1_glide_start_nm':
                    self.case1_reset_btn=ttk.Button(group,image=self.reset_start_image,style='Square.TButton',command=reset_start)
                    self.case1_reset_btn.grid(row=i,column=2,padx=(6,0))
        carrier=ttk.LabelFrame(carrier_page,text='Carrier ILS',padding=(16,12));carrier.pack(fill='x');carrier.columnconfigure(0,weight=1)
        for i,(key,label) in enumerate({'offset_x':'X Offset','offset_y':'Y Offset','offset_z':'Z Offset','runway_deg':'Runway Offset','glide_deg':'Glide Slope Angle'}.items()):entry(carrier,key,label,i)
        ttk.Label(carrier_page,text='X: right · Y: up · Z: forward',foreground=MUTED,padding=(0,12)).pack(anchor='w')
        def readouts(*_):
            if self.settings.case1_glide_start_nm==0 and variables['case1_glide_start_nm'].get()==self.auto_start_display:
                self.auto_start_display=f'{displayed(self.settings,"case1_glide_start_nm"):.12g}'
                variables['case1_glide_start_nm'].set(self.auto_start_display)
        self.update_settings_readouts=readouts
        sections=(('CASE 1 Points',{'scoring_loc_points':'Localizer','scoring_glide_points':'Glide','scoring_aoa_points':'AoA'}),
                  ('CASE 3 Points',{'scoring_case3_position_points':'Platform Position Accuracy','scoring_case3_speed_points':'Platform Speed Accuracy','scoring_case3_loc_points':'Localizer','scoring_case3_glide_points':'Glide','scoring_case3_aoa_points':'AoA'}),
                  ('Landing points',{'scoring_bolter_points':'Bolter','scoring_wire1_points':'1 Wire','scoring_wire2_points':'2 Wire','scoring_wire3_points':'3 Wire','scoring_wire4_points':'4 Wire'}))
        scoring_page.columnconfigure(0,weight=1);scoring_page.columnconfigure(1,weight=1);totals={}
        for section,(heading,mapping) in enumerate(sections):
            group=ttk.LabelFrame(scoring_page,text=heading,padding=(12,8));group.grid(row=section//2,column=section%2,sticky='new',padx=(0,12) if section%2==0 else 0,pady=(0,12));group.columnconfigure(0,weight=1)
            for i,(key,label) in enumerate(mapping.items()):entry(group,key,label,i)
            if section<2:
                total=tk.StringVar();totals[section]=total
                ttk.Label(group,textvariable=total,font=('Helvetica',11,'bold')).grid(row=len(mapping),column=0,columnspan=2,sticky='w',pady=8)
        self.approach_totals=totals
        def update_totals(*_):
            for case_index,(_,mapping) in enumerate(sections[:2]):
                try:totals[case_index].set(f'Total: {sum(float(variables[key].get()) for key in mapping):,.0f}')
                except ValueError:totals[case_index].set('Total: —')
        for _,mapping in sections[:2]:
            for key in mapping:variables[key].trace_add('write',update_totals)
        update_totals()
        def save():
            try:
                values=asdict(self.settings);entered={k:float(v.get()) for k,v in variables.items()};half=entered.pop('aoa_tolerance_deg')
                if not 0<half<=172:raise ValueError('AoA +/- must be positive and at most 172°.')
                values.update(entered);values.update(aoa_min_deg=8-half,aoa_max_deg=8+half);settings=Settings(**values);settings.validate()
                target=glide_start_nm(settings,glide_origin_msl_ft(self.carrier,settings))
                if target is None or settings.scoring_changeover_nm>=target:raise ValueError('Glide End must be closer to the carrier than Glide Start.')
                if not self.editor_page.confirm_context_change():return
                settings.save(SETTINGS_PATH)
            except (ValueError,TypeError,OSError) as e:messagebox.showerror('Invalid settings',str(e),parent=self);return
            self.settings=settings;self.points_value.set(settings.show_data_points);self.selected=None;self.redraw();self.status.set('Settings saved and applied.');readouts();self.score_window.refresh()
            if self.carrier is not None:self.reanalyze()
        def restore(settings):
            for k,v in variables.items():v.set(f'{displayed(settings,k):.12g}')
            self.auto_start_display=variables['case1_glide_start_nm'].get()
        ttk.Button(buttons,text='Restore defaults',command=lambda:restore(Settings())).pack(side='left')
        ttk.Button(buttons,text='Reset changes',command=lambda:restore(self.settings)).pack(side='right')
        self.save_settings_btn=ttk.Button(buttons,text='Save & apply',command=save);self.save_settings_btn.pack(side='right',padx=8)

if __name__=='__main__':WireJudge().mainloop()
